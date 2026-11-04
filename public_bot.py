"""Audience-only Telegram bot. Never imports or starts the RTMP control bot."""
import html
import os
import time
from urllib.parse import urlencode, quote

import requests

from agenda_service import schedule, ScheduleUnavailable
from bot_catalog import fold, normalize_command
from audience import OWNER_ID, bot_entry, summary

TOKEN = os.environ.get("PUBLIC_BOT_TOKEN") or os.environ.get("ELCIRO_BOT_TOKEN", "")
BASE_URL = (os.environ.get("WEB_APP_BASE_URL") or
            "https://" + (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "web-production-dc68f.up.railway.app")).rstrip("/")
COMMANDS = [dict(command=c, description=d) for c, d in (
    ("start", "Ver los partidos directamente en este chat"),
    ("partidos", "Todos los partidos y deportes de hoy"),
    ("buscar", "Buscar equipo, torneo, deporte o canal"),
    ("canales", "Todos los canales disponibles"))]
USERNAME = None


def api(method, **payload):
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=35)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('error_code', response.status_code)}")
    return data["result"]


def button(label, path, private=True):
    return {"text": label[:120], "web_app" if private else "url":
            {"url": BASE_URL + path} if private else BASE_URL + path}


def send(chat_id, text, rows=None, keyboard=None):
    payload = dict(chat_id=chat_id, text=text, parse_mode="HTML")
    if rows:
        payload["reply_markup"] = dict(inline_keyboard=rows)
    elif keyboard:
        payload["reply_markup"] = dict(keyboard=keyboard, resize_keyboard=True,
                                     is_persistent=True, input_field_placeholder="Escribe tu equipo, liga o deporte")
    api("sendMessage", **payload)


def event_buttons(event, private):
    channels = event.get("channels", [])
    if not channels:
        return []
    params = urlencode(dict(m=event["match_slug"], title=event["match"], c=event["competition"], mode="watch"))
    label = "▶ " + event["time"] + " · " + event["match"]
    return [[button(label, "/ver/" + quote(channels[0]["slug"], safe="") + "?" + params, private)]]


def chat_keyboard(owner=False):
    rows = [[dict(text="⚽ Partidos de hoy"), dict(text="📺 Canales")], [dict(text="🔎 Buscar")]]
    if owner:
        rows.append([dict(text="📊 Estadísticas")])
    return rows


def handle_message(message):
    chat = message.get("chat", {})
    user_id = message.get("from", {}).get("id")
    chat_id = chat.get("id")
    if not chat_id or not user_id:
        return
    private = chat.get("type") == "private"
    raw = message.get("text", "").strip()
    shortcuts = {"⚽ Partidos de hoy": "/partidos", "📺 Canales": "/canales",
                 "🔎 Buscar": "/buscar", "📊 Estadísticas": "/estadisticas"}
    text = normalize_command(shortcuts.get(raw, raw), USERNAME)
    if not text:
        return
    bot_entry(user_id)
    parts = text.split(maxsplit=1)
    command = parts[0]
    query = parts[1] if len(parts) > 1 else ""
    if command in ("/estadisticas", "/stats"):
        if user_id != OWNER_ID or not private:
            return
        data = summary()
        send(chat_id, f"📊 <b>Estadísticas privadas</b>\nUsuarios del bot: {data['bot_users']}\n"
             f"Interacciones: {data['bot_entries']}\nEntradas al reproductor: {data['player_entries']}\n"
             f"Visitantes del reproductor: {data['player_visitors']}\nReproduciendo ahora: {data['watching']}\n"
             "Presencia estimada por actividad del video en los últimos 45 segundos.",
             [[button("📊 Ver todos los partidos", "/estadisticas")]])
        for start in range(0, len(data["matches"]), 15):
            send(chat_id, "\n\n".join(f"<b>{html.escape(r['title'][:140])}</b>\n"
                 f"Viendo: {r['watching']} · Entradas: {r['entries']} · Visitantes: {r['visitors']}"
                 for r in data["matches"][start:start + 15]))
        return
    if command in ("/start", "/help", "/ayuda", "/app", "/web", "/miniapp", "/menu"):
        if private and user_id == OWNER_ID:
            try:
                api("setMyCommands", scope=dict(type="chat", chat_id=OWNER_ID), commands=COMMANDS + [
                    dict(command="estadisticas", description="Audiencia y entradas por partido · privado")])
            except (RuntimeError, requests.RequestException):
                pass
        send(chat_id, "📺 <b>El Ciro TV</b>\nBusca tu equipo, torneo, deporte o canal escribiendo su nombre.\n"
             "Aquí tienes la cartelera. Toca el partido para abrir directamente su video.",
             keyboard=chat_keyboard(user_id == OWNER_ID) if private else None)
        command, query = "/partidos", ""
    if command in ("/canales", "/deportes"):
        send_channels(chat_id, query, private)
        return
    if command.startswith("/") and command not in ("/partidos", "/agenda", "/hoy", "/juegos", "/buscar", "/search"):
        send(chat_id, "Usa /partidos, /canales o /buscar equipo, torneo o deporte.")
        return
    if not command.startswith("/"):
        query = text
    if command in ("/buscar", "/search") and not query:
        send(chat_id, "🔎 Escribe el nombre del equipo, torneo, deporte o canal que quieres ver.\n"
             "Por ejemplo: <b>Real Madrid</b>, <b>NBA</b> o <b>ESPN</b>.")
        return
    needle = fold(query)
    events = schedule.get()
    matches = [e for e in events if not needle or needle in fold(
        " ".join([e["match"], e["competition"]] + [c["name"] for c in e["channels"]]))]
    send(chat_id, f"📅 <b>{len(matches)} eventos</b> · Hora de Venezuela\nToca un partido para ver el video." +
         ("\n⚠ Agenda guardada; la fuente no pudo actualizarse." if schedule.stale else "") +
         ("\nNo hay eventos coincidentes. Prueba /canales o busca otro equipo." if not matches else ""))
    # All results are included. Each message stays below Telegram's button/text limits.
    for start in range(0, len(matches), 8):
        blocks, rows = [], []
        for event in matches[start:start + 8]:
            blocks.append(f"{event['time']} · <b>{html.escape(event['match'][:180])}</b>\n"
                          f"{html.escape(event['competition'][:120])}" +
                          ("" if event["channels"] else "\nSeñal pendiente de publicación"))
            rows.extend(event_buttons(event, private))
        # Telegram allows up to 100 buttons; split separately for events with many signals.
        send(chat_id, "\n\n".join(blocks), rows[:80])
        for pos in range(80, len(rows), 80):
            send(chat_id, "Más señales de estos eventos", rows[pos:pos + 80])
        time.sleep(1.1)
    if needle and not matches:
        send_channels(chat_id, query, private)


def send_channels(chat_id, query, private):
    # This function is also used by Flask, so both catalogs remain identical.
    from web_app import get_unique_channels
    channels = [c for c in get_unique_channels() if fold(query) in fold(c["name"] + " " + c["slug"])]
    if not channels:
        send(chat_id, "No hay canales coincidentes. Prueba otro nombre.")
    for start in range(0, len(channels), 40):
        send(chat_id, f"📺 Canales ({len(channels)})\nToca un canal para abrir su video.", [[button(c["name"], "/ver/" + quote(c["slug"], safe="") + "?mode=watch", private)]
             for c in channels[start:start + 40]])
        time.sleep(1.1)


def configure():
    global USERNAME
    USERNAME = api("getMe")["username"]
    api("setMyCommands", commands=COMMANDS)
    try:
        api("setMyCommands", scope=dict(type="chat", chat_id=OWNER_ID),
            commands=COMMANDS + [dict(command="estadisticas", description="Audiencia y entradas por partido · privado")])
    except RuntimeError:
        # Telegram may not know the owner's private chat until their first /start.
        print("Menú privado pendiente; /estadisticas sigue disponible para el dueño.", flush=True)
    api("setChatMenuButton", menu_button=dict(type="commands"))
    try:
        api("setChatMenuButton", chat_id=OWNER_ID, menu_button=dict(type="commands"))
    except RuntimeError:
        pass


def main():
    if not TOKEN:
        raise SystemExit("Configura PUBLIC_BOT_TOKEN o ELCIRO_BOT_TOKEN")
    configure()
    api("deleteWebhook", drop_pending_updates=False)
    offset = 0
    while True:
        try:
            updates = api("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            for update in updates:
                try:
                    if "message" in update:
                        handle_message(update["message"])
                except ScheduleUnavailable:
                    send(update["message"]["chat"]["id"], "La agenda no está disponible temporalmente. Prueba /canales.")
                except Exception as exc:
                    print("Error procesando solicitud pública:", type(exc).__name__, flush=True)
                offset = update["update_id"] + 1
        except Exception as exc:
            print("Error de conexión del bot público:", type(exc).__name__, flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
