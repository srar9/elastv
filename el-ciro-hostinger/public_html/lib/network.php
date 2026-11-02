<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';

function ciro_curl(string $url,string $referer=''): CurlHandle {
 if(!extension_loaded('curl'))throw new RuntimeException('CURL_REQUIRED');$p=ciro_public_url($url);$host=strtolower($p['host']);
 static $resolved=[];if(!isset($resolved[$host])){$ips=gethostbynamel($host)?:[];$ips=array_values(array_filter($ips,fn($ip)=>filter_var($ip,FILTER_VALIDATE_IP,FILTER_FLAG_IPV4|FILTER_FLAG_NO_PRIV_RANGE|FILTER_FLAG_NO_RES_RANGE)!==false));if(!$ips)throw new RuntimeException('INVALID_MEDIA');$resolved[$host]=$ips[0];}
 $port=$p['port']??($p['scheme']==='https'?443:80);$curl=curl_init($url);if(!$curl)throw new RuntimeException('NETWORK_UNAVAILABLE');
 $headers=['Accept: */*','Accept-Encoding: identity'];if($referer!==''&&!preg_match('/[\r\n]/',$referer))$headers[]='Referer: '.$referer;
 curl_setopt_array($curl,[CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>6,CURLOPT_TIMEOUT=>18,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROTOCOLS=>CURLPROTO_HTTP|CURLPROTO_HTTPS,CURLOPT_RESOLVE=>[$host.':'.$port.':'.$resolved[$host]],CURLOPT_USERAGENT=>'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',CURLOPT_HTTPHEADER=>$headers]);return $curl;
}
function ciro_buffer(string $url,string $referer='',int $limit=2500000): array {
 for($hop=0;$hop<4;$hop++){$curl=ciro_curl($url,$referer);$headers=[];$body='';$status=0;
  curl_setopt($curl,CURLOPT_HEADERFUNCTION,function($ch,$line)use(&$headers,&$status){if(preg_match('~^HTTP/\S+\s+(\d+)~i',$line,$m)){$status=(int)$m[1];$headers=[];}elseif(str_contains($line,':')){[$k,$v]=explode(':',$line,2);$headers[strtolower(trim($k))]=trim($v);}return strlen($line);});
  curl_setopt($curl,CURLOPT_WRITEFUNCTION,function($ch,$data)use(&$body,$limit){if(strlen($body)+strlen($data)>$limit)return 0;$body.=$data;return strlen($data);});$ok=curl_exec($curl);$error=curl_errno($curl);curl_close($curl);
  if($ok===false||$error)throw new RuntimeException('NETWORK_UNAVAILABLE');if(in_array($status,[301,302,303,307,308],true)&&isset($headers['location'])){$url=ciro_absolute($headers['location'],$url);continue;}return ['status'=>$status,'headers'=>$headers,'body'=>$body,'url'=>$url];
 }throw new RuntimeException('TOO_MANY_REDIRECTS');
}
function ciro_agenda(): array {
 $file=ciro_storage().'/agenda.php';$cached=null;if(is_file($file)){$text=@file_get_contents($file);$cached=json_decode(explode("\n",$text?:'',2)[1]??'',true);}
 $day=ciro_today();$same=is_array($cached)&&($cached['day']??'')===$day;$age=$same?time()-(int)($cached['loaded']??0):PHP_INT_MAX;
 if($same&&$age<90)return $cached+['stale'=>false];
 $lock=fopen(ciro_storage().'/refresh.php','c+');if(!$lock)throw new RuntimeException('STORAGE_UNAVAILABLE');
 if(!flock($lock,LOCK_EX|LOCK_NB)){if($same&&$age<1800){fclose($lock);return $cached+['stale'=>true];}if(!flock($lock,LOCK_EX)){fclose($lock);throw new RuntimeException('STORAGE_UNAVAILABLE');}}
 try{
  // Another request may have completed the refresh while this request waited.
  $new=is_file($file)?json_decode(explode("\n",(string)file_get_contents($file),2)[1]??'',true):null;if(is_array($new)&&($new['day']??'')===$day&&time()-(int)($new['loaded']??0)<90)return $new+['stale'=>false];
  $response=ciro_buffer('https://api.wqxag.com/diaries.json','',6000000);if($response['status']!==200)throw new RuntimeException('AGENDA_UNAVAILABLE');$result=ciro_normalize(json_decode($response['body'],true,128,JSON_THROW_ON_ERROR));$result['loaded']=time();$result['updatedAt']=gmdate('Y-m-d\TH:i:s.000\Z');
  $temp=tempnam(ciro_storage(),'agenda-');if($temp===false)throw new RuntimeException('STORAGE_UNAVAILABLE');if(file_put_contents($temp,"<?php exit; ?>\n".json_encode($result,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE))===false){@unlink($temp);throw new RuntimeException('STORAGE_UNAVAILABLE');}@chmod($temp,0660);if(!@rename($temp,$file)){@unlink($temp);throw new RuntimeException('STORAGE_UNAVAILABLE');}return $result+['stale'=>false];
 }catch(Throwable $error){if($same&&$age<1800)return $cached+['stale'=>true];throw $error;}finally{flock($lock,LOCK_UN);fclose($lock);}
}
function ciro_public_agenda(): array {$data=ciro_agenda();unset($data['sources'],$data['loaded']);return $data;}
function ciro_source(string $id): array {
 if(str_starts_with($id,'catalog-'))foreach(ciro_catalog() as [$slug,$name,$path])if($id==='catalog-'.$slug)return ['url'=>'https://rojadirectatvmas.net/en-vivo/'.$path,'name'=>$name];
 $settings=ciro_settings();if(str_starts_with($id,'custom-')&&isset($settings['custom_channels'][substr($id,7)]))return $settings['custom_channels'][substr($id,7)];
 $agenda=ciro_agenda();if(!isset($agenda['sources'][$id]))throw new RuntimeException('SOURCE_NOT_FOUND');return $agenda['sources'][$id];
}
function ciro_resolve(string $initial,string $reference=''): array {
 if(preg_match('~\.m3u8(?:\?|$)~i',$initial)){ciro_public_url($initial);return ['url'=>$initial,'referer'=>$reference];}
 $players=['rojadirectatvmas.net','www.rojadirectatvmas.net','tvf90.com','www.tvf90.com'];$queue=[[$initial,'https://rojadirectatvmas.net/',0]];$visited=[];
 while($queue&&count($visited)<5){[$url,$referer,$depth]=array_shift($queue);try{$parts=ciro_public_url($url);if(!in_array(strtolower($parts['host']),$players,true)||isset($visited[$url])||$depth>3)continue;$visited[$url]=true;$r=ciro_buffer($url,$referer,1500000);if($r['status']!==200||!in_array(strtolower(parse_url($r['url'],PHP_URL_HOST)??''),$players,true))continue;$body=str_replace(['\\/','&amp;'],['/','&'],$r['body']);$found=[];
   if(preg_match('~\b(?:var|let|const)\s+playbackURL\s*=\s*["\x27]([^"\x27]+)["\x27]~',$body,$found)||preg_match('~["\x27]((?:https?:)?//[^\s"\x27<>]+\.m3u8(?:\?[^\s"\x27<>]*)?)["\x27]~i',$body,$found)){$media=ciro_absolute($found[1],$r['url']);ciro_public_url($media);return ['url'=>$media,'referer'=>$r['url']];}
   preg_match_all('~<iframe\b[^>]*\bsrc\s*=\s*["\x27]([^"\x27]+)["\x27]~i',$body,$frames);foreach($frames[1] as $frame)$queue[]=[ciro_absolute($frame,$r['url']),$r['url'],$depth+1];
  }catch(Throwable){continue;}
 }throw new RuntimeException('SOURCE_UNAVAILABLE');
}
function ciro_relay(array $permission,string $secret): void {
 @ini_set('zlib.output_compression','0');$url=$permission['u'];$range=$_SERVER['HTTP_RANGE']??'';
 for($hop=0;$hop<4;$hop++){$curl=ciro_curl($url,$permission['r']);$status=0;$headers=[];$body='';$sent=false;$isManifest=false;$allowed=false;
  if(preg_match('/^bytes=\d+-\d*$/D',$range))curl_setopt($curl,CURLOPT_RANGE,substr($range,6));
  curl_setopt($curl,CURLOPT_HEADERFUNCTION,function($ch,$line)use(&$status,&$headers,&$isManifest,&$allowed,$url){if(preg_match('~^HTTP/\S+\s+(\d+)~i',$line,$m)){$status=(int)$m[1];$headers=[];}elseif(str_contains($line,':')){[$k,$v]=explode(':',$line,2);$headers[strtolower(trim($k))]=trim($v);}elseif(trim($line)===''){$type=strtolower($headers['content-type']??'application/octet-stream');$isManifest=str_ends_with(strtolower(parse_url($url,PHP_URL_PATH)??''),'.m3u8')||str_contains($type,'mpegurl');$allowed=$status>=200&&$status<300&&!preg_match('~text/html|javascript|image/svg|application/json~i',$type);}return strlen($line);});
  curl_setopt($curl,CURLOPT_WRITEFUNCTION,function($ch,$data)use(&$body,&$sent,&$isManifest,&$allowed,&$status,&$headers){if(!$allowed)return strlen($data);if(connection_aborted())return 0;if($isManifest){if(strlen($body)+strlen($data)>1000000)return 0;$body.=$data;}else{if(!$sent){http_response_code($status);header('Content-Type: '.($headers['content-type']??'application/octet-stream'));header('Cache-Control: private, max-age=10');header('X-Content-Type-Options: nosniff');header('X-Accel-Buffering: no');foreach(['content-range','accept-ranges'] as $name)if(isset($headers[$name]))header($name.': '.$headers[$name]);while(ob_get_level()>0)ob_end_flush();$sent=true;}echo $data;flush();}return strlen($data);});
  $ok=curl_exec($curl);$error=curl_errno($curl);curl_close($curl);if($sent)return;if($ok===false||$error)throw new RuntimeException('MEDIA_UNAVAILABLE');
  if(in_array($status,[301,302,303,307,308],true)&&isset($headers['location'])){$url=ciro_absolute($headers['location'],$url);continue;}
  if(!$allowed)throw new RuntimeException('MEDIA_UNAVAILABLE');if($isManifest){header('Content-Type: application/vnd.apple.mpegurl');header('Cache-Control: no-store');header('X-Content-Type-Options: nosniff');echo ciro_manifest($body,$url,$permission['r'],$secret,$permission['e']);return;}
  throw new RuntimeException('MEDIA_UNAVAILABLE');
 }throw new RuntimeException('MEDIA_UNAVAILABLE');
}
