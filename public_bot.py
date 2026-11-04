"""Audience-only Telegram bot. Never imports or starts the RTMP control bot."""
import html
import os
import time
import secrets
import threading
from collections import OrderedDict
from urllib.parse import urlencode, quote

import requests

from agenda_service import schedule, ScheduleUnavailable, chronological
from bot_catalog import fold, normalize_command
from audience import OWNER_ID, bot_entry, summary

TOKEN = os.environ.get("PUBLIC_BOT_TOKEN") or os.environ.get("ELCIRO_BOT_TOKEN", "")
BASE_URL = (os.environ.get("WEB_APP_BASE_URL") or
            "https://" + (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "web-production-dc68f.up.railway.app")).rstrip("/")
COMMANDS = [dict(command=c, description=d) for c, d in (
    ("start", "Menú, mini app y partidos por hora"),
    ("app", "Abrir la mini app con la agenda completa"),
    ("partidos", "Partidos de hoy, ordenados por hora"),
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


def send(chat_id, text, rows=None, keyboard=None, remove_keyboard=False):
    payload = dict(chat_id=chat_id, text=text, parse_mode="HTML")
    if remove_keyboard:
        payload["reply_markup"] = dict(remove_keyboard=True)
    elif rows:
        payload["reply_markup"] = dict(inline_keyboard=rows)
    elif keyboard:
        payload["reply_markup"] = dict(keyboard=keyboard, resize_keyboard=True,
                                     is_persistent=True, input_field_placeholder="Escribe tu equipo, liga o deporte")
    return api("sendMessage", **payload)


def event_buttons(event, private):
    channels = event.get("channels", [])
    if not channels:
        return []
    params = urlencode(dict(m=event["match_slug"], title=event["match"], c=event["competition"], mode="watch"))
    label = "▶ " + event["time"] + " · " + event["match"]
    return [[button(label, "/ver/" + quote(channels[0]["slug"], safe="") + "?" + params, private)]]


PAGE_SIZE = 5
VIEWS = OrderedDict()
VIEW_LOCK = threading.Lock()
VIEW_TTL = 1800
HOME_TEXT = (
    "📺 <b>El Ciro TV</b>\n\n"
    "Tu agenda deportiva, ordenada por hora de Venezuela.\n"
    "Abre la mini app para ver todos los partidos o elige uno aquí."
)


def action(text, data):
    return dict(text=text, callback_data=data)


def home_rows(owner=False, private=True):
    rows = [[button("📱 Abrir mini app", "/", private)],
            [action("⚽ Partidos por hora", "menu:events")],
            [action("📺 Canales", "menu:channels"), action("🔎 Buscar", "menu:search")]]
    if owner:
        rows.append([action("📊 Estadísticas", "menu:stats")])
    return rows


def display(chat_id, text, rows, message_id=None):
    if message_id is None:
        return send(chat_id, text, rows)
    return api("editMessageText", chat_id=chat_id, message_id=message_id,
               text=text, parse_mode="HTML", reply_markup=dict(inline_keyboard=rows))


def show_home(chat_id, user_id, private, message_id=None):
    rows = home_rows(private and user_id == OWNER_ID, private)
    if message_id is None:
        # Make the mini app available immediately, then load the first games into
        # this same message. Never send the complete agenda as multiple messages.
        result = send(chat_id, HOME_TEXT, remove_keyboard=True)
        message_id = result["message_id"]
        api("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
            reply_markup=dict(inline_keyboard=rows))
    try:
        return show_events(chat_id, user_id, private, message_id)
    except ScheduleUnavailable:
        return display(chat_id, HOME_TEXT + "\n\nLa agenda no pudo actualizarse. Puedes abrir la mini app o probar los canales.", rows, message_id)


def show_app(chat_id, user_id, private):
    return display(chat_id, "📱 <b>Mini app de El Ciro TV</b>\n\nTodos los partidos ordenados por hora, búsqueda y canales en un solo lugar.",
                   home_rows(private and user_id == OWNER_ID, private))


def new_view(chat_id, user_id, private, kind, items, heading, refresh, message_id=None):
    token = secrets.token_urlsafe(6)
    view = dict(chat_id=chat_id, user_id=user_id, private=private, kind=kind,
                items=items, heading=heading, refresh=refresh, created=time.time())
    with VIEW_LOCK:
        for key in list(VIEWS):
            if time.time() - VIEWS[key]["created"] > VIEW_TTL:
                del VIEWS[key]
        VIEWS[token] = view
        while len(VIEWS) > 256:
            VIEWS.popitem(last=False)
    text, rows = render_page(token, view, 0)
    return display(chat_id, text, rows, message_id)


def render_page(token, view, page):
    items = view["items"]
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    selected = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    text = view["heading"]
    if items:
        text += f"\n\nPágina {page + 1} de {pages} · {len(items)} resultados"
    elif view["kind"] == "stats":
        text += "\n\nTodavía no hay reproducciones registradas por partido."
    else:
        text += "\n\nNo hay resultados. Prueba otra búsqueda o vuelve al menú."
    app_path = "/canales" if view["kind"] == "channels" else "/"
    rows = [[button("📱 Abrir mini app", app_path, view["private"])]] if view["kind"] != "stats" else []
    for item in selected:
        kind, data = item["kind"], item["data"]
        if kind == "event":
            buttons = event_buttons(data, view["private"])
            if buttons:
                rows.extend(buttons)
            else:
                rows.append([action((data["time"] + " · " + data["match"] + " · Pendiente")[:120], "noop:pending")])
        elif kind == "channel":
            rows.append([button("▶ " + data["name"], "/ver/" + quote(data["slug"], safe="") + "?mode=watch", view["private"])])
        elif kind == "stats":
            text += (f"\n\n<b>{html.escape(data['title'][:120])}</b>\n"
                     f"Viendo: {data['watching']} · Entradas: {data['entries']} · Visitantes: {data['visitors']}")
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(action("‹ Anterior", f"page:{token}:{page - 1}"))
        nav.append(action(f"{page + 1} / {pages}", "noop:page"))
        if page + 1 < pages:
            nav.append(action("Siguiente ›", f"page:{token}:{page + 1}"))
        rows.append(nav)
    refresh_label = "Otra búsqueda" if view["kind"] == "search" else "Actualizar"
    if view["kind"] == "events":
        rows.append([action("📺 Canales", "menu:channels"), action("🔎 Buscar", "menu:search")])
        if view["private"] and view["user_id"] == OWNER_ID:
            rows.append([action("📊 Estadísticas", "menu:stats")])
    rows.append([action("‹ Inicio", "menu:home"), action(refresh_label, view["refresh"])])
    return text, rows


def catalog_channels():
    from web_app import get_unique_channels
    return get_unique_channels()


def show_events(chat_id, user_id, private, message_id=None):
    events = chronological(schedule.get())
    heading = "⚽ <b>Partidos de hoy · por hora</b>\nHora de Venezuela · Toca el partido para ver su video.\nMini app: agenda completa, búsqueda y canales."
    if schedule.stale:
        heading += "\nAgenda guardada; la fuente no pudo actualizarse."
    return new_view(chat_id, user_id, private, "events", [dict(kind="event", data=e) for e in events],
                    heading, "menu:events", message_id)


def show_channels(chat_id, user_id, private, message_id=None):
    return new_view(chat_id, user_id, private, "channels", [dict(kind="channel", data=c) for c in catalog_channels()],
                    "📺 <b>Canales</b>\nToca un canal para abrir su video.", "menu:channels", message_id)


def show_search(chat_id, user_id, private, query, message_id=None):
    needle = fold(query)
    events = chronological(schedule.get())
    matches = [dict(kind="event", data=e) for e in events if needle in fold(
        " ".join([e["match"], e["competition"]] + [c["name"] for c in e["channels"]]))]
    matches += [dict(kind="channel", data=c) for c in catalog_channels() if needle in fold(c["name"] + " " + c["slug"])]
    return new_view(chat_id, user_id, private, "search", matches,
                    f"🔎 <b>Resultados para {html.escape(query[:100])}</b>\nToca un resultado para abrir el video.",
                    "menu:search", message_id)


def search_prompt(chat_id, message_id=None):
    return display(chat_id, "🔎 <b>Buscar</b>\n\nEscribe aquí el nombre de tu equipo, liga, deporte o canal.\n"
                   "Por ejemplo: Real Madrid, NBA o ESPN.", [[action("‹ Menú", "menu:home")]], message_id)


def show_stats(chat_id, user_id, private, message_id=None):
    if user_id != OWNER_ID or not private:
        return
    data = summary()
    heading = (f"📊 <b>Mis estadísticas</b>\n\nViendo ahora: {data['watching']}\n"
               f"Usuarios del bot: {data['bot_users']}\nEntradas al reproductor: {data['player_entries']}\n"
               f"Visitantes: {data['player_visitors']}\nEntradas a la Mini App: {data['app_entries']}\nInteracciones: {data['bot_entries']}\n"
               "Actividad estimada en los últimos 45 segundos.")
    return new_view(chat_id, user_id, private, "stats", [dict(kind="stats", data=r) for r in data["matches"]],
                    heading, "menu:stats", message_id)


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
    command, query = parts[0], parts[1] if len(parts) > 1 else ""
    if command in ("/start", "/menu", "/help", "/ayuda"):
        return show_home(chat_id, user_id, private)
    if command in ("/app", "/web", "/miniapp"):
        return show_app(chat_id, user_id, private)
    if command in ("/estadisticas", "/stats"):
        return show_stats(chat_id, user_id, private)
    if command in ("/canales", "/deportes"):
        return show_search(chat_id, user_id, private, query) if query else show_channels(chat_id, user_id, private)
    if command in ("/partidos", "/agenda", "/hoy", "/juegos"):
        return show_events(chat_id, user_id, private)
    if command in ("/buscar", "/search"):
        return show_search(chat_id, user_id, private, query) if query else search_prompt(chat_id)
    if not command.startswith("/"):
        return show_search(chat_id, user_id, private, text)
    return display(chat_id, "Elige una opción del menú o escribe tu equipo para buscar.", home_rows(private and user_id == OWNER_ID, private))


def handle_callback(callback):
    message = callback.get("message", {})
    chat = message.get("chat", {})
    chat_id, message_id = chat.get("id"), message.get("message_id")
    user_id = callback.get("from", {}).get("id")
    data = callback.get("data", "")
    if not chat_id or not message_id or not user_id:
        return
    private = chat.get("type") == "private"
    if data.startswith("noop:"):
        return api("answerCallbackQuery", callback_query_id=callback["id"],
                   text="La señal todavía no ha sido publicada." if data == "noop:pending" else "Usa Anterior o Siguiente para cambiar de página.")
    if data.startswith("page:"):
        try:
            _, token, raw_page = data.split(":")
            page = int(raw_page)
        except ValueError:
            return api("answerCallbackQuery", callback_query_id=callback["id"], text="Botón no válido.")
        with VIEW_LOCK:
            view = VIEWS.get(token)
        if view and (view["chat_id"] != chat_id or view["user_id"] != user_id):
            return api("answerCallbackQuery", callback_query_id=callback["id"],
                       text="Abre tu propio menú con /start.", show_alert=True)
        api("answerCallbackQuery", callback_query_id=callback["id"])
        if not view or time.time() - view["created"] > VIEW_TTL:
            return display(chat_id, "Este listado caducó. Abre Partidos o Canales para actualizarlo.",
                           home_rows(private and user_id == OWNER_ID, private), message_id)
        if view["kind"] == "stats" and (user_id != OWNER_ID or not private):
            return
        text, rows = render_page(token, view, page)
        return display(chat_id, text, rows, message_id)
    api("answerCallbackQuery", callback_query_id=callback["id"])
    bot_entry(user_id)
    routes = {"menu:home": show_home, "menu:events": show_events, "menu:channels": show_channels,
              "menu:stats": show_stats}
    try:
        if data == "menu:search":
            return search_prompt(chat_id, message_id)
        if data in routes:
            return routes[data](chat_id, user_id, private, message_id)
    except ScheduleUnavailable:
        return display(chat_id, "La agenda no está disponible temporalmente. Puedes probar los canales.",
                       home_rows(private and user_id == OWNER_ID, private), message_id)


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
    mini_app_menu = dict(type="web_app", text="Mini app", web_app=dict(url=BASE_URL))
    api("setChatMenuButton", menu_button=mini_app_menu)
    try:
        api("setChatMenuButton", chat_id=OWNER_ID, menu_button=mini_app_menu)
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
            updates = api("getUpdates", offset=offset, timeout=25, allowed_updates=["message", "callback_query"])
            for update in updates:
                try:
                    if "callback_query" in update:
                        handle_callback(update["callback_query"])
                    elif "message" in update:
                        handle_message(update["message"])
                except ScheduleUnavailable:
                    message = update.get("message")
                    if message:
                        send(message["chat"]["id"], "La agenda no está disponible temporalmente. Prueba /canales.")
                except Exception as exc:
                    print("Error procesando solicitud pública:", type(exc).__name__, flush=True)
                offset = update["update_id"] + 1
        except Exception as exc:
            print("Error de conexión del bot público:", type(exc).__name__, flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
