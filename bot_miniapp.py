# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import re
import html
import threading
import requests
import urllib.parse

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from bot_catalog import normalize_command, pack_blocks, event_blocks, telegram_parts, fold
from agenda_service import LOCAL_TZ, schedule
from datetime import datetime
from web_app import TR_CHANNELS, CATEGORIES_META, fetch_tarjetaroja_schedule, slugify_match

TELEGRAM_MINIAPP_BOT_TOKEN = (os.environ.get("TELEGRAM_MINIAPP_BOT_TOKEN") or "8932891830:AAFIibf3wwLq0JGAvGHVnDcF6rPO_UOIc0U").strip()
API_URL = f"https://api.telegram.org/bot{TELEGRAM_MINIAPP_BOT_TOKEN}"

# Detectar automáticamente el dominio activo de Railway o usar el fallback verificado
railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("RAILWAY_STATIC_URL")
if railway_domain:
    default_base = f"https://{railway_domain}" if not railway_domain.startswith("http") else railway_domain
else:
    default_base = "https://web-production-dc68f.up.railway.app"

WEB_APP_BASE_URL = os.environ.get("WEB_APP_BASE_URL", default_base).rstrip("/")
ADMIN_IDS_RAW = os.environ.get("ADMIN_USER_IDS", "")
_env_admins = [x.strip() for x in ADMIN_IDS_RAW.split(",") if x.strip()]
ADMIN_USER_IDS = list(set(_env_admins + ["6467102546"]))

def send_msg(chat_id, text, reply_markup=None):
    result = {"ok": False}
    for index, (part, mode) in enumerate(telegram_parts(str(text))):
        payload = {"chat_id": chat_id, "text": part, "disable_web_page_preview": True}
        if mode:
            payload["parse_mode"] = mode
        if reply_markup and index == 0:
            payload["reply_markup"] = reply_markup
        try:
            for attempt in range(3):
                response = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=12)
                result = response.json()
                if response.status_code == 429 and attempt < 2:
                    time.sleep(max(1, int(result.get("parameters", {}).get("retry_after", 2))))
                    continue
                break
        except (requests.RequestException, ValueError, TypeError) as exc:
            print("[Mini App] Error enviando mensaje:", type(exc).__name__)
            result = {"ok": False}
        if not result.get("ok"):
            print("[Mini App] Telegram no aceptó un mensaje")
    return result


def send_photo(chat_id, photo, caption=None, reply_markup=None):
    try:
        url = f"{API_URL}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo,
            "parse_mode": "HTML"
        }
        if caption:
            payload["caption"] = caption
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        print(f"Error enviando foto a Telegram ({chat_id}):", e)
        return {"ok": False, "description": str(e)}

def setup_menu_button():
    tokens_to_setup = [TELEGRAM_MINIAPP_BOT_TOKEN]
    elciro_token = os.environ.get("ELCIRO_BOT_TOKEN", "8626036800:AAEqCZ-bEXrRCNL2E30gLRvJuCP1piDJwPQ").strip()
    if elciro_token and elciro_token not in tokens_to_setup:
        tokens_to_setup.append(elciro_token)

    for tok in tokens_to_setup:
        try:
            url = f"https://api.telegram.org/bot{tok}/setChatMenuButton"
            payload = {
                "menu_button": {
                    "type": "web_app",
                    "text": "📺 Ver Partidos en Vivo",
                    "web_app": {
                        "url": WEB_APP_BASE_URL
                    }
                }
            }
            r = requests.post(url, json=payload, timeout=8)
            print(f"Configuración menu_button ({tok[:10]}...):", r.json())
        except Exception as e:
            print("Error configurando menu_button en bot_miniapp:", e)

def normalize_channel_search(query):
    raw = query.strip()
    q = raw.lower()
    q_clean = re.sub(r'[^a-z0-9]', '', q)
    if not q_clean:
        return "espn", "ESPN 1 HD"

    # 1. Búsqueda exacta en claves o slugs de TR_CHANNELS
    for key, info in TR_CHANNELS.items():
        k_clean = re.sub(r'[^a-z0-9]', '', key)
        slug_clean = re.sub(r'[^a-z0-9]', '', info.get("slug", ""))
        if q_clean == k_clean or q_clean == slug_clean:
            return info.get("slug", key), info.get("name", key)

    # 2. Detección específica Apple TV MLS (ej. "appletv1", "apple 1", "apple tv 2", "appletv")
    m_apple = re.search(r'apple(?:tv)?(\d+)', q_clean)
    if m_apple:
        num = m_apple.group(1)
        return f"appletv{num}", f"Apple TV {num} HD (MLS)"
    if "appletv" in q_clean or "apple" in q_clean:
        return "appletv1", "Apple TV 1 HD (MLS)"

    # 3. Detección específica Disney+ (ej. "disney 1", "disney-7")
    m_disney = re.search(r'disney(\d+)', q_clean)
    if m_disney:
        num = int(m_disney.group(1))
        slug_d = f"disney-{num}" if num <= 7 else f"disney{num}"
        return slug_d, f"Disney+ {num} HD"

    # 4. Coincidencia parcial en nombres de canales de TR_CHANNELS
    for key, info in TR_CHANNELS.items():
        k_clean = re.sub(r'[^a-z0-9]', '', key)
        slug_clean = re.sub(r'[^a-z0-9]', '', info.get("slug", ""))
        name_clean = re.sub(r'[^a-z0-9]', '', info.get("name", ""))
        if q_clean in k_clean or q_clean in slug_clean or q_clean in name_clean:
            return info.get("slug", key), info.get("name", key)

    # 5. Si es un slug válido alfanumérico directo (ej. "canal5mx", "tudn"), respetarlo directamente
    if re.match(r'^[a-z0-9_\-]+$', raw.lower()):
        return raw.lower(), raw.upper()

    return "espn", "ESPN 1 HD"

def handle_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    raw_text = msg.get("text") or msg.get("caption") or ""
    text = normalize_command(raw_text)
    command = text.split(maxsplit=1)[0] if text else ""
    if not chat_id or not text:
        return

    # Extraer foto adjunta o de mensaje respondido
    attached_photo = None
    if msg.get("photo"):
        attached_photo = msg.get("photo")[-1].get("file_id")
    elif msg.get("reply_to_message", {}).get("photo"):
        attached_photo = msg.get("reply_to_message", {}).get("photo")[-1].get("file_id")

    try:
        if command in ("/start", "/ayuda", "/help", "/comandos"):
            welcome_text = (
                "⚽ <b>¡BIENVENIDO A ELCiro LIVE MINI APP!</b>\n\n"
                "🚀 <b>Transmisiones en Directo 100% Inmunes a Bloqueos:</b>\n"
                "Mira los mejores partidos de fútbol y eventos deportivos del mundo en calidad HD directamente dentro de Telegram.\n\n"
                "🛡️ <b>¿Por qué usar la Mini App?</b>\n"
                "• <b>Cero Riesgo de Cierre:</b> No se transmiten flujos ilegales dentro de canales; la señal se reproduce en el navegador seguro de Telegram.\n"
                "• <b>Acceso Inmediato:</b> 63 canales deportivos 24/7 (ESPN, Fox Sports, Champions MAX, DSports, ViX+, Disney+).\n"
                "• <b>Botón en tu Menú:</b> Toca el botón <i>'📺 Ver Partidos en Vivo'</i> abajo a la izquierda en cualquier momento.\n\n"
                "📋 <b>COMANDOS DISPONIBLES:</b>\n"
                "• <code>/web</code> $\\rightarrow$ Abrir la Mini App de inmediato\n"
                "• <code>/partidos</code> $\\rightarrow$ Cartelera y horarios de partidos de hoy\n"
                "• <code>/canales</code> $\\rightarrow$ Directorio de los 63 canales disponibles\n"
                "• <code>/buscar &lt;texto&gt;</code> $\\rightarrow$ Buscar partido o canal específico\n"
                "• <code>/post &lt;@canal&gt; [canal o texto]</code> $\\rightarrow$ Publicar anuncio interactivo con botón en tu canal"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📺 ABRIR ELCiro EN VIVO (Mini App)",
                            "web_app": {"url": WEB_APP_BASE_URL}
                        }
                    ],
                    [
                        {
                            "text": "⚽ Partidos de Hoy",
                            "web_app": {"url": WEB_APP_BASE_URL}
                        },
                        {
                            "text": "📡 Canales 24/7",
                            "web_app": {"url": f"{WEB_APP_BASE_URL}/canales"}
                        }
                    ],
                    [
                        {
                            "text": "📢 Unirse al Canal Oficial (@elasdelfutbol)",
                            "url": "https://t.me/elasdelfutbol"
                        }
                    ]
                ]
            }
            send_msg(chat_id, welcome_text, reply_markup=keyboard)

        elif command in ("/web", "/app", "/ver"):
            msg_body = (
                "📱 <b>ELCiro Mini App en Telegram:</b>\n\n"
                "Presiona el botón interactivo abajo para desplegar el reproductor en vivo y la cartelera de eventos sin salir de Telegram:"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "▶️ ENTRAR A ELCiro EN VIVO",
                            "web_app": {"url": WEB_APP_BASE_URL}
                        }
                    ]
                ]
            }
            send_msg(chat_id, msg_body, reply_markup=keyboard)

        elif command in ("/partidos", "/partido", "/agenda", "/hoy", "/juegos", "/cartelera"):
            send_msg(chat_id, "⏳ <b>Cargando la agenda de partidos de hoy desde ElCiro...</b>")
            events = fetch_tarjetaroja_schedule()
            if not events:
                send_msg(chat_id, "⚠️ No se encontraron partidos programados en este momento o la cartelera se está actualizando. Intenta nuevamente en unos minutos.")
                return

            blocks = [f"📅 <b>PARTIDOS DEL {datetime.now(LOCAL_TZ).strftime('%d/%m/%Y')} · {len(events)} eventos</b>\n"
                      "Horarios de Venezuela (UTC−4). Disponibilidad sujeta al proveedor."]
            if schedule.stale:
                blocks.append("⚠️ Última agenda de hoy guardada; no se pudo actualizar.")
            blocks.extend(event_blocks(events, stream_commands=False))
            pages = pack_blocks(blocks)
            keyboard = {"inline_keyboard": [[{"text": "Abrir la agenda en la Mini App",
                                               "web_app": {"url": WEB_APP_BASE_URL}}]]}
            for index, page in enumerate(pages, 1):
                send_msg(chat_id, f"📄 Agenda {index}/{len(pages)}\n\n{page}", reply_markup=keyboard if index == 1 else None)
                if index < len(pages):
                    time.sleep(1.2)

        elif command in ("/canales", "/deportes", "/menu"):
            entries = {info["slug"]: info for info in TR_CHANNELS.values()}
            for event in fetch_tarjetaroja_schedule():
                for channel in event["channels"]:
                    entries.setdefault(channel["slug"], channel)
            parts = text.split(maxsplit=1)
            query = fold(parts[1]) if len(parts) > 1 else ""
            channels = [ch for ch in entries.values() if query in fold(ch["name"] + " " + ch["slug"])]
            blocks = [f"📺 <b>CANALES · {len(channels)} señales configuradas o publicadas</b>\nDisponibilidad sujeta al origen."]
            for channel in sorted(channels, key=lambda ch: fold(ch["name"])):
                url = f"{WEB_APP_BASE_URL}/ver/{urllib.parse.quote(channel['slug'])}"
                blocks.append(f"📺 <a href=\"{html.escape(url, quote=True)}\">{html.escape(channel['name'][:100])}</a>")
            for page in pack_blocks(blocks):
                send_msg(chat_id, page)

        elif command in ("/buscar", "/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre del equipo, canal o liga&gt;</code>\nEjemplo: <code>/buscar barcelona</code> o <code>/buscar espn</code>")
                return

            query = parts[1].strip()[:200]
            events = fetch_tarjetaroja_schedule()
            matched = [e for e in events if fold(query) in fold(e["match"] + " " + e["competition"])]
            entries = {info["slug"]: info for info in TR_CHANNELS.values()}
            for event in events:
                for channel in event["channels"]:
                    entries.setdefault(channel["slug"], channel)
            channels = [ch for ch in entries.values() if fold(query) in fold(ch["name"] + " " + ch["slug"])]
            blocks = [f"🔎 <b>{html.escape(query)}</b> · {len(matched)} eventos / {len(channels)} canales"]
            blocks.extend(event_blocks(matched, stream_commands=False))
            for channel in channels:
                url = f"{WEB_APP_BASE_URL}/ver/{urllib.parse.quote(channel['slug'])}"
                blocks.append(f"📺 <a href=\"{html.escape(url, quote=True)}\">{html.escape(channel['name'][:100])}</a>")
            if not matched and not channels:
                blocks.append("No se encontraron coincidencias.")
            for page in pack_blocks(blocks):
                send_msg(chat_id, page)

        elif command in ("/id", "/myid", "/mi_id"):
            send_msg(
                chat_id, 
                f"👤 <b>Tu ID de Telegram:</b> <code>{user_id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
                f"🛡️ <i>Copia tu ID numérico y colócalo en la variable <code>ADMIN_USER_IDS</code> de Railway para proteger tu bot de accesos no autorizados.</i>"
            )
            return

        elif command in ("/post", "/anunciar", "/publicar"):
            if ADMIN_USER_IDS and str(user_id) not in ADMIN_USER_IDS:
                send_msg(chat_id, "⛔ <b>Acceso denegado:</b> Solo el administrador autorizado puede usar el comando /post.")
                return

            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                help_post = (
                    "📢 <b>PUBLICAR ENLACES PROTEGIDOS CON O SIN IMAGEN EN TU CANAL:</b>\n\n"
                    "<b>Modos de uso:</b>\n"
                    "1️⃣ <b>Con Imagen Adjunta (Recomendado):</b> Toca el clip 📎 en Telegram, selecciona tu foto y en el comentario escribe:\n"
                    "<code>/post @mi_canal Real Madrid vs Barcelona | espn</code>\n\n"
                    "2️⃣ <b>Respondiendo a una foto:</b> Responde a cualquier foto en este chat con:\n"
                    "<code>/post @mi_canal Inter Miami vs Cruz Azul | appletv1</code>\n\n"
                    "3️⃣ <b>Con Enlace Web de Imagen:</b>\n"
                    "<code>/post @mi_canal Partido | canal | https://i.imgur.com/foto.jpg</code>\n\n"
                    "4️⃣ <b>Solo Texto:</b>\n"
                    "<code>/post @mi_canal Inter Miami vs Cruz Azul | appletv1</code>\n\n"
                    "⚠️ <i>Nota: Asegúrate de añadir a @Elciroas_bot como Administrador en tu canal.</i>"
                )
                send_msg(chat_id, help_post)
                return

            target_channel = parts[1].strip()
            extra = parts[2].strip() if len(parts) > 2 else ""

            target_photo = attached_photo
            target_slug = "espn"
            match_title = "⚽ Transmisión Deportiva en Vivo"
            channel_label = "Señal en Directo"
            clean_match_title = ""

            if extra:
                if "|" in extra:
                    raw_segments = [s.strip() for s in extra.split("|") if s.strip()]
                    clean_segments = []
                    for seg in raw_segments:
                        if seg.startswith(("http://", "https://")) and not target_photo:
                            target_photo = seg
                        else:
                            clean_segments.append(seg)

                    if len(clean_segments) >= 1:
                        clean_match_title = clean_segments[0]
                        match_title = f"⚽ <b>{clean_match_title}</b>"
                    if len(clean_segments) >= 2:
                        slug_c, ch_name = normalize_channel_search(clean_segments[1])
                        target_slug = slug_c
                        channel_label = ch_name
                    elif len(clean_segments) == 1:
                        slug_c, ch_name = normalize_channel_search(clean_segments[0])
                        if slug_c in [c.get("slug") for c in TR_CHANNELS.values()]:
                            target_slug = slug_c
                            channel_label = ch_name
                            clean_match_title = ch_name
                            match_title = f"📺 <b>{ch_name} en Directo</b>"
                else:
                    if extra.startswith(("http://", "https://")) and not target_photo:
                        target_photo = extra
                    else:
                        slug_c, clean_name = normalize_channel_search(extra)
                        target_slug = slug_c
                        channel_label = clean_name
                        if slug_c in [c.get("slug") for c in TR_CHANNELS.values()]:
                            clean_match_title = clean_name
                            match_title = f"📺 <b>{clean_name} en Directo</b>"
                        else:
                            clean_match_title = extra
                            match_title = f"⚽ <b>{extra}</b>"

            m_slug = slugify_match(clean_match_title)
            if extra and m_slug:
                target_url = f"{WEB_APP_BASE_URL}/ver/{target_slug}?m={m_slug}&title={urllib.parse.quote(clean_match_title)}"
            elif extra:
                target_url = f"{WEB_APP_BASE_URL}/ver/{target_slug}"
            else:
                target_url = WEB_APP_BASE_URL

            post_text = (
                f"{match_title}\n\n"
                f"📡 <b>Canal:</b> {channel_label}\n"
                "🔥 <b>¡TRANSMISIÓN EN VIVO SIN CORTES!</b>\n"
                "Toca el botón interactivo de abajo para ver la señal en HD directamente en Telegram:\n\n"
                "📢 <b>Canal Oficial:</b> @elasdelfutbol"
            )

            # Nota: En canales de Telegram los botones inline de tipo 'web_app' no están permitidos
            # por Telegram Bot API (devuelve BUTTON_TYPE_INVALID). Deben ser de tipo 'url'.
            # Al ser un enlace HTTPS, Telegram lo abre de forma idéntica en el navegador interno.
            channel_kb = {
                "inline_keyboard": [
                    [
                        {
                            "text": f"📺 VER EN VIVO ({channel_label})",
                            "url": target_url
                        }
                    ],
                    [
                        {
                            "text": "📢 Canal Oficial: @elasdelfutbol",
                            "url": "https://t.me/elasdelfutbol"
                        }
                    ]
                ]
            }

            if target_photo:
                res = send_photo(target_channel, target_photo, caption=post_text, reply_markup=channel_kb)
                if not res or not res.get("ok"):
                    # Fallback a texto si la foto falla
                    res = send_msg(target_channel, post_text, reply_markup=channel_kb)
            else:
                res = send_msg(target_channel, post_text, reply_markup=channel_kb)

            if res and res.get("ok"):
                photo_notice = " con imagen" if target_photo else ""
                send_msg(chat_id, f"✅ <b>Anuncio{photo_notice} publicado exitosamente en {target_channel}</b>")
            else:
                err_desc = res.get("description", "Error desconocido") if res else "No se pudo conectar"
                send_msg(
                    chat_id, 
                    f"❌ <b>Error al publicar en {target_channel}:</b> <code>{html.escape(err_desc)}</code>\n\n"
                    "💡 <b>Solución:</b>\n"
                    "1. Ve a los ajustes de tu canal en Telegram.\n"
                    "2. En 'Administradores', añade a <b>@Elciroas_bot</b>.\n"
                    "3. Asígnale permiso para 'Publicar mensajes' (Post Messages)."
                )

        elif text.startswith("/"):
            send_msg(
                chat_id, 
                "❓ <b>Comando no reconocido.</b>\nUsa <code>/web</code>, <code>/partidos</code>, <code>/canales</code> o <code>/ayuda</code>."
            )

    except Exception as e:
        print("Error en handle_message bot_miniapp:", e)
        send_msg(chat_id, f"⚠️ Ocurrió un error temporal al procesar la solicitud: <code>{html.escape(str(e))}</code>")

def main():
    print("=" * 65)
    print("🚀 BOT DEDICADO MINI APP (@Elciroas_bot)")
    print("=" * 65)
    if not TELEGRAM_MINIAPP_BOT_TOKEN:
        print("⚠️ AVISO: Variable TELEGRAM_MINIAPP_BOT_TOKEN no configurada.")
        return

    try:
        del_res = requests.get(f"{API_URL}/deleteWebhook?drop_pending_updates=false", timeout=10)
        print(f"Estado de webhook miniapp eliminado: {del_res.status_code}")
    except Exception as e:
        print(f"Aviso al limpiar webhook inicial: {e}")

    setup_menu_button()
    print("Iniciando polling de Telegram para @Elciroas_bot...")
    offset = 0

    while True:
        try:
            url = f"{API_URL}/getUpdates?offset={offset}&timeout=25"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for result in data.get("result", []):
                        offset = result["update_id"] + 1
                        if "message" in result:
                            t = threading.Thread(target=handle_message, args=(result["message"],), daemon=True)
                            t.start()
            elif r.status_code == 409:
                print("Conflicto 409 en @Elciroas_bot. Limpiando webhook...")
                try:
                    requests.get(f"{API_URL}/deleteWebhook?drop_pending_updates=false", timeout=10)
                except Exception:
                    pass
                time.sleep(2)
            elif r.status_code in [401, 404]:
                print(f"Error de token Telegram @Elciroas_bot: {r.status_code}.")
                time.sleep(15)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
