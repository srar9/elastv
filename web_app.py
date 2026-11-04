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
import hmac
import secrets
import audience
from contextlib import closing
from datetime import datetime, timezone, timedelta
from agenda_service import schedule, ScheduleUnavailable, LOCAL_TZ, chronological
from channel_source import CHANNEL_NAMES, resolve_roja_source, resolve_player
from flask import Flask, render_template, request, jsonify, abort, Response, stream_with_context, url_for, redirect

from team_helper import parse_match_teams, get_team_short, get_team_badge, is_match_live

app = Flask(__name__)


def telegram_owner():
    """Trust only Telegram's signed initData, never an ID supplied by the browser."""
    from public_bot import TOKEN
    raw = request.headers.get("X-Telegram-Init-Data", "")
    try:
        pairs = urllib.parse.parse_qsl(raw, strict_parsing=True)
        data = dict(pairs)
        if not TOKEN or len(data) != len(pairs):
            return False
        signature = data.pop("hash")
        auth_date = int(data["auth_date"])
        if not 0 <= time.time() - auth_date <= 86400:
            return False
        check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature) and json.loads(data["user"])["id"] == audience.OWNER_ID
    except (ValueError, KeyError, TypeError):
        return False


@app.route("/estadisticas")
def statistics_page():
    # The shell contains no data; every request for statistics is authenticated.
    return render_template("statistics.html", active_page="stats")


@app.route("/api/admin/statistics")
def statistics_api():
    if not telegram_owner():
        abort(403)
    response = jsonify(audience.summary())
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/audience", methods=["POST"])
def audience_presence():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400)
    session_id = data.get("session_id", "")
    match_id = data.get("match_id", "")
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", session_id):
        abort(400)
    if not isinstance(match_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,200}", match_id):
        abort(400)
    title = str(data.get("title", match_id))[:200]
    audience.playback(session_id, extract_client_id(), match_id, title, data.get("playing") is True)
    return jsonify(ok=True)

# ==============================================================================
# CONFIGURACIÓN GENERAL Y HEADERS
# ==============================================================================
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://tarjetarojaonline.info/"
}

# ==============================================================================
# DIRECTORIO DE CANALES DEPORTIVOS VERIFICADOS (tarjetarojaonline.info / la18hd.su)
# ==============================================================================
TR_CHANNELS = {
    # ESPN Suite
    "espn": {"slug": "espnmx", "name": "ESPN 1 HD", "category": "espn"},
    "espn1": {"slug": "espnmx", "name": "ESPN 1 HD", "category": "espn"},
    "espn-1": {"slug": "espnmx", "name": "ESPN 1 HD", "category": "espn"},
    "espn2": {"slug": "espn2mx", "name": "ESPN 2 HD", "category": "espn"},
    "espn-2": {"slug": "espn2mx", "name": "ESPN 2 HD", "category": "espn"},
    "espn3": {"slug": "espn3mx", "name": "ESPN 3 HD", "category": "espn"},
    "espn-3": {"slug": "espn3mx", "name": "ESPN 3 HD", "category": "espn"},
    "espn4": {"slug": "espn4mx", "name": "ESPN 4 HD", "category": "espn"},
    "espn-4": {"slug": "espn4mx", "name": "ESPN 4 HD", "category": "espn"},
    "espn5": {"slug": "espn5", "name": "ESPN 5 HD", "category": "espn"},
    "espn6": {"slug": "espn6", "name": "ESPN 6 HD", "category": "espn"},
    "espn7": {"slug": "espn7", "name": "ESPN 7 HD", "category": "espn"},
    "espnpremium": {"slug": "espnpremium", "name": "ESPN Premium HD", "category": "espn"},
    "espnextra": {"slug": "espnextra", "name": "ESPN Extra HD", "category": "espn"},
    "espnmx": {"slug": "espnmx", "name": "ESPN México HD", "category": "espn"},
    "espn2mx": {"slug": "espn2mx", "name": "ESPN 2 México HD", "category": "espn"},
    "espn3mx": {"slug": "espn3mx", "name": "ESPN 3 México HD", "category": "espn"},
    "espn4mx": {"slug": "espn4mx", "name": "ESPN 4 México HD", "category": "espn"},
    "espnplus": {"slug": "espnplus", "name": "ESPN Plus HD", "category": "espn"},

    # Fox Sports Suite
    "fox1": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox1ar": {"slug": "fox1ar", "name": "Fox Sports 1 Argentina", "category": "fox"},
    "fox": {"slug": "foxsportsmx", "name": "Fox Sports 1 HD", "category": "fox"},
    "foxsports": {"slug": "foxsportsmx", "name": "Fox Sports 1 HD", "category": "fox"},
    "fox-sports-1": {"slug": "foxsportsmx", "name": "Fox Sports 1 HD", "category": "fox"},
    "fox-sports-2": {"slug": "foxsports2mx", "name": "Fox Sports 2 HD", "category": "fox"},
    "fox-sports-3": {"slug": "foxsports3mx", "name": "Fox Sports 3 HD", "category": "fox"},
    "fox-sports-premium": {"slug": "foxsportspremium", "name": "Fox Sports Premium HD", "category": "fox"},
    "foxsportsar": {"slug": "foxsportsar", "name": "Fox Sports Argentina", "category": "fox"},
    "fox2": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "foxsports2": {"slug": "foxsports2mx", "name": "Fox Sports 2 HD", "category": "fox"},
    "foxsports2ar": {"slug": "fox2ar", "name": "Fox Sports 2 Argentina", "category": "fox"},
    "fox3": {"slug": "foxsports3mx", "name": "Fox Sports 3 HD", "category": "fox"},
    "foxsports3": {"slug": "foxsports3mx", "name": "Fox Sports 3 HD", "category": "fox"},
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
    "tudn": {"slug": "tudn_mx", "name": "TUDN México HD", "category": "vix"},
    "tudn_mx": {"slug": "tudn_mx", "name": "TUDN México HD", "category": "vix"},
    "tudn-mx": {"slug": "tudn_mx", "name": "TUDN México HD", "category": "vix"},
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
    "agenda": {"name": "Señales de los partidos de hoy", "icon": "calendar"},
    "espn": {"name": "ESPN Suite", "icon": "tv"},
    "fox": {"name": "Fox Sports", "icon": "trophy"},
    "dsports": {"name": "DIRECTV Sports", "icon": "radio"},
    "latam": {"name": "Argentina y Sudamérica", "icon": "flag"},
    "max": {"name": "MAX (Champions)", "icon": "sparkles"},
    "disney": {"name": "Disney+ / Star+", "icon": "star"},
    "vix": {"name": "ViX+ y TUDN", "icon": "zap"},
    "otros": {"name": "Internacionales y España", "icon": "globe"},
}

# Provider-backed aliases use the same IDs in the web app and streaming bot.
for _slug, _name in CHANNEL_NAMES.items():
    _cat = "espn" if _slug.startswith("espn") else "fox" if _slug.startswith("fox") else "dsports" if _slug.startswith("dsports") else "latam"
    TR_CHANNELS[_slug] = {"slug": _slug, "name": _name, "category": _cat}
TR_CHANNELS["espn1"] = TR_CHANNELS["espn"]
TR_CHANNELS["espn-1"] = TR_CHANNELS["espn"]
TR_CHANNELS["winplus"] = TR_CHANNELS["winsports2"]

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
        with closing(get_db()) as conn, conn:
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
    if "elciro.visitor" not in request.environ:
        request.environ["elciro.visitor"] = secrets.token_urlsafe(24)
    return request.environ["elciro.visitor"]

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
    with closing(audience.connect()) as conn:
        rows = conn.execute("SELECT match_id, client_id FROM visits WHERE playing=1 AND last_seen>=?", (time.time() - 45,)).fetchall()
    mapping = {}
    for row in rows:
        mapping.setdefault(row["match_id"], set()).add(row["client_id"])
    return mapping


def calculate_event_viewers_from_map(viewers_map, match_slug, channels=None):
    """Calcula el número exacto de espectadores únicos para un evento considerando match_slug y canales."""
    return len(viewers_map.get(str(match_slug).strip().lower(), set()))


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
# OBTENCIÓN DE AGENDA DE PARTIDOS DIRECTAMENTE DESDE https://tarjetarojaonline.info/
# ==============================================================================
def fetch_tarjetarojatv_schedule():
    try:
        events = chronological(schedule.get())
    except ScheduleUnavailable:
        events = []
    SCHEDULE_CACHE["events"] = events
    SCHEDULE_CACHE["timestamp"] = time.time()
    return events

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
    clean_slug = channel_slug.strip().lower()
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

    # 1. Probar en tvf90.com (CDN ftlly.com - alta compatibilidad sin bloqueo 403 en Railway)
    from channel_source import resolve_tvf90
    tv_stream, tv_ref, tv_st = resolve_tvf90(clean_slug)
    if not tv_stream and actual_slug != clean_slug:
        tv_stream, tv_ref, tv_st = resolve_tvf90(actual_slug)
    if tv_stream:
        data = {"slug": clean_slug, "stream_url": tv_stream, "iframe_url": tv_ref, "status": tv_st}
        STREAM_RESOLVER_CACHE[clean_slug] = {"timestamp": now, "data": data}
        return data

    stream, ref, status = resolve_roja_source(actual_slug)
    if not stream:
        fetch_tarjetarojatv_schedule()
        registered = schedule.channel(clean_slug) or schedule.channel(actual_slug)
        if registered:
            stream, ref, status = resolve_player(registered["iframe"])
    if stream:
        data = {"slug": clean_slug, "stream_url": stream, "iframe_url": ref, "status": status}
        STREAM_RESOLVER_CACHE[clean_slug] = {"timestamp": now, "data": data}
        return data

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
                "Referer": "https://tarjetarojaonline.info/"
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
                                        "Referer": "https://tarjetarojaonline.info/"
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
    for event in fetch_tarjetarojatv_schedule():
        for channel in event.get("channels", []):
            if channel["slug"] not in seen:
                seen.add(channel["slug"])
                unique.append(dict(slug=channel["slug"], name=channel["name"], category="agenda"))
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


def find_match(events, match_slug, competition="", starts_at=""):
    """Select a specific fixture, including fixtures with the same title."""
    candidates = [event for event in events if event.get("match_slug") == match_slug
                  and (not competition or event.get("competition") == competition)
                  and (not starts_at or event.get("starts_at", "") == starts_at)]
    return candidates[0] if len(candidates) == 1 else None


@app.route("/partido/<match_slug>")
def match_view(match_slug):
    event = find_match(fetch_tarjetarojatv_schedule(), match_slug,
                       request.args.get("c", ""), request.args.get("at", ""))
    if not event:
        return render_template("match.html", event=None, active_page="home"), 404
    return render_template("match.html", event=event, active_page="home")


@app.route("/ver/<slug>")
def player_view(slug):
    clean_slug = slug.strip().lower()
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
    event_start = request.args.get("at", "")

    match_slug = ""
    match_title = ""
    competition = req_comp
    event_channels = []
    match_url = ""

    watch_mode = request.args.get("mode") == "watch"
    if watch_mode:
        # Render the video shell immediately, even on a cold web worker. The browser
        # fetches alternative signals separately while the embedded player starts.
        schedule_events = list(schedule.events) if schedule.day == datetime.now(LOCAL_TZ).date() else []
    else:
        schedule_events = fetch_tarjetarojatv_schedule()

    if req_match:
        match_slug = slugify_match(req_match)
        match_title = req_title or req_match.replace("-", " ").title()
        ev = find_match(schedule_events, match_slug, req_comp, event_start)
        if ev:
            event_channels = list(ev.get("channels", []))
            match_title = ev.get("match", match_title)
            competition = ev.get("competition", competition)
            event_start = ev.get("starts_at", "")
            match_url = url_for("match_view", match_slug=match_slug, c=competition, at=event_start)
            if not any(channel.get("slug") == clean_slug for channel in event_channels):
                return redirect(match_url)

    if not match_slug:
        match_slug = clean_slug
        match_title = channel_info.get("name", clean_slug.upper())

    if not competition:
        competition = channel_info.get("category", "")

    # Asegurar que el canal actual esté en event_channels
    found_curr = any(c.get("slug") == clean_slug for c in event_channels)
    if not found_curr:
        event_channels.insert(0, {"name": channel_info.get("name", clean_slug.upper()), "slug": clean_slug})

    # Resolve the native video once, inside the embedded player.
    iframe_url = None
    clean_embed_url = f"/embed/{clean_slug}"
    clean_stream_src = None

    # Canales recomendados para el menú inferior
    recommended = []

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
        clean_embed_url=clean_embed_url,
        recommended=recommended,
        match_title=match_title,
        match_slug=match_slug,
        competition=competition,
        event_channels=event_channels,
        match_url=match_url,
        event_start=event_start,
        team1=t1,
        team2=t2,
        team1_badge=t1_badge,
        team2_badge=t2_badge,
        team1_short=get_team_short(t1),
        team2_short=get_team_short(t2),
        viewers=v_count,
        formatted_viewers=formatted_v,
        short_viewers=short_v,
        active_page="home" if match_url else "channels"
    )

@app.route("/api/viewers/<slug>")
def api_viewers(slug):
    clean_slug = slug.strip().lower()
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
from live_delivery import MediaCache, Reports, complete_media, UpstreamHTTPError
import threading as _delivery_threads
MEDIA_CACHE = MediaCache()
MEDIA_DOWNLOADS = _delivery_threads.local()
SOURCE_REPORTS = Reports(lambda *args: audience.signal_event(*args))
_adapter = requests.adapters.HTTPAdapter(pool_connections=60, pool_maxsize=120, max_retries=2)
HLS_SESSION.mount("https://", _adapter)
HLS_SESSION.mount("http://", _adapter)

def proxy_secret():
    from public_bot import TOKEN
    return (os.environ.get("HLS_PROXY_SECRET") or TOKEN or audience.proxy_key()).encode()


def signed_target(slug, target, ref, playlist=False):
    expires = str(int(time.time()) + 3600)
    signature = hmac.new(proxy_secret(), f"{slug}\n{target}\n{ref}\n{expires}".encode(), hashlib.sha256).hexdigest()
    route = "sub.m3u8" if playlist else "segment.ts"
    return f"/stream/live/{slug}/{route}?" + urllib.parse.urlencode(dict(target=target, ref=ref, expires=expires, sig=signature))


def verified_target(slug):
    target, ref = request.args.get("target", ""), request.args.get("ref", "")
    expires, signature = request.args.get("expires", ""), request.args.get("sig", "")
    try:
        if not int(time.time()) <= int(expires) <= time.time() + 3605:
            abort(403)
    except ValueError:
        abort(403)
    expected = hmac.new(proxy_secret(), f"{slug}\n{target}\n{ref}\n{expires}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        abort(403)
    if urllib.parse.urlsplit(target).scheme not in ("https", "http"):
        abort(400)
    return target, ref


def rewrite_playlist(text, base, slug, ref):
    lines = []
    variant = False
    def uri(value, playlist=False):
        target = urllib.parse.urljoin(base, value)
        if urllib.parse.urlsplit(target).scheme not in ("http", "https"):
            raise ValueError("Unsupported HLS URI")
        return signed_target(slug, target, ref, playlist)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(uri(stripped, variant or ".m3u8" in urllib.parse.urlsplit(stripped).path))
            variant = False
        else:
            playlist_tag = stripped.startswith(("#EXT-X-MEDIA:", "#EXT-X-I-FRAME-STREAM-INF:", "#EXT-X-RENDITION-REPORT:"))
            lines.append(re.sub(r'URI="([^"\n]+)"', lambda m: 'URI="' + uri(m.group(1), playlist_tag) + '"', line))
            if stripped.startswith("#EXT-X-STREAM-INF:"):
                variant = True
    return "\n".join(lines)


def upstream_headers(ref):
    headers = {"User-Agent": HEADERS_BASE["User-Agent"]}
    if ref:
        headers["Referer"] = ref
        parsed = urllib.parse.urlsplit(ref)
        headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
    return headers


def playlist_response(target, ref, slug):
    with HLS_SESSION.get(target, headers=upstream_headers(ref), timeout=(5, 12)) as upstream:
        upstream.raise_for_status()
        if not upstream.text.lstrip().startswith("#EXTM3U"):
            raise ValueError("Invalid HLS playlist")
        text = upstream.text
        prepare_recent_media(text, upstream.url, ref)
        response = Response(rewrite_playlist(text, upstream.url, slug, ref), content_type="application/vnd.apple.mpegurl")
        response.headers["Cache-Control"] = "no-store"
        return response


def download_complete_media(target, ref):
    # A separate session per thread avoids sharing mutable requests state and
    # the old adapter's repeated long retries while a live buffer drains.
    if not hasattr(MEDIA_DOWNLOADS, "session"):
        MEDIA_DOWNLOADS.session = requests.Session()
    started = time.monotonic()
    for attempt in range(2):
        try:
            with MEDIA_DOWNLOADS.session.get(target, headers=upstream_headers(ref), stream=True, timeout=(2, 3)) as response:
                return complete_media(response, deadline=max(1, 10 - (time.monotonic() - started)))
        except UpstreamHTTPError as error:
            if error.status not in (408, 429, 500, 502, 503, 504) or attempt or time.monotonic() - started > 6:
                raise
        except (requests.RequestException, OSError):
            if attempt or time.monotonic() - started > 6:
                raise
            # Retry a broken/truncated transfer on a fresh connection. Never
            # change the source or retry a denied authorization here.
            MEDIA_DOWNLOADS.session.close()
            MEDIA_DOWNLOADS.session = requests.Session()


def prepare_recent_media(text, base, ref):
    if "#EXT-X-STREAM-INF" in text or "#EXT-X-BYTERANGE" in text:
        return
    origin = urllib.parse.urlsplit(base)
    targets = [urllib.parse.urljoin(base, line.strip()) for line in text.splitlines()
               if line.strip() and not line.startswith("#")]
    for target in targets[-3:]:
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme not in ("https", "http") or parsed.netloc != origin.netloc:
            continue
        MEDIA_CACHE.prepare((target, ref), lambda target=target: download_complete_media(target, ref))


def source_status(slug, status, detail):
    try:
        name = TR_CHANNELS.get(slug, {}).get("name") or next(
            (ch.get("name", slug) for event in schedule.events for ch in event.get("channels", []) if ch.get("slug") == slug), slug)
        SOURCE_REPORTS.submit(slug, status, detail, name)
    except sqlite3.Error:
        # Diagnostics must never prevent playback when the database is busy.
        app.logger.warning("No se pudo registrar el estado de la señal")


@app.route("/api/playback/<slug>")
def playback_session(slug):
    """Pin one signed playlist to this viewer instead of rotating resolver caches."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", slug):
        return jsonify({"error": "Canal no válido."}), 400
    if request.args.get("refresh") == "1":
        STREAM_RESOLVER_CACHE.pop(slug, None)
    data = resolve_tarjetarojatv_stream(slug) or {}
    if not data.get("stream_url"):
        return jsonify({"error": "La señal no está disponible."}), 503
    response = jsonify({"url": signed_target(slug, data["stream_url"], data.get("iframe_url", ""), True)})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/stream/live/<slug>/master.m3u8")
def hls_proxy_master(slug):
    data = resolve_tarjetarojatv_stream(slug) or {}
    for attempt in range(2):
        if not data.get("stream_url"):
            source_status(slug, "failed", "El origen no publicó una señal reproducible.")
            abort(503)
        try:
            return playlist_response(data["stream_url"], data.get("iframe_url", ""), slug)
        except (requests.RequestException, ValueError):
            if not attempt:
                STREAM_RESOLVER_CACHE.pop(slug, None)
                data = resolve_tarjetarojatv_stream(slug) or {}
    source_status(slug, "failed", "No se pudo descargar la lista de reproducción del origen.")
    abort(502)


@app.route("/stream/live/<slug>/sub.m3u8")
def hls_proxy_sub(slug):
    target, ref = verified_target(slug)
    try:
        return playlist_response(target, ref, slug)
    except requests.HTTPError as error:
        status = getattr(error.response, "status_code", 0)
        source_status(slug, "failed", "El origen rechazó la lista de reproducción.")
        response = jsonify({"error": "La señal debe volver a conectarse."})
        response.status_code = status if status in (401, 403) else 502
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Video-Error"] = "source-auth" if status in (401, 403) else "source-http"
        return response
    except (requests.RequestException, ValueError):
        source_status(slug, "failed", "No se pudo descargar una lista de reproducción de la señal.")
        abort(502)


@app.route("/stream/live/<slug>/segment.ts")
def hls_proxy_segment(slug):
    target, ref = verified_target(slug)
    if not request.headers.get("Range"):
        try:
            media = MEDIA_CACHE.get((target, ref), lambda: download_complete_media(target, ref))
        except UpstreamHTTPError as error:
            source_status(slug, "failed", "El origen rechazó el fragmento de video.")
            response = jsonify({"error": "La señal debe volver a conectarse."})
            response.status_code = error.status if error.status in (401, 403) else 502
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Video-Error"] = "source-auth" if error.status in (401, 403) else "source-http"
            return response
        except (requests.RequestException, OSError, ValueError):
            source_status(slug, "failed", "No se pudo completar el fragmento de video.")
            response = jsonify({"error": "No se pudo descargar el fragmento."})
            response.status_code = 502
            response.headers["Cache-Control"] = "no-store"
            return response
        source_status(slug, "ok", "El origen de la señal está entregando datos.")
        response = Response(media.body, content_type=media.content_type)
        response.headers["Cache-Control"] = "private, max-age=30"
        response.headers["X-Video-Delivery"] = "prepared-v4"
        return response
    headers = upstream_headers(ref)
    if request.headers.get("Range"):
        headers["Range"] = request.headers["Range"]
    try:
        upstream = HLS_SESSION.get(target, headers=headers, stream=True, timeout=(5, 15))
        content_type = upstream.headers.get("Content-Type", "").lower()
        if content_type.startswith(("text/html", "application/xhtml+xml", "application/json")):
            source_status(slug, "failed", "El origen devolvió una página o un error en lugar de la señal.")
            upstream.close()
            abort(502)
        if upstream.status_code not in (200, 206):
            source_status(slug, "failed", f"El origen respondió HTTP {upstream.status_code} al solicitar video.")
            upstream.close()
            abort(502)
    except requests.RequestException:
        source_status(slug, "failed", "Se perdió la conexión con el origen de video.")
        abort(502)
    def generate():
        received = False
        try:
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    if not received:
                        source_status(slug, "ok", "El origen de la señal está entregando datos.")
                        received = True
                    yield chunk
            if not received:
                source_status(slug, "failed", "El origen entregó una respuesta de video vacía.")
        except requests.RequestException:
            source_status(slug, "failed", "La descarga de video se interrumpió.")
            raise
        finally:
            upstream.close()
    response = Response(stream_with_context(generate()), status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/octet-stream"))
    for key in ("Content-Range", "Accept-Ranges", "Content-Length"):
        if key in upstream.headers and not (key == "Content-Length" and upstream.headers.get("Content-Encoding")):
            response.headers[key] = upstream.headers[key]
    response.headers["Cache-Control"] = "private, max-age=30"
    response.call_on_close(upstream.close)
    return response


@app.route("/embed/<slug>")
def embed_view(slug):
    clean_slug = slug.strip().lower()
    if request.args.get("refresh") == "1":
        STREAM_RESOLVER_CACHE.pop(clean_slug, None)
    stream_data = resolve_tarjetarojatv_stream(clean_slug) or {}
    stream_url = stream_data.get("stream_url")
    if not stream_url:
        source_status(clean_slug, "failed", "El origen no publicó una señal reproducible.")
    response = app.make_response(render_template(
        "native_embed.html", stream_url=f"/stream/live/{clean_slug}/master.m3u8" if stream_url else "",
        channel_name=TR_CHANNELS.get(clean_slug, {}).get("name", clean_slug.upper()), slug=clean_slug))
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

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
