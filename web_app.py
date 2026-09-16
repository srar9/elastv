# -*- coding: utf-8 -*-
import os
import sys
import time
import re
import json
import html
import requests
from flask import Flask, render_template, request, jsonify, abort

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
    "goltv": {"slug": "goltv", "name": "GolTV HD", "category": "otros"},
    "dazn1": {"slug": "dazn1", "name": "DAZN 1 España", "category": "otros"},
    "dazn2": {"slug": "dazn2", "name": "DAZN 2 España", "category": "otros"},
    "laligatv": {"slug": "laligatv", "name": "LaLiga TV Bar", "category": "otros"},
    "movistar-laliga": {"slug": "movistar-laliga", "name": "Movistar LaLiga HD", "category": "otros"},
    "movistar-campeones": {"slug": "movistar-campeones", "name": "Movistar Liga de Campeones", "category": "otros"},
}

CATEGORIES_META = {
    "espn": {"name": "ESPN Suite", "icon": "tv"},
    "fox": {"name": "Fox Sports", "icon": "trophy"},
    "max": {"name": "MAX (Champions)", "icon": "sparkles"},
    "dsports": {"name": "DIRECTV Sports", "icon": "radio"},
    "disney": {"name": "Disney+ / Star+", "icon": "star"},
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
                events.append({
                    "time": ev_time,
                    "competition": ev_comp,
                    "match": match_name,
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

    page_url = f"https://tarjetaroja.my/stream/{clean_slug}"
    try:
        r_page = requests.get(page_url, headers=HEADERS_BASE, timeout=8)
        if r_page.status_code != 200:
            return None

        m_if = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r_page.text, re.IGNORECASE)
        if not m_if:
            return None

        iframe_url = m_if.group(1)
        if iframe_url.startswith("//"):
            iframe_url = "https:" + iframe_url

        data = {
            "slug": clean_slug,
            "page_url": page_url,
            "iframe_url": iframe_url
        }
        STREAM_RESOLVER_CACHE[clean_slug] = {"timestamp": now, "data": data}
        return data
    except Exception as e:
        print(f"Error resolving stream for {clean_slug}:", e)
        return None

def get_unique_channels():
    seen = set()
    unique = []
    for k, v in TR_CHANNELS.items():
        if v["slug"] not in seen:
            seen.add(v["slug"])
            unique.append({
                "slug": v["slug"],
                "name": v["name"],
                "category": v["category"]
            })
    return sorted(unique, key=lambda x: (x["category"], x["name"]))

# ==============================================================================
# RUTAS WEB PRINCIPALES
# ==============================================================================
@app.route("/")
def index():
    events = fetch_tarjetaroja_schedule()
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
        # Fallback slug directo
        channel_info = {
            "slug": clean_slug,
            "name": clean_slug.upper().replace("-", " "),
            "category": "deportes"
        }

    stream_data = resolve_tarjetaroja_stream(clean_slug)
    iframe_url = stream_data["iframe_url"] if stream_data else None

    # Canales recomendados para el menú inferior
    all_unique = get_unique_channels()
    recommended = [c for c in all_unique if c["slug"] != clean_slug][:12]

    return render_template(
        "player.html",
        channel=channel_info,
        iframe_url=iframe_url,
        recommended=recommended,
        active_page="player"
    )

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
    return jsonify({"status": "ok", "service": "tarjetaroja-web-live"})

# ==============================================================================
# INICIO DEL SERVIDOR LOCAL O RAILWAY
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Iniciando Tarjeta Roja Web en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
