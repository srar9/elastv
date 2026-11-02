"""Telegram presentation and command normalization, independent of bot secrets."""
import html
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser

from agenda_service import LOCAL_TZ


def normalize_command(text, username=None):
    text = re.sub(r"^(?:/\s*)+", "/", str(text).strip())
    parts = text.split(maxsplit=1)
    if not parts:
        return ""
    target = parts[0].split("@", 1)
    if len(target) > 1 and username and target[1].lower() != username.lower().lstrip("@"):
        return ""
    command = target[0].lower()
    return command + (" " + parts[1] if len(parts) > 1 else "")


def fold(text):
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()


def pack_blocks(blocks, limit=3400):
    result, current = [], ""
    for block in blocks:
        if current and len((current + "\n\n" + block).encode("utf-16-le")) // 2 > limit:
            result.append(current)
            current = ""
        current += ("\n\n" if current else "") + block
    if current:
        result.append(current)
    return result


def event_blocks(events, stream_commands=True):
    blocks = []
    for event in events:
        title = html.escape(event["match"][:250])
        comp = html.escape(event["competition"][:160])
        blocks.append(f"⏰ <b>{event['time']}</b> | {comp}\n⚽ <b>{title}</b>")
        if not event["channels"]:
            blocks.append("📡 Canal pendiente de publicación")
        for channel in event["channels"]:
            name = html.escape(channel["name"][:100])
            line = f"📺 {name}"
            if stream_commands:
                line += f" · <code>/stream {html.escape(channel['slug'])}</code>"
            blocks.append(line)
    return blocks


def agenda_messages(events, stale=False):
    day = datetime.now(LOCAL_TZ).strftime("%d/%m/%Y")
    total_events = len(events)
    header = f"📅 <b>PARTIDOS DEL {day} · {total_events} eventos</b>\nHorarios de Venezuela (UTC−4)."
    header += "\nDisponibilidad sujeta al origen. Usa /envivo para ver solo los que juegan ahora."
    if stale:
        header += "\n⚠️ No se pudo actualizar: se muestra la última agenda de hoy guardada en memoria."
    blocks = [header] + event_blocks(events)
    if not events:
        blocks.append("No hay eventos publicados para hoy en esta fuente. Usa /canales para consultar el directorio.")
    pages = pack_blocks(blocks)
    result = []
    for i, page in enumerate(pages, 1):
        nav = f"\n\n📄 <i>Página {i} de {len(pages)} (usa /partidos {2 if i==1 else 1} para ver otra página)</i>" if len(pages) > 1 else ""
        result.append(f"📄 <b>Agenda {i}/{len(pages)}</b>\n\n{page}{nav}")
    return result


def live_now_messages(events):
    now = datetime.now(LOCAL_TZ)
    live_events = []
    for ev in events:
        try:
            ev_dt = datetime.fromisoformat(ev["starts_at"])
            diff_mins = (ev_dt - now).total_seconds() / 60
            if -140 <= diff_mins <= 45:
                live_events.append((diff_mins, ev))
        except Exception:
            continue

    if not live_events:
        return [
            f"ℹ️ <b>No hay partidos jugándose en este momento</b> (Hora actual en Venezuela: <b>{now.strftime('%H:%M')}</b>).\n\n"
            "• Consulta toda la cartelera del día con <code>/partidos</code>\n"
            "• O sintoniza canales 24/7 con <code>/canales</code>"
        ]

    live_events.sort(key=lambda x: x[0])
    blocks = [
        f"🔴 <b>PARTIDOS EN VIVO Y PRÓXIMOS A INICIAR</b>\n"
        f"Hora de Venezuela: <b>{now.strftime('%H:%M')}</b> · {len(live_events)} eventos activos o por comenzar:"
    ]
    for diff_mins, ev in live_events:
        status_label = "🟢 EN JUEGO AHORA" if diff_mins <= 0 else f"🟡 COMIENZA EN {int(diff_mins)} MIN"
        title = html.escape(ev["match"][:250])
        comp = html.escape(ev["competition"][:160])
        blocks.append(f"⏰ <b>{ev['time']}</b> | {comp} — <b>{status_label}</b>\n⚽ <b>{title}</b>")
        if not ev["channels"]:
            blocks.append("📡 Señal pendiente de publicación")
        for ch in ev["channels"][:6]:
            blocks.append(f"📺 {html.escape(ch['name'][:100])} · <code>/stream {html.escape(ch['slug'])}</code>")

    pages = pack_blocks(blocks)
    return [f"🔴 <b>En Vivo {i}/{len(pages)}</b>\n\n{page}" if len(pages) > 1 else page for i, page in enumerate(pages, 1)]


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def telegram_parts(text):
    """Keep normal HTML intact; oversized responses have a complete plain fallback."""
    if len(text.encode("utf-16-le")) // 2 <= 3500:
        return [(text, "HTML")]
    parser = PlainText()
    parser.feed(text)
    plain = "".join(parser.parts)
    return [(plain[start:start + 1700], None) for start in range(0, len(plain), 1700)]
