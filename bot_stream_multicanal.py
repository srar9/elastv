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
from datetime import datetime, timezone, timedelta

# ==============================================================================
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "8988332685:AAF-6ulB_iNjIl5QeGxGQx8ehiZjMNeNQfE").strip()
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CONFIG_FILE = "stream_config.json"

ADMIN_IDS_RAW = os.environ.get("ADMIN_USER_IDS", "")
_env_admins = [x.strip() for x in ADMIN_IDS_RAW.split(",") if x.strip()]
# Garantizar que el ID del propietario siempre tenga acceso de administrador
ADMIN_USER_IDS = list(set(_env_admins + ["6467102546"]))

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

def _fetch_single_tr_slug(clean_slug):
    # 1. Probar en la18hd.su (infraestructura oficial de tarjetarojatv.mobi)
    page_url_la = f"https://la18hd.su/vivo/canal.php?stream={clean_slug}"
    try:
        h_la = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tarjetarojatv.mobi/"
        }
        r_page = requests.get(page_url_la, headers=h_la, timeout=8)
        if r_page.status_code == 200:
            m_play = re.search(r'var\s+playbackURL\s*=\s*["\']([^"\']+)["\']', r_page.text)
            if m_play:
                stream_url = m_play.group(1).replace(r'\/', '/')
                return stream_url, "https://la18hd.su/", "OK (la18hd directo)"
    except Exception as e:
        print(f"Error fetching la18hd for {clean_slug}:", e)

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
    except Exception as e:
        pass

    return None, None, "No stream url"

def resolve_tarjetaroja_stream(channel_slug):
    clean_slug = channel_slug.strip().lower().replace("_", "-")
    
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

    return None, None, st

def resolve_stream_source(channel_input):
    clean_in = clean_arg(channel_input)

    if clean_in.startswith("http://") or clean_in.startswith("https://"):
        headers_str = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
        return clean_in, headers_str, "Canal Personalizado", clean_in, True

    resolved_slug, channel_name = resolve_channel_input(clean_in)

    stream_url, iframe_ref, status_info = resolve_tarjetaroja_stream(resolved_slug)
    if stream_url:
        ref_header = f"Referer: {iframe_ref}\r\n" if iframe_ref else "Referer: https://la18hd.su/\r\n"
        headers_str = f"{ref_header}User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
        return stream_url, headers_str, channel_name, resolved_slug, True

    return None, None, channel_name, resolved_slug, False

# ==============================================================================
# MOTOR DE TRANSMISIÓN ULTRA-FLUIDO (REAL-TIME / ZERO B-FRAMES / SINCRONIZACIÓN PERFECTA)
# ==============================================================================
def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    """
    Motor de emisión ultra-fluido con sincronización A/V automática perfecta:
    1. Cadencia Real-Time (-re): lee y emite a 1.00x de velocidad constante.
    2. Sincronización A/V Automática (-copyts -start_at_zero -af aresample=async=1):
       Alinea el audio y video con el reloj de la señal en tiempo cero. 
       Elimina al 100% el desfase sin importar el canal o la señal.
    3. Audio Broadcast 48kHz (-ar 48000): tasa estándar para evitar desincronización
       por diferencias de muestreo entre canales de 44.1kHz y 48kHz.
    4. Zero B-Frames (-bf 0) y Perfil Baseline: decodificación instantánea en Telegram.
    5. Keyframes cada 2 segundos (-g 60 -keyint_min 60 -sc_threshold 0).
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "3",
        "-rw_timeout", "15000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "2000000",
        "-probesize", "2000000"
    ]

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-copyts",
        "-start_at_zero",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-profile:v", "baseline",
        "-level", "3.1",
        "-bf", "0",
        "-r", "30",
        "-fps_mode", "cfr",
        "-b:v", "1200k",
        "-maxrate", "1500k",
        "-bufsize", "2500k",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-af", "aresample=async=1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ])

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    return proc, out_f, log_file

# ==============================================================================
# GESTIÓN MULTI-PANTALLA ILIMITADA (1, 2, 3, 4, 5, ...)
# ==============================================================================
def start_single_stream(channel_input, stream_key, chat_id, requested_slot=None):
    clean_channel_input = clean_arg(channel_input)
    clean_key = clean_arg(stream_key)

    source_url, headers_str, channel_name, resolved_slug, ok = resolve_stream_source(clean_channel_input)
    if not ok or not source_url:
        return False, (
            f"❌ No se pudo conectar a la señal de <b>{html.escape(clean_channel_input)}</b> en ElCiro.\n\n"
            "💡 Usa <code>/partidos</code> para ver los eventos de hoy o <code>/canales</code> para el directorio completo."
        )

    destination = clean_key if clean_key.startswith(("rtmp://", "rtmps://")) else f"rtmps://dc4-1.rtmp.t.me/s/{clean_key}"

    target_slot = None
    with stream_lock:
        if requested_slot and str(requested_slot).isdigit() and int(requested_slot) >= 1:
            target_slot = str(int(requested_slot))
            if target_slot in active_streams:
                old_info = active_streams[target_slot]
                old_info["auto_restart"] = False
                old_proc = old_info.get("process")
                if old_proc:
                    try:
                        old_proc.terminate()
                        try:
                            old_proc.wait(timeout=1.5)
                        except subprocess.TimeoutExpired:
                            old_proc.kill()
                            old_proc.wait(timeout=1)
                    except Exception:
                        try:
                            old_proc.kill()
                        except Exception:
                            pass
                try:
                    if old_info.get("log_handle"):
                        old_info["log_handle"].close()
                except Exception:
                    pass
                del active_streams[target_slot]

        if not target_slot:
            for sid, info in list(active_streams.items()):
                if info.get("key") == clean_key:
                    target_slot = sid
                    info["auto_restart"] = False
                    old_proc = info.get("process")
                    if old_proc:
                        try:
                            old_proc.terminate()
                            try:
                                old_proc.wait(timeout=1.5)
                            except subprocess.TimeoutExpired:
                                old_proc.kill()
                                old_proc.wait(timeout=1)
                        except Exception:
                            try:
                                old_proc.kill()
                            except Exception:
                                pass
                    try:
                        if info.get("log_handle"):
                            info["log_handle"].close()
                    except Exception:
                        pass
                    del active_streams[sid]
                    break

        if not target_slot:
            cand = 1
            while str(cand) in active_streams:
                cand += 1
            target_slot = str(cand)

        active_streams[target_slot] = {
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
            "last_active_time": time.time(),
            "last_log_size": 0,
            "auto_restart": True,
            "restarts": 0,
            "status": "starting"
        }

    proc, out_f, log_file = launch_ffmpeg_process(source_url, headers_str, destination, target_slot)

    with stream_lock:
        if target_slot in active_streams and active_streams[target_slot].get("key") == clean_key:
            active_streams[target_slot]["process"] = proc
            active_streams[target_slot]["log_handle"] = out_f
            active_streams[target_slot]["log_file"] = log_file
            active_streams[target_slot]["status"] = "running"
            active_streams[target_slot]["last_active_time"] = time.time()

    time.sleep(3.0)
    poll_res = proc.poll()
    if poll_res is not None:
        try:
            out_f.close()
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-600:]
        except Exception:
            logs = "Sin logs"

        with stream_lock:
            if target_slot in active_streams and active_streams[target_slot].get("process") == proc:
                del active_streams[target_slot]

        if "Input/output error" in logs or "Error opening output" in logs or "Error number -138" in logs or "Connection to tcp://" in logs:
            return False, (
                "⚠️ <b>Telegram rechazó la conexión de transmisión.</b>\n\n"
                "👉 <b>Motivo:</b> La sala en vivo no está abierta en tu canal o la clave es incorrecta.\n\n"
                "<b>Pasos obligatorios para transmitir en Telegram:</b>\n"
                "1. Abre tu canal o grupo de Telegram.\n"
                "2. Toca en el menú de arriba (<code>...</code>) $\\rightarrow$ <b>\"Transmitir con...\"</b>.\n"
                "3. Mantén abierta la ventana que dice <i>\"Listo para transmitir\"</i> o <i>\"Esperando señal...\"</i>.\n"
                "4. Vuelve a enviar el comando: <code>/stream " + resolved_slug + " " + clean_key + "</code>"
            )

        return False, f"❌ <b>Error al conectar con Telegram RTMP</b> (Código: {poll_res})\n\n<code>{html.escape(logs)}</code>"

    active_count = len(active_streams)
    return True, (
        f"✅ <b>TRANSMISIÓN EN VIVO INICIADA (PANTALLA #{target_slot})</b>\n\n"
        f"📺 <b>Canal:</b> {html.escape(channel_name)} [<code>{html.escape(resolved_slug)}</code>]\n"
        f"⚡ <b>Rendimiento:</b> Ultra-Fluido Zero B-Frames (0% Tirones / 100% Suave)\n"
        f"🌐 <b>Servidor:</b> ElCiro Nativo\n"
        f"🔑 <b>Stream Key:</b> <code>{clean_key[:12]}...</code>\n"
        f"📡 <b>Pantallas Activas:</b> {active_count} simultáneas en emisión\n"
        f"⏱️ <b>Sincronización Audio/Video:</b> 100% Automática (Cero Desfase)\n\n"
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
# SUPERVISOR INFINITO Y WATCHDOG ANTI-CONGELAMIENTO (CERO CAÍDAS)
# ==============================================================================
def supervisor_thread():
    while True:
        time.sleep(3.5)
        now = time.time()
        
        with stream_lock:
            for sid, info in list(active_streams.items()):
                if not info.get("auto_restart", False):
                    continue

                proc = info.get("process")
                log_file = info.get("log_file")
                
                is_stalled = False
                if log_file and os.path.exists(log_file):
                    try:
                        cur_size = os.path.getsize(log_file)
                        if cur_size > info.get("last_log_size", 0):
                            info["last_log_size"] = cur_size
                            info["last_active_time"] = now
                        elif now - info.get("last_active_time", now) > 22:
                            is_stalled = True
                    except Exception:
                        pass

                needs_restart = False
                if proc is None:
                    needs_restart = True
                elif proc.poll() is not None:
                    needs_restart = True
                elif is_stalled:
                    needs_restart = True
                    print(f"[Watchdog] Pantalla #{sid} detectada congelada. Forzando reinicio...")
                    try:
                        proc.kill()
                        proc.wait(timeout=1)
                    except Exception:
                        pass

                if not needs_restart:
                    if now - info.get("start_time", 0) > 30 and info.get("restarts", 0) > 0:
                        info["restarts"] = 0
                    continue

                last_restart_attempt = info.get("last_restart_attempt", 0)
                backoff_time = min(10, 4 + (info.get("restarts", 0) // 3) * 2)
                if now - last_restart_attempt < backoff_time:
                    continue

                info["last_restart_attempt"] = now
                info["restarts"] = info.get("restarts", 0) + 1
                info["status"] = "reconnecting"

                slug = info.get("resolved_slug") or info.get("channel_input")
                dest = info['key'] if info['key'].startswith(('rtmp://', 'rtmps://')) else f"rtmps://dc4-1.rtmp.t.me/s/{info['key']}"

                src_url, headers_str, ch_name, res_slug, ok = resolve_stream_source(slug)
                if ok and src_url:
                    try:
                        if info.get("log_handle"):
                            info["log_handle"].close()
                    except Exception:
                        pass

                    new_proc, new_out_f, new_log_file = launch_ffmpeg_process(src_url, headers_str, dest, sid)
                    info["process"] = new_proc
                    info["log_handle"] = new_out_f
                    info["log_file"] = new_log_file
                    info["status"] = "running"
                    info["last_active_time"] = time.time()
                    info["last_log_size"] = 0
                    print(f"[Supervisor] Pantalla #{sid} ({ch_name}) reanudada exitosamente con nuevo token.")

t_super = threading.Thread(target=supervisor_thread, daemon=True)
t_super.start()

# ==============================================================================
# AGENDA DINÁMICA DE PARTIDOS (100% TARJETA ROJA DIRECTA)
# ==============================================================================
MATCHES_AGENDA_CACHE = {"timestamp": 0, "messages": []}

def slugify_match_bot(match_title):
    if not match_title:
        return ""
    s = unicodedata.normalize('NFKD', str(match_title)).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9\s\-]', '', s).strip().lower()
    s = re.sub(r'[\s\-]+', '-', s)
    return s

def fetch_tarjetaroja_schedule():
    url = "https://tarjetarojatv.mobi/api/agenda"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tarjetarojatv.mobi/"
        }
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return []

        raw = r.json()
        events_list = raw.get("events", []) if isinstance(raw, dict) else raw
        events = []

        for ev in events_list:
            raw_title = ev.get("title", "").strip().replace("–", "-").replace("—", "-")
            if ":" in raw_title:
                comp, match_name = raw_title.split(":", 1)
                comp = comp.strip()
                match_name = match_name.strip()
            else:
                comp = ev.get("sport", "Deportes").title()
                match_name = raw_title

            date_str = ev.get("date", "")
            time_str = ev.get("time", "")
            try:
                dt_utc = datetime.strptime(f"{date_str} {time_str[:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                dt_arg = dt_utc.astimezone(timezone(timedelta(hours=-3)))
                ev_time = dt_arg.strftime("%H:%M")
            except Exception:
                ev_time = time_str[:5] if time_str else ""

            channels = []
            seen_slugs = set()
            for idx, emb in enumerate(ev.get("embeds", [])):
                iframe_url = emb.get("iframe", "").strip()
                name = emb.get("name", f"Señal {idx+1}").strip()

                slug = None
                if "stream=" in iframe_url:
                    m_s = re.search(r'stream=([a-zA-Z0-9_\-]+)', iframe_url)
                    if m_s:
                        slug = m_s.group(1).lower()

                if not slug:
                    # Mapear señales espejo (móvil, web) a canales conocidos
                    target = f"{name} {iframe_url}".lower()
                    if "espn2" in target:
                        slug = "espn2"
                    elif "espn3" in target:
                        slug = "espn3"
                    elif "espn4" in target:
                        slug = "espn4"
                    elif "espn" in target:
                        slug = "espn"
                    elif "tyc" in target:
                        slug = "tycsports"
                    elif "tnt" in target:
                        slug = "tntsports"
                    elif "tudn" in target:
                        slug = "tudn"
                    elif "dsport" in target:
                        slug = "dsports"
                    elif "america" in target:
                        slug = "americatv"
                    elif "telefe" in target:
                        slug = "telefe"
                    elif "caracol" in target:
                        slug = "caracol"
                    elif "canal5" in target or "canal 5" in target:
                        slug = "canal5"
                    elif "azteca" in target:
                        slug = "azteca7"

                # Solo incluir canales con señal directa reproducible por FFmpeg y evitar duplicados
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    channels.append({"name": name, "slug": slug, "iframe": iframe_url})

            if match_name:
                events.append({
                    "time": ev_time,
                    "competition": comp,
                    "match": match_name,
                    "channels": channels
                })

        return events
    except Exception as e:
        print("Error fetching tarjetarojatv schedule:", e)
        return []

def get_live_matches_agenda(curr_key):
    global MATCHES_AGENDA_CACHE
    now = time.time()
    if now - MATCHES_AGENDA_CACHE["timestamp"] < 90 and MATCHES_AGENDA_CACHE["messages"]:
        return MATCHES_AGENDA_CACHE["messages"]

    try:
        tr_events = fetch_tarjetaroja_schedule()
        if tr_events:
            agenda_blocks = []
            for ev in tr_events:
                channels = ev.get("channels", [])
                if not channels:
                    continue

                time_str = f"[{ev['time']}] " if ev['time'] else ""
                block = f"🏆 <b>{time_str}{html.escape(ev['competition'])}: {html.escape(ev['match'])}</b>\n"
                
                seen_slugs = set()
                for ch in channels:
                    slug = ch["slug"]
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    cname = ch["name"]
                    if slug in TR_CHANNELS:
                        cname = TR_CHANNELS[slug]["name"]

                    block += f"• 📺 <i>{html.escape(cname)}:</i>\n  <code>/stream {slug} {curr_key}</code>\n"
                
                agenda_blocks.append(block)

            if agenda_blocks:
                messages = []
                header = (
                    "📅 <b>AGENDA DE PARTIDOS DE HOY (ElCiro - EN VIVO)</b>\n"
                    "📢 <b>Canal Oficial:</b> @elasdelfutbol\n"
                    "<i>Señales exactas verificadas canal por canal en directo:</i>\n\n"
                )
                current_msg = header
                for b in agenda_blocks:
                    if len(current_msg) + len(b) + 2 > 3500:
                        messages.append(current_msg.strip())
                        current_msg = b + "\n"
                    else:
                        current_msg += b + "\n"

                if current_msg:
                    messages.append(current_msg.strip())

                MATCHES_AGENDA_CACHE["timestamp"] = now
                MATCHES_AGENDA_CACHE["messages"] = messages
                return messages
    except Exception as e:
        print("Error generando agenda deportiva:", e)

    return get_sports_menu_messages(curr_key)

# ==============================================================================
# DIRECTORIO COMPLETO DE CANALES (/canales) - 63 SEÑALES TARJETA ROJA
# ==============================================================================
def get_sports_menu_messages(curr_key):
    msg1 = (
        "🏆 <b>DIRECTORIO DE CANALES (ElCiro - EN VIVO) [Parte 1/3]</b>\n\n"
        "✨ <b>SUITE DISNEY+ EVENTOS (FÚTBOL & CHAMPIONS EN DIRECTO):</b>\n"
        f"• 🏆 <b>Disney 1 HD:</b> <code>/stream disney-1 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 2 HD:</b> <code>/stream disney-2 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 3 HD:</b> <code>/stream disney-3 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 4 HD:</b> <code>/stream disney-4 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 5 HD:</b> <code>/stream disney-5 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 6 HD:</b> <code>/stream disney-6 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 7 HD:</b> <code>/stream disney-7 {curr_key}</code>\n"
        f"• 🏆 <b>Disney 8 al 15:</b> <code>/stream disney8 {curr_key}</code> a <code>disney15</code>\n\n"
        "🎬 <b>SUITE MAX (HBO / WARNER MULTISEÑAL EN VIVO):</b>\n"
        f"• ⚽ <b>MAX 1 HD:</b> <code>/stream max1 {curr_key}</code>\n"
        f"• ⚽ <b>MAX 2 HD:</b> <code>/stream max2 {curr_key}</code>\n"
        f"• ⚽ <b>MAX 3 HD:</b> <code>/stream max3 {curr_key}</code>\n\n"
        "🌎 <b>SUITE COMPLETA ESPN SUR:</b>\n"
        f"• ⚽ <b>ESPN 1 HD (Sur):</b> <code>/stream espn {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD (Sur):</b> <code>/stream espn2 {curr_key}</code>\n"
        f"• 🚴 <b>ESPN 3 HD (Ciclismo / Tenis):</b> <code>/stream espn3 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD (Sur):</b> <code>/stream espn4 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 5 HD (Sur):</b> <code>/stream espn5 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN Premium HD (Argentina):</b> <code>/stream espnpremium {curr_key}</code>\n"
        f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>"
    )

    msg2 = (
        "🏆 <b>DIRECTORIO DE CANALES (ElCiro) [Parte 2/3]</b>\n\n"
        "🦊 <b>SUITE FOX SPORTS:</b>\n"
        f"• ⚽ <b>Fox Sports 1 Argentina:</b> <code>/stream fox1ar {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 2 Argentina:</b> <code>/stream fox2ar {curr_key}</code>\n"
        f"• ⚽ <b>Fox ONE MX:</b> <code>/stream foxone {curr_key}</code>\n"
        f"• ⚽ <b>FOX One 2:</b> <code>/stream foxone2 {curr_key}</code>\n"
        f"• ⚽ <b>FOX One 3 / Fox Sports 3 HD:</b> <code>/stream foxone3 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Deportes USA:</b> <code>/stream fox_deportes_usa {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports Premium HD:</b> <code>/stream foxpremium {curr_key}</code>\n\n"
        "🇲🇽 <b>SUITE ViX+ & TUDN (MÉXICO & USA):</b>\n"
        f"• 🇲🇽 <b>ViX+ TUDN Deportes 1 HD:</b> <code>/stream vix1 {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ Zona TUDN HD:</b> <code>/stream vix2 {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ Deportes 3 HD:</b> <code>/stream vix3 {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ Deportes 4 HD:</b> <code>/stream vix4 {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ Deportes 5 HD:</b> <code>/stream vix5 {curr_key}</code>\n"
        f"• 🇲🇽 <b>TUDN MX HD:</b> <code>/stream tudn {curr_key}</code>\n"
        f"• 🇺🇸 <b>Universo USA HD:</b> <code>/stream universo_usa {curr_key}</code>\n\n"
        "🎟️ <b>SUITE FANATIZ (EVENTOS EXCLUSIVOS 1 AL 5):</b>\n"
        f"• ⚽ <b>Fanatiz 1 HD:</b> <code>/stream fanatiz {curr_key}</code>\n"
        f"• ⚽ <b>Fanatiz 2 HD:</b> <code>/stream fanatiz-2 {curr_key}</code>\n"
        f"• ⚽ <b>Fanatiz 3 HD:</b> <code>/stream fanatiz-3 {curr_key}</code>\n"
        f"• ⚽ <b>Fanatiz 4 HD:</b> <code>/stream fanatiz-4 {curr_key}</code>\n"
        f"• ⚽ <b>Fanatiz 5 HD:</b> <code>/stream fanatiz-5 {curr_key}</code>"
    )

    msg3 = (
        "🏆 <b>DIRECTORIO DE CANALES (ElCiro) [Parte 3/3]</b>\n\n"
        "🇨🇴 <b>DIRECTV SPORTS & WIN SPORTS & BRASIL & ARGENTINA:</b>\n"
        f"• ⚽ <b>DSports 1 HD:</b> <code>/stream dsports {curr_key}</code>\n"
        f"• ⚽ <b>DSports 2 HD:</b> <code>/stream dsports2 {curr_key}</code>\n"
        f"• ⚽ <b>DSports+ HD:</b> <code>/stream dsportsplus {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream tycsports {curr_key}</code>\n"
        f"• ⚽ <b>TNT Sports HD:</b> <code>/stream tntsports {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports + HD (Colombia):</b> <code>/stream winplus {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports HD (Colombia):</b> <code>/stream winsports {curr_key}</code>\n"
        f"• ⚽ <b>Sport TV 1 BR (Brasil):</b> <code>/stream sporttvbr1 {curr_key}</code>\n"
        f"• ⚽ <b>Liga 1 MAX (Perú):</b> <code>/stream liga1max {curr_key}</code>\n\n"
        "🍏 <b>APPLE TV (MLS SEASON PASS 1 AL 15):</b>\n"
        f"• ⚽ <b>Apple TV 1:</b> <code>/stream appletv1 {curr_key}</code>\n"
        f"• ⚽ <b>Apple TV 2:</b> <code>/stream appletv2 {curr_key}</code>\n"
        f"• ⚽ <b>Apple TV 3 al 15:</b> <code>/stream appletv3</code> al <code>appletv15</code>\n\n"
        "🇪🇸 <b>ESPAÑA & LIGA DE CAMPEONES:</b>\n"
        f"• ⚽ <b>Movistar LaLiga HD:</b> <code>/stream movistarlaliga {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream daznlaliga {curr_key}</code>\n"
        f"• ⚽ <b>M+ Liga de Campeones 1 FHD:</b> <code>/stream campeones {curr_key}</code>\n"
        f"• ⚽ <b>M+ Liga de Campeones 2 FHD:</b> <code>/stream campeones2 {curr_key}</code>\n\n"
        "💡 <i>Usa <code>/partidos</code> para ver qué señal transmite el partido que quieres ver hoy.</i>"
    )
    return [msg1, msg2, msg3]

def search_tarjetaroja(query, curr_key):
    q = query.strip().lower()
    results = []

    events = fetch_tarjetaroja_schedule()
    match_found = []
    for ev in events:
        text_ev = f"{ev.get('competition', '')} {ev.get('match', '')}".lower()
        if q in text_ev:
            match_found.append(ev)

    if match_found:
        results.append("⚽ <b>PARTIDOS ENCONTRADOS EN ElCiro:</b>\n")
        for ev in match_found[:6]:
            time_str = f"[{ev['time']}] " if ev['time'] else ""
            block = f"🏆 <b>{time_str}{html.escape(ev['competition'])}: {html.escape(ev['match'])}</b>\n"
            for ch in ev.get("channels", []):
                block += f"• 📺 <i>{html.escape(ch['name'])}:</i> <code>/stream {ch['slug']} {curr_key}</code>\n"
            results.append(block)

    channels_found = []
    seen = set()
    for alias, info in TR_CHANNELS.items():
        if info["slug"] in seen:
            continue
        if q in alias or q in info["name"].lower() or q in info["slug"]:
            seen.add(info["slug"])
            channels_found.append(info)

    if channels_found:
        results.append("📺 <b>CANALES ENCONTRADOS EN ElCiro:</b>\n")
        for ch in channels_found[:12]:
            results.append(f"• 📺 <b>{html.escape(ch['name'])}:</b>\n  <code>/stream {ch['slug']} {curr_key}</code>\n")

    if not results:
        return f"🔍 No se encontraron partidos ni canales para '<b>{html.escape(query)}</b>'. Usa <code>/partidos</code> o <code>/canales</code>."

    return "\n".join(results)

def send_msg(chat_id, text, parse_mode="HTML"):
    try:
        url = f"{API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)

def handle_message(msg):
    global CONFIG
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return

    try:
        if text.startswith(("/id", "/myid", "/mi_id")):
            send_msg(
                chat_id, 
                f"👤 <b>Tu ID de Telegram:</b> <code>{user_id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
                f"🛡️ <i>Copia tu ID numérico y colócalo en la variable <code>ADMIN_USER_IDS</code> de Railway para proteger tu bot de transmisiones no autorizadas.</i>"
            )
            return

        admin_commands = ["/stream", "/stop", "/stopall", "/stoppal", "/detener", "/key", "/delay", "/pausar"]
        if any(text.lower().startswith(cmd) for cmd in admin_commands):
            if ADMIN_USER_IDS and str(user_id) not in ADMIN_USER_IDS:
                send_msg(chat_id, "⛔ <b>Acceso denegado:</b> Solo el administrador autorizado puede iniciar transmisiones o cambiar configuraciones.")
                return

        curr_key = CONFIG.get("stream_key", "3936015063:nG8N_no46UfNuA6jXewiag")

        if text.startswith("/start") or text.startswith("/ayuda"):
            help_text = (
                "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (ElCiro - FLUIDEZ TOTAL)</b>\n\n"
                "⚡ <b>Rendimiento:</b> Modo Ultra-Fluido Zero B-Frames (0% Lag / 0% Tirones en Telegram).\n\n"
                "📋 <b>COMANDOS PRINCIPALES:</b>\n"
                "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver partidos de hoy con enlaces listos en 1-click\n"
                "• <code>/canales</code> o <code>/deportes</code> $\\rightarrow$ Ver los 63 canales de ElCiro\n"
                "• <code>/buscar &lt;texto&gt;</code> $\\rightarrow$ Buscar partido o canal en ElCiro\n"
                "• <code>/espn</code> $\\rightarrow$ Ver suite completa de ESPN Sur\n"
                "• <code>/stream &lt;CANAL&gt; [PANTALLA] [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión\n"
                "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas y estado en vivo\n"
                "• <code>/stop [ID]</code> $\\rightarrow$ Detener pantalla activa (ej. <code>/stop 1</code>)\n"
                "• <code>/stopall</code> $\\rightarrow$ Detener todas las pantallas activas\n"
                "• <code>/delay &lt;ms o s&gt;</code> $\\rightarrow$ Calibrar audio (ej: <code>/delay +300</code> o <code>/delay 1500</code>)\n"
                f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar Stream Key por defecto"
            )
            send_msg(chat_id, help_text)

        elif text.startswith("/buscar") or text.startswith("/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;partido o canal&gt;</code>\nEjemplo: <code>/buscar barcelona</code> o <code>/buscar max</code> o <code>/buscar vix</code>")
                return
            q = parts[1].strip()
            send_msg(chat_id, f"🔍 <b>Buscando en ElCiro para '{q}'...</b>")
            res_text = search_tarjetaroja(q, curr_key)
            send_msg(chat_id, res_text)

        elif text.startswith("/canales") or text.startswith("/deportes") or text.startswith("/menu"):
            msgs = get_sports_menu_messages(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/espn"):
            espn_msg = (
                "📺 <b>SUITE COMPLETA ESPN SUR (24/7 EN DIRECTO - ElCiro):</b>\n\n"
                "🇦🇷 <b>SEÑALES ESPN SUR (HD / FHD):</b>\n"
                f"• ⚽ <b>ESPN 1 HD (Sur):</b> <code>/stream espn {curr_key}</code> o <code>/stream espn 1</code>\n"
                f"• ⚽ <b>ESPN 2 HD (Sur):</b> <code>/stream espn2 {curr_key}</code> o <code>/stream espn 2</code>\n"
                f"• 🚴 <b>ESPN 3 HD (Ciclismo / Tenis):</b> <code>/stream espn3 {curr_key}</code> o <code>/stream espn 3</code>\n"
                f"• ⚽ <b>ESPN 4 HD (Sur):</b> <code>/stream espn4 {curr_key}</code> o <code>/stream espn 4</code>\n"
                f"• ⚽ <b>ESPN 5 HD (Sur):</b> <code>/stream espn5 {curr_key}</code> o <code>/stream espn 5</code>\n"
                f"• ⚽ <b>ESPN Premium HD (Argentina):</b> <code>/stream espnpremium {curr_key}</code>\n"
                f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>\n\n"
                "💡 <i>Usa <code>/partidos</code> para ver qué canal transmite cada partido hoy.</i>"
            )
            send_msg(chat_id, espn_msg)

        elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
            send_msg(chat_id, "⏳ <b>Cargando partidos de hoy desde ElCiro...</b>")
            msgs = get_live_matches_agenda(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/stream"):
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
            elif ":" in last_token and len(last_token) >= 12:
                is_stream_key = True
            elif len(last_token) >= 20 and not any(kw in last_token.lower() for kw in ["espn", "fox", "sport", "deporte", "campeon", "star", "disney", "vix", "fanatiz", "max", "apple"]):
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
            send_msg(chat_id, f"🔄 <b>Conectando a ElCiro para {ch_input}{slot_notice}...</b>")
            ok, response_msg = start_single_stream(ch_input, s_key, chat_id, requested_slot=requested_slot)
            send_msg(chat_id, response_msg)

        elif text.startswith("/status") or text.startswith("/logs"):
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
                    if proc and proc.poll() is None:
                        proc_state = "🟢 EMITIENDO (Ultra-Fluido / 0% Lag)"
                    elif info.get("status") == "reconnecting":
                        proc_state = "🔄 RECONECTANDO CON NUEVO TOKEN"
                    else:
                        proc_state = "🔴 DETENIDO"

                    last_log = ""
                    try:
                        log_file = info.get("log_file")
                        if log_file and os.path.exists(log_file):
                            with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                                last_log = lf.read()[-300:]
                    except Exception:
                        pass

                    msg_status += (
                        f"🔹 <b>Pantalla #{sid}:</b> {html.escape(info['channel_name'])} [<code>{html.escape(info['resolved_slug'])}</code>]\n"
                        f"• 🌐 <b>Estado:</b> {proc_state}\n"
                        f"• ⏱️ <b>Tiempo activo:</b> {mins}m {secs}s\n"
                        f"• 🔑 <b>Key:</b> <code>{info['key'][:12]}...</code>\n"
                        f"• 🛑 <b>Detener esta pantalla:</b> <code>/stop {sid}</code>\n"
                    )
                    if last_log:
                        msg_status += f"• 📋 <b>Último log FFmpeg:</b>\n<code>{html.escape(last_log)}</code>\n\n"
                    else:
                        msg_status += "\n"

                msg_status += "🛑 <i>Para detener todas las transmisiones a la vez:</i> <code>/stopall</code>"
                send_msg(chat_id, msg_status)

        elif any(text.strip().lower().startswith(c) for c in ["/stopall", "/stoppal", "/stopal", "/stoppall", "/stop all", "/stop_all", "/detener todo", "/detener todos"]):
            ok, response_msg = stop_all_streams()
            send_msg(chat_id, response_msg)

        elif text.startswith(("/stop", "/detener", "/pausar", "/pause")):
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else None
            if arg and arg.lower() in ["all", "todas", "todo", "todos"]:
                ok, response_msg = stop_all_streams()
            else:
                ok, response_msg = stop_single_stream(arg)
            send_msg(chat_id, response_msg)

        elif text.startswith("/key"):
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

def main():
    print("=" * 65)
    print("🤖 BOT DE TRANSMISIÓN DEPORTIVA (ElCiro - FLUIDEZ TOTAL)")
    print("=" * 65)
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ AVISO: Variable TELEGRAM_BOT_TOKEN no configurada.")
        return

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
