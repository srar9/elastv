<?php
declare(strict_types=1);
require_once __DIR__.'/lib/network.php';
ini_set('display_errors','0');@set_time_limit(50);
function ciro_json(array $data,int $status=200): never {http_response_code($status);header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');header('X-Content-Type-Options: nosniff');echo json_encode($data,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);exit;}
if(!in_array($_SERVER['REQUEST_METHOD']??'GET',['GET','HEAD'],true)){header('Allow: GET, HEAD');ciro_json(['error'=>'Método no permitido.'],405);}
$action=(string)($_GET['action']??'');
try {
 if($action==='agenda')ciro_json(ciro_public_agenda());
 if($action==='status')ciro_json(['ok'=>extension_loaded('curl')&&extension_loaded('mbstring')&&is_writable(ciro_storage()),'curl'=>extension_loaded('curl'),'mbstring'=>extension_loaded('mbstring'),'storage'=>is_writable(ciro_storage()),'day'=>ciro_today()]);
 if($action==='play'){$id=(string)($_GET['source']??'');if($id===''||strlen($id)>150)ciro_json(['error'=>'Selecciona una señal válida.'],400);$source=ciro_source($id);$resolved=ciro_resolve($source['url'],$source['referer']??'');$token=ciro_grant($resolved['url'],$resolved['referer'],ciro_secret());ciro_json(['url'=>'api.php?action=media&t='.rawurlencode($token),'name'=>$source['name']]);}
 if($action==='media'){$token=(string)($_GET['t']??'');if($token==='')ciro_json(['error'=>'Selecciona una señal desde el reproductor.'],400);try{$secret=ciro_secret();$permission=ciro_verify($token,$secret);}catch(Throwable){ciro_json(['error'=>'La sesión de reproducción venció. Vuelve a abrir la señal.'],403);}ciro_relay($permission,$secret);exit;}
 ciro_json(['error'=>'Acción no encontrada.'],404);
}catch(Throwable $error){$message=$action==='agenda'?'No pudimos actualizar la agenda. Intenta nuevamente en unos minutos.':($action==='status'?'No se pudo escribir la caché. Revisa los permisos de la carpeta.':'Esta señal no está disponible. Prueba otra opción o reintenta más tarde.');ciro_json(['error'=>$message],$action==='agenda'?503:502);}
