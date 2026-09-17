# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import re
import html
import threading
import requests

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from web_app import TR_CHANNELS, CATEGORIES_META, fetch_tarjetaroja_schedule

TELEGRAM_MINIAPP_BOT_TOKEN = os.environ.get("TELEGRAM_MINIAPP_BOT_TOKEN", "8932891830:AAFIibf3wwLq0JGAvGHVnDcF6rPO_UOIc0U").strip()
API_URL = f"https://api.telegram.org/bot{TELEGRAM_MINIAPP_BOT_TOKEN}"
WEB_APP_BASE_URL = os.environ.get(
    "WEB_APP_BASE_URL", 
    "https://elasdelfutbol-production.up.railway.app"
)
ADMIN_IDS_RAW = os.environ.get("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = [x.strip() for x in ADMIN_IDS_RAW.split(",") if x.strip()]

def send_msg(chat_id, text, reply_markup=None):
    try:
        url = f"{API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"Error enviando mensaje a Telegram ({chat_id}):", e)
        return {"ok": False, "description": str(e)}

def setup_menu_button():
    try:
        url = f"{API_URL}/setChatMenuButton"
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
        print("Configuración menu_button @Elciroas_bot:", r.json())
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
    text = msg.get("text", "").strip()
    if not chat_id or not text:
        return

    try:
        if text.startswith("/start") or text.startswith("/ayuda") or text.startswith("/help"):
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
                    ]
                ]
            }
            send_msg(chat_id, welcome_text, reply_markup=keyboard)

        elif text.startswith("/web") or text.startswith("/app") or text.startswith("/ver"):
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

        elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
            send_msg(chat_id, "⏳ <b>Cargando la agenda de partidos de hoy desde ElCiro...</b>")
            events = fetch_tarjetaroja_schedule()
            if not events:
                send_msg(chat_id, "⚠️ No se encontraron partidos programados en este momento o la cartelera se está actualizando. Intenta nuevamente en unos minutos.")
                return

            msg_text = f"📅 <b>AGENDA DE PARTIDOS DE HOY ({len(events)} eventos):</b>\n\n"
            inline_buttons = []

            for i, ev in enumerate(events[:12]):
                ev_time = ev.get("time", "")
                ev_comp = ev.get("competition", "")
                ev_match = ev.get("match") or ev.get("title") or ""
                ev_channels = ev.get("channels", [])

                ch_names = ", ".join([c["name"] for c in ev_channels[:3]]) if ev_channels else ""
                ch_line = f"\n   📡 <i>{html.escape(ch_names)}</i>" if ch_names else ""

                msg_text += f"⏰ <b>{ev_time}</b> | 🏆 <i>{html.escape(ev_comp)}</i>\n⚽ <b>{html.escape(ev_match)}</b>{ch_line}\n\n"

                # Agregar botón para los primeros 4 partidos más destacados
                if i < 4:
                    best_slug = ev_channels[0]["slug"] if ev_channels else ""
                    match_url = f"{WEB_APP_BASE_URL}/ver/{best_slug}" if best_slug else WEB_APP_BASE_URL
                    inline_buttons.append([
                        {
                            "text": f"▶️ {ev_match[:28]}",
                            "web_app": {"url": match_url}
                        }
                    ])

            inline_buttons.append([
                {
                    "text": "📋 Ver Todos los Partidos en la Mini App",
                    "web_app": {"url": WEB_APP_BASE_URL}
                }
            ])

            send_msg(chat_id, msg_text, reply_markup={"inline_keyboard": inline_buttons})

        elif text.startswith("/canales") or text.startswith("/deportes"):
            canales_msg = (
                "📡 <b>DIRECTORIO DE CANALES DEPORTIVOS ELCiro (24/7):</b>\n\n"
                "• ⚽ <b>ESPN Suite:</b> ESPN 1, ESPN 2, ESPN 3, ESPN 4, ESPN 5, ESPN Premium, ESPN Deportes\n"
                "• 🏆 <b>Fox Sports Suite:</b> Fox Sports 1, Fox Sports 2, Fox Sports 3, FOX One MX, Fox Deportes USA\n"
                "• ✨ <b>MAX (Champions League):</b> MAX 1, MAX 2, MAX 3 HD\n"
                "• 📻 <b>DSports:</b> DSports 1, DSports 2, DSports+ HD\n"
                "• ⭐ <b>Disney+ / Star+ PPV:</b> Canales 1 al 7 HD\n"
                "• ⚡ <b>ViX+ Deportes:</b> Canales 1 al 8 HD\n"
                "• 🌐 <b>Internacionales:</b> TyC Sports, TUDN, DAZN 1/2, GolTV, Movistar LaLiga, Movistar Campeones\n\n"
                "Toca el botón abajo para abrir la lista interactiva con selector de calidad y reproductores instantáneos:"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📡 EXPLORAR 63 CANALES (Mini App)",
                            "web_app": {"url": f"{WEB_APP_BASE_URL}/canales"}
                        }
                    ],
                    [
                        {
                            "text": "⚽ ESPN 1 HD",
                            "web_app": {"url": f"{WEB_APP_BASE_URL}/ver/espn"}
                        },
                        {
                            "text": "🏆 Fox Sports 1",
                            "web_app": {"url": f"{WEB_APP_BASE_URL}/ver/fox1ar"}
                        }
                    ]
                ]
            }
            send_msg(chat_id, canales_msg, reply_markup=keyboard)

        elif text.startswith("/buscar") or text.startswith("/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre del equipo, canal o liga&gt;</code>\nEjemplo: <code>/buscar barcelona</code> o <code>/buscar espn</code>")
                return

            query = parts[1].strip()
            q_lower = query.lower()

            # Buscar en eventos de la agenda
            events = fetch_tarjetaroja_schedule()
            matched_events = [
                e for e in events 
                if q_lower in (e.get("match") or "").lower() or q_lower in (e.get("competition") or "").lower()
            ]

            # Buscar en canales
            matched_channels = []
            for k, info in TR_CHANNELS.items():
                if q_lower in k or q_lower in info.get("name", "").lower() or q_lower in info.get("slug", "").lower():
                    if info not in matched_channels:
                        matched_channels.append(info)

            if not matched_events and not matched_channels:
                send_msg(chat_id, f"🔍 No se encontraron coincidencias para <b>'{html.escape(query)}'</b>. Intenta con otra palabra clave.")
                return

            res_text = f"🔍 <b>RESULTADOS PARA:</b> <i>{html.escape(query)}</i>\n\n"
            buttons = []

            if matched_events:
                res_text += "⚽ <b>Partidos encontrados:</b>\n"
                for ev in matched_events[:6]:
                    ev_match = ev.get("match") or ev.get("title") or ""
                    ev_channels = ev.get("channels", [])
                    best_slug = ev_channels[0]["slug"] if ev_channels else ""
                    match_url = f"{WEB_APP_BASE_URL}/ver/{best_slug}" if best_slug else WEB_APP_BASE_URL
                    res_text += f"• <b>{ev.get('time', '')}</b>: {html.escape(ev_match)}\n"
                    buttons.append([
                        {
                            "text": f"▶️ {ev_match[:28]}",
                            "web_app": {"url": match_url}
                        }
                    ])
                res_text += "\n"

            if matched_channels:
                res_text += "📡 <b>Canales encontrados:</b>\n"
                for ch in matched_channels[:5]:
                    res_text += f"• <b>{html.escape(ch.get('name', ''))}</b> (<code>{ch.get('slug', '')}</code>)\n"
                    buttons.append([
                        {
                            "text": f"📺 Ver {ch.get('name', '')[:22]}",
                            "web_app": {"url": f"{WEB_APP_BASE_URL}/ver/{ch.get('slug', '')}"}
                        }
                    ])

            send_msg(chat_id, res_text, reply_markup={"inline_keyboard": buttons})

        elif text.startswith(("/id", "/myid", "/mi_id")):
            send_msg(
                chat_id, 
                f"👤 <b>Tu ID de Telegram:</b> <code>{user_id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
                f"🛡️ <i>Copia tu ID numérico y colócalo en la variable <code>ADMIN_USER_IDS</code> de Railway para proteger tu bot de accesos no autorizados.</i>"
            )
            return

        elif text.startswith("/post") or text.startswith("/anunciar") or text.startswith("/publicar"):
            if ADMIN_USER_IDS and str(user_id) not in ADMIN_USER_IDS:
                send_msg(chat_id, "⛔ <b>Acceso denegado:</b> Solo el administrador autorizado puede usar el comando /post.")
                return

            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                help_post = (
                    "📢 <b>PUBLICAR ENLACES PROTEGIDOS EN TU CANAL DE TELEGRAM:</b>\n\n"
                    "Usa este comando para publicar anuncios con botones interactivos que tus seguidores abrirán directamente en Telegram.\n"
                    "<b>¡100% Inmune a bloqueos y cierres por copyright!</b>\n\n"
                    "<b>Formato:</b>\n"
                    "<code>/post &lt;@canal&gt; [canal o partido | canal]</code>\n\n"
                    "<b>Ejemplos:</b>\n"
                    "• <code>/post @mi_canal</code> $\\rightarrow$ Publica la cartelera de hoy con botón directo\n"
                    "• <code>/post @mi_canal espn</code> $\\rightarrow$ Publica botón directo a ESPN 1 HD\n"
                    "• <code>/post @mi_canal Real Madrid vs Barcelona | espn</code> $\\rightarrow$ Publica partido específico\n\n"
                    "⚠️ <i>Nota: Asegúrate de añadir a este bot como Administrador en tu canal para que pueda publicar.</i>"
                )
                send_msg(chat_id, help_post)
                return

            target_channel = parts[1].strip()
            extra = parts[2].strip() if len(parts) > 2 else ""

            target_slug = "espn"
            match_title = "⚽ Transmisión Deportiva en Vivo"
            channel_label = "Señal en Directo"

            if extra:
                if "|" in extra:
                    m_parts = extra.split("|", 1)
                    match_title = f"⚽ <b>{m_parts[0].strip()}</b>"
                    slug_c, ch_name = normalize_channel_search(m_parts[1].strip())
                    target_slug = slug_c
                    channel_label = ch_name
                else:
                    slug_c, clean_name = normalize_channel_search(extra)
                    target_slug = slug_c
                    channel_label = clean_name
                    if slug_c in [c.get("slug") for c in TR_CHANNELS.values()]:
                        match_title = f"📺 <b>{clean_name} en Directo</b>"
                    else:
                        match_title = f"⚽ <b>{extra}</b>"

            target_url = f"{WEB_APP_BASE_URL}/ver/{target_slug}" if extra else WEB_APP_BASE_URL

            post_text = (
                f"{match_title}\n\n"
                f"📡 <b>Canal:</b> {channel_label}\n"
                "🔥 <b>¡TRANSMISIÓN EN VIVO SIN CORTES!</b>\n"
                "Toca el botón interactivo de abajo para ver la señal en HD directamente en Telegram:"
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
                            "text": "📋 Ver Agenda Completa de Hoy",
                            "url": WEB_APP_BASE_URL
                        }
                    ]
                ]
            }

            res = send_msg(target_channel, post_text, reply_markup=channel_kb)
            if res and res.get("ok"):
                send_msg(chat_id, f"✅ <b>Mensaje con botón interactivo publicado exitosamente en {target_channel}</b>")
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
            elif r.status_code in [401, 404]:
                print(f"Error de token Telegram @Elciroas_bot: {r.status_code}.")
                time.sleep(15)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
