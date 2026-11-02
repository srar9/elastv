FROM python:3.11-slim
ENV STREAM_FRAME_PERCENT=4 STREAM_FRAME_COLOR=102A43 STREAM_LOGO_WIDTH=180 STREAM_LOGO_OPACITY=90 STREAM_LOGO_MOTION=3 STREAM_PITCH_PERCENT=102 STREAM_PLAYBACK_PERCENT=100
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080 BOT_ENABLED=false BOT_CONFIG_PATH=/data/stream_config.json
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY entrypoint.py bot_stream_multicanal.py stream_runtime.py channel_source.py agenda_service.py bot_catalog.py ./
COPY assets/el-ciro.png ./assets/el-ciro.png
EXPOSE 8080
CMD ["python", "-u", "entrypoint.py"]
