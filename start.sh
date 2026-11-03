#!/bin/sh
# Iniciar el bot de streaming RTMP en segundo plano con autoreinicio continuo (Bot 1: @Elciro_bot)
if [ "$BOT_ENABLED" != "false" ] && [ "$BOT_ENABLED" != "0" ]; then
    while true; do
        echo "Iniciando bot_stream_multicanal.py..."
        python -u bot_stream_multicanal.py
        echo "bot_stream_multicanal.py termino inesperadamente. Reiniciando en 3s..."
        sleep 3
    done &
else
    echo "BOT_ENABLED=false: bot_stream_multicanal.py desactivado en Railway (modo standby)."
fi

# Iniciar el bot de Mini App y difusion en segundo plano con autoreinicio continuo (Bot 2: @Elciroas_bot)
while true; do
    echo "Iniciando bot_miniapp.py..."
    python -u bot_miniapp.py
    echo "bot_miniapp.py termino inesperadamente. Reiniciando en 3s..."
    sleep 3
done &

# Iniciar la aplicacion web en primer plano vinculada al puerto de Railway ($PORT o 8080)
exec gunicorn web_app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 12 --timeout 120
