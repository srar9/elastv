"""Resolve public static player links from user-selected channel directory and tarjetadigital.club.

Only follows known player hosts with bounded traversal. No challenges or authentication mechanisms bypassed.
"""
import html
import re
from urllib.parse import urljoin, urlsplit, parse_qs
import requests

CHANNEL_PAGES = {"espn": "espn-1", "espn1": "espn-1", "espn2": "espn-2", "espn3": "espn-3"}
CHANNEL_PAGES.update({
    "telemundo": "telemundo", "tycsports": "tyc-sports", "dsports": "directv-sports",
    "dsports2": "directv-sports-2", "dsportsplus": "directv-sports-plus", "tudn": "tudn",
    "winsports": "win-sports", "winsports2": "win-sports-plus", "foxsports": "fox-sports-1",
    "foxsports2": "fox-sports-2", "foxsports3": "fox-sports-3", "foxsportspremium": "fox-sports-premium",
    "tntsports": "tnt-sports-argentina", "espnpremium": "espn-premium",
    "espndeportes": "espn-deportes", "liga1max": "liga-1-max", "movistardeportes": "movistar-deportes",
})

TARJETA_DIGITAL_CHANNELS = {
    # ESPN Suite
    "espn": "espn",
    "espn1": "espn",
    "espn-1": "espn",
    "espn2": "espn2",
    "espn-2": "espn2",
    "espn3": "espn3",
    "espn-3": "espn3",
    "espn4": "espn4",
    "espn-4": "espn4",
    "espn5": "espn5",
    "espn-5": "espn5",
    "espn6": "espn6",
    "espn-6": "espn6",
    "espn7": "espn7",
    "espn-7": "espn7",
    "espnpremium": "espnpremium",
    "espn-premium": "espnpremium",
    "espnextra": "espnextra",
    "espn-extra": "espnextra",
    "espnmx": "espnmx",
    "espn-mx": "espnmx",
    "espn2mx": "espn2mx",
    "espn-2mx": "espn2mx",
    "espn3mx": "espn3mx",
    "espn-3mx": "espn3mx",
    "espn4mx": "espn4mx",
    # Fox Sports Suite
    "foxsports": "foxsports",
    "fox-sports": "foxsports",
    "foxsports1": "foxsports",
    "fox-sports-1": "foxsports",
    "fox1": "foxsports",
    "fox": "foxsports",
    "foxsports2": "foxsports2",
    "fox-sports-2": "foxsports2",
    "fox2": "foxsports2",
    "foxsports3": "foxsports3",
    "fox-sports-3": "foxsports3",
    "fox3": "foxsports3",
    "foxsportsmx": "foxsportsmx",
    "fox-sports-mx": "foxsportsmx",
    "foxsports2mx": "foxsports2mx",
    "fox-sports-2mx": "foxsports2mx",
    "foxsports3mx": "foxsports3mx",
    "fox-sports-3mx": "foxsports3mx",
    "foxsportspremium": "foxsportspremium",
    "fox-sports-premium": "foxsportspremium",
    "foxpremium": "foxsportspremium",
    # DIRECTV Sports / DSports
    "dsports": "dsports",
    "dsports1": "dsports",
    "dsports-1": "dsports",
    "dsports2": "dsports2",
    "dsports-2": "dsports2",
    "dsportsplus": "dsportsplus",
    "dsports-plus": "dsportsplus",
    "dsports3": "dsportsplus",
    # Latam & Fútbol Internacional
    "tyc": "tycsports",
    "tycsports": "tycsports",
    "tyc-sports": "tycsports",
    "tntsports": "tntsports",
    "tnt-sports": "tntsports",
    "winplus": "winplus",
    "win-plus": "winplus",
    "winsports": "winsports",
    "win-sports": "winsports",
    "winsports2": "winplus",
    "liga1max": "liga1max",
    "liga-1-max": "liga1max",
    "movistardeportes": "movistardeportes",
    "movistar-deportes": "movistardeportes",
    "laligatv": "laligatv",
    "laliga-tv": "laligatv",
    "dazn1": "dazn1",
    "dazn-1": "dazn1",
    # TUDN & ViX
    "tudn": "tudn",
    "tudn_mx": "tudn_mx",
    "tudnmx": "tudn_mx",
    "tudn-mx": "tudn_mx",
    "vix1": "vix1",
    "vix-1": "vix1",
    "max1": "max1",
    "max-1": "max1",
    # TV Abierta
    "telefe": "telefe",
    "canal5": "canal5",
    "canal-5": "canal5",
    "azteca7": "azteca7",
    "azteca-7": "azteca7",
}

CHANNEL_NAMES = {
    "espn": "ESPN 1", "espn2": "ESPN 2", "espn3": "ESPN 3", "telemundo": "Telemundo",
    "tycsports": "TyC Sports", "dsports": "DSports", "dsports2": "DSports 2", "dsportsplus": "DSports+",
    "tudn": "TUDN", "winsports": "Win Sports", "winsports2": "Win Sports+", "foxsports": "Fox Sports 1",
    "foxsports2": "Fox Sports 2", "foxsports3": "Fox Sports 3", "foxsportspremium": "Fox Sports Premium",
    "tntsports": "TNT Sports Argentina", "espnpremium": "ESPN Premium", "espndeportes": "ESPN Deportes",
    "liga1max": "Liga 1 Max", "movistardeportes": "Movistar Deportes",
    # Canales Tarjeta Digital
    "espnmx": "ESPN 1 México (Tarjeta Digital)",
    "espn2mx": "ESPN 2 México (Tarjeta Digital)",
    "espn3mx": "ESPN 3 México (Tarjeta Digital)",
    "foxsportsmx": "FOX Sports 1 México (Tarjeta Digital)",
    "foxsports2mx": "FOX Sports 2 México (Tarjeta Digital)",
    "foxsports3mx": "FOX Sports 3 México (Tarjeta Digital)",
    "foxsportspremium": "FOX Sports Premium (Tarjeta Digital)",
    "tudn_mx": "TUDN México (Tarjeta Digital)",
}

PLAYER_HOSTS = {
    "rojadirectatvmas.net", "www.rojadirectatvmas.net",
    "rojadirectatvplay.org", "www.rojadirectatvplay.org",
    "tarjetadigital.club", "www.tarjetadigital.club",
    "la18hd.su", "www.la18hd.su",
    "tvf90.com", "www.tvf90.com"
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
}


def extract_hls(page):
    normalized = html.unescape(page.replace(r"\/", "/"))
    # 1. Clappr src o reproductor embebido JSON
    m_src = re.search(r'''["']src["']\s*:\s*["']([^"']+\.m3u8(?:\?[^"']*)?)["']''', normalized)
    if m_src:
        return m_src.group(1)

    # 2. playbackURL variable JS
    playback = re.search(r'''\b(?:var|let|const)\s+playbackURL\s*=\s*["']([^"']+)["']''', normalized)
    candidates = [playback.group(1)] if playback else []

    # 3. M3U8 directo en la respuesta
    candidates += re.findall(r'''["']((?:https?:)?//[^\s"'<>]+\.m3u8(?:\?[^\s"'<>]*)?)["']''', normalized)
    for candidate in candidates:
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        parsed = urlsplit(candidate)
        if parsed.scheme in ("http", "https") and parsed.hostname and ".m3u8" in parsed.path.lower():
            return candidate
    return None


def resolve_la18hd(stream_slug):
    """Resuelve la señal directa HLS desde la18hd.su con headers del navegador."""
    url = f"https://la18hd.su/vivo/canal.php?stream={stream_slug}"
    headers = dict(BROWSER_HEADERS)
    headers["Referer"] = "https://tarjetadigital.club/"
    try:
        resp = requests.get(url, headers=headers, timeout=(6, 10))
        if resp.status_code == 200:
            stream = extract_hls(resp.text)
            if stream:
                return stream, url, "OK (Tarjeta Digital / la18hd)"
    except Exception as exc:
        return None, None, f"Tarjeta Digital err: {type(exc).__name__}"
    return None, None, "Tarjeta Digital: sin señal HLS"


def resolve_tarjeta_digital(input_str):
    """Resuelve canales o transmisiones provenientes de https://tarjetadigital.club/."""
    clean = str(input_str).strip()
    if not clean:
        return None, None, "Vacío"

    # URL directa de tarjetadigital.club
    if "tarjetadigital.club" in clean:
        m_ch = re.search(r"/en-vivo/([a-zA-Z0-9_\-]+)", clean)
        if m_ch:
            clean = m_ch.group(1).lower()
        else:
            parsed = urlsplit(clean)
            inner_url = parse_qs(parsed.query).get("url", [""])[0]
            if inner_url:
                return resolve_player(inner_url)

    # URL directa de la18hd.su
    if "la18hd.su" in clean:
        parsed = urlsplit(clean)
        stream_param = parse_qs(parsed.query).get("stream", [""])[0]
        if stream_param:
            return resolve_la18hd(stream_param)

    # Slugs de canales de Tarjeta Digital
    slug_key = clean.lower().replace("_", "-")
    if slug_key in TARJETA_DIGITAL_CHANNELS:
        return resolve_la18hd(TARJETA_DIGITAL_CHANNELS[slug_key])
    alt_key = clean.lower().replace("-", "")
    if alt_key in TARJETA_DIGITAL_CHANNELS:
        return resolve_la18hd(TARJETA_DIGITAL_CHANNELS[alt_key])

    # Búsqueda dinámica directa en la18hd.su
    direct_slug = clean.lower().replace("-", "").replace("_", "")
    if re.match(r'^[a-z0-9]+$', direct_slug):
        st, u, msg = resolve_la18hd(direct_slug)
        if st:
            return st, u, msg

    return None, None, "No es canal de Tarjeta Digital"


def resolve_tvf90(stream_slug):
    """Resuelve canales desde tvf90.com (CDN ftlly.com), altamente compatible con servidores cloud."""
    clean = str(stream_slug).strip().lower()
    if not clean:
        return None, None, "Slug vacío"

    endpoints = [
        f"https://tvf90.com/5.php?stream={clean}",
        f"https://tvf90.com/plus1.php?stream={clean}",
    ]
    alt = clean.replace("-", "").replace("_", "")
    if alt != clean:
        endpoints.append(f"https://tvf90.com/5.php?stream={alt}")

    for test_url in endpoints:
        stream, ref, msg = resolve_player(test_url)
        if stream:
            return stream, ref, "OK (tvf90 / ftlly)"

    return None, None, "tvf90: sin señal"


def resolve_roja_source(slug):
    page = CHANNEL_PAGES.get(slug)
    if not page:
        return None, None, "Sin alias en el directorio nuevo"
    return resolve_player(f"https://rojadirectatvplay.org/en-vivo/{page}")


def resolve_player(url):
    pending = [(url, "https://tarjetadigital.club/", 0)]
    visited = set()
    failures = []
    while pending and len(visited) < 8:
        url, referer, depth = pending.pop(0)
        host = urlsplit(url).hostname
        if url in visited or host not in PLAYER_HOSTS:
            continue
        visited.add(url)

        headers = dict(BROWSER_HEADERS)
        headers["Referer"] = referer

        # Si el destino es la18hd.su y tiene stream parameter
        if "la18hd.su" in url:
            stream_param = parse_qs(urlsplit(url).query).get("stream", [""])[0]
            if stream_param:
                st, u, msg = resolve_la18hd(stream_param)
                if st:
                    return st, u, msg

        try:
            response = requests.get(url, headers=headers, timeout=(6, 10), allow_redirects=False)
        except requests.RequestException as exc:
            failures.append(type(exc).__name__)
            continue

        if response.status_code in (301, 302, 303, 307, 308):
            if depth < 4:
                loc = response.headers.get("Location", "")
                target = urljoin(url, loc)
                pending.append((target, referer, depth + 1))
            continue

        if response.status_code != 200:
            failures.append(f"HTTP {response.status_code}")
            continue

        stream = extract_hls(response.text)
        if stream:
            return stream, url, "OK (HLS detectado)"

        if depth < 4:
            for iframe in re.findall(r'''<iframe\b[^>]*\bsrc\s*=\s*["']([^"']+)["']''', response.text, re.I):
                target = urljoin(url, html.unescape(iframe))
                if urlsplit(target).hostname in PLAYER_HOSTS:
                    pending.append((target, url, depth + 1))

    return None, None, "Directorio: " + (", ".join(failures) if failures else "sin enlace HLS visible")
