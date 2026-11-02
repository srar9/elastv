import subprocess
from stream_runtime import launch, health, stop_process, safe_tail, retry_delay, explicit_rejection
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
    """Emite con el perfil compartido de video y audio."""
    proc, log, path = launch(source_url, headers, rtmp_destination, "stream_manual.log")
    try:
        while proc.poll() is None:
            state, reason = health(proc)
            if state == "stalled":
                print(reason)
                stop_process(proc)
                break
            time.sleep(2)
        logs = safe_tail(path, (rtmp_destination,))
        if logs:
            print(logs)
        return subprocess.CompletedProcess([], 77 if explicit_rejection(logs) else proc.returncode)
    finally:
        stop_process(proc)
        log.close()

def main():
    cfg = load_config()
    
    print("=" * 72)
    print("       SISTEMA DE TRANSMISIÓN TELEGRAM CON MONITOR DE SALIDA        ")
    print("   [ 720p 30fps | H.264 / AAC | Keyframes 2s | Recuperación técnica ]   ")
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
    print("🚀 INICIANDO CODIFICADOR:")
    print("   • Resolución: 720p HD @ 30 FPS")
    print("   • Keyframes: cada 2 segundos")
    print("   • Bitrate configurable con STREAM_VIDEO_KBPS (1200 por defecto)")
    print("   • Destino:", server_url + stream_key[:6] + "********")
    print("   • Para detener: Presiona Ctrl + C")
    print("-" * 72)
    print()

    failures = 0
    while True:
        try:
            started = time.monotonic()
            res = run_ffmpeg_stream(source_url, rtmp_destination, headers)
            if res.returncode == 77:
                print("Acceso rechazado explícitamente. Revisa el aviso de Telegram, la sala y las credenciales. Reintentos pausados.")
                break
            if res.returncode != 0:
                failures = 1 if time.monotonic() - started > 120 else failures + 1
                delay = retry_delay(failures)
                print(f"\n⚠️ Fallo técnico. Nuevo intento en {delay} segundos...")
                time.sleep(delay)
            else:
                break
        except KeyboardInterrupt:
            print("\n\n Transmisión detenida por el usuario.")
            break
        except Exception as e:
            failures += 1
            print(f"\n⚠️ Error ({type(e).__name__}). Reintentando conexión...")
            time.sleep(retry_delay(failures))

if __name__ == "__main__":
    main()
