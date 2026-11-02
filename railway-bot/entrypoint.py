"""Run the existing private Telegram bot with a minimal health endpoint.

Starts in standby until BOT_ENABLED=true, avoiding a second polling instance
while the operator prepares the Railway deployment.
"""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"mode": "standby", "bot_running": False}
STOP = threading.Event()


def enabled(env=None):
    values = os.environ if env is None else env
    return values.get("BOT_ENABLED", "false").strip().lower() in ("true", "1", "yes")


def validate(env=None):
    values = os.environ if env is None else env
    if not enabled(values):
        return
    if not re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}", values.get("TELEGRAM_BOT_TOKEN", "").strip()):
        raise ValueError("Configura TELEGRAM_BOT_TOKEN en Variables de Railway.")
    admins = [x.strip() for x in values.get("ADMIN_USER_IDS", "").split(",") if x.strip()]
    if not admins or not all(x.isdecimal() and int(x) > 0 for x in admins):
        raise ValueError("Configura ADMIN_USER_IDS con tu ID numérico de Telegram.")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return
        status = 200 if STATE["mode"] == "standby" or STATE["bot_running"] else 503
        body = json.dumps({"ok": status == 200, **STATE}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def stop_child(child):
    if child is None:
        return
    try:
        if os.name == "posix":
            # FFmpeg runs inside this process group as well.
            os.killpg(child.pid, signal.SIGTERM)
        elif child.poll() is None:
            child.terminate()
        child.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait(timeout=3)
    except ProcessLookupError:
        pass


def main():
    try:
        validate()
        if enabled():
            if not shutil.which("ffmpeg"):
                raise ValueError("Falta FFmpeg. Despliega utilizando el Dockerfile incluido.")
            folder = Path(os.environ.get("BOT_CONFIG_PATH", "/data/stream_config.json")).parent
            folder.mkdir(parents=True, exist_ok=True)
            if not os.access(folder, os.W_OK):
                raise ValueError("El volumen de configuración no permite escritura.")
    except ValueError as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1
    STATE["mode"] = "active" if enabled() else "standby"
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for event in (signal.SIGTERM, signal.SIGINT):
        signal.signal(event, lambda *_: STOP.set())
    child = None
    retries = 0
    print("Servicio preparado. Modo:", STATE["mode"], flush=True)
    if not enabled():
        print("Sin conexión a Telegram. Detén la copia local antes de activar BOT_ENABLED=true.", flush=True)
    try:
        while not STOP.is_set():
            if enabled() and child is None:
                child = subprocess.Popen(
                    [sys.executable, "-u", str(Path(__file__).with_name("bot_stream_multicanal.py"))],
                    cwd=Path(__file__).parent,
                    start_new_session=os.name == "posix",
                )
                STATE["bot_running"] = True
            if child is not None and child.poll() is not None:
                STATE["bot_running"] = False
                stop_child(child)
                child = None
                retries += 1
                print("El bot terminó. Reintento:", retries, flush=True)
                STOP.wait(min(30, 2 ** min(retries, 5)))
            STOP.wait(0.5)
    finally:
        STATE["bot_running"] = False
        stop_child(child)
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
