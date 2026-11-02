<?php
declare(strict_types=1);

function ciro_settings(): array { static $settings; return $settings ??= require __DIR__.'/settings.php'; }
function ciro_today(?DateTimeImmutable $now=null): string { return ($now??new DateTimeImmutable())->setTimezone(new DateTimeZone('America/Caracas'))->format('Y-m-d'); }
function ciro_attrs(mixed $v): array { return is_array($v)?(is_array($v['attributes']??null)?$v['attributes']:$v):[]; }
function ciro_rows(mixed $v): array { if(!is_array($v))return [];return array_is_list($v)?$v:(is_array($v['data']??null)?$v['data']:[]); }
function ciro_catalog(): array {return [
 ['espn','ESPN 1','espn-1'],['espn2','ESPN 2','espn-2'],['espn3','ESPN 3','espn-3'],['espnpremium','ESPN Premium','espn-premium'],['espndeportes','ESPN Deportes','espn-deportes'],
 ['foxsports','Fox Sports 1','fox-sports-1'],['foxsports2','Fox Sports 2','fox-sports-2'],['foxsports3','Fox Sports 3','fox-sports-3'],['foxsportspremium','Fox Sports Premium','fox-sports-premium'],
 ['dsports','DSports','directv-sports'],['dsports2','DSports 2','directv-sports-2'],['dsportsplus','DSports+','directv-sports-plus'],['tntsports','TNT Sports','tnt-sports-argentina'],['tycsports','TyC Sports','tyc-sports'],
 ['tudn','TUDN','tudn'],['telemundo','Telemundo','telemundo'],['winsports','Win Sports','win-sports'],['winsports2','Win Sports+','win-sports-plus'],['liga1max','Liga 1 Max','liga-1-max'],['movistardeportes','Movistar Deportes','movistar-deportes'],
 ];}
function ciro_absolute(string $value,string $base): string {
 $value=html_entity_decode(trim($value),ENT_QUOTES|ENT_HTML5,'UTF-8');
 if(preg_match('~^[a-z][a-z0-9+.-]*:~i',$value))return $value;
 $b=parse_url($base);if(!$b||empty($b['host']))throw new RuntimeException('INVALID_URL');
 $origin=($b['scheme']??'https').'://'.$b['host'].(isset($b['port'])?':'.$b['port']:'');
 if(str_starts_with($value,'//'))return ($b['scheme']??'https').':'.$value;
 if($value==='')return $base;
 if($value[0]==='?')return $origin.($b['path']??'/').$value;
 $path=$value[0]==='/'?$value:preg_replace('~/[^/]*$~','/',($b['path']??'/')).$value;
 $split=preg_split('/([?#])/',$path,2,PREG_SPLIT_DELIM_CAPTURE);$stack=[];
 foreach(explode('/',$split[0]) as $part){if($part===''||$part==='.')continue;if($part==='..')array_pop($stack);else $stack[]=$part;}
 return $origin.'/'.implode('/',$stack).(isset($split[1])?$split[1].($split[2]??''):'');
}
function ciro_player_url(string $raw): string {
 if($raw==='')return '';try{$url=ciro_absolute($raw,'https://rojadirectatvmas.net/');parse_str(parse_url($url,PHP_URL_QUERY)??'',$query);if(isset($query['r'])){$decoded=base64_decode((string)$query['r'],true);return $decoded===false?'':$decoded;}return $url;}catch(Throwable){return '';}
}
function ciro_normalize(mixed $raw,?DateTimeImmutable $now=null): array {
 $list=is_array($raw)?(array_is_list($raw)?$raw:($raw['data']??null)):null;if(!is_array($list))throw new RuntimeException('INVALID_AGENDA');
 $day=ciro_today($now);$events=[];$sources=[];$seen=[];$zone=new DateTimeZone('America/Caracas');
 foreach($list as $row){if(!is_array($row))continue;$a=ciro_attrs($row);$title=trim(preg_replace('/\s+/u',' ',(string)($a['diary_description']??''))??'');$hour=(string)($a['diary_hour']??'');$date=substr((string)($a['date_diary']??''),0,10);
  try{$instant=str_contains($hour,'T')?new DateTimeImmutable($hour):new DateTimeImmutable($date.'T'.($hour!==''?substr($hour,0,8):'12:00:00').'-05:00');}catch(Throwable){continue;}
  if($title===''||ciro_today($instant)!==$day)continue;$iso=$instant->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s.000\Z');$unique=$iso.$title;if(isset($seen[$unique]))continue;$seen[$unique]=true;
  $pieces=explode(':',$title,2);$league=count($pieces)>1?trim($pieces[0]):'Deportes';$match=count($pieces)>1?trim($pieces[1]):$title;$id=(string)($row['id']??hash('sha256',$unique));$signals=[];$urls=[];
  foreach(ciro_rows($a['embeds']??[]) as $index=>$embed){$e=ciro_attrs($embed);$url=ciro_player_url((string)($e['embed_iframe']??''));$parts=parse_url($url);if(!$parts||!in_array(strtolower($parts['scheme']??''),['http','https'],true)||isset($urls[$url]))continue;$urls[$url]=true;parse_str($parts['query']??'',$q);$embedId=(string)($embed['id']??$index);$signal=['id'=>'event-'.$id.'-'.$embedId,'name'=>mb_substr((string)($e['embed_name']??('Señal '.($index+1))),0,100),'slug'=>mb_substr((string)($q['stream']??('evento-'.$id.'-'.$embedId)),0,80)];$signals[]=$signal;$sources[$signal['id']]=$signal+['url'=>$url];}
  $events[]=['id'=>$id,'title'=>mb_substr($match,0,300),'league'=>mb_substr($league,0,120),'startsAt'=>$iso,'time'=>$hour!==''?$instant->setTimezone($zone)->format('H:i'):'--:--','teams'=>array_slice(preg_split('/\s+vs?\.?\s+/iu',$match)?:[$match],0,2),'signals'=>$signals];
 }
 usort($events,fn($a,$b)=>strcmp($a['startsAt'],$b['startsAt']));$channels=[];foreach(ciro_catalog() as [$slug,$name])$channels[$slug]=['id'=>'catalog-'.$slug,'slug'=>$slug,'name'=>$name,'group'=>'Directorio'];
 foreach($events as $event)foreach($event['signals'] as $s)if(!isset($channels[$s['slug']]))$channels[$s['slug']]=$s+['group'=>'Agenda de hoy'];
 foreach(ciro_settings()['custom_channels'] as $slug=>$s){if(!preg_match('/^[a-z0-9_-]{1,70}$/',(string)$slug)||!is_array($s)||empty($s['url']))continue;$c=['id'=>'custom-'.$slug,'slug'=>(string)$slug,'name'=>(string)($s['name']??$slug),'group'=>'Señales de la comunidad'];$channels[$slug]=$c;$sources[$c['id']]=$c+['url'=>$s['url'],'referer'=>$s['referer']??''];}
 return ['day'=>$day,'events'=>$events,'channels'=>array_values($channels),'sources'=>$sources];
}
function ciro_storage(): string {
 static $path;if($path)return $path;$path=dirname(__DIR__).'/.el-ciro';
 if(!is_dir($path)&&!@mkdir($path,0770,true)&&!is_dir($path))throw new RuntimeException('STORAGE_UNAVAILABLE');
 if(!is_file($path.'/.htaccess'))@file_put_contents($path.'/.htaccess',"Require all denied\nDeny from all\n");
 return $path;
}
function ciro_secret(): string {
 $file=ciro_storage().'/secret.php';$fp=fopen($file,'c+');if(!$fp||!flock($fp,LOCK_EX))throw new RuntimeException('STORAGE_UNAVAILABLE');
 try{$text=stream_get_contents($fp);$secret=trim(explode("\n",$text,2)[1]??'');if(!preg_match('/^[a-f0-9]{64}$/',$secret)){$secret=bin2hex(random_bytes(32));ftruncate($fp,0);rewind($fp);if(fwrite($fp,"<?php exit; ?>\n".$secret)===false)throw new RuntimeException('STORAGE_UNAVAILABLE');fflush($fp);@chmod($file,0660);}return $secret;}finally{flock($fp,LOCK_UN);fclose($fp);}
}
function ciro_b64(string $value): string {return rtrim(strtr(base64_encode($value),'+/','-_'),'=');}
function ciro_un64(string $value): string {if(!preg_match('/^[A-Za-z0-9_-]+$/D',$value))throw new RuntimeException('INVALID_GRANT');$decoded=base64_decode(strtr($value,'-_','+/'),true);if($decoded===false)throw new RuntimeException('INVALID_GRANT');return $decoded;}
function ciro_public_url(string $url): array {
 $p=parse_url($url);if(!$p||!in_array(strtolower($p['scheme']??''),['http','https'],true)||empty($p['host'])||isset($p['user'])||isset($p['pass'])||isset($p['port'])&&!in_array($p['port'],[80,443],true))throw new RuntimeException('INVALID_MEDIA');
 $h=strtolower($p['host']);if(!str_contains($h,'.')||filter_var($h,FILTER_VALIDATE_IP)||str_contains($h,':')||preg_match('/(^localhost$|\.localhost$|\.local$|\.internal$)/',$h)||$h==='metadata.google.internal'||!preg_match('/^[a-z0-9.-]+$/D',$h))throw new RuntimeException('INVALID_MEDIA');return $p;
}
function ciro_grant(string $url,string $referer,string $secret,?int $expiry=null): string {
 ciro_public_url($url);if(strlen($secret)<32)throw new RuntimeException('INVALID_KEY');$payload=ciro_b64(json_encode(['u'=>$url,'r'=>$referer,'e'=>$expiry??time()+21600],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES));return $payload.'.'.ciro_b64(hash_hmac('sha256',$payload,$secret,true));
}
function ciro_verify(string $token,string $secret): array {
 if(strlen($token)>12000)throw new RuntimeException('INVALID_GRANT');$parts=explode('.',$token);if(count($parts)!==2||!hash_equals(hash_hmac('sha256',$parts[0],$secret,true),ciro_un64($parts[1])))throw new RuntimeException('INVALID_GRANT');$p=json_decode(ciro_un64($parts[0]),true,32,JSON_THROW_ON_ERROR);if(!is_array($p)||!is_int($p['e']??null)||$p['e']<time()||!is_string($p['r']??null)||!is_string($p['u']??null))throw new RuntimeException('EXPIRED_GRANT');ciro_public_url($p['u']);return $p;
}
function ciro_manifest(string $text,string $base,string $referer,string $secret,int $expiry): string {
 if(!str_starts_with(ltrim($text),'#EXTM3U')||strlen($text)>1000000)throw new RuntimeException('INVALID_MANIFEST');
 $local=fn(string $u):string=>'api.php?action=media&t='.rawurlencode(ciro_grant(ciro_absolute($u,$base),$referer,$secret,$expiry));$lines=[];
 foreach(preg_split('/\r?\n/',$text) as $line){if(trim($line)!==''&&!str_starts_with($line,'#'))$lines[]=$local(trim($line));else $lines[]=preg_replace_callback('/URI="([^"]+)"/',fn($m)=>'URI="'.$local($m[1]).'"',$line);}
 return implode("\n",$lines);
}
