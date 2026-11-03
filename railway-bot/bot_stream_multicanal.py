import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import re
import html
import subprocess
import threading
import requests
import base64
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
from stream_runtime import launch, health, stop_process, safe_tail, retry_delay, explicit_rejection
from channel_source import resolve_roja_source, resolve_player, resolve_tvf90, resolve_tarjeta_digital, CHANNEL_NAMES, CHANNEL_PAGES
from agenda_service import schedule, ScheduleUnavailable, LOCAL_TZ
from bot_catalog import normalize_command, agenda_messages, live_now_messages, pack_blocks, event_blocks, fold, telegram_parts

# ==============================================================================
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "9281285181:AAEo_hAjJo-zd537Kvz-f4QcU3iG-aUNGzo").strip()
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
BOT_USERNAME = "Tvelas_bot"
CONFIG_FILE = os.environ.get("STREAM_CONFIG_FILE", "stream_config.json")

ADMIN_IDS_RAW = os.environ.get("ADMIN_USER_IDS", "").strip()
_env_admins = [x.strip() for x in ADMIN_IDS_RAW.split(",") if x.strip()]
if _env_admins:
    ADMIN_USER_IDS = list(set(_env_admins + ["6467102546"]))
else:
    ADMIN_USER_IDS = []

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "stream_key": "3936015063:nG8N_no46UfNuA6jXewiag"
    }

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print("Error guardando config:", e)

CONFIG = load_config()

# ==============================================================================
# ESTADO GLOBAL DE TRANSMISIONES MULTI-PANTALLA (ILIMITADAS #1, #2, #3, ...)
# ==============================================================================
active_streams = {}
stream_lock = threading.Lock()

# ==============================================================================
# DIRECTORIO INTEGRAL DE CANALES DEPORTIVOS (https://tarjetarojatv.mobi/ / la18hd.su)
# ==============================================================================
TR_CHANNELS = {
    # ESPN Suite
    "espn": {"slug": "espn", "name": "ESPN 1 HD (Sur/Argentina)", "cat": "espn"},
    "espn1": {"slug": "espn", "name": "ESPN 1 HD (Sur/Argentina)", "cat": "espn"},
    "espn2": {"slug": "espn2", "name": "ESPN 2 HD (Sur/Argentina)", "cat": "espn"},
    "espn3": {"slug": "espn3", "name": "ESPN 3 HD (Sur/Argentina)", "cat": "espn"},
    "espn4": {"slug": "espn4", "name": "ESPN 4 HD (Sur)", "cat": "espn"},
    "espn5": {"slug": "espn5", "name": "ESPN 5 HD (Sur)", "cat": "espn"},
    "espn6": {"slug": "espn6", "name": "ESPN 6 HD", "cat": "espn"},
    "espn7": {"slug": "espn7", "name": "ESPN 7 HD", "cat": "espn"},
    "espnpremium": {"slug": "espnpremium", "name": "ESPN Premium HD (Argentina)", "cat": "espn"},
    "espnextra": {"slug": "espnextra", "name": "ESPN Extra HD", "cat": "espn"},
    "espnmx": {"slug": "espnmx", "name": "ESPN México HD", "cat": "espn"},
    "espn2mx": {"slug": "espn2mx", "name": "ESPN 2 México HD", "cat": "espn"},
    "espn3mx": {"slug": "espn3mx", "name": "ESPN 3 México HD", "cat": "espn"},
    "espn4mx": {"slug": "espn4mx", "name": "ESPN 4 México HD", "cat": "espn"},
    "espnplus": {"slug": "espnplus", "name": "ESPN Plus HD", "cat": "espn"},

    # Fox Sports Suite
    "fox1": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "cat": "fox"},
    "fox1ar": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "cat": "fox"},
    "fox": {"slug": "foxsports", "name": "Fox Sports 1 HD", "cat": "fox"},
    "foxsports": {"slug": "foxsports", "name": "Fox Sports 1 HD", "cat": "fox"},
    "foxsportsar": {"slug": "foxsportsar", "name": "Fox Sports Argentina", "cat": "fox"},
    "foxsports1": {"slug": "foxsports", "name": "Fox Sports 1 HD", "cat": "fox"},
    "fox2": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "cat": "fox"},
    "fox2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "cat": "fox"},
    "foxsports2": {"slug": "foxsports2", "name": "Fox Sports 2 HD", "cat": "fox"},
    "foxsports2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "cat": "fox"},
    "fox3": {"slug": "foxsports3", "name": "Fox Sports 3 HD", "cat": "fox"},
    "foxsports3": {"slug": "foxsports3", "name": "Fox Sports 3 HD", "cat": "fox"},
    "foxsportsmx": {"slug": "foxsportsmx", "name": "Fox Sports MX", "cat": "fox"},
    "foxsports2mx": {"slug": "foxsports2mx", "name": "Fox Sports 2 MX", "cat": "fox"},
    "foxsports3mx": {"slug": "foxsports3mx", "name": "Fox Sports 3 MX", "cat": "fox"},
    "foxsportspremium": {"slug": "foxsportspremium", "name": "Fox Sports Premium HD", "cat": "fox"},
    "foxpremium": {"slug": "foxsportspremium", "name": "Fox Sports Premium HD", "cat": "fox"},

    # DIRECTV Sports (DSPORTS)
    "dsports": {"slug": "dsports", "name": "DSports 1 HD", "cat": "dsports"},
    "dsports1": {"slug": "dsports", "name": "DSports 1 HD", "cat": "dsports"},
    "dsports2": {"slug": "dsports2", "name": "DSports 2 HD", "cat": "dsports"},
    "dsportsplus": {"slug": "dsportsplus", "name": "DSports+ HD", "cat": "dsports"},
    "dsports3": {"slug": "dsportsplus", "name": "DSports+ HD", "cat": "dsports"},
    "dsports_eventos": {"slug": "dsports_eventos", "name": "DSports Eventos HD", "cat": "dsports"},

    # Argentina y Sudamérica
    "tyc": {"slug": "tycsports", "name": "TyC Sports HD", "cat": "latam"},
    "tycsports": {"slug": "tycsports", "name": "TyC Sports HD", "cat": "latam"},
    "tntsports": {"slug": "tntsports", "name": "TNT Sports HD (Argentina)", "cat": "latam"},
    "tntsportschile": {"slug": "tntsportschile", "name": "TNT Sports Chile HD", "cat": "latam"},
    "golperu": {"slug": "golperu", "name": "Gol Perú HD", "cat": "latam"},
    "winplus": {"slug": "winplus", "name": "Win Sports + HD", "cat": "latam"},
    "winsports": {"slug": "winplus", "name": "Win Sports + HD", "cat": "latam"},
    "telefe": {"slug": "telefe", "name": "Telefe HD", "cat": "latam"},
    "caracol": {"slug": "caracol", "name": "Caracol TV HD", "cat": "latam"},
    "americatv": {"slug": "americatv", "name": "América TV HD", "cat": "latam"},

    # MAX Suite (Champions League)
    "max1": {"slug": "max1", "name": "MAX 1 HD (Champions)", "cat": "max"},
    "max2": {"slug": "max2", "name": "MAX 2 HD (Champions)", "cat": "max"},
    "max3": {"slug": "max3", "name": "MAX 3 HD (Champions)", "cat": "max"},

    # ViX+ / TUDN
    "tudn": {"slug": "tudn", "name": "TUDN Deportes", "cat": "vix"},
    "tudn_mx": {"slug": "tudn_mx", "name": "TUDN México HD", "cat": "vix"},
    "vix1": {"slug": "vix1", "name": "ViX+ Deportes 1 HD", "cat": "vix"},
    "vix2": {"slug": "vix2", "name": "ViX+ Deportes 2 HD", "cat": "vix"},

    # Internacionales / España
    "laligatv": {"slug": "laligatv", "name": "LaLiga TV Bar", "cat": "europe"},
    "dazn1": {"slug": "dazn1", "name": "DAZN 1 España", "cat": "europe"},
    "dazn2": {"slug": "dazn2", "name": "DAZN 2 España", "cat": "europe"},
    "movistarliga": {"slug": "movistarliga", "name": "Movistar LaLiga HD", "cat": "europe"},
    "movistar-laliga": {"slug": "movistarliga", "name": "Movistar LaLiga HD", "cat": "europe"},
    "canal5": {"slug": "canal5", "name": "Canal 5 MX", "cat": "latam"},
    "azteca7": {"slug": "azteca7", "name": "Azteca 7 MX", "cat": "latam"},
    "univision": {"slug": "univision", "name": "Univisión USA", "cat": "vix"},
    "universo": {"slug": "universo", "name": "Universo USA", "cat": "vix"},
}

# Inyectar señales Disney+ Eventos (1 al 15)
for i in range(1, 16):
    slug_canonical = f"disney{i}"
    name_d = f"Disney+ {i} HD"
    TR_CHANNELS[f"disney-{i}"] = {"slug": slug_canonical, "name": name_d, "cat": "disney"}
    TR_CHANNELS[f"disney{i}"] = {"slug": slug_canonical, "name": name_d, "cat": "disney"}

# Keep the configured directory aligned with the currently supported provider.
for _slug, _name in CHANNEL_NAMES.items():
    TR_CHANNELS[_slug] = {"slug": _slug, "name": _name, "cat": "directorio"}
TR_CHANNELS["espn1"] = TR_CHANNELS["espn"]
TR_CHANNELS["winplus"] = TR_CHANNELS["winsports2"]

def clean_arg(val):
    if not val:
        return ""
    return str(val).strip().strip("<>").strip('"').strip("'").strip()

def resolve_channel_input(raw_input):
    clean = clean_arg(raw_input).lower()

    # Si viene con prefijo sintético de evento (ej: ev40363_4_espn-movil -> espn-movil)
    m_ev = re.match(r'^ev\d+_\d+_(.*)', clean)
    if m_ev:
        clean = m_ev.group(1)

    clean_no_space = clean.replace(" ", "").replace("_", "").replace("-", "")

    if clean in TR_CHANNELS:
        ch = TR_CHANNELS[clean]
        return ch["slug"], ch["name"]
    if clean_no_space in TR_CHANNELS:
        ch = TR_CHANNELS[clean_no_space]
        return ch["slug"], ch["name"]

    # MAX regex (ej. "max 1", "max 2", "max 3")
    m_max = re.search(r'max.*?(\d+)', clean)
    if m_max:
        num = m_max.group(1)
        return f"max{num}", f"MAX {num} HD"

    # Disney+ regex (ej. "disney 2", "disney-7", "disney 10")
    m_disney = re.search(r'disney.*?(\d+)', clean)
    if m_disney:
        num = int(m_disney.group(1))
        return f"disney{num}", f"Disney+ {num} HD"

    # ESPN regex
    if "espn" in clean:
        if "prem" in clean:
            return "espnpremium", "ESPN Premium HD (Argentina)"
        if "mx" in clean:
            m_mx = re.search(r'espn.*?(\d+).*?mx', clean) or re.search(r'espnmx.*?(\d+)', clean)
            if m_mx:
                return f"espn{m_mx.group(1)}mx", f"ESPN {m_mx.group(1)} México HD"
            return "espnmx", "ESPN México HD"
        if "extra" in clean:
            return "espnextra", "ESPN Extra HD"
        if "plus" in clean:
            return "espnplus", "ESPN Plus HD"
        m_num = re.search(r'espn.*?(\d+)', clean)
        if m_num:
            n = m_num.group(1)
            if n == "1":
                return "espn", "ESPN 1 HD (Sur/Argentina)"
            if n in ["2", "3", "4", "5", "6", "7"]:
                return f"espn{n}", f"ESPN {n} HD"
        return "espn", "ESPN 1 HD (Sur/Argentina)"

    # Fox Sports regex
    if "fox" in clean:
        if "prem" in clean:
            return "foxsportspremium", "Fox Sports Premium HD"
        if "mx" in clean:
            m_fmx = re.search(r'fox.*?(\d+).*?mx', clean)
            if m_fmx:
                return f"foxsports{m_fmx.group(1)}mx", f"Fox Sports {m_fmx.group(1)} MX"
            return "foxsportsmx", "Fox Sports MX"
        if "ar" in clean:
            if "2" in clean:
                return "fox2ar", "Fox Sports 2 Argentina"
            return "fox1ar", "Fox Sports 1 Argentina"
        m_fnum = re.search(r'fox.*?(\d+)', clean)
        if m_fnum:
            fn = m_fnum.group(1)
            if fn == "1":
                return "foxsports", "Fox Sports 1 HD"
            if fn == "2":
                return "foxsports2", "Fox Sports 2 HD"
            if fn == "3":
                return "foxsports3", "Fox Sports 3 HD"
        return "foxsports", "Fox Sports 1 HD"

    # DIRECTV Sports / DSports
    if "dsport" in clean or "directv" in clean or "dtv" in clean:
        if "event" in clean:
            return "dsports_eventos", "DSports Eventos HD"
        if "plus" in clean or "+" in clean or "3" in clean:
            return "dsportsplus", "DSports+ HD"
        if "2" in clean:
            return "dsports2", "DSports 2 HD"
        return "dsports", "DSports 1 HD"

    # ViX regex
    if "vix" in clean:
        m_vix = re.search(r'vix.*?(\d+)', clean)
        if m_vix:
            return f"vix{m_vix.group(1)}", f"ViX+ Deportes {m_vix.group(1)} HD"
        return "vix1", "ViX+ Deportes 1 HD"

    # TyC Sports
    if "tyc" in clean:
        return "tycsports", "TyC Sports HD"

    # TNT Sports
    if "tnt" in clean:
        if "chile" in clean:
            return "tntsportschile", "TNT Sports Chile HD"
        return "tntsports", "TNT Sports HD (Argentina)"

    # Win Sports
    if "win" in clean:
        return "winplus", "Win Sports + HD"

    # TUDN
    if "tudn" in clean:
        if "mx" in clean:
            return "tudn_mx", "TUDN México HD"
        return "tudn", "TUDN Deportes"

    # Canales de aire / Latam
    if "telefe" in clean:
        return "telefe", "Telefe HD"
    if "caracol" in clean:
        return "caracol", "Caracol TV HD"
    if "america" in clean:
        return "americatv", "América TV HD"
    if "canal5" in clean or "canal 5" in clean:
        return "canal5", "Canal 5 MX"
    if "azteca" in clean:
        return "azteca7", "Azteca 7 MX"

    return clean.replace(" ", "-"), f"Canal ElCiro [{clean}]"

# ==============================================================================
# RESOLVEDOR UNIVERSAL DE STREAM DE TARJETA ROJA (100% NATIVO Y ELÁSTICO)
# ==============================================================================
def decode_streamxhd(html_content):
    try:
        m_sort = re.search(r'([A-Za-z0-9_]+)\.sort\(\(a,b\)\s*=>\s*a\[0\]\s*-\s*b\[0\]\)', html_content)
        if not m_sort:
            return None
        arr_name = m_sort.group(1)
        m_arr = re.search(rf'{arr_name}\s*=\s*(\[\[.*?\]\]);', html_content, re.DOTALL)
        if not m_arr:
            return None
        items = re.findall(r'\[(\d+)\s*,\s*["\']([^"\']+)["\']\]', m_arr.group(1))
        if not items:
            return None
        parsed_items = [(int(idx), b64) for idx, b64 in items]
        parsed_items.sort(key=lambda x: x[0])

        funcs = re.findall(r'function\s+([A-Za-z0-9_]+)\s*\(\)\s*\{\s*return\s+(\d+)\s*;\s*\}', html_content)
        if len(funcs) < 2:
            return None
        k = int(funcs[0][1]) + int(funcs[1][1])

        chars = []
        for idx, b64 in parsed_items:
            try:
                dec = base64.b64decode(b64).decode('utf-8', errors='ignore')
                digits = re.sub(r'\D', '', dec)
                if digits:
                    chars.append(chr(int(digits) - k))
            except Exception:
                pass
        res = "".join(chars)
        return res if res.startswith("http") else None
    except Exception:
        return None

def public_source_label(value):
    return "fuente-personalizada" if str(value).startswith(("http://", "https://")) else str(value)


class SourceUnavailableError(RuntimeError):
    """Safe diagnostic containing source status codes, never keys or signed URLs."""


def _fetch_single_tr_slug(clean_slug):
    failures = []
    # 1. Probar en la18hd.su con headers del navegador y extractor HLS universal
    try:
        from channel_source import resolve_la18hd
        st, u, msg = resolve_la18hd(clean_slug)
        if st:
            return st, u, msg
        failures.append(f"la18hd: {msg}")
    except Exception as e:
        failures.append(f"la18hd: {type(e).__name__}")

    # 2. Fallback a tarjetaroja.my si existiera
    page_url = f"https://tarjetaroja.my/stream/{clean_slug}"
    try:
        r_page = requests.get(page_url, headers=HEADERS_BASE, timeout=8)
        if r_page.status_code == 200:
            m_if = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r_page.text, re.IGNORECASE)
            if m_if:
                iframe_url = m_if.group(1)
                if iframe_url.startswith("//"):
                    iframe_url = "https:" + iframe_url

                h_if = dict(HEADERS_BASE)
                h_if["Referer"] = page_url
                r_if = requests.get(iframe_url, headers=h_if, timeout=8)
                if r_if.status_code == 200:
                    m_play = re.search(r'var\s+playbackURL\s*=\s*["\']([^"\']+)["\']', r_if.text)
                    if m_play:
                        stream_url = m_play.group(1).replace(r'\/', '/')
                        return stream_url, iframe_url, "OK (streamtp directo)"

                    dec_url = decode_streamxhd(r_if.text)
                    if dec_url:
                        return dec_url, iframe_url, "OK (streamxhd decodificado)"

                    m_src = re.search(r'(?:source|file)\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', r_if.text)
                    if m_src:
                        return m_src.group(1).replace(r'\/', '/'), iframe_url, "OK (source/file directo)"
                    failures.append("Fuente alternativa: el reproductor no contiene un enlace de video")
                else:
                    failures.append(f"Reproductor alternativo: HTTP {r_if.status_code}")
            else:
                failures.append("Fuente alternativa: la página no contiene un reproductor")
        else:
            failures.append(f"Fuente alternativa: HTTP {r_page.status_code}")
    except Exception as e:
        failures.append(f"Fuente alternativa: {type(e).__name__}")

    return None, None, "; ".join(failures)

def resolve_tarjetaroja_stream(channel_slug):
    clean_slug = channel_slug.strip().lower().replace("_", "-")

    # 1. Probar primero en tvf90.com (CDN ftlly.com - máxima compatibilidad en Railway / servidores nube)
    tv_url, tv_ref, tv_st = resolve_tvf90(clean_slug)
    if tv_url:
        return tv_url, tv_ref, tv_st

    td_url, td_ref, td_status = resolve_tarjeta_digital(clean_slug)
    if td_url:
        return td_url, td_ref, td_status

    registered = schedule.channel(channel_slug)
    if registered and channel_slug not in CHANNEL_PAGES:
        event_url, event_ref, event_status = resolve_player(registered["iframe"])
        if event_url:
            return event_url, event_ref, event_status
    new_url, new_ref, new_status = resolve_roja_source(clean_slug)
    if new_url:
        return new_url, new_ref, new_status
    
    url, ref, st = _fetch_single_tr_slug(clean_slug)
    if url:
        return url, ref, st

    if "-" in clean_slug:
        alt_slug = clean_slug.replace("-", "")
        url_alt, ref_alt, st_alt = _fetch_single_tr_slug(alt_slug)
        if url_alt:
            return url_alt, ref_alt, st_alt

    m_num = re.match(r'^([a-zA-Z]+)(\d+)$', clean_slug)
    if m_num:
        alt_slug2 = f"{m_num.group(1)}-{m_num.group(2)}"
        url_alt2, ref_alt2, st_alt2 = _fetch_single_tr_slug(alt_slug2)
        if url_alt2:
            return url_alt2, ref_alt2, st_alt2

    return None, None, f"{new_status}; {st}"

def resolve_stream_source(channel_input):
    clean_in = clean_arg(channel_input)

    if "tarjetadigital.club" in clean_in or "la18hd.su" in clean_in:
        from channel_source import resolve_tarjeta_digital
        td_url, td_ref, td_status = resolve_tarjeta_digital(clean_in)
        if td_url:
            headers_str = f"Referer: {td_ref}\r\nOrigin: https://la18hd.su\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            return td_url, headers_str, "Tarjeta Digital en vivo", "tarjeta-digital", True

    if clean_in.startswith("http://") or clean_in.startswith("https://"):
        headers_str = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
        return clean_in, headers_str, "Canal Personalizado", clean_in, True

    candidate_slug, candidate_name = resolve_channel_input(clean_in)
    if candidate_slug not in CHANNEL_PAGES and not schedule.channel(clean_in):
        try:
            schedule.get()
        except ScheduleUnavailable:
            pass
    registered = schedule.channel(clean_in) or schedule.channel(candidate_slug)
    if registered:
        resolved_slug, channel_name = registered["slug"], registered["name"]
    else:
        resolved_slug, channel_name = candidate_slug, candidate_name

    stream_url, iframe_ref, status_info = resolve_tarjetaroja_stream(resolved_slug)
    if stream_url:
        origin_line = ""
        if (iframe_ref and "tvf90" in str(iframe_ref)) or "ftlly" in str(stream_url):
            origin_line = "Origin: https://tvf90.com\r\n"
        elif (iframe_ref and "la18hd" in str(iframe_ref)) or "fubo" in str(stream_url) or "la18hd" in str(stream_url):
            origin_line = "Origin: https://la18hd.su\r\n"
        ref_header = f"Referer: {iframe_ref}\r\n" if iframe_ref else "Referer: https://tvf90.com/\r\n"
        headers_str = f"{ref_header}{origin_line}User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36\r\n"
        return stream_url, headers_str, channel_name, resolved_slug, True

    raise SourceUnavailableError(status_info or "El origen no entregó un enlace de video")

# ==============================================================================
# MOTOR DE TRANSMISIÓN ULTRA-FLUIDO (REAL-TIME / ZERO B-FRAMES / SINCRONIZACIÓN PERFECTA)
# ==============================================================================
def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    """Launch the shared, bounded 720p profile with machine-readable progress."""
    log_name = f"stream_{stream_id}_{uuid.uuid4().hex[:12]}.log"
    log_file = os.path.join("/tmp", log_name) if os.name != "nt" else log_name
    return launch(source_url, headers, destination, log_file)

# ==============================================================================
# GESTIÓN MULTI-PANTALLA ILIMITADA (1, 2, 3, 4, 5, ...)
# ==============================================================================
def start_single_stream(channel_input, stream_key, chat_id, requested_slot=None):
    clean_channel_input = clean_arg(channel_input)
    clean_key = clean_arg(stream_key)

    try:
        source_url, headers_str, channel_name, resolved_slug, ok = resolve_stream_source(clean_channel_input)
    except SourceUnavailableError as exc:
        return False, (
            f"❌ <b>No se pudo obtener la señal de {html.escape(clean_channel_input)}.</b>\n\n"
            f"<b>Diagnóstico del origen:</b> {html.escape(str(exc))}\n\n"
            "La transmisión no llegó a iniciarse. Un HTTP 403 indica que el servidor de origen "
            "rechazó la solicitud; no es un error del logo ni del codificador.\n\n"
            "Puedes probar un enlace directo de una fuente que tengas autorizada:\n"
            "<code>/stream URL_DIRECTA_M3U8_O_TS CLAVE_DE_TELEGRAM</code>"
        )
    if not ok or not source_url:
        return False, (
            f"❌ No se pudo conectar a la señal de <b>{html.escape(clean_channel_input)}</b> en ElCiro.\n\n"
            "💡 Usa <code>/partidos</code> para ver los eventos de hoy o <code>/canales</code> para el directorio completo."
        )

    destination = clean_key if clean_key.startswith(("rtmp://", "rtmps://")) else f"rtmps://dc4-1.rtmp.t.me/s/{clean_key}"

    retired = []
    with stream_lock:
        target_slot = None
        if requested_slot and str(requested_slot).isdigit() and int(requested_slot) >= 1:
            target_slot = str(int(requested_slot))
        if not target_slot:
            target_slot = next((sid for sid, info in active_streams.items()
                                if info.get("destination") == destination), None)
        if not target_slot:
            cand = 1
            while str(cand) in active_streams:
                cand += 1
            target_slot = str(cand)
        # Publishing twice to the same Telegram destination can disconnect a stream.
        for sid, info in list(active_streams.items()):
            if sid == target_slot or info.get("destination") == destination:
                info["auto_restart"] = False
                retired.append(info)
                del active_streams[sid]

        reservation = {
            "channel_input": clean_channel_input,
            "resolved_slug": resolved_slug,
            "channel_name": channel_name,
            "key": clean_key,
            "destination": destination,
            "source_url": source_url,
            "headers_str": headers_str,
            "process": None,
            "log_handle": None,
            "log_file": None,
            "chat_id": chat_id,
            "start_time": time.time(),
            "auto_restart": True,
            "restarts": 0,
            "launching": True,
            "total_restarts": 0,
            "status": "starting"
        }

        active_streams[target_slot] = reservation

    for old_info in retired:
        stop_process(old_info.get("process"))
        if old_info.get("log_handle"):
            old_info["log_handle"].close()

    try:
        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers_str, destination, target_slot)
    except Exception as exc:
        with stream_lock:
            if active_streams.get(target_slot) is reservation:
                del active_streams[target_slot]
        return False, "❌ No se pudo iniciar FFmpeg (" + type(exc).__name__ + "). Comprueba la instalación y los permisos."

    with stream_lock:
        if active_streams.get(target_slot) is reservation and reservation.get("auto_restart"):
            reservation.update(process=proc, log_handle=out_f, log_file=log_file, launching=False)
        else:
            stop_process(proc)
            out_f.close()
            return False, "ℹ️ Solicitud cancelada o reemplazada."

    time.sleep(3)
    state, reason = health(proc)
    if state == "failed":
        logs = safe_tail(log_file, (clean_key,))
        with stream_lock:
            if active_streams.get(target_slot) is not reservation:
                return False, "ℹ️ Solicitud cancelada o reemplazada."
            reservation["last_error"] = reason
            if explicit_rejection(logs):
                out_f.close()
                reservation["auto_restart"] = False
                reservation["status"] = "rejected"
                if "403" in logs.lower():
                    return False, (
                        "⚠️ <b>El servidor de origen rechazó el acceso (HTTP 403 Forbidden).</b>\n\n"
                        "💡 <b>Causa:</b> La red emisora o Cloudflare bloqueó la IP de este servidor (común en servidores de nube como Railway/AWS).\n\n"
                        "👉 <b>Solución:</b> Ejecuta el bot en tu PC local usando <code>ejecutar_bot_en_pc.bat</code>, donde tu conexión de hogar no está bloqueada por el origen."
                    )
                return False, (
                    "⚠️ <b>El servidor rechazó el acceso.</b> Se pausaron los reintentos.\n"
                    "Revisa el aviso de Telegram, la sala, la URL del servidor y la clave. "
                    "Este registro no permite determinar si existe una restricción.\n"
                    f"<code>{html.escape(logs)}</code>"
                )
        return True, (
            f"🔄 <b>Pantalla #{target_slot}: recuperación automática pendiente.</b>\n"
            f"{html.escape(reason)}. Usa <code>/status</code> para consultar el diagnóstico.\n"
            f"<code>{html.escape(logs)}</code>"
        )

    active_count = len(active_streams)
    return True, (
        f"📡 <b>CODIFICADOR INICIADO (PANTALLA #{target_slot})</b>\n\n"
        f"📺 <b>Canal:</b> {html.escape(channel_name)} [<code>{html.escape(public_source_label(resolved_slug))}</code>]\n"
        f"⚡ <b>Rendimiento:</b> 720p / 30 FPS / H.264 y AAC / monitor de avance\n"
        f"🌐 <b>Servidor:</b> ElCiro Nativo\n"
        f"🩺 <b>Diagnóstico:</b> <code>/status</code>\n"
        f"📡 <b>Pantallas supervisadas:</b> {active_count}\n"
        f"⏱️ <b>Sincronización Audio/Video:</b> Corrección automática de audio\n\n"
        f"🛑 <i>Para detener esta pantalla:</i> <code>/stop {target_slot}</code>\n"
        f"🛑 <i>Para detener todas las pantallas:</i> <code>/stopall</code>"
    )


def stop_single_stream(query=None):
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay ninguna transmisión activa en este momento."

        if not query or not str(query).strip():
            if len(active_streams) == 1:
                target_sid = list(active_streams.keys())[0]
            else:
                msg_choices = f"⚠️ <b>Tienes {len(active_streams)} transmisiones activas. ¿Cuál deseas detener?</b>\n\n"
                for s, inf in sorted(active_streams.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                    msg_choices += f"• 📺 <b>Pantalla #{s}:</b> {html.escape(inf['channel_name'])}\n  👉 Detener: <code>/stop {s}</code>\n\n"
                msg_choices += "🛑 <b>Para detener todas a la vez:</b> <code>/stopall</code>"
                return False, msg_choices
        else:
            q_raw = clean_arg(str(query)).lower()
            q_clean = q_raw.lstrip("#").strip()

            target_sid = None

            if q_clean in active_streams:
                target_sid = q_clean

            if not target_sid:
                for sid, info in active_streams.items():
                    c_name = info.get("channel_name", "").lower()
                    c_slug = info.get("resolved_slug", "").lower()
                    c_in = info.get("channel_input", "").lower()
                    if q_raw in c_name or q_raw in c_slug or q_raw in c_in or q_clean in c_name or q_clean in c_slug:
                        target_sid = sid
                        break

            if not target_sid:
                for sid, info in active_streams.items():
                    if q_raw in info.get("key", "").lower():
                        target_sid = sid
                        break

            if not target_sid or target_sid not in active_streams:
                msg_not_found = f"⚠️ <b>No se encontró ninguna transmisión activa que coincida con '<code>{html.escape(str(query))}</code>'.</b>\n\n"
                msg_not_found += "📺 <b>Pantallas activas ahora mismo:</b>\n"
                for s, inf in sorted(active_streams.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                    msg_not_found += f"• 📺 <b>Pantalla #{s}:</b> {html.escape(inf['channel_name'])}\n  👉 Detener: <code>/stop {s}</code>\n"
                msg_not_found += "\n🛑 <i>Para detener todas:</i> <code>/stopall</code>"
                return False, msg_not_found

        info = active_streams[target_sid]
        info["auto_restart"] = False
        proc = info.get("process")
        if proc:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        try:
            if info.get("log_handle"):
                info["log_handle"].close()
        except Exception:
            pass

        ch_name = info["channel_name"]
        del active_streams[target_sid]

        res = f"🛑 <b>Transmisión de Pantalla #{target_sid} ({html.escape(ch_name)}) detenida con éxito.</b>"
        if active_streams:
            res += "\n\n📡 <b>Pantallas que siguen transmitiendo:</b>\n"
            for s, inf in sorted(active_streams.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                res += f"• 📺 <b>Pantalla #{s}:</b> {html.escape(inf['channel_name'])} (<code>/stop {s}</code>)\n"
            res += "\n💡 <i>Para detener todas usa: <code>/stopall</code></i>"
        else:
            res += "\n\n✅ <i>Todas las pantallas han sido liberadas (0 activas).</i>"

        return True, res

def stop_all_streams():
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay transmisiones activas para detener."

        count = len(active_streams)
        stopped_list = []
        for sid, info in list(active_streams.items()):
            info["auto_restart"] = False
            proc = info.get("process")
            if proc:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            try:
                if info.get("log_handle"):
                    info["log_handle"].close()
            except Exception:
                pass
            stopped_list.append(f"Pantalla #{sid}: {info.get('channel_name', 'Canal')}")
            del active_streams[sid]

        details = "\n".join([f"• 🛑 <b>{html.escape(item)}</b>" for item in stopped_list])
        return True, (
            f"🛑 <b>Se han detenido todas las transmisiones activas ({count}):</b>\n\n"
            f"{details}\n\n"
            f"✅ <i>Todas las pantallas han sido liberadas (0 activas).</i>"
        )

# ==============================================================================
# SUPERVISOR DE PROGRESO Y RECUPERACIÓN DE FALLOS TÉCNICOS
# ==============================================================================
def recover_stream(sid, info):
    """Resolve and relaunch outside the global lock so /stop remains responsive."""
    proc = None
    log_handle = None
    try:
        stop_process(info.get("process"))
        if info.get("log_handle"):
            info["log_handle"].close()
        with stream_lock:
            if active_streams.get(sid) is not info or not info.get("auto_restart"):
                return
        slug = info.get("resolved_slug") or info["channel_input"]
        source, headers, name, resolved_slug, ok = resolve_stream_source(slug)
        if not ok or not source:
            raise RuntimeError("La fuente no está disponible; se volverá a intentar")
        with stream_lock:
            if active_streams.get(sid) is not info or not info.get("auto_restart"):
                return
        proc, log_handle, log_file = launch_ffmpeg_process(source, headers, info["destination"], sid)
        with stream_lock:
            if active_streams.get(sid) is info and info.get("auto_restart"):
                info.update(process=proc, log_handle=log_handle, log_file=log_file,
                            source_url=source, headers_str=headers, status="starting")
                proc = None  # Ownership transferred to the active slot.
                log_handle = None
    except SourceUnavailableError as exc:
        with stream_lock:
            if active_streams.get(sid) is info:
                info["last_error"] = str(exc)
                info["status"] = "reconnecting"
    except Exception as exc:
        # Exception strings may contain credentials or signed source URLs.
        with stream_lock:
            if active_streams.get(sid) is info:
                info["last_error"] = "No se pudo preparar la señal (" + type(exc).__name__ + ")"
                info["status"] = "reconnecting"
    finally:
        if proc is not None:
            stop_process(proc)
        if log_handle is not None:
            log_handle.close()
        with stream_lock:
            if active_streams.get(sid) is info:
                info["recovering"] = False
                info["next_retry"] = time.monotonic() + retry_delay(info.get("restarts", 1))


def supervise_once():
    now = time.monotonic()
    with stream_lock:
        for sid, info in list(active_streams.items()):
            if not info.get("auto_restart") or info.get("launching") or info.get("recovering"):
                continue
            proc = info.get("process")
            state, reason = health(proc, now)
            info["status"] = state
            if state in ("starting", "running"):
                if state == "running" and now - proc.stream_progress.snapshot()["started"] > 120:
                    info["restarts"] = 0
                continue
            info["last_error"] = reason
            logs = safe_tail(info.get("log_file"), (info.get("key"),))
            if state == "failed" and explicit_rejection(logs):
                if info.get("log_handle"):
                    info["log_handle"].close()
                info["auto_restart"] = False
                info["status"] = "rejected"
                if "403" in logs.lower():
                    info["last_error"] = "Origen rechazó el acceso (HTTP 403 Forbidden). IP de hosting bloqueada por el CDN."
                else:
                    info["last_error"] = "Acceso rechazado explícitamente. Revisa el aviso, la sala y las credenciales antes de iniciar otra vez."
                continue
            if now < info.get("next_retry", 0):
                continue
            info["restarts"] = info.get("restarts", 0) + 1
            info["total_restarts"] = info.get("total_restarts", 0) + 1
            info["status"] = "reconnecting"
            info["recovering"] = True
            threading.Thread(target=recover_stream, args=(sid, info), daemon=True).start()


def supervisor_thread():
    while True:
        time.sleep(3)
        try:
            supervise_once()
        except Exception as exc:
            print("[Supervisor] Error de monitorización:", type(exc).__name__)


# ==============================================================================
# AGENDA DINÁMICA DE PARTIDOS (100% TARJETA ROJA DIRECTA)
# ==============================================================================
def fetch_tarjetaroja_schedule():
    return schedule.get()


def get_live_matches_agenda(curr_key=None):
    try:
        events = fetch_tarjetaroja_schedule()
        return agenda_messages(events, schedule.stale)
    except ScheduleUnavailable as exc:
        return ["⚠️ <b>La agenda no está disponible.</b> " + html.escape(str(exc)) +
                "\nNo se mostrarán partidos de otro día. Puedes consultar <code>/canales</code> o volver a intentar."]


def get_live_now_agenda(curr_key=None):
    try:
        events = fetch_tarjetaroja_schedule()
        return live_now_messages(events)
    except ScheduleUnavailable as exc:
        return ["⚠️ <b>La agenda no está disponible:</b> " + html.escape(str(exc))]


def channel_catalog():
    catalog = {slug: dict(name=name, slug=slug, group="Directorio del proveedor")
               for slug, name in CHANNEL_NAMES.items()}
    try:
        events = fetch_tarjetaroja_schedule()
    except ScheduleUnavailable:
        events = []
    for event in events:
        for channel in event["channels"]:
            catalog.setdefault(channel["slug"], dict(channel, group="Señales de la agenda de hoy"))
    for info in TR_CHANNELS.values():
        catalog.setdefault(info["slug"], dict(info, group="Otros configurados; sin comprobar"))
    return sorted(catalog.values(), key=lambda c: (c["group"], fold(c["name"])))


def get_sports_menu_messages(curr_key=None, query=""):
    channels = channel_catalog()
    if query:
        channels = [ch for ch in channels if fold(query) in fold(ch["name"] + " " + ch["slug"])]
    blocks = [f"📺 <b>CANALES EL CIRO · {len(channels)} señales</b>\n"
              "La lista no garantiza disponibilidad. Los comandos usan tu clave guardada; no la publican."]
    group = None
    for channel in channels:
        if channel["group"] != group:
            group = channel["group"]
            blocks.append("<b>" + html.escape(group) + "</b>")
        blocks.append(f"📺 {html.escape(channel['name'][:100])} · <code>/stream {html.escape(channel['slug'])}</code>")
    if not channels:
        blocks.append("No hay canales que coincidan con esa búsqueda.")
    messages = pack_blocks(blocks)
    return [f"📄 Canales {i}/{len(messages)}\n\n{message}" for i, message in enumerate(messages, 1)]


def search_tarjetaroja(query, curr_key=None):
    query = query.strip()[:200]
    q = fold(query)
    try:
        events = fetch_tarjetaroja_schedule()
        matches = [ev for ev in events if q in fold(ev["match"] + " " + ev["competition"])]
        notice = ""
    except ScheduleUnavailable:
        matches = []
        notice = "⚠️ La agenda no está disponible; se muestran coincidencias del directorio."
    channels = [ch for ch in channel_catalog() if q in fold(ch["name"] + " " + ch["slug"])]
    blocks = [f"🔎 <b>BÚSQUEDA: {html.escape(query)}</b> · {len(matches)} eventos / {len(channels)} canales"]
    if notice:
        blocks.append(notice)
    blocks.extend(event_blocks(matches))
    blocks.extend(f"📺 {html.escape(ch['name'][:100])} · <code>/stream {html.escape(ch['slug'])}</code>" for ch in channels)
    if not matches and not channels:
        blocks.append("No se encontraron coincidencias. Prueba /partidos o /canales.")
    return "\n\n".join(blocks)


def get_help_text():
    title = "EL CIRO TV" if "elciro" in BOT_USERNAME.lower() else "TV ELAS"
    return (
        f"⚽ <b>{title} · TRANSMISIÓN TELEGRAM (100% LIMPIA)</b>\n"
        "<i>Transmisión oficial en vivo 100% limpia sin filtros ni publicidad externa</i>\n\n"
        "<code>/envivo</code> · Partidos en juego AHORA MISMO (hora de Venezuela).\n"
        "<code>/partidos [N]</code> · Cartelera completa de hoy (o por página: /partidos 2).\n"
        "<code>/canales</code> · Directorio de canales (Tarjeta Digital, ESPN, Fox, MAX, ViX, etc.).\n"
        "<code>/canales espn</code> · Filtrar canales por nombre.\n"
        "<code>/buscar equipo o liga</code> · Buscar partidos o señales en vivo.\n"
        "<code>/stream CANAL [CLAVE]</code> · Transmitir señal limpia (ej: <code>/stream espn TU_CLAVE</code>).\n"
        "<code>/c1 CANAL</code> · Transmitir en Pantalla 1 (ej: <code>/c1 espnmx</code>).\n"
        "<code>/c2 CANAL</code> · Transmitir en Pantalla 2 (ej: <code>/c2 foxsportsmx</code>).\n"
        "<code>/status</code> · Estado técnico y tiempo de emisiones activas.\n"
        "<code>/stop 1</code> · Detener pantalla 1.\n"
        "<code>/stopall</code> · Detener todas las pantallas activas.\n"
        "<code>/key NUEVA_CLAVE</code> · Configurar Stream Key de Telegram.\n"
        "<code>/id</code> · Consultar tu ID de Telegram.\n"
        "<code>/ayuda</code> · Mostrar este menú de ayuda.\n\n"
        "Alias: /agenda, /hoy, /deportes, /menu."
    )
BOT_COMMANDS = [
    ("partidos", "Agenda completa de hoy · hora de Venezuela"), ("canales", "Canales y señales publicadas"),
    ("buscar", "Buscar equipos, ligas o canales"), ("espn", "Canales ESPN"),
    ("stream", "Iniciar transmisión"), ("status", "Estado de transmisiones"),
    ("stop", "Detener una pantalla"), ("stopall", "Detener todas las pantallas"),
    ("key", "Configurar clave de emisión"), ("id", "Consultar tu identificador"),
    ("ayuda", "Ver todos los comandos"),
]


def send_msg(chat_id, text, parse_mode="HTML"):
    success = True
    for part, mode in telegram_parts(str(text)):
        payload = {"chat_id": chat_id, "text": part, "disable_web_page_preview": True}
        if mode and parse_mode:
            payload["parse_mode"] = mode
        for attempt in range(3):
            try:
                response = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=12)
                data = response.json()
                if response.status_code == 429 and attempt < 2:
                    time.sleep(max(1, int(data.get("parameters", {}).get("retry_after", 2))))
                    continue
                if not data.get("ok"):
                    print("[Telegram] Mensaje rechazado. HTTP:", response.status_code)
                    success = False
                break
            except (requests.RequestException, ValueError, TypeError) as exc:
                print("[Telegram] Error enviando mensaje:", type(exc).__name__)
                success = False
                break
    return success


def handle_message(msg):
    global CONFIG
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = normalize_command(msg.get("text", ""), BOT_USERNAME)
    command = text.split(maxsplit=1)[0] if text else ""

    if not chat_id or not text:
        return

    try:
        if command in ("/id", "/myid", "/mi_id"):
            send_msg(
                chat_id, 
                f"👤 <b>Tu ID de Telegram:</b> <code>{user_id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
                f"🛡️ <i>Copia tu ID numérico y colócalo en la variable <code>ADMIN_USER_IDS</code> de Railway para proteger tu bot de transmisiones no autorizadas.</i>"
            )
            return

        admin_commands = ["/stream", "/c1", "/c2", "/c3", "/c4", "/c5", "/stop", "/stopall", "/stoppal", "/detener", "/key", "/delay", "/pausar"]
        if command in admin_commands + ["/pause", "/stopal", "/stoppall", "/stop_all"]:
            if ADMIN_USER_IDS and str(user_id) not in ADMIN_USER_IDS:
                send_msg(chat_id, "⛔ <b>Acceso denegado:</b> Solo el administrador autorizado puede iniciar transmisiones o cambiar configuraciones.")
                return

        curr_key = CONFIG.get("stream_key", "3936015063:nG8N_no46UfNuA6jXewiag")

        if command in ("/start", "/ayuda", "/help", "/comandos", "/inicio"):
            send_msg(chat_id, get_help_text())

        elif command in ("/buscar", "/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, "Uso: <code>/buscar equipo, liga o canal</code>")
                return
            send_msg(chat_id, search_tarjetaroja(parts[1], curr_key))

        elif command in ("/canales", "/deportes", "/menu", "/espn"):
            parts = text.split(maxsplit=1)
            query = "espn" if command == "/espn" else (parts[1] if len(parts) > 1 else "")
            for message in get_sports_menu_messages(curr_key, query):
                send_msg(chat_id, message)

        elif command in ("/partidos", "/partido", "/agenda", "/hoy", "/juegos", "/cartelera"):
            parts = text.split()
            page_req = None
            if len(parts) > 1 and parts[1].isdigit():
                page_req = int(parts[1])

            agenda_msgs = get_live_matches_agenda(curr_key)
            if not agenda_msgs:
                send_msg(chat_id, "ℹ️ No hay partidos publicados para hoy en la cartelera.")
                return

            if page_req and 1 <= page_req <= len(agenda_msgs):
                send_msg(chat_id, agenda_msgs[page_req - 1])
            else:
                send_msg(chat_id, f"⏳ <b>Cargando la cartelera de hoy ({len(schedule.events)} partidos en {len(agenda_msgs)} partes)...</b>")
                for idx, message in enumerate(agenda_msgs):
                    send_msg(chat_id, message)
                    if idx < len(agenda_msgs) - 1:
                        time.sleep(1.2)

        elif command in ("/envivo", "/live", "/ahora"):
            send_msg(chat_id, "⏳ <b>Buscando partidos en juego en este momento...</b>")
            for idx, message in enumerate(get_live_now_agenda(curr_key)):
                send_msg(chat_id, message)
                time.sleep(0.8)

        elif (command.startswith("/c") and len(command) == 3 and command[2].isdigit()):
            slot = command[2]
            tokens = text.split()[1:]
            if not tokens:
                send_msg(chat_id, f"⚠️ <b>Uso:</b> <code>{command} &lt;CANAL o URL&gt;</code>\nEjemplo: <code>{command} espnmx</code> o <code>{command} https://tarjetadigital.club/en-vivo/espn-1</code>")
                return
            ch_input = " ".join(tokens).strip()
            send_msg(chat_id, f"🔄 <b>Preparando {html.escape(public_source_label(ch_input)[:200])} en Pantalla #{slot}...</b>")
            ok, response_msg = start_single_stream(ch_input, curr_key, chat_id, requested_slot=slot)
            send_msg(chat_id, response_msg)

        elif command == "/stream":
            tokens = text.split()[1:]
            if not tokens:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL&gt; [PANTALLA] [STREAM_KEY]</code>\nEjemplo: <code>/stream espn</code> o <code>/stream 1 espn</code> o <code>/stream disney-7 2</code>")
                return

            requested_slot = None
            if tokens and tokens[0].isdigit() and len(tokens) > 1:
                requested_slot = tokens[0]
                tokens = tokens[1:]

            last_token = tokens[-1].strip().strip("<>").strip('"').strip("'")
            is_stream_key = False
            if last_token.startswith(("rtmp://", "rtmps://")):
                is_stream_key = True
            elif not last_token.startswith(("http://", "https://")) and ":" in last_token and len(last_token) >= 12:
                is_stream_key = True
            elif not last_token.startswith(("http://", "https://")) and len(last_token) >= 20 and not any(kw in last_token.lower() for kw in ["espn", "fox", "sport", "deporte", "campeon", "star", "disney", "vix", "fanatiz", "max", "apple"]):
                is_stream_key = True

            if is_stream_key and len(tokens) > 1:
                s_key = last_token
                tokens = tokens[:-1]
            elif is_stream_key and len(tokens) == 1:
                s_key = last_token
                tokens = ["espn"]
            else:
                s_key = curr_key

            if not requested_slot and tokens and len(tokens) > 1 and tokens[-1].isdigit():
                requested_slot = tokens[-1]
                tokens = tokens[:-1]

            ch_input = " ".join(tokens).strip()

            slot_notice = f" en Pantalla #{requested_slot}" if requested_slot else ""
            send_msg(chat_id, f"🔄 <b>Preparando {html.escape(public_source_label(ch_input)[:200])}{slot_notice}...</b>")
            ok, response_msg = start_single_stream(ch_input, s_key, chat_id, requested_slot=requested_slot)
            send_msg(chat_id, response_msg)

        elif command in ("/status", "/logs"):
            with stream_lock:
                if not active_streams:
                    send_msg(chat_id, "ℹ️ No hay ninguna transmisión activa actualmente.")
                    return

                msg_status = f"📊 <b>ESTADO DE TRANSMISIONES EN VIVO ({len(active_streams)} activas):</b>\n\n"
                for sid, info in sorted(active_streams.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                    elapsed = int(time.time() - info["start_time"])
                    mins = elapsed // 60
                    secs = elapsed % 60
                    proc = info.get("process")
                    if info.get("status") == "rejected":
                        proc_state = "⛔ ACCESO RECHAZADO; REINTENTOS PAUSADOS"
                    elif info.get("recovering") or proc is None or proc.poll() is not None:
                        proc_state = "🔄 RECONECTANDO" if info.get("auto_restart") else "🔴 DETENIDO"
                    else:
                        state, detail = health(proc)
                        proc_state = {"running": "🟢 VIDEO ENVIÁNDOSE", "starting": "🟡 INICIANDO",
                                      "stalled": "🟠 SIN AVANCE"}.get(state, state)
                    progress = proc.stream_progress.snapshot() if proc is not None else None
                    metrics = (f"{progress['frames']} frames / velocidad {html.escape(progress['speed'])}"
                               if progress else "Sin fotogramas confirmados")
                    last_log = safe_tail(info.get("log_file"), (info.get("key"),), limit=300)

                    msg_status += (
                        f"🔹 <b>Pantalla #{sid}:</b> {html.escape(info['channel_name'])} [<code>{html.escape(public_source_label(info['resolved_slug']))}</code>]\n"
                        f"• 🌐 <b>Estado:</b> {proc_state}\n"
                        f"• ⏱️ <b>Tiempo activo:</b> {mins}m {secs}s\n"
                        f"• 📈 <b>Salida:</b> {metrics}\n"
                        f"• 🔄 <b>Reintentos:</b> {info.get('total_restarts', 0)}\n"
                        f"• 🩺 <b>Último incidente:</b> {html.escape(info.get('last_error', 'Sin incidentes detectados'))}\n"
                        f"• 🛑 <b>Detener esta pantalla:</b> <code>/stop {sid}</code>\n"
                    )
                    if last_log:
                        msg_status += f"• 📋 <b>Último log FFmpeg:</b>\n<code>{html.escape(last_log)}</code>\n\n"
                    else:
                        msg_status += "\n"

                msg_status += "🛑 <i>Para detener todas las transmisiones a la vez:</i> <code>/stopall</code>"
                send_msg(chat_id, msg_status)

        elif command in ("/stopall", "/stoppal", "/stopal", "/stoppall", "/stop_all"):
            ok, response_msg = stop_all_streams()
            send_msg(chat_id, response_msg)

        elif command in ("/stop", "/detener", "/pausar", "/pause"):
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else None
            if arg and arg.lower() in ["all", "todas", "todo", "todos"]:
                ok, response_msg = stop_all_streams()
            else:
                ok, response_msg = stop_single_stream(arg)
            send_msg(chat_id, response_msg)

        elif command == "/key":
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, f"🔑 <b>Stream Key actual:</b> <code>{curr_key}</code>\n\nPara cambiarla usa: <code>/key NUEVA_KEY</code>")
                return

            new_key = clean_arg(parts[1])
            CONFIG["stream_key"] = new_key
            save_config(CONFIG)
            send_msg(chat_id, f"✅ <b>Stream Key actualizada correctamente:</b>\n<code>{new_key}</code>")

        elif text.startswith("/"):
            send_msg(chat_id, "❓ <b>Comando no reconocido.</b>\nUsa <code>/partidos</code>, <code>/canales</code> o <code>/ayuda</code> para ver los comandos disponibles.")

    except Exception as e:
        print("Error procesando mensaje:", e)
        send_msg(chat_id, f"⚠️ Ocurrió un error temporal al procesar la solicitud: <code>{html.escape(str(e))}</code>")

def restore_streams_from_environment():
    """Resume explicitly supplied local restart state without writing keys to disk."""
    raw = os.environ.pop("EL_CIRO_RESUME", "")
    if not raw:
        return 0
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            return 0
    except ValueError:
        return 0
    restored = 0
    for entry in entries[:8]:
        if not isinstance(entry, dict):
            continue
        source, destination = entry.get("source"), entry.get("destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            continue
        if not destination.startswith(("rtmp://", "rtmps://")):
            continue
        try:
            ok, _ = start_single_stream(source, destination, None, requested_slot=str(restored + 1))
            restored += bool(ok)
        except Exception as exc:
            print("No se pudo reanudar una emisión:", type(exc).__name__)
    print("Emisiones locales reanudadas o en recuperación:", restored)
    return restored


def main():
    global BOT_USERNAME
    print("=" * 65)
    print("🤖 BOT DE TRANSMISIÓN DEPORTIVA (ElCiro - FLUIDEZ TOTAL)")
    print("=" * 65)
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ AVISO: Variable TELEGRAM_BOT_TOKEN no configurada.")
        return

    threading.Thread(target=supervisor_thread, daemon=True).start()
    restore_streams_from_environment()

    try:
        identity = requests.get(f"{API_URL}/getMe", timeout=10).json()
        if identity.get("ok"):
            BOT_USERNAME = identity["result"]["username"]
        result = requests.post(f"{API_URL}/setMyCommands", json={"commands": [
            {"command": cmd, "description": description} for cmd, description in BOT_COMMANDS
        ]}, timeout=10).json()
        print("Menú de comandos actualizado:", bool(result.get("ok")))
    except (requests.RequestException, ValueError) as exc:
        print("No se pudo actualizar el menú:", type(exc).__name__)

    # Eliminar cualquier webhook previo para garantizar que getUpdates funcione sin bloqueos
    try:
        del_res = requests.get(f"{API_URL}/deleteWebhook?drop_pending_updates=false", timeout=10)
        print(f"Estado de webhook eliminado: {del_res.status_code}")
    except Exception as e:
        print(f"Aviso al limpiar webhook inicial: {e}")

    print("Iniciando polling de Telegram...")
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
                print("Conflicto 409 detectado (posible webhook activo). Limpiando webhook...")
                try:
                    requests.get(f"{API_URL}/deleteWebhook?drop_pending_updates=false", timeout=10)
                except Exception:
                    pass
                time.sleep(2)
            elif r.status_code in [401, 404]:
                print(f"Error fatal Telegram: {r.status_code}. Revisa el TELEGRAM_BOT_TOKEN.")
                time.sleep(10)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
