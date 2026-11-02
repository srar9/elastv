@echo off
setlocal
title EL CIRO - Estilo de transmision
cd /d "%~dp0"
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0estilo_el_ciro.env") do set "%%A=%%B"
echo EL CIRO: marco, logo con movimiento y efectos de audio.
echo Estos efectos no evitan reclamaciones de derechos de autor.
echo.
echo 1. Bot multicanal
echo 2. Transmision manual
echo 3. Bot local
choice /c 123 /n /m "Selecciona el programa: "
if errorlevel 3 goto local
if errorlevel 2 goto manual
python bot_stream_multicanal.py
goto fin
:manual
python transmitir_telegram.py
goto fin
:local
python bot_local_pc.py
:fin
pause
endlocal
