<?php
declare(strict_types=1);
require_once __DIR__.'/../public_html/lib/network.php';
try{$a=ciro_public_agenda();echo json_encode(['day'=>$a['day'],'events'=>count($a['events']),'channels'=>count($a['channels'])],JSON_UNESCAPED_UNICODE)."\n";$source=ciro_source('catalog-espn');$resolved=ciro_resolve($source['url']);$r=ciro_buffer($resolved['url'],$resolved['referer'],1000000);echo json_encode(['check'=>'manifest','status'=>$r['status'],'valid'=>str_starts_with($r['body'],'#EXTM3U')])."\n";if($r['status']!==200)exit(1);}catch(Throwable $e){echo $e->getMessage()."\n";exit(1);}
