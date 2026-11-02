<?php
declare(strict_types=1);
$base=__DIR__.'/public_html';$output=__DIR__.'/el-ciro-hostinger-premium.zip';
$zip=new ZipArchive();if($zip->open($output,ZipArchive::CREATE|ZipArchive::OVERWRITE)!==true)throw new RuntimeException('No se pudo crear ZIP');
$iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($base,FilesystemIterator::SKIP_DOTS));$files=[];
foreach($iterator as $file){if(!$file->isFile()||$file->isLink())continue;$relative=str_replace('\\','/',substr($file->getPathname(),strlen($base)+1));if(str_starts_with($relative,'.el-ciro/'))continue;if(!preg_match('~^(assets/[a-zA-Z0-9_.-]+|lib/(core|network|settings)\.php|index\.php|api\.php|\.htaccess|LICENSES\.txt)$~D',$relative))throw new RuntimeException('Archivo inesperado en paquete: '.$relative);if(!$zip->addFile($file->getPathname(),$relative))throw new RuntimeException('No se pudo añadir archivo');$files[]=$relative;}
$zip->close();$verify=new ZipArchive();if($verify->open($output,ZipArchive::CHECKCONS)!==true)throw new RuntimeException('ZIP no válido');
foreach(['index.php','api.php','.htaccess','lib/core.php','lib/network.php','lib/settings.php','assets/app.js','assets/app.css','LICENSES.txt'] as $required)if($verify->locateName($required)===false)throw new RuntimeException('Falta archivo: '.$required);
for($i=0;$i<$verify->numFiles;$i++)if(str_contains($verify->getNameIndex($i),'.el-ciro')||str_contains($verify->getNameIndex($i),'secret'))throw new RuntimeException('No incluir estado privado');$count=$verify->numFiles;$verify->close();
file_put_contents(__DIR__.'/PAQUETE-SHA256.txt',hash_file('sha256',$output).'  '.basename($output)."\n");
echo json_encode(['package'=>basename($output),'files'=>$count,'bytes'=>filesize($output),'runtimeSecretsIncluded'=>false],JSON_UNESCAPED_SLASHES)."\n";
