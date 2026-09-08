import subprocess
import sys
import os
import json
import time
from urllib.parse import urlparse

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_stream.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "server_url": "rtmps://dc4-1.rtmp.t.me/s/",
        "last_stream_key": "4394528713:myDTS60UhFs8Q1cpXDDyaQ"
    }

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def extract_referer(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        pass
    return "https://google.com/"

def run_ffmpeg_stream(source_url, rtmp_destination, headers):
    """
    Perfil BLINDADO ANTI-CONGELAMIENTO para Telegram:
    - SIN '-re' en la entrada: Permite absorber micro-fluctuaciones de internet sin cortar el buffer.
    - Buffer elástico sin '+nobuffer': Evita caídas ante jitter de red.
    - Keyframe forzado cada 2.0s exactos (-g 60 -keyint_min 60 -sc_threshold 0 -bf 0): Telegram nunca se congela esperando IDR.
    - Bitrate ultra-estable (1500k, max 1800k, bufsize 3000k): Cero saturación de ancho de banda de subida.
    - Sincronización continua de audio (aresample async): Evita congelamientos por desincronización A/V.
    """
    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-thread_queue_size", "8192",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "15000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "2000000",
        "-probesize", "2000000",
        "-live_start_index", "-3"
    ]
    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-vf", "fps=fps=30:round=near,setpts=N/(30*TB),scale=1280:720:flags=fast_bilinear",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-profile:v", "main",
        "-level", "3.1",
        "-threads", "0",
        "-b:v", "1500k",
        "-maxrate", "1800k",
        "-bufsize", "3000k",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-af", "aresample=48000:async=1000:first_pts=0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-bsf:a", "aac_adtstoasc",
        "-avoid_negative_ts", "make_zero",
        "-flush_packets", "1",
        "-max_interleave_delta", "0",
        "-max_muxing_queue_size", "8192",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        rtmp_destination
    ])
    return subprocess.run(cmd)

def main():
    cfg = load_config()
    
    print("=" * 72)
    print("       SISTEMA DE TRANSMISIÓN TELEGRAM (PERFIL ULTRA-FLUIDO)        ")
    print("   [ 720p 30fps | Bitrate Estable 1800k | Keyframes 2s | Anti-Freeze ]   ")
    print("=" * 72)
    print()

    # 1. URL del Servidor
    server_url = input(f"1. Servidor RTMP [Enter para {cfg['server_url']}]: ").strip()
    if not server_url:
        server_url = cfg.get("server_url", "rtmps://dc4-1.rtmp.t.me/s/")
    if not server_url.endswith("/"):
        server_url += "/"
    cfg["server_url"] = server_url

    # 2. Clave de Transmisión (Stream Key)
    last_key = cfg.get("last_stream_key", "")
    key_prompt = f"2. Stream Key de Telegram"
    if last_key:
        key_prompt += f" [Enter para usar la actual: {last_key[:8]}...{last_key[-4:]}]: "
    else:
        key_prompt += ": "
    
    stream_key = input(key_prompt).strip()
    if not stream_key and last_key:
        stream_key = last_key
    elif not stream_key:
        print("❌ Error: La clave de transmisión es obligatoria.")
        input("\nPresiona Enter para salir...")
        return

    cfg["last_stream_key"] = stream_key
    save_config(cfg)

    rtmp_destination = server_url + stream_key

    # 3. URL del Partido (.m3u8)
    print()
    source_url = input("3. Pega la URL del partido (.m3u8): ").strip()
    if not source_url:
        print("❌ Error: Debes ingresar el enlace de la señal.")
        input("\nPresiona Enter para salir...")
        return

    referer = extract_referer(source_url)
    headers = (
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
        f"Referer: {referer}\r\n"
        f"Origin: {referer.rstrip('/')}\r\n"
    )

    print()
    print("-" * 72)
    print("🚀 TRANSMISIÓN ULTRA-FLUIDA INICIADA:")
    print("   • Resolución: 720p HD @ 30 FPS (Fluidez constante sin saturar subida)")
    print("   • Keyframes forzados: cada 2 segundos (Estándar Telegram)")
    print("   • Bitrate controlado: 1800 Kbps")
    print("   • Destino:", server_url + stream_key[:6] + "********")
    print("   • Para detener: Presiona Ctrl + C")
    print("-" * 72)
    print()

    while True:
        try:
            res = run_ffmpeg_stream(source_url, rtmp_destination, headers)
            if res.returncode != 0:
                print("\n⚠️ Parpadeo en la señal. Reconectando en 2 segundos...")
                time.sleep(2)
            else:
                break
        except KeyboardInterrupt:
            print("\n\n Transmisión detenida por el usuario.")
            break
        except Exception as e:
            print(f"\n⚠️ Error ({e}). Reintentando conexión...")
            time.sleep(2)

if __name__ == "__main__":
    main()
