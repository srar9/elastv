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
    header = f"📅 <b>PARTIDOS DEL {day} · {len(events)} eventos</b>\nHorarios de Venezuela (UTC−4)."
    header += "\nAgenda publicada por el proveedor; disponibilidad de señales sujeta al origen."
    if stale:
        header += "\n⚠️ No se pudo actualizar: se muestra la última agenda de hoy guardada en memoria."
    blocks = [header] + event_blocks(events)
    if not events:
        blocks.append("No hay eventos publicados para hoy en esta fuente. Usa /canales para consultar el directorio.")
    pages = pack_blocks(blocks)
    return [f"📄 Agenda {i}/{len(pages)}\n\n{page}" for i, page in enumerate(pages, 1)]


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
