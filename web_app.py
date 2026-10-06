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
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, abort, Response, stream_with_context

from team_helper import parse_match_teams, get_team_short, get_team_badge, is_match_live

app = Flask(__name__)

# ==============================================================================
# CONFIGURACIÓN GENERAL Y HEADERS
# ==============================================================================
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://tarjetarojatv.mobi/"
}

# ==============================================================================
# DIRECTORIO DE CANALES DEPORTIVOS VERIFICADOS (tarjetarojatv.mobi / la18hd.su)
# ==============================================================================
TR_CHANNELS = {
    # ESPN Suite
    "espn": {"slug": "espn", "name": "ESPN 1 HD (Sur/Argentina)", "category": "espn"},
    "espn1": {"slug": "espn", "name": "ESPN 1 HD (Sur/Argentina)", "category": "espn"},
    "espn2": {"slug": "espn2", "name": "ESPN 2 HD (Sur/Argentina)", "category": "espn"},
    "espn3": {"slug": "espn3", "name": "ESPN 3 HD (Sur/Argentina)", "category": "espn"},
    "espn4": {"slug": "espn4", "name": "ESPN 4 HD (Sur)", "category": "espn"},
    "espn5": {"slug": "espn5", "name": "ESPN 5 HD (Sur)", "category": "espn"},
    "espn6": {"slug": "espn6", "name": "ESPN 6 HD", "category": "espn"},
    "espn7": {"slug": "espn7", "name": "ESPN 7 HD", "category": "espn"},
    "espnpremium": {"slug": "espnpremium", "name": "ESPN Premium HD (Argentina)", "category": "espn"},
    "espnextra": {"slug": "espnextra", "name": "ESPN Extra HD", "category": "espn"},
    "espnmx": {"slug": "espnmx", "name": "ESPN México HD", "category": "espn"},
    "espn2mx": {"slug": "espn2mx", "name": "ESPN 2 México HD", "category": "espn"},
    "espn3mx": {"slug": "espn3mx", "name": "ESPN 3 México HD", "category": "espn"},
    "espn4mx": {"slug": "espn4mx", "name": "ESPN 4 México HD", "category": "espn"},
    "espnplus": {"slug": "espnplus", "name": "ESPN Plus HD", "category": "espn"},

    # Fox Sports Suite
    "fox1": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox1ar": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox": {"slug": "foxsports", "name": "Fox Sports 1 HD", "category": "fox"},
    "foxsports": {"slug": "foxsports", "name": "Fox Sports 1 HD", "category": "fox"},
    "foxsportsar": {"slug": "foxsportsar", "name": "Fox Sports Argentina", "category": "fox"},
    "fox2": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "foxsports2": {"slug": "foxsports2", "name": "Fox Sports 2 HD", "category": "fox"},
    "foxsports2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox3": {"slug": "foxsports3", "name": "Fox Sports 3 HD", "category": "fox"},
    "foxsports3": {"slug": "foxsports3", "name": "Fox Sports 3 HD", "category": "fox"},
    "foxsportsmx": {"slug": "foxsportsmx", "name": "Fox Sports MX", "category": "fox"},
    "foxsports2mx": {"slug": "foxsports2mx", "name": "Fox Sports 2 MX", "category": "fox"},
    "foxsports3mx": {"slug": "foxsports3mx", "name": "Fox Sports 3 MX", "category": "fox"},
    "foxsportspremium": {"slug": "foxsportspremium", "name": "Fox Sports Premium HD", "category": "fox"},
    "foxpremium": {"slug": "foxsportspremium", "name": "Fox Sports Premium HD", "category": "fox"},

    # DIRECTV Sports (DSPORTS)
    "dsports": {"slug": "dsports", "name": "DSports 1 HD", "category": "dsports"},
    "dsports1": {"slug": "dsports", "name": "DSports 1 HD", "category": "dsports"},
    "dsports2": {"slug": "dsports2", "name": "DSports 2 HD", "category": "dsports"},
    "dsportsplus": {"slug": "dsportsplus", "name": "DSports+ HD", "category": "dsports"},
    "dsports3": {"slug": "dsportsplus", "name": "DSports+ HD", "category": "dsports"},
    "dsports_eventos": {"slug": "dsports_eventos", "name": "DSports Eventos HD", "category": "dsports"},

    # Argentina y Sudamérica
    "tyc": {"slug": "tycsports", "name": "TyC Sports HD", "category": "latam"},
    "tycsports": {"slug": "tycsports", "name": "TyC Sports HD", "category": "latam"},
    "tntsports": {"slug": "tntsports", "name": "TNT Sports HD (Argentina)", "category": "latam"},
    "tntsportschile": {"slug": "tntsportschile", "name": "TNT Sports Chile HD", "category": "latam"},
    "golperu": {"slug": "golperu", "name": "Gol Perú HD", "category": "latam"},
    "winplus": {"slug": "winplus", "name": "Win Sports + HD", "category": "latam"},
    "winsports": {"slug": "winplus", "name": "Win Sports + HD", "category": "latam"},
    "telefe": {"slug": "telefe", "name": "Telefe HD", "category": "latam"},
    "caracol": {"slug": "caracol", "name": "Caracol TV HD", "category": "latam"},
    "americatv": {"slug": "americatv", "name": "América TV HD", "category": "latam"},

    # MAX Suite (Champions League)
    "max1": {"slug": "max1", "name": "MAX 1 HD (Champions)", "category": "max"},
    "max2": {"slug": "max2", "name": "MAX 2 HD (Champions)", "category": "max"},
    "max3": {"slug": "max3", "name": "MAX 3 HD (Champions)", "category": "max"},

    # ViX+ / TUDN
    "tudn": {"slug": "tudn", "name": "TUDN Deportes", "category": "vix"},
    "tudn_mx": {"slug": "tudn_mx", "name": "TUDN México HD", "category": "vix"},
    "vix1": {"slug": "vix1", "name": "ViX+ Deportes 1 HD", "category": "vix"},
    "vix2": {"slug": "vix2", "name": "ViX+ Deportes 2 HD", "category": "vix"},

    # Internacionales / España
    "laligatv": {"slug": "laligatv", "name": "LaLiga TV Bar", "category": "otros"},
    "dazn1": {"slug": "dazn1", "name": "DAZN 1 España", "category": "otros"},
    "dazn2": {"slug": "dazn2", "name": "DAZN 2 España", "category": "otros"},
    "movistarliga": {"slug": "movistarliga", "name": "Movistar LaLiga HD", "category": "otros"},
    "movistar-laliga": {"slug": "movistarliga", "name": "Movistar LaLiga HD", "category": "otros"},
    "canal5": {"slug": "canal5", "name": "Canal 5 MX", "category": "otros"},
    "azteca7": {"slug": "azteca7", "name": "Azteca 7 MX", "category": "otros"},
    "univision": {"slug": "univision", "name": "Univisión USA", "category": "otros"},
    "universo": {"slug": "universo", "name": "Universo USA", "category": "otros"},
}

# Inyectar señales Disney+ Eventos (1 al 15)
for i in range(1, 16):
    slug_d = f"disney{i}"
    name_d = f"Disney+ {i} HD"
    TR_CHANNELS[slug_d] = {"slug": slug_d, "name": name_d, "category": "disney"}
    TR_CHANNELS[f"disney-{i}"] = {"slug": slug_d, "name": name_d, "category": "disney"}

CATEGORIES_META = {
    "espn": {"name": "ESPN Suite", "icon": "tv"},
    "fox": {"name": "Fox Sports", "icon": "trophy"},
    "dsports": {"name": "DIRECTV Sports", "icon": "radio"},
    "latam": {"name": "Argentina y Sudamérica", "icon": "flag"},
    "max": {"name": "MAX (Champions)", "icon": "sparkles"},
    "disney": {"name": "Disney+ / Star+", "icon": "star"},
    "vix": {"name": "ViX+ y TUDN", "icon": "zap"},
    "otros": {"name": "Internacionales y España", "icon": "globe"},
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
# MOTOR DE ESPECTADORES REALES EN VIVO POR PARTIDO
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
    """Identifica unívocamente al visitante mediante cookie persistente, vid o hash IP+UA determinista."""
    vid = request.cookies.get("elas_vid")
    if vid and 4 < len(vid) < 64:
        return vid.strip()
    param_vid = request.args.get("vid")
    if param_vid and 4 < len(param_vid) < 64:
        return param_vid.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "127.0.0.1")
    ua = request.headers.get("User-Agent", "")[:40]
    return "u_" + hashlib.md5(f"{ip}-{ua}".encode()).hexdigest()[:14]

@app.after_request
def ensure_viewer_cookie(response):
    if not request.cookies.get("elas_vid"):
        vid = extract_client_id()
        response.set_cookie("elas_vid", vid, max_age=30*86400, samesite="Lax", path="/")
    return response

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
            if int(now) % 50 == 0:
                conn.execute("DELETE FROM match_viewers WHERE last_seen < ?", (now - 7200,))
    except Exception as e:
        print("Error registrando espectador en SQLite:", e)

def get_all_active_viewers_map():
    """Devuelve un diccionario { match_id: set(client_ids) } con todos los espectadores activos."""
    cutoff = time.time() - 90
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT match_id, client_id FROM match_viewers WHERE last_seen >= ?", (cutoff,))
            rows = cur.fetchall()
            mapping = {}
            for m_id, c_id in rows:
                if m_id not in mapping:
                    mapping[m_id] = set()
                mapping[m_id].add(c_id)
            return mapping
    except Exception as e:
        print("Error consultando mapa de espectadores activos:", e)
        return {}

def calculate_event_viewers_from_map(viewers_map, match_slug, channels=None):
    """Calcula el número exacto de espectadores únicos para un evento considerando match_slug y canales."""
    keys = set()
    if match_slug:
        keys.add(str(match_slug).strip().lower())
    if channels:
        for ch in channels:
            slug = ch.get("slug") if isinstance(ch, dict) else str(ch)
            if slug:
                keys.add(slug.strip().lower().replace("_", "-"))
    unique_clients = set()
    for k in keys:
        if k in viewers_map:
            unique_clients.update(viewers_map[k])
    return len(unique_clients)

def get_event_viewers_count(match_slug, channels=None):
    viewers_map = get_all_active_viewers_map()
    return calculate_event_viewers_from_map(viewers_map, match_slug, channels)

def get_match_viewers_count(match_id):
    return get_event_viewers_count(match_id)

def get_all_matches_viewers_counts():
    cutoff = time.time() - 90
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
    return get_event_viewers_count(slug)

def format_viewers(count):
    if count >= 1000:
        return f"{count / 1000:.1f}K".replace(".", ",")
    return str(count)

# ==============================================================================
# OBTENCIÓN DE AGENDA DE PARTIDOS DIRECTAMENTE DESDE https://tarjetarojatv.mobi/
# ==============================================================================
def fetch_tarjetarojatv_schedule():
    """
    Obtiene la agenda oficial de partidos y eventos directamente desde
    la API JSON de https://tarjetarojatv.mobi/api/agenda.
    Ultra-rápido, sin parseo HTML frágil y con resolución directa de embeds.
    """
    now = time.time()
    if now - SCHEDULE_CACHE["timestamp"] < 90 and SCHEDULE_CACHE["events"]:
        return SCHEDULE_CACHE["events"]

    url = "https://tarjetarojatv.mobi/api/agenda"
    try:
        r = requests.get(url, headers=HEADERS_BASE, timeout=8)
        if r.status_code != 200:
            return SCHEDULE_CACHE["events"]

        raw = r.json()
        events_list = raw.get("events", []) if isinstance(raw, dict) else raw
        events = []

        for ev in events_list:
            raw_title = ev.get("title", "").strip()
            # Limpiar guiones especiales
            raw_title = raw_title.replace("–", "-").replace("—", "-")

            if ":" in raw_title:
                comp, match_name = raw_title.split(":", 1)
                comp = comp.strip()
                match_name = match_name.strip()
            else:
                comp = ev.get("sport", "Deportes").title()
                match_name = raw_title

            # Convertir hora UTC a hora de Argentina (UTC-3)
            date_str = ev.get("date", "")
            time_str = ev.get("time", "")
            try:
                dt_utc = datetime.strptime(f"{date_str} {time_str[:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                dt_arg = dt_utc.astimezone(timezone(timedelta(hours=-3)))
                ev_time = dt_arg.strftime("%H:%M")
            except Exception:
                ev_time = time_str[:5] if time_str else ""

            comp_img = ev.get("flag", "")

            # Canales / Embeds de transmisión
            channels = []
            seen_slugs = set()
            for idx, emb in enumerate(ev.get("embeds", [])):
                iframe_url = emb.get("iframe", "").strip()
                name = emb.get("name", f"Señal {idx+1}").strip()
                lang = emb.get("lang", "Español").strip()

                slug = ""
                if "stream=" in iframe_url:
                    m_s = re.search(r'stream=([a-zA-Z0-9_\-]+)', iframe_url)
                    if m_s:
                        slug = m_s.group(1).lower()

                if not slug:
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
                    else:
                        slug = f"ev{ev.get('id', '')}_{idx+1}_{slugify_match(name)}"

                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    channels.append({
                        "name": name,
                        "slug": slug,
                        "iframe": iframe_url,
                        "lang": lang
                    })

            if match_name:
                m_slug = slugify_match(match_name)
                events.append({
                    "id": ev.get("id"),
                    "time": ev_time,
                    "competition": comp,
                    "comp_img": comp_img,
                    "match": match_name,
                    "match_slug": m_slug,
                    "channels": channels
                })

        SCHEDULE_CACHE["timestamp"] = now
        SCHEDULE_CACHE["events"] = events
        return events
    except Exception as e:
        print("Error fetching tarjetarojatv schedule:", e)
        return SCHEDULE_CACHE["events"]

# Alias para compatibilidad con código existente
fetch_tarjetaroja_schedule = fetch_tarjetarojatv_schedule

# ==============================================================================
# RESOLVEDOR DE TRANSMISIONES DE TARJETA ROJA TV (la18hd.su / fubo18.com)
# ==============================================================================
def resolve_tarjetarojatv_stream(channel_slug):
    """
    Resuelve el slug de canal extrayendo el enlace directo HLS (.m3u8)
    o el iframe purificado desde la infraestructura de tarjetarojatv.mobi / la18hd.su.
    """
    clean_slug = channel_slug.strip().lower().replace("_", "-")
    now = time.time()

    if clean_slug in STREAM_RESOLVER_CACHE:
        cached = STREAM_RESOLVER_CACHE[clean_slug]
        if now - cached["timestamp"] < 60:
            return cached["data"]

    # Mapeo de alias a slug oficial de la18hd
    mapped_info = TR_CHANNELS.get(clean_slug)
    actual_slug = mapped_info["slug"] if mapped_info else clean_slug

    # Si viene con prefijo sintético de evento (ej: ev40363_4_espn-movil)
    m_ev = re.match(r'^ev\d+_\d+_(.*)', clean_slug)
    if m_ev:
        candidate_tag = m_ev.group(1).replace("-", "").replace("_", "")
        for k, v in TR_CHANNELS.items():
            if k in candidate_tag or candidate_tag in k:
                actual_slug = v["slug"]
                break

    slug_candidates = [actual_slug]
    if clean_slug != actual_slug:
        slug_candidates.append(clean_slug)
    if "-" in actual_slug:
        slug_candidates.append(actual_slug.replace("-", ""))
    if "_" in actual_slug:
        slug_candidates.append(actual_slug.replace("_", ""))

    stream_url = None
    iframe_url = f"https://la18hd.su/vivo/canal.php?stream={actual_slug}"
    status_info = "No stream"

    # 1. Probar en la18hd.su
    for candidate in slug_candidates:
        page_url = f"https://la18hd.su/vivo/canal.php?stream={candidate}"
        try:
            r = requests.get(page_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://tarjetarojatv.mobi/"
            }, timeout=6)
            if r.status_code == 200:
                m_play = re.search(r'var\s+playbackURL\s*=\s*["\']([^"\']+)["\']', r.text)
                if m_play:
                    stream_url = m_play.group(1).replace(r'\/', '/')
                    iframe_url = page_url
                    status_info = "OK (la18hd directo)"
                    break
        except Exception as e:
            status_info = str(e)

    # 2. Si no se encontró directo, revisar si es un iframe de la agenda activa
    if not stream_url:
        for ev in SCHEDULE_CACHE.get("events", []):
            for ch in ev.get("channels", []):
                if ch.get("slug") == clean_slug or ch.get("slug") == actual_slug:
                    ch_if = ch.get("iframe")
                    if ch_if:
                        iframe_url = ch_if
                        status_info = "OK (agenda embed)"
                        if "stream=" in ch_if:
                            m_st = re.search(r'stream=([a-zA-Z0-9_\-]+)', ch_if)
                            if m_st:
                                try:
                                    r_sub = requests.get(ch_if, headers={
                                        "User-Agent": "Mozilla/5.0",
                                        "Referer": "https://tarjetarojatv.mobi/"
                                    }, timeout=6)
                                    m_p = re.search(r'var\s+playbackURL\s*=\s*["\']([^"\']+)["\']', r_sub.text)
                                    if m_p:
                                        stream_url = m_p.group(1).replace(r'\/', '/')
                                        status_info = "OK (agenda la18hd)"
                                except Exception:
                                    pass
                    break
            if stream_url:
                break

    data = {
        "slug": clean_slug,
        "stream_url": stream_url,
        "iframe_url": iframe_url,
        "status": status_info
    }
    STREAM_RESOLVER_CACHE[clean_slug] = {
        "timestamp": now,
        "data": data
    }
    return data

# Alias para compatibilidad con código existente
resolve_tarjetaroja_stream = resolve_tarjetarojatv_stream

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
    raw_events = fetch_tarjetarojatv_schedule()
    viewers_map = get_all_active_viewers_map()
    events = []
    live_count = 0
    for ev in raw_events:
        ev_copy = dict(ev)
        m_slug = ev_copy.get("match_slug", "")
        channels = ev_copy.get("channels", [])
        v_count = calculate_event_viewers_from_map(viewers_map, m_slug, channels)

        ev_copy["viewers"] = v_count
        ev_copy["viewers_formatted"] = f"{v_count:,}".replace(",", ".")
        ev_copy["viewers_short"] = format_viewers(v_count)

        # Determinar si el partido está actualmente EN VIVO
        is_live = is_match_live(ev_copy.get("time"), v_count)
        ev_copy["is_live"] = is_live
        if is_live:
            live_count += 1

        # Separar equipos y buscar escudos oficiales
        match_title = ev_copy.get("match", "")
        comp = ev_copy.get("competition", "")
        t1, t2 = parse_match_teams(match_title, comp)
        ev_copy["team1"] = t1
        ev_copy["team2"] = t2
        ev_copy["team1_badge"] = get_team_badge(t1, comp)
        ev_copy["team2_badge"] = get_team_badge(t2, comp)
        ev_copy["team1_short"] = get_team_short(t1)
        ev_copy["team2_short"] = get_team_short(t2)

        events.append(ev_copy)
    return render_template(
        "index.html", 
        events=events, 
        live_events_count=live_count, 
        active_page="home"
    )

@app.route("/canales")
def channels_view():
    all_channels = get_unique_channels()
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

    req_match = request.args.get("m") or request.args.get("match")
    req_title = request.args.get("title")
    req_comp = request.args.get("c") or request.args.get("competition") or ""

    match_slug = ""
    match_title = ""
    competition = req_comp
    event_channels = []

    schedule_events = fetch_tarjetarojatv_schedule()

    if req_match:
        match_slug = slugify_match(req_match)
        match_title = req_title or req_match.replace("-", " ").title()
        for ev in schedule_events:
            if ev.get("match_slug") == match_slug:
                event_channels = list(ev.get("channels", []))
                if not req_title and ev.get("match"):
                    match_title = ev.get("match")
                if not competition and ev.get("competition"):
                    competition = ev.get("competition")
                break
    else:
        # Buscar si este canal tiene un partido en curso en la agenda
        for ev in schedule_events:
            for ch in ev.get("channels", []):
                if ch.get("slug") == clean_slug:
                    match_slug = ev.get("match_slug")
                    match_title = ev.get("match")
                    if not competition and ev.get("competition"):
                        competition = ev.get("competition")
                    event_channels = list(ev.get("channels", []))
                    break
            if match_slug:
                break

    if not match_slug:
        match_slug = clean_slug
        match_title = channel_info.get("name", clean_slug.upper())

    if not competition:
        competition = channel_info.get("category", "")

    # Asegurar que el canal actual esté en event_channels
    found_curr = any(c.get("slug") == clean_slug for c in event_channels)
    if not found_curr:
        event_channels.insert(0, {"name": channel_info.get("name", clean_slug.upper()), "slug": clean_slug})

    # Si hay sólo 1 señal, ofrecer opciones de contingencia populares
    if len(event_channels) < 2:
        fallbacks = [
            {"slug": "espn", "name": "ESPN 1 HD"},
            {"slug": "espn2", "name": "ESPN 2 HD"},
            {"slug": "foxsports", "name": "Fox Sports 1"},
            {"slug": "tycsports", "name": "TyC Sports HD"}
        ]
        for fb in fallbacks:
            if fb["slug"] != clean_slug and not any(c.get("slug") == fb["slug"] for c in event_channels):
                event_channels.append(fb)
            if len(event_channels) >= 3:
                break

    # Registrar heartbeat
    client_id = extract_client_id()
    record_match_viewer(match_slug, client_id)
    record_match_viewer(clean_slug, client_id)

    stream_data = resolve_tarjetarojatv_stream(clean_slug)
    stream_url = stream_data.get("stream_url") if stream_data else None
    iframe_url = stream_data.get("iframe_url") if stream_data else None
    clean_stream_src = f"/stream/live/{clean_slug}/master.m3u8" if stream_url else None

    # Canales recomendados para el menú inferior
    all_unique = get_unique_channels()
    recommended = [c for c in all_unique if c["slug"] != clean_slug][:12]

    # Calcular espectadores en vivo
    v_count = get_event_viewers_count(match_slug, event_channels)
    formatted_v = f"{v_count:,}".replace(",", ".")
    short_v = format_viewers(v_count)

    # Equipos y escudos
    t1, t2 = parse_match_teams(match_title, competition)
    t1_badge = get_team_badge(t1, competition)
    t2_badge = get_team_badge(t2, competition)

    return render_template(
        "player.html",
        channel=channel_info,
        clean_stream_src=clean_stream_src,
        iframe_url=iframe_url,
        recommended=recommended,
        match_title=match_title,
        match_slug=match_slug,
        competition=competition,
        event_channels=event_channels,
        team1=t1,
        team2=t2,
        team1_badge=t1_badge,
        team2_badge=t2_badge,
        team1_short=get_team_short(t1),
        team2_short=get_team_short(t2),
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
    event_channels = []
    schedule_events = fetch_tarjetarojatv_schedule()

    if req_match:
        match_slug = slugify_match(req_match)
        for ev in schedule_events:
            if ev.get("match_slug") == match_slug:
                event_channels = ev.get("channels", [])
                break
    else:
        for ev in schedule_events:
            for ch in ev.get("channels", []):
                if ch.get("slug") == clean_slug:
                    match_slug = ev.get("match_slug")
                    event_channels = ev.get("channels", [])
                    break
            if match_slug:
                break

    if not match_slug:
        match_slug = clean_slug

    if not event_channels:
        event_channels = [{"slug": clean_slug}]

    client_id = extract_client_id()
    record_match_viewer(match_slug, client_id)
    record_match_viewer(clean_slug, client_id)

    v_count = get_event_viewers_count(match_slug, event_channels)
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
    raw_events = fetch_tarjetarojatv_schedule()
    viewers_map = get_all_active_viewers_map()
    data = []
    for ev in raw_events:
        m_slug = ev.get("match_slug", "")
        channels = ev.get("channels", [])
        v_count = calculate_event_viewers_from_map(viewers_map, m_slug, channels)

        is_live = is_match_live(ev.get("time"), v_count)
        data.append({
            "match": ev.get("match", ""),
            "match_slug": m_slug,
            "viewers": v_count,
            "short": format_viewers(v_count),
            "is_live": is_live
        })
    return jsonify({"ok": True, "events": data})

# ==============================================================================
# PROXY HLS UNIVERSAL (KEEP-ALIVE ULTRA-RÁPIDO CON AUTO-REFRESCO DE TOKEN)
# ==============================================================================
HLS_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=60, pool_maxsize=120, max_retries=2)
HLS_SESSION.mount("https://", _adapter)
HLS_SESSION.mount("http://", _adapter)

@app.route("/stream/live/<slug>/master.m3u8")
def hls_proxy_master(slug):
    clean_slug = slug.strip().lower().replace("_", "-")
    stream_data = resolve_tarjetarojatv_stream(clean_slug)
    stream_url = stream_data.get("stream_url")
    if not stream_url:
        return abort(404)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://la18hd.su/"
        }
        r = HLS_SESSION.get(stream_url, headers=headers, timeout=8)
        
        # Si el token expiró, limpiar caché y reintentar con token fresco
        if r.status_code != 200:
            STREAM_RESOLVER_CACHE.pop(clean_slug, None)
            stream_data = resolve_tarjetarojatv_stream(clean_slug)
            stream_url = stream_data.get("stream_url")
            if not stream_url:
                return abort(r.status_code)
            r = HLS_SESSION.get(stream_url, headers=headers, timeout=8)
            if r.status_code != 200:
                return abort(r.status_code)

        base_url = stream_url.split("?")[0].rsplit("/", 1)[0]
        lines = []
        for line in r.text.splitlines():
            l = line.strip()
            if l and not l.startswith("#"):
                sub_target = base_url + "/" + l if not l.startswith("http") else l
                encoded = urllib.parse.quote_plus(sub_target)
                if ".m3u8" in l:
                    lines.append(f"/stream/live/{clean_slug}/sub.m3u8?target={encoded}")
                else:
                    lines.append(f"/stream/live/{clean_slug}/segment.ts?target={encoded}")
            else:
                lines.append(line)

        resp = Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://la18hd.su/"
        }
        r = HLS_SESSION.get(target, headers=headers, timeout=8)
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
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://la18hd.su/"
        }
        r = HLS_SESSION.get(target, headers=headers, stream=True, timeout=12)
        if r.status_code != 200:
            return abort(r.status_code)

        def generate():
            for chunk in r.iter_content(chunk_size=131072):
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
    stream_data = resolve_tarjetarojatv_stream(clean_slug)
    iframe_url = stream_data.get("iframe_url") if stream_data else None
    if not iframe_url:
        return "Canal no disponible", 404

    try:
        headers = dict(HEADERS_BASE)
        headers["Referer"] = "https://tarjetarojatv.mobi/"
        r = requests.get(iframe_url, headers=headers, timeout=8)
        if r.status_code != 200:
            return "Error al cargar la señal de origen", 502

        html_content = r.text

        # 1. Eliminar scripts publicitarios conocidos
        html_content = re.sub(r'<script[^>]*src=["\'][^"\']*(?:aclib|llvpn|luugy|adcash|popunder|onclick|track)[^"\']*["\'][^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<script[^>]*>.*?aclib\.runPop.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<script[^>]*>.*?(?:11545073|11645073|11918478).*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # 2. Desactivar detección de sandbox
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
    events = fetch_tarjetarojatv_schedule()
    return jsonify({"success": True, "count": len(events), "events": events})

@app.route("/api/canales")
def api_canales():
    channels = get_unique_channels()
    return jsonify({"success": True, "count": len(channels), "channels": channels})

@app.route("/api/stream/<slug>")
def api_stream(slug):
    data = resolve_tarjetarojatv_stream(slug)
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
