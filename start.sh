#!/bin/sh

# Forzar modo limpio por defecto: 100% nativo, sin marcos, sin filtros, sin distorsión de audio
export STREAM_CLEAN_MODE="${STREAM_CLEAN_MODE:-1}"
export STREAM_FRAME_PERCENT=0
export STREAM_COLOR_CORRECTION=0
export STREAM_HIDE_LOGOS=0
export STREAM_PIXEL_NOISE=0
export STREAM_PITCH_PERCENT=100
export STREAM_AUDIO_NOISE=0
export STREAM_AUDIO_ECHO=0
export STREAM_LOGO_PATH=""

# 1. Iniciar Bot 1 (@Tvelas_bot / TELEGRAM_BOT_TOKEN) en segundo plano
BOT1_TOKEN="${TELEGRAM_BOT_TOKEN:-9281285181:AAEo_hAjJo-zd537Kvz-f4QcU3iG-aUNGzo}"
while true; do
    echo "Iniciando Bot 1 (Tvelas_bot)..."
    TELEGRAM_BOT_TOKEN="$BOT1_TOKEN" STREAM_CONFIG_FILE="stream_config_bot1.json" python -u bot_stream_multicanal.py
    echo "Bot 1 termino inesperadamente. Reiniciando en 3s..."
    sleep 3
done &

# 2. Iniciar Bot 2: El Ciro TV Bot (@Elcirotv_bot) en segundo plano
ELCIRO_TOKEN="${ELCIRO_BOT_TOKEN:-8626036800:AAEqCZ-bEXrRCNL2E30gLRvJuCP1piDJwPQ}"
export PUBLIC_BOT_TOKEN="${PUBLIC_BOT_TOKEN:-$ELCIRO_TOKEN}"
if [ "${ENABLE_PUBLIC_BOT:-0}" = "1" ] && [ "$PUBLIC_BOT_TOKEN" != "$BOT1_TOKEN" ]; then
    while true; do
        echo "Iniciando Bot ElCiro TV (Elcirotv_bot)..."
        ELCIRO_BOT_TOKEN="$ELCIRO_TOKEN" PUBLIC_BOT_TOKEN="${PUBLIC_BOT_TOKEN:-$ELCIRO_TOKEN}" python -u public_bot.py
        echo "Bot ElCiro TV termino inesperadamente. Reiniciando en 3s..."
        sleep 3
    done &
fi

# 3. Iniciar la aplicacion web en primer plano vinculada al puerto de Railway ($PORT o 8080)
exec gunicorn web_app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 12 --timeout 120
