#!/bin/sh
# Iniciar el bot de streaming RTMP en segundo plano (Bot 1: @Elciro_bot)
python bot_stream_multicanal.py &

# Iniciar el bot de Mini App y difusión en segundo plano (Bot 2: @Elciroas_bot)
python bot_miniapp.py &

# Iniciar la aplicación web en primer plano vinculada al puerto de Railway ($PORT o 8080)
exec gunicorn web_app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120

