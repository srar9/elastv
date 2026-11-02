@echo off
setlocal
cd /d "%~dp0"
set "CIRO_PHP=php"
where php >nul 2>nul
if errorlevel 1 (
 if exist "C:\php-portable\php.exe" (
  set "CIRO_PHP=C:\php-portable\php.exe"
 ) else (
  echo PHP no esta instalado. Este paquete se puede subir directamente a Hostinger.
  pause
  exit /b 1
 )
)
echo Abre http://127.0.0.1:8787/ en tu navegador.
echo Deja esta ventana abierta mientras pruebas. Para terminar pulsa Ctrl+C.
"%CIRO_PHP%" -S 127.0.0.1:8787 -t public_html
pause
