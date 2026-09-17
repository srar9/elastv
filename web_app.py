# -*- coding: utf-8 -*-
import os
import sys
import time
import re
import json
import html
import sqlite3
import unicodedata
import requests
import urllib.parse
import hashlib
from flask import Flask, render_template, request, jsonify, abort, Response, stream_with_context

from bot_stream_multicanal import resolve_tarjetaroja_stream as resolve_tr_engine

app = Flask(__name__)

# ==============================================================================
# CONFIGURACIÓN GENERAL Y HEADERS
# ==============================================================================
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

# ==============================================================================
# DIRECTORIO DE 63 CANALES DEPORTIVOS ORGANIZADOS POR CATEGORÍA
# ==============================================================================
TR_CHANNELS = {
    # ESPN Suite
    "espn": {"slug": "espn", "name": "ESPN 1 HD (Sur)", "category": "espn"},
    "espn1": {"slug": "espn", "name": "ESPN 1 HD (Sur)", "category": "espn"},
    "espn2": {"slug": "espn2", "name": "ESPN 2 HD (Sur)", "category": "espn"},
    "espn3": {"slug": "espn3", "name": "ESPN 3 HD (Sur)", "category": "espn"},
    "espn4": {"slug": "espn4", "name": "ESPN 4 HD (Sur)", "category": "espn"},
    "espn5": {"slug": "espn5", "name": "ESPN 5 HD (Sur)", "category": "espn"},
    "espn6": {"slug": "foxone3", "name": "Fox Sports 3 / ESPN 6 HD", "category": "espn"},
    "espn7": {"slug": "foxone3", "name": "Fox Sports 3 / ESPN 7 HD", "category": "espn"},
    "espnextra": {"slug": "foxone3", "name": "ESPN Extra HD", "category": "espn"},
    "espnpremium": {"slug": "espnpremium", "name": "ESPN Premium HD (Argentina)", "category": "espn"},
    "espn-deportes": {"slug": "espn-deportes", "name": "ESPN Deportes USA", "category": "espn"},

    # Fox Sports Suite
    "fox1": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox1ar": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox2": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox3": {"slug": "foxone3", "name": "FOX One 3 / Fox Sports 3 HD", "category": "fox"},
    "foxone": {"slug": "foxone", "name": "Fox ONE MX", "category": "fox"},
    "foxone2": {"slug": "foxone2", "name": "FOX One 2", "category": "fox"},
    "foxone3": {"slug": "foxone3", "name": "FOX One 3", "category": "fox"},
    "foxpremium": {"slug": "foxpremium", "name": "Fox Sports Premium HD", "category": "fox"},
    "fox-deportes": {"slug": "fox_deportes_usa", "name": "Fox Deportes USA", "category": "fox"},

    # MAX Suite (Champions League)
    "max1": {"slug": "max1", "name": "MAX 1 HD (Champions)", "category": "max"},
    "max2": {"slug": "max2", "name": "MAX 2 HD (Champions)", "category": "max"},
    "max3": {"slug": "max3", "name": "MAX 3 HD (Champions)", "category": "max"},

    # DIRECTV Sports (DSPORTS)
    "dsports": {"slug": "dsports", "name": "DSports 1 HD", "category": "dsports"},
    "dsports1": {"slug": "dsports", "name": "DSports 1 HD", "category": "dsports"},
    "dsports2": {"slug": "dsports2", "name": "DSports 2 HD", "category": "dsports"},
    "dsportsplus": {"slug": "dsportsplus", "name": "DSports+ HD", "category": "dsports"},

    # Disney+ / Star+ PPV Suite
    "disney1": {"slug": "disney-1", "name": "Disney+ 1 HD", "category": "disney"},
    "disney2": {"slug": "disney-2", "name": "Disney+ 2 HD", "category": "disney"},
    "disney3": {"slug": "disney-3", "name": "Disney+ 3 HD", "category": "disney"},
    "disney4": {"slug": "disney-4", "name": "Disney+ 4 HD", "category": "disney"},
    "disney5": {"slug": "disney-5", "name": "Disney+ 5 HD", "category": "disney"},
    "disney6": {"slug": "disney-6", "name": "Disney+ 6 HD", "category": "disney"},
    "disney7": {"slug": "disney-7", "name": "Disney+ 7 HD", "category": "disney"},
    "disney-1": {"slug": "disney-1", "name": "Disney+ 1 HD", "category": "disney"},
    "disney-2": {"slug": "disney-2", "name": "Disney+ 2 HD", "category": "disney"},
    "disney-3": {"slug": "disney-3", "name": "Disney+ 3 HD", "category": "disney"},
    "disney-4": {"slug": "disney-4", "name": "Disney+ 4 HD", "category": "disney"},
    "disney-5": {"slug": "disney-5", "name": "Disney+ 5 HD", "category": "disney"},
    "disney-6": {"slug": "disney-6", "name": "Disney+ 6 HD", "category": "disney"},
    "disney-7": {"slug": "disney-7", "name": "Disney+ 7 HD", "category": "disney"},

    # ViX+ Suite
    "vix1": {"slug": "vix1", "name": "ViX+ Deportes 1 HD", "category": "vix"},
    "vix2": {"slug": "vix2", "name": "ViX+ Deportes 2 HD", "category": "vix"},
    "vix3": {"slug": "vix3", "name": "ViX+ Deportes 3 HD", "category": "vix"},
    "vix4": {"slug": "vix4", "name": "ViX+ Deportes 4 HD", "category": "vix"},
    "vix5": {"slug": "vix5", "name": "ViX+ Deportes 5 HD", "category": "vix"},
    "vix6": {"slug": "vix6", "name": "ViX+ Deportes 6 HD", "category": "vix"},
    "vix7": {"slug": "vix7", "name": "ViX+ Deportes 7 HD", "category": "vix"},
    "vix8": {"slug": "vix8", "name": "ViX+ Deportes 8 HD", "category": "vix"},

    # Otros Canales Internacionales
    "tyc": {"slug": "tyc", "name": "TyC Sports HD", "category": "otros"},
    "tudn": {"slug": "tudn", "name": "TUDN Deportes", "category": "otros"},
    "canal5mx": {"slug": "canal5mx", "name": "Canal 5 MX", "category": "otros"},
    "azteca7": {"slug": "azteca7", "name": "Azteca 7 HD", "category": "otros"},
    "goltv": {"slug": "goltv", "name": "GolTV HD", "category": "otros"},
    "dazn1": {"slug": "dazn1", "name": "DAZN 1 España", "category": "otros"},
    "dazn2": {"slug": "dazn2", "name": "DAZN 2 España", "category": "otros"},
    "laligatv": {"slug": "laligatv", "name": "LaLiga TV Bar", "category": "otros"},
    "movistar-laliga": {"slug": "movistar-laliga", "name": "Movistar LaLiga HD", "category": "otros"},
    "movistar-campeones": {"slug": "movistar-campeones", "name": "Movistar Liga de Campeones", "category": "otros"},
}

# Inyectar señales Disney+ Eventos adicionales (8 al 15)
for i in range(8, 16):
    slug_d = f"disney{i}"
    name_d = f"Disney+ {i} HD"
    TR_CHANNELS[slug_d] = {"slug": slug_d, "name": name_d, "category": "disney"}
    TR_CHANNELS[f"disney-{i}"] = {"slug": slug_d, "name": name_d, "category": "disney"}

# Inyectar señales Apple TV MLS (appletv1 a appletv15)
for i in range(1, 16):
    slug_a = f"appletv{i}"
    name_a = f"Apple TV {i} HD (MLS)"
    TR_CHANNELS[slug_a] = {"slug": slug_a, "name": name_a, "category": "appletv"}
    TR_CHANNELS[f"apple{i}"] = {"slug": slug_a, "name": name_a, "category": "appletv"}
    TR_CHANNELS[f"appletv-{i}"] = {"slug": slug_a, "name": name_a, "category": "appletv"}
    TR_CHANNELS[f"apple-{i}"] = {"slug": slug_a, "name": name_a, "category": "appletv"}

CATEGORIES_META = {
    "espn": {"name": "ESPN Suite", "icon": "tv"},
    "fox": {"name": "Fox Sports", "icon": "trophy"},
    "max": {"name": "MAX (Champions)", "icon": "sparkles"},
    "dsports": {"name": "DIRECTV Sports", "icon": "radio"},
    "disney": {"name": "Disney+ / Star+", "icon": "star"},
    "appletv": {"name": "Apple TV (MLS)", "icon": "film"},
    "vix": {"name": "ViX+ Deportes", "icon": "zap"},
    "otros": {"name": "Internacionales", "icon": "globe"},
}

# ==============================================================================
# CACHÉ DE EVENTOS Y CANALES
# ==============================================================================
SCHEDULE_CACHE = {
    "timestamp": 0,
    "events": []
}

STREAM_RESOLVER_CACHE = {}

# ==============================================================================
# MOTOR DE ESPECTADORES REALES EN VIVO POR PARTIDO (COMPARTIDO ENTRE WORKERS)
# ==============================================================================
DB_PATH = os.path.join(os.path.dirname(__file__), "viewers.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS match_viewers (
                    match_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    last_seen REAL NOT NULL,
                    PRIMARY KEY (match_id, client_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mv_match_time 
                ON match_viewers(match_id, last_seen);
            """)
    except Exception as e:
        print("Error inicializando SQLite viewers:", e)

init_db()

def slugify_match(match_title):
    """Genera un slug limpio y estandarizado para identificar un partido unívocamente."""
    if not match_title:
        return ""
    s = unicodedata.normalize('NFKD', str(match_title)).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9\s\-]', '', s).strip().lower()
    s = re.sub(r'[\s\-]+', '-', s)
    return s

def extract_client_id():
    """Identifica al visitante real mediante su vid (localStorage/memoria) o hash IP + UA."""
    vid = request.args.get("vid")
    if vid and len(vid) < 64:
        return vid
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "127.0.0.1"
    ua = request.headers.get("User-Agent", "")[:50]
    return hashlib.md5(f"{client_ip}-{ua}".encode()).hexdigest()[:16]

def record_match_viewer(match_id, client_id):
    """Registra o renueva el heartbeat de un usuario para un partido específico."""
    if not match_id or not client_id:
        return
    clean_m = str(match_id).strip().lower()
    now = time.time()
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO match_viewers (match_id, client_id, last_seen) VALUES (?, ?, ?)",
                (clean_m, str(client_id)[:64], now)
            )
            # Limpieza periódica ligera de registros de más de 2 horas (1 de cada 50 peticiones)
            if int(now) % 50 == 0:
                conn.execute("DELETE FROM match_viewers WHERE last_seen < ?", (now - 7200,))
    except Exception as e:
        print("Error registrando espectador en SQLite:", e)

def get_match_viewers_count(match_id):
    """
    Devuelve la cantidad exacta de usuarios reales de nuestra web viendo este partido
    en una ventana activa de 120 segundos (anti-throttling en móviles y Telegram).
    """
    if not match_id:
        return 0
    clean_m = str(match_id).strip().lower()
    cutoff = time.time() - 120
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(DISTINCT client_id) FROM match_viewers WHERE match_id = ? AND last_seen >= ?",
                (clean_m, cutoff)
            )
            row = cur.fetchone()
            return row[0] if row else 0
    except Exception as e:
        print("Error consultando espectadores en SQLite:", e)
        return 0

def get_all_matches_viewers_counts():
    """Devuelve un diccionario { match_id: count } con todas las métricas en 1 sola consulta ultra-rápida."""
    cutoff = time.time() - 120
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT match_id, COUNT(DISTINCT client_id) FROM match_viewers WHERE last_seen >= ? GROUP BY match_id",
                (cutoff,)
            )
            return dict(cur.fetchall())
    except Exception as e:
        print("Error consultando todos los espectadores en SQLite:", e)
        return {}

def get_channel_viewers(slug):
    """Compatibilidad de respaldo por canal."""
    return get_match_viewers_count(slug)

def format_viewers(count):
    if count >= 1000:
        return f"{count / 1000:.1f}K".replace(".", ",")
    return str(count)

def fetch_tarjetaroja_schedule():
    now = time.time()
    if now - SCHEDULE_CACHE["timestamp"] < 180 and SCHEDULE_CACHE["events"]:
        return SCHEDULE_CACHE["events"]

    url = "https://tarjetaroja.my/"
    try:
        r = requests.get(url, headers=HEADERS_BASE, timeout=8)
        if r.status_code != 200:
            return SCHEDULE_CACHE["events"]

        html_text = r.text
        parts = html_text.split('<article')
        events = []

        for p in parts[1:]:
            art = '<article ' + p.split('</article>')[0] + '</article>'
            if 'tr-event' not in art:
                continue

            m_time = re.search(r'class="tr-event-time[^"]*">([^<]+)<', art)
            ev_time = m_time.group(1).strip() if m_time else ""

            m_comp = re.search(r'class="tr-event-competition">([^<]+)<', art)
            ev_comp = m_comp.group(1).strip().rstrip(":") if m_comp else ""

            m_title = re.search(r'class="tr-event-title">(.*?)</span>\s*<span class="tr-event-chevron"', art, re.DOTALL)
            if m_title:
                raw_title = m_title.group(1)
                clean_title = re.sub(r'<[^>]+>', ' ', raw_title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                if ev_comp and clean_title.startswith(ev_comp):
                    match_name = clean_title[len(ev_comp):].strip().lstrip(":").strip()
                else:
                    match_name = clean_title
            else:
                m_search = re.search(r'data-search="([^"]+)"', art)
                match_name = m_search.group(1).strip() if m_search else ""

            channels = []
            ch_sec = re.search(r'class="tr-event-channels"[^>]*>(.*?)</div>', art, re.DOTALL)
            if ch_sec:
                for href, cname in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', ch_sec.group(1)):
                    slug = href.rstrip("/").split("/")[-1].lower()
                    channels.append({"name": cname.strip(), "slug": slug})

            if match_name:
                m_slug = slugify_match(match_name)
                events.append({
                    "time": ev_time,
                    "competition": ev_comp,
                    "match": match_name,
                    "match_slug": m_slug,
                    "channels": channels
                })

        SCHEDULE_CACHE["timestamp"] = now
        SCHEDULE_CACHE["events"] = events
        return events
    except Exception as e:
        print("Error fetching tarjetaroja schedule:", e)
        return SCHEDULE_CACHE["events"]

def resolve_tarjetaroja_stream(channel_slug):
    clean_slug = channel_slug.strip().lower().replace("_", "-")
    now = time.time()

    if clean_slug in STREAM_RESOLVER_CACHE:
        cached = STREAM_RESOLVER_CACHE[clean_slug]
        if now - cached["timestamp"] < 90:
            return cached["data"]

    stream_url, iframe_ref, status_info = resolve_tr_engine(clean_slug)
    data = {
        "slug": clean_slug,
        "stream_url": stream_url,
        "iframe_url": iframe_ref,
        "status": status_info
    }
    STREAM_RESOLVER_CACHE[clean_slug] = {
        "timestamp": now,
        "data": data
    }
    return data

def get_unique_channels():
    seen = set()
    unique = []
    for k, v in TR_CHANNELS.items():
        slug = v["slug"]
        if slug not in seen:
            seen.add(slug)
            unique.append({
                "slug": slug,
                "name": v["name"],
                "category": v["category"]
            })
    return sorted(unique, key=lambda x: (x["category"], x["name"]))

# ==============================================================================
# RUTAS WEB PRINCIPALES
# ==============================================================================
@app.route("/")
def index():
    raw_events = fetch_tarjetaroja_schedule()
    all_counts = get_all_matches_viewers_counts()
    events = []
    for ev in raw_events:
        ev_copy = dict(ev)
        m_slug = ev_copy.get("match_slug", "")
        v_count = all_counts.get(m_slug, 0)
        if v_count == 0:
            for ch in ev_copy.get("channels", []):
                c_slug = ch.get("slug", "")
                if c_slug in all_counts:
                    v_count = max(v_count, all_counts[c_slug])

        ev_copy["viewers"] = v_count
        ev_copy["viewers_formatted"] = f"{v_count:,}".replace(",", ".")
        ev_copy["viewers_short"] = format_viewers(v_count)
        events.append(ev_copy)
    return render_template("index.html", events=events, active_page="home")

@app.route("/canales")
def channels_view():
    all_channels = get_unique_channels()
    
    # Agrupar por categorías
    cat_dict = {}
    for cat_id, meta in CATEGORIES_META.items():
        cat_dict[cat_id] = {
            "name": meta["name"],
            "icon": meta["icon"],
            "channels": [c for c in all_channels if c["category"] == cat_id]
        }

    return render_template(
        "channels.html",
        channels=all_channels,
        categories=cat_dict,
        total_channels=len(all_channels),
        active_page="channels"
    )

@app.route("/ver/<slug>")
def player_view(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    channel_info = TR_CHANNELS.get(clean_slug)
    if not channel_info:
        channel_info = {
            "slug": clean_slug,
            "name": clean_slug.upper().replace("-", " "),
            "category": "deportes"
        }

    # Identificar el partido (por parámetro ?m=, ?title= o por agenda de hoy)
    req_match = request.args.get("m") or request.args.get("match")
    req_title = request.args.get("title")

    match_slug = ""
    match_title = ""

    if req_match:
        match_slug = slugify_match(req_match)
        match_title = req_title or req_match.replace("-", " ").title()
    else:
        # Buscar si este canal tiene un partido en curso en la agenda
        schedule_events = fetch_tarjetaroja_schedule()
        for ev in schedule_events:
            for ch in ev.get("channels", []):
                if ch.get("slug") == clean_slug:
                    match_slug = ev.get("match_slug")
                    match_title = ev.get("match")
                    break
            if match_slug:
                break

    if not match_slug:
        match_slug = clean_slug
        match_title = channel_info.get("name", clean_slug.upper())

    # Registrar al usuario tanto en el partido como en el canal
    client_id = extract_client_id()
    record_match_viewer(match_slug, client_id)
    record_match_viewer(clean_slug, client_id)

    stream_data = resolve_tarjetaroja_stream(clean_slug)
    stream_url = stream_data.get("stream_url") if stream_data else None
    iframe_url = stream_data.get("iframe_url") if stream_data else None
    clean_stream_src = f"/stream/live/{clean_slug}/master.m3u8" if stream_url else None

    # Canales recomendados para el menú inferior
    all_unique = get_unique_channels()
    recommended = [c for c in all_unique if c["slug"] != clean_slug][:12]

    # Calcular espectadores en vivo reales para ESTE PARTIDO
    v_count = get_match_viewers_count(match_slug)
    formatted_v = f"{v_count:,}".replace(",", ".")
    short_v = format_viewers(v_count)

    return render_template(
        "player.html",
        channel=channel_info,
        clean_stream_src=clean_stream_src,
        iframe_url=iframe_url,
        recommended=recommended,
        match_title=match_title,
        match_slug=match_slug,
        viewers=v_count,
        formatted_viewers=formatted_v,
        short_viewers=short_v,
        active_page="player"
    )

@app.route("/api/viewers/<slug>")
def api_viewers(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    req_match = request.args.get("m") or request.args.get("match")

    match_slug = ""
    if req_match:
        match_slug = slugify_match(req_match)
    else:
        schedule_events = fetch_tarjetaroja_schedule()
        for ev in schedule_events:
            for ch in ev.get("channels", []):
                if ch.get("slug") == clean_slug:
                    match_slug = ev.get("match_slug")
                    break
            if match_slug:
                break

    if not match_slug:
        match_slug = clean_slug

    client_id = extract_client_id()
    record_match_viewer(match_slug, client_id)
    record_match_viewer(clean_slug, client_id)

    v_count = get_match_viewers_count(match_slug)
    return jsonify({
        "ok": True,
        "slug": clean_slug,
        "match_slug": match_slug,
        "viewers": v_count,
        "formatted": f"{v_count:,}".replace(",", "."),
        "short": format_viewers(v_count)
    })

@app.route("/api/events/viewers")
def api_events_viewers():
    raw_events = fetch_tarjetaroja_schedule()
    all_counts = get_all_matches_viewers_counts()
    data = []
    for ev in raw_events:
        m_slug = ev.get("match_slug", "")
        v_count = all_counts.get(m_slug, 0)
        if v_count == 0:
            for ch in ev.get("channels", []):
                c_slug = ch.get("slug", "")
                if c_slug in all_counts:
                    v_count = max(v_count, all_counts[c_slug])

        data.append({
            "match": ev.get("match", ""),
            "match_slug": m_slug,
            "viewers": v_count,
            "short": format_viewers(v_count)
        })
    return jsonify({"ok": True, "events": data})

# ==============================================================================
# PROXY HLS UNIVERSAL (0 PUBLICIDAD / 0 POPUPS / CARGA INSTANTÁNEA EN MÓVILES)
# ==============================================================================
@app.route("/stream/live/<slug>/master.m3u8")
def hls_proxy_master(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    stream_data = resolve_tarjetaroja_stream(clean_slug)
    stream_url = stream_data.get("stream_url")
    if not stream_url:
        return abort(404)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": stream_data.get("iframe_url") or f"https://tarjetaroja.my/stream/{clean_slug}"
        }
        r = requests.get(stream_url, headers=headers, timeout=8)
        if r.status_code != 200:
            return abort(r.status_code)

        base_url = stream_url.split("?")[0].rsplit("/", 1)[0]
        lines = []
        for line in r.text.splitlines():
            l = line.strip()
            if l and not l.startswith("#"):
                sub_target = base_url + "/" + l if not l.startswith("http") else l
                encoded = urllib.parse.quote_plus(sub_target)
                lines.append(f"/stream/live/{clean_slug}/sub.m3u8?target={encoded}")
            else:
                lines.append(line)

        resp = Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-cache"
        return resp
    except Exception as e:
        print(f"Error in master proxy for {clean_slug}:", e)
        return abort(500)

@app.route("/stream/live/<slug>/sub.m3u8")
def hls_proxy_sub(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    target = request.args.get("target")
    if not target:
        return abort(400)

    try:
        stream_data = resolve_tarjetaroja_stream(clean_slug)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": stream_data.get("iframe_url") or f"https://tarjetaroja.my/stream/{clean_slug}"
        }
        r = requests.get(target, headers=headers, timeout=8)
        if r.status_code != 200:
            return abort(r.status_code)

        base_url = target.split("?")[0].rsplit("/", 1)[0]
        lines = []
        for line in r.text.splitlines():
            l = line.strip()
            if l and not l.startswith("#"):
                chunk_target = base_url + "/" + l if not l.startswith("http") else l
                encoded = urllib.parse.quote_plus(chunk_target)
                lines.append(f"/stream/live/{clean_slug}/segment.ts?target={encoded}")
            else:
                lines.append(line)

        resp = Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-cache"
        return resp
    except Exception as e:
        print(f"Error in sub proxy for {clean_slug}:", e)
        return abort(500)

@app.route("/stream/live/<slug>/segment.ts")
def hls_proxy_segment(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    target = request.args.get("target")
    if not target:
        return abort(400)

    try:
        stream_data = resolve_tarjetaroja_stream(clean_slug)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": stream_data.get("iframe_url") or f"https://tarjetaroja.my/stream/{clean_slug}"
        }
        r = requests.get(target, headers=headers, stream=True, timeout=10)
        if r.status_code != 200:
            return abort(r.status_code)

        def generate():
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        resp = Response(stream_with_context(generate()), content_type="video/mp2t")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=60"
        return resp
    except Exception as e:
        print(f"Error in segment proxy for {clean_slug}:", e)
        return abort(500)

@app.route("/embed/<slug>")
def embed_view(slug):
    """
    Proxy que purifica completamente los iframes eliminando cualquier script
    de publicidad (aclib, llvpn, luugy, popunders, redirecciones forzadas).
    """
    clean_slug = slug.strip().lower().replace("_", "-")
    stream_data = resolve_tarjetaroja_stream(clean_slug)
    iframe_url = stream_data.get("iframe_url") if stream_data else None
    if not iframe_url:
        return "Canal no disponible", 404

    try:
        headers = dict(HEADERS_BASE)
        headers["Referer"] = f"https://tarjetaroja.my/stream/{clean_slug}"
        r = requests.get(iframe_url, headers=headers, timeout=8)
        if r.status_code != 200:
            return "Error al cargar la señal de origen", 502

        html_content = r.text

        # 1. Eliminar scripts publicitarios conocidos (aclib, llvpn, luugy, popunders)
        html_content = re.sub(r'<script[^>]*src=["\'][^"\']*(?:aclib|llvpn|luugy|adcash|popunder|onclick|track)[^"\']*["\'][^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<script[^>]*>.*?aclib\.runPop.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<script[^>]*>.*?(?:11545073|11645073|11918478).*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # 2. Desactivar detección de sandbox de la señal original
        html_content = html_content.replace('.hasAttribute("sandbox")', '.hasAttribute("nosandbox")')
        html_content = html_content.replace("hasAttribute('sandbox')", "hasAttribute('nosandbox')")

        # 3. Inyectar anulador de popups en el encabezado
        anti_pop_script = """
        <script>
        (function() {
            window.open = function() { console.log('Bloqueado intento de popup'); return null; };
            window.alert = function() {};
            window.confirm = function() { return false; };
            window.prompt = function() { return null; };
        })();
        </script>
        """
        if "<head>" in html_content:
            html_content = html_content.replace("<head>", f"<head>{anti_pop_script}")
        else:
            html_content = f"{anti_pop_script}{html_content}"

        response = app.make_response(html_content)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response
    except Exception as e:
        print(f"Error en embed_view para {clean_slug}:", e)
        return "Error al procesar la señal limpia", 500

# ==============================================================================
# API REST JSON
# ==============================================================================
@app.route("/api/partidos")
def api_partidos():
    events = fetch_tarjetaroja_schedule()
    return jsonify({"success": True, "count": len(events), "events": events})

@app.route("/api/canales")
def api_canales():
    channels = get_unique_channels()
    return jsonify({"success": True, "count": len(channels), "channels": channels})

@app.route("/api/stream/<slug>")
def api_stream(slug):
    data = resolve_tarjetaroja_stream(slug)
    if not data:
        return jsonify({"success": False, "error": "Canal no disponible"}), 404
    return jsonify({"success": True, "data": data})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "elciro-web-live"})

# ==============================================================================
# INICIO DEL SERVIDOR LOCAL O RAILWAY
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Iniciando ElCiro Web en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
