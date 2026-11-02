"""FFmpeg profile and output health shared by the cloud and desktop launchers."""
import os
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit


def setting(name, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


STALL_SECONDS = setting("STREAM_STALL_SECONDS", 40, 15, 300)
STARTUP_SECONDS = setting("STREAM_STARTUP_SECONDS", 60, 20, 300)


def is_hls_source(source):
    if not isinstance(source, str):
        return False
    parsed = urlsplit(source)
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    path = parsed.path.lower()
    return path.endswith(".m3u8") or ".m3u8" in parsed.query.lower() or "m3u8" in path


def style_filters():
    """Presentation effects are opt-in so live encoding stays inexpensive."""
    # Marco y reencuadre opcionales.
    inset = setting("STREAM_FRAME_PERCENT", 0, 0, 20)
    width = int(1280 * (100 - inset * 2) / 100) // 2 * 2
    height = int(720 * (100 - inset * 2) / 100) // 2 * 2
    color = os.environ.get("STREAM_FRAME_COLOR", "102A43").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        raise ValueError("STREAM_FRAME_COLOR debe ser un color RRGGBB")
    pad_color = f"0x{color}" if inset else "black"

    video_filters = []
    
    if inset > 0:
        video_filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2"
        )
        try:
            rotate_deg = float(os.environ.get("STREAM_ROTATE_DEGREES", "0"))
        except ValueError:
            rotate_deg = 0
        if rotate_deg != 0:
            video_filters.append(f"rotate={rotate_deg}*PI/180:ow={width}:oh={height}:fillcolor={pad_color}:bilinear=0")
        video_filters.append(f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color={pad_color},setsar=1")
    else:
        video_filters.append("scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")

    # 2. Corrección de color y contraste sutil
    if setting("STREAM_COLOR_CORRECTION", 0, 0, 1):
        try:
            contrast = float(os.environ.get("STREAM_CONTRAST", "1.08"))
            saturation = float(os.environ.get("STREAM_SATURATION", "1.08"))
            brightness = float(os.environ.get("STREAM_BRIGHTNESS", "0.01"))
            hue_deg = float(os.environ.get("STREAM_HUE_DEGREES", "3"))
        except ValueError:
            contrast, saturation, brightness, hue_deg = 1.08, 1.08, 0.01, 3
        video_filters.append(f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation},hue=h={hue_deg}")

    # 3. Ocultar logo del canal original y marcador con máscaras sutiles
    if setting("STREAM_HIDE_LOGOS", 0, 0, 1) and inset > 0:
        x_logo = 1280 - int(1280 * inset / 100) - 160
        y_top = int(720 * inset / 100) + 12
        x_score = int(1280 * inset / 100) + 14
        video_filters.append(f"drawbox=x={x_logo}:y={y_top}:w=150:h=42:color=0x111620@0.95:t=fill")
        video_filters.append(f"drawbox=x={x_score}:y={y_top}:w=175:h=42:color=0x111620@0.85:t=fill")

    # Ruido de píxel opcional
    if setting("STREAM_PIXEL_NOISE", 0, 0, 1):
        video_filters.append("noise=c0s=3:allf=t+u")

    speed = setting("STREAM_PLAYBACK_PERCENT", 100, 95, 105) / 100
    if speed != 1:
        video_filters.append(f"setpts=PTS/{speed}")

    video_filters.append("fps=30")
    video = ",".join(video_filters)

    # Audio: nativo, cristalino y sincronizado
    audio_filters = ["aresample=48000:async=1:first_pts=0"]
    pitch = setting("STREAM_PITCH_PERCENT", 100, 90, 110) / 100
    if pitch != 1:
        rate = round(48000 * pitch)
        audio_filters.append(f"asetrate={rate},aresample=48000,atempo={1 / pitch:.8f}")

    if speed != 1:
        audio_filters.append(f"atempo={speed}")

    if setting("STREAM_AUDIO_ECHO", 0, 0, 1):
        audio_filters.append("aecho=0.8:0.88:40:0.08")

    noise = setting("STREAM_AUDIO_NOISE", 0, 0, 10) / 1000
    if noise:
        audio_filters.append(
            "aformat=channel_layouts=stereo,"
            f"aeval=exprs='val(0)+{noise}*(2*random(0)-1)|val(1)+{noise}*(2*random(1)-1)'"
        )

    audio = ",".join(audio_filters)
    return video, audio, speed


def build_command(source, headers, destination, progress=False):
    bitrate = setting("STREAM_VIDEO_KBPS", 1800, 300, 5000)
    video_filter, audio_filter, speed = style_filters()
    network_source = bool(urlsplit(source).scheme and not os.path.isfile(source))
    if speed != 1 and network_source:
        raise ValueError("STREAM_PLAYBACK_PERCENT debe ser 100 para fuentes de red en directo")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-nostdin",
           "-filter_threads", "2"]
    if progress:
        cmd += ["-progress", "pipe:1", "-stats_period", "2"]

    if urlsplit(source).scheme.lower() in ("http", "https"):
        cmd += [
            "-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1", "-reconnect_on_http_error", "408,429,5xx",
            "-reconnect_delay_max", "2", "-rw_timeout", "15000000"
        ]
        if headers:
            cmd += ["-headers", headers]
        if is_hls_source(source):
            # Preserve playlist semantics (master playlists, encryption, init
            # segments and discontinuities). Keep a small live cushion and let
            # the demuxer prefetch over persistent HTTP connections.
            cmd += ["-live_start_index", "-3", "-http_persistent", "1", "-http_multiple", "1",
                    "-seg_max_retry", "3"]

    cmd += [
        "-thread_queue_size", "512",
        "-fflags", "+genpts+discardcorrupt",
        "-analyzeduration", "2000000",
        "-probesize", "2000000"
    ]

    # HLS downloads arrive in bursts. Pace them at the media clock instead of
    # sending bursts to RTMP and then waiting idle for the next segment.
    if not network_source or is_hls_source(source):
        cmd += ["-re"] if speed == 1 else ["-readrate", str(speed)]
    cmd += ["-i", source]

    # Logo overlay: solo si se especifica explícitamente en STREAM_LOGO_PATH
    logo = os.environ.get("STREAM_LOGO_PATH", "").strip()
    if logo:
        logo = os.path.abspath(os.path.expanduser(logo))
        if not os.path.isfile(logo):
            raise ValueError("STREAM_LOGO_PATH debe apuntar a un archivo de imagen existente")
        if os.path.splitext(logo)[1].lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("El logo debe ser PNG, JPG o WebP estático")
        width = setting("STREAM_LOGO_WIDTH", 160, 40, 400)
        opacity = setting("STREAM_LOGO_OPACITY", 85, 10, 100) / 100
        margin = setting("STREAM_LOGO_MARGIN", 24, 0, 100)
        positions = {
            "top-left": (str(margin), str(margin)),
            "top-right": (f"main_w-overlay_w-{margin}", str(margin)),
            "bottom-left": (str(margin), f"main_h-overlay_h-{margin}"),
            "bottom-right": (f"main_w-overlay_w-{margin}", f"main_h-overlay_h-{margin}"),
        }
        position = os.environ.get("STREAM_LOGO_POSITION", "top-right").strip().lower()
        x, y = positions.get(position, positions["top-right"])
        motion = setting("STREAM_LOGO_MOTION", 0, 0, 20)
        if motion:
            x = f"'clip({x}+{motion}*sin(t/3),0,main_w-overlay_w)'"
            y = f"'clip({y}+{motion}*sin(t/4),0,main_h-overlay_h)'"
        cmd += [
            "-thread_queue_size", "512",
            "-loop", "1", "-framerate", "1", "-i", logo,
            "-filter_complex_threads", "2", "-filter_complex",
            f"[0:v:0]{video_filter}[base];"
            f"[1:v:0]scale=w={width}:h=180:force_original_aspect_ratio=decrease,"
            f"format=rgba,colorchannelmixer=aa={opacity}[logo];"
            f"[base][logo]overlay=x={x}:y={y}:shortest=1:format=auto,format=yuv420p[branded]",
            "-map", "[branded]"
        ]
    else:
        cmd += ["-map", "0:v:0", "-vf", video_filter]

    encoder_threads = str(setting("STREAM_ENCODER_THREADS", 2, 0, 16))
    preset = os.environ.get("STREAM_ENCODER_PRESET", "ultrafast").strip().lower()

    cmd += [
        "-map", "0:a:0?", "-sn", "-dn",
        "-c:v", "libx264", "-preset", preset, "-tune", "zerolatency",
        "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-threads", encoder_threads, "-bf", "0",
        "-b:v", f"{bitrate}k", "-maxrate", f"{bitrate}k", "-bufsize", f"{bitrate}k",
        "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
        "-af", audio_filter,
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-avoid_negative_ts", "make_zero", "-max_muxing_queue_size", "2048",
        # Wait for both tracks before flushing: fMP4 audio can start earlier
        # than the first video packet, especially after a segment retry.
        "-max_interleave_delta", "0", "-flush_packets", "1",
        "-rw_timeout", "10000000", "-flvflags", "no_duration_filesize", "-f", "flv", destination
    ]
    return cmd


class OutputProgress:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.last_advance = self.started
        self.frames = 0
        self.output_us = -1
        self.speed = "N/A"
        self.received = False

    def update(self, values):
        try:
            frames = int(values.get("frame", 0))
            output_us = int(values.get("out_time_us", -1))
        except ValueError:
            return
        with self.lock:
            if frames > self.frames and output_us > self.output_us:
                self.last_advance = time.monotonic()
                self.received = True
            self.frames = max(self.frames, frames)
            self.output_us = max(self.output_us, output_us)
            self.speed = values.get("speed", "N/A").strip()

    def snapshot(self):
        with self.lock:
            return dict(started=self.started, last_advance=self.last_advance,
                        frames=self.frames, output_us=self.output_us,
                        speed=self.speed, received=self.received)


def consume_progress(pipe, progress):
    values = {}
    try:
        for line in pipe:
            key, sep, value = line.strip().partition("=")
            if sep:
                values[key] = value
            if key == "progress":
                progress.update(values)
                values = {}
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def launch(source, headers, destination, log_path):
    cmd = build_command(source, headers, destination, progress=True)
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(cmd,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                text=True, encoding="utf-8", errors="replace", bufsize=1)
    except Exception:
        log.close()
        raise

    proc.stream_progress = OutputProgress()
    threading.Thread(target=consume_progress, args=(proc.stdout, proc.stream_progress), daemon=True).start()
    return proc, log, log_path


def health(proc, now=None):
    if proc is None:
        return "waiting", "Esperando un nuevo intento"
    code = proc.poll()
    if code is not None:
        return "failed", f"FFmpeg terminó (código {code})"
    now = time.monotonic() if now is None else now
    data = proc.stream_progress.snapshot()
    if not data["received"]:
        if now - data["started"] > STARTUP_SECONDS:
            return "stalled", "No se produjo video durante el arranque"
        return "starting", "Conectando y esperando los primeros fotogramas"
    if now - data["last_advance"] > STALL_SECONDS:
        return "stalled", "La salida de video dejó de avanzar"
    return "running", "FFmpeg está enviando video; no confirma la recepción de Telegram"


def stop_process(proc):
    if proc is not None:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass


def safe_tail(path, secrets=(), limit=600):
    try:
        with open(path, "rb") as log:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 4096))
            text = log.read().decode("utf-8", errors="replace")
    except (OSError, TypeError):
        return ""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[oculto]")
    text = re.sub(r"(?:https?|rtmps?)://[^\s\]\"']+", "[URL oculta]", text)
    return text[-limit:]


def retry_delay(failures):
    return min(60, 3 * 2 ** min(max(failures - 1, 0), 5))


def explicit_rejection(log_text):
    """Only explicit server rejections justify stopping automatic retries."""
    text = log_text.lower()
    return any(marker in text for marker in (
        "netstream.publish.badname", "netstream.publish.denied",
        "netconnection.connect.rejected", "authentication failed",
    ))
