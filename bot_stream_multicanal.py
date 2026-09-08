import os
import sys
import time
import json
import re
import html
import subprocess
import threading
import requests
import datetime

# ==============================================================================
# CONFIGURACIÓN GENERAL DEL BOT Y SERVIDOR IPTV DEDICADO (XTREAM CODES)
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8988332685:AAF-6ulB_iNjIl5QeGxGQx8ehiZjMNeNQfE")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CONFIG_FILE = "stream_config.json"

# Servidor IPTV dedicado (Xtream Codes - Máxima estabilidad 0% lag)
IPTV_SERVER = os.environ.get("IPTV_SERVER", "http://qpyzyvkm.cdngold.info")
IPTV_USER = os.environ.get("IPTV_USER", "96PX3Q2J")
IPTV_PASS = os.environ.get("IPTV_PASS", "24V7N2A1")
IPTV_MAX_CONNECTIONS = int(os.environ.get("IPTV_MAX_CONNECTIONS", 3))
HEADERS_IPTV = {"User-Agent": "IPTVSmartersPro"}

# Directorio verificado de Canales IPTV (Enlace directo .ts de alta velocidad)
IPTV_DIRECT_CHANNELS = {
    # Suite ESPN
    "espn": {"id": "30326", "name": "ESPN 1 HD (Sur/Argentina)"},
    "espn2": {"id": "33893", "name": "ESPN 2 HD"},
    "espn3": {"id": "30328", "name": "ESPN 3 HD"},
    "espn4": {"id": "1201550", "name": "ESPN 4 HD"},
    "espnpremium": {"id": "4883", "name": "ESPN Premium HD (Argentina)"},
    "espnextra": {"id": "30329", "name": "ESPN Extra HD"},
    "espn-deportes": {"id": "32038", "name": "ESPN Deportes USA"},
    
    # Directv Sports (DSPORTS)
    "dsports": {"id": "33933", "name": "DIRECTV Sports 1 HD (DSports)"},
    "dsports2": {"id": "33932", "name": "DIRECTV Sports 2 HD (DSports 2)"},
    "dsportsplus": {"id": "33931", "name": "DIRECTV Sports+ HD (DSports+)"},
    
    # Argentina & Conmebol & Chile
    "tycsports": {"id": "30365", "name": "TyC Sports HD (Argentina)"},
    "tntsports": {"id": "30362", "name": "TNT Sports HD (Argentina)"},
    "tntsportschile": {"id": "97901", "name": "TNT Sports Chile HD"},
    
    # Fox Sports Suite
    "foxsports": {"id": "4880", "name": "Fox Sports 1 (Argentina)"},
    "foxsports2": {"id": "4881", "name": "Fox Sports 2 (Argentina)"},
    "foxsports3": {"id": "4882", "name": "Fox Sports 3 (Argentina)"},
    "foxone": {"id": "4880", "name": "Fox Sports 1 (Argentina)"},
    "foxpremium": {"id": "1024956", "name": "Fox Sports Premium HD"},

    # Colombia
    "winplus": {"id": "33945", "name": "Win Sports+ HD (Colombia)"},
    "winsports": {"id": "33944", "name": "Win Sports Colombia HD"},

    # España & LaLiga & Champions
    "movistarlaliga": {"id": "30974", "name": "Movistar LaLiga HD"},
    "daznlaliga": {"id": "224832", "name": "DAZN LaLiga 1 FHD"},
    "daznlaliga2": {"id": "224831", "name": "DAZN LaLiga 2 FHD"},
    "hypermotion1": {"id": "6560", "name": "LaLiga TV Hypermotion FHD"},
    "campeones": {"id": "33682", "name": "Movistar Liga de Campeones 1 FHD"},
    
    # Premier League (UK & USA)
    "skysportspremier": {"id": "29016", "name": "Sky Sports Premier League FHD"},
    "skysportsmain": {"id": "1256711", "name": "Sky Sports Main Events FHD"},
    "skysportsfootball": {"id": "29018", "name": "Sky Sports Football FHD"},
    "nbcsports": {"id": "18849", "name": "NBC Sports FHD"},
    "usanetwork": {"id": "2213", "name": "USA Network HD"},

    # Perú & México & USA
    "liga1max": {"id": "1067841", "name": "Liga 1 MAX (Perú)"},
    "golperu": {"id": "29848", "name": "Gol Perú HD"},
    "tudn_usa": {"id": "31987", "name": "TUDN USA HD"},
    "vix1": {"id": "985726", "name": "ViX+ TUDN Deportes 1"},
    "vix2": {"id": "985722", "name": "ViX+ Zona TUDN"}
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "stream_key": os.environ.get("STREAM_KEY", "3936015063:nG8N_no46UfNuA6jXewiag")
    }

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

CONFIG = load_config()
ADMIN_USER_ID = None
active_streams = {}
stream_lock = threading.Lock()

# ==============================================================================
# RESOLVEDOR DE CANALES Y EVENTOS (100% IPTV DEDICADO)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def resolve_channel_input(raw_input):
    clean = str(raw_input).strip().lower()
    
    if clean in IPTV_DIRECT_CHANNELS:
        return clean, IPTV_DIRECT_CHANNELS[clean]["name"]

    # ESPN
    if "espn" in clean:
        if "prem" in clean:
            return "espnpremium", "ESPN Premium HD (Argentina)"
        if "deportes" in clean or "usa" in clean:
            return "espn-deportes", "ESPN Deportes USA"
        if "extra" in clean:
            return "espnextra", "ESPN Extra HD"
        if "4" in clean:
            return "espn4", "ESPN 4 HD"
        if "3" in clean:
            return "espn3", "ESPN 3 HD"
        if "2" in clean:
            return "espn2", "ESPN 2 HD"
        return "espn", "ESPN 1 HD (Sur/Argentina)"

    # DIRECTV Sports / DSports
    if "dsport" in clean or "directv" in clean or "dtv" in clean:
        if "plus" in clean or "+" in clean:
            return "dsportsplus", "DIRECTV Sports+ HD"
        if "2" in clean:
            return "dsports2", "DIRECTV Sports 2 HD"
        return "dsports", "DIRECTV Sports 1 HD (DSports)"

    # Fox Sports
    if "fox" in clean:
        if "prem" in clean:
            return "foxpremium", "Fox Sports Premium HD"
        if "3" in clean:
            return "foxsports3", "Fox Sports 3 (Argentina)"
        if "2" in clean:
            return "foxsports2", "Fox Sports 2 (Argentina)"
        return "foxsports", "Fox Sports 1 (Argentina)"

    # Argentina
    if "tyc" in clean:
        return "tycsports", "TyC Sports HD (Argentina)"
    if "tnt" in clean:
        if "chile" in clean:
            return "tntsportschile", "TNT Sports Chile HD"
        return "tntsports", "TNT Sports HD (Argentina)"

    # Colombia
    if "win" in clean:
        if "+" in clean or "plus" in clean:
            return "winplus", "Win Sports+ HD (Colombia)"
        return "winsports", "Win Sports Colombia HD"

    # España
    if "movistar" in clean or "laliga" in clean or "la liga" in clean:
        if "hyper" in clean or "segunda" in clean:
            return "hypermotion1", "LaLiga TV Hypermotion FHD"
        if "champ" in clean or "campeon" in clean:
            return "campeones", "Movistar Liga de Campeones 1 FHD"
        return "movistarlaliga", "Movistar LaLiga HD"
        
    if "dazn" in clean:
        if "2" in clean:
            return "daznlaliga2", "DAZN LaLiga 2 FHD"
        return "daznlaliga", "DAZN LaLiga 1 FHD"

    if "sky" in clean or "premier" in clean:
        return "skysportspremier", "Sky Sports Premier League FHD"

    if "liga 1" in clean or "liga1" in clean:
        return "liga1max", "Liga 1 MAX (Perú)"

    if "gol" in clean and "peru" in clean:
        return "golperu", "Gol Perú HD"

    if "tudn" in clean:
        return "tudn_usa", "TUDN USA HD"

    if "vix" in clean:
        if "2" in clean:
            return "vix2", "ViX+ Zona TUDN"
        return "vix1", "ViX+ TUDN Deportes 1"

    return clean, f"Canal [{clean}]"

def smart_match_channel_resolver(title, channels_raw=None):
    """
    Asigna ÚNICAMENTE canales oficiales de IPTV verificados para cada partido / evento.
    """
    title_lower = title.lower()
    channels = []
    
    # 1. Premier League (Inglaterra)
    if "premier" in title_lower or any(team in title_lower for team in ["arsenal", "aston villa", "chelsea", "liverpool", "manchester", "tottenham", "newcastle", "brighton", "west ham", "fulham", "wolves", "everton"]):
        channels.append({"id": "espn", "name": "ESPN 1 HD (Sur/Argentina)"})
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        channels.append({"id": "skysportspremier", "name": "Sky Sports Premier League FHD"})
        channels.append({"id": "daznlaliga", "name": "DAZN / M+ Deportes FHD"})
        return channels

    # 2. LaLiga Española
    if "laliga" in title_lower or "espana" in title_lower or any(team in title_lower for team in ["barcelona", "real madrid", "atletico", "rayo vallecano", "sevilla", "betis", "valencia", "villarreal", "athletic", "sociedad", "girona"]):
        channels.append({"id": "movistarlaliga", "name": "Movistar LaLiga HD"})
        channels.append({"id": "daznlaliga", "name": "DAZN LaLiga 1 FHD"})
        channels.append({"id": "daznlaliga2", "name": "DAZN LaLiga 2 FHD"})
        channels.append({"id": "espn-deportes", "name": "ESPN Deportes USA"})
        return channels

    # 3. Champions League / Europa League / Conference
    if "champions" in title_lower or "europa league" in title_lower or "conference" in title_lower:
        channels.append({"id": "campeones", "name": "Movistar Liga de Campeones 1 FHD"})
        channels.append({"id": "espn", "name": "ESPN 1 HD"})
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        channels.append({"id": "foxsports", "name": "Fox Sports 1 (Argentina)"})
        return channels

    # 4. Liga Profesional Argentina / Copa Argentina
    if any(k in title_lower for k in ["argentina", "boca", "river", "racing", "san lorenzo", "independiente", "velez", "rosario central", "newell", "talleres", "estudiantes", "gimnasia", "huracan"]):
        channels.append({"id": "espnpremium", "name": "ESPN Premium HD (Argentina)"})
        channels.append({"id": "tntsports", "name": "TNT Sports HD (Argentina)"})
        channels.append({"id": "tycsports", "name": "TyC Sports HD (Argentina)"})
        return channels

    # 5. Colombia (Liga BetPlay / Copa Colombia)
    if any(k in title_lower for k in ["colombia", "millonarios", "santa fe", "junior", "nacional", "cali", "america de cali", "medellin", "tolima", "bucaramanga", "pereira", "once caldas"]):
        channels.append({"id": "winplus", "name": "Win Sports+ HD (Colombia)"})
        channels.append({"id": "winsports", "name": "Win Sports Colombia HD"})
        return channels

    # 6. Perú (Liga 1 Te Apuesto)
    if any(k in title_lower for k in ["peru", "perú", "alianza lima", "universitario", "sporting cristal", "melgar", "cienciano", "vallejo", "cusco"]):
        channels.append({"id": "liga1max", "name": "Liga 1 MAX (Perú)"})
        channels.append({"id": "golperu", "name": "Gol Perú HD"})
        return channels

    # 7. Chile (Campeonato Nacional)
    if any(k in title_lower for k in ["chile", "colo colo", "universidad de chile", "universidad catolica", "cobreloa", "union espanola", "coquimbo", "audax"]):
        channels.append({"id": "tntsportschile", "name": "TNT Sports Chile HD"})
        return channels

    # 8. México (Liga MX)
    if any(k in title_lower for k in ["mexico", "méxico", "liga mx", "america", "chivas", "cruz azul", "pumas", "tigres", "monterrey", "toluca", "pachuca", "santos"]):
        channels.append({"id": "tudn_usa", "name": "TUDN USA HD"})
        channels.append({"id": "vix1", "name": "ViX+ TUDN Deportes 1"})
        channels.append({"id": "foxpremium", "name": "Fox Sports Premium HD"})
        return channels

    # 9. Tenis (Grand Slams / US Open / ATP)
    if any(k in title_lower for k in ["open", "tenis", "tennis", "alcaraz", "sinner", "djokovic", "us open", "wimbledon", "roland garros", "atp"]):
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        channels.append({"id": "espn3", "name": "ESPN 3 HD"})
        channels.append({"id": "espnextra", "name": "ESPN Extra HD"})
        return channels

    # 10. Fórmula 1 & MotoGP
    if any(k in title_lower for k in ["formula 1", "f1", "gran premio", "motogp", "moto gp", "verstappen", "hamilton", "alonso", "sainz", "leclerc", "norris"]):
        channels.append({"id": "foxsports", "name": "Fox Sports 1 (Argentina)"})
        channels.append({"id": "foxpremium", "name": "Fox Sports Premium HD"})
        channels.append({"id": "daznlaliga", "name": "DAZN 1 FHD"})
        return channels

    # 11. Serie A / Serie B / Copa Italia
    if any(k in title_lower for k in ["serie a", "italia", "juventus", "inter", "milan", "roma", "napoli", "lazio", "atalanta", "fiorentina"]):
        channels.append({"id": "espn", "name": "ESPN 1 HD"})
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        channels.append({"id": "espn3", "name": "ESPN 3 HD"})
        return channels

    # 12. Bundesliga (Alemania)
    if any(k in title_lower for k in ["bundesliga", "bayern", "dortmund", "leverkusen", "leipzig", "frankfurt", "stuttgart"]):
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        channels.append({"id": "espn4", "name": "ESPN 4 HD"})
        channels.append({"id": "campeones", "name": "Movistar Liga de Campeones FHD"})
        return channels

    # 13. Conmebol Libertadores / Sudamericana / Liga de Portugal
    if any(k in title_lower for k in ["libertadores", "sudamericana", "portugal", "benfica", "porto", "sporting lisboa", "flamengo", "palmeiras", "fluminense", "gremio"]):
        channels.append({"id": "dsports", "name": "DIRECTV Sports 1 HD (DSports)"})
        channels.append({"id": "dsports2", "name": "DIRECTV Sports 2 HD (DSports 2)"})
        channels.append({"id": "espn", "name": "ESPN 1 HD"})
        channels.append({"id": "espn2", "name": "ESPN 2 HD"})
        return channels

    # Respaldo general: Canales principales IPTV
    channels.append({"id": "espn", "name": "ESPN 1 HD (Sur/Argentina)"})
    channels.append({"id": "espn2", "name": "ESPN 2 HD"})
    channels.append({"id": "dsports", "name": "DIRECTV Sports 1 HD (DSports)"})
    return channels

def resolve_stream_source(channel_input):
    """
    Resuelve la fuente de transmisión 100% con el servidor IPTV dedicado (Xtream Codes).
    """
    clean_in = clean_arg(channel_input).lower()
    
    # 1. Enlace directo http / https
    if clean_in.startswith("http://") or clean_in.startswith("https://"):
        return clean_in, "User-Agent: IPTVSmartersPro\r\n", "Canal Personalizado", clean_in, True

    # 2. ID numérico directo de IPTV (ej. 33933)
    if clean_in.isdigit():
        iptv_url = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{clean_in}.ts"
        headers_str = "User-Agent: IPTVSmartersPro\r\n"
        return iptv_url, headers_str, f"Canal IPTV #{clean_in}", clean_in, True

    # 3. Canales pre-mapeados de IPTV
    resolved_slug, channel_name = resolve_channel_input(clean_in)
    
    if resolved_slug in IPTV_DIRECT_CHANNELS:
        ch_info = IPTV_DIRECT_CHANNELS[resolved_slug]
        sid = ch_info["id"]
        iptv_url = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{sid}.ts"
        headers_str = "User-Agent: IPTVSmartersPro\r\n"
        return iptv_url, headers_str, ch_info["name"], resolved_slug, True
        
    return None, None, channel_name, resolved_slug, False

# ==============================================================================
# MOTOR DE TRANSMISIÓN FFmpeg (ULTRA BAJA LATENCIA / 0% LAG / AV SYNC)
# ==============================================================================
def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    is_hls = ".m3u8" in source_url
    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-thread_queue_size", "8192",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "15000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "2000000",
        "-probesize", "2000000",
    ]
    if is_hls:
        cmd.extend(["-live_start_index", "-3"])
    else:
        cmd.extend(["-reconnect_at_eof", "1", "-avoid_negative_ts", "make_zero"])

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-vf", "fps=fps=30:round=near,setpts=N/(30*TB),scale=1280:720:flags=fast_bilinear",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-profile:v", "main",
        "-level", "3.1",
        "-threads", "0",
        "-b:v", "1500k",
        "-maxrate", "1800k",
        "-bufsize", "3000k",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-af", "aresample=48000:async=1000:first_pts=0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-bsf:a", "aac_adtstoasc",
        "-avoid_negative_ts", "make_zero",
        "-flush_packets", "1",
        "-max_interleave_delta", "0",
        "-max_muxing_queue_size", "8192",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ])

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    return proc, out_f, log_file

def search_iptv_channels(query, curr_key):
    try:
        url_streams = f"{IPTV_SERVER}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(url_streams, headers=HEADERS_IPTV, timeout=12).json()
        q_clean = query.strip().lower()
        results = []
        for s in r:
            name = s.get("name", "")
            clean_name = re.sub(r'[^\x00-\x7F]+', ' ', name).strip()
            if q_clean in clean_name.lower():
                sid = s.get("stream_id")
                results.append((sid, clean_name))
                if len(results) >= 15:
                    break
        if not results:
            return "🔍 No se encontraron canales en IPTV para: <code>" + html.escape(query) + "</code>"
        
        msg = f"📺 <b>CANALES IPTV ENCONTRADOS ({len(results)}):</b>\n\n"
        for sid, cname in results:
            msg += f"• ⚽ <b>{html.escape(cname)}:</b>\n  <code>/stream {sid} {curr_key}</code>\n\n"
        return msg
    except Exception as e:
        return f"❌ Error buscando canales IPTV: {e}"

def start_single_stream(channel_input, stream_key, chat_id):
    clean_channel_input = clean_arg(channel_input)
    clean_key = clean_arg(stream_key)

    source_url, headers_str, channel_name, resolved_slug, ok = resolve_stream_source(clean_channel_input)
    if not ok or not source_url:
        return False, f"❌ No se encontró el canal <b>{html.escape(clean_channel_input)}</b> en el IPTV. Usa <code>/canales</code> o <code>/buscar &lt;nombre&gt;</code>."
    
    if clean_key.startswith("rtmp://") or clean_key.startswith("rtmps://"):
        destination = clean_key
    else:
        destination = f"rtmps://dc4-1.rtmp.t.me/s/{clean_key}"

    # Manejo inteligente de conexiones simultáneas (hasta IPTV_MAX_CONNECTIONS = 3 pantallas)
    with stream_lock:
        # 1. Si ya existe una transmisión con exactamente esta misma Stream Key, la reemplazamos
        for sid, info in list(active_streams.items()):
            if info["key"] == clean_key:
                info["auto_restart"] = False
                try:
                    info["process"].terminate()
                    info["process"].wait(timeout=2)
                except Exception:
                    try:
                        info["process"].kill()
                    except Exception:
                        pass
                try:
                    if info.get("log_handle"):
                        info["log_handle"].close()
                except Exception:
                    pass
                del active_streams[sid]
                break

        # 2. Si se alcanzó el límite máximo de conexiones simultáneas (3 pantallas), liberar la más antigua
        if len(active_streams) >= IPTV_MAX_CONNECTIONS:
            oldest_sid = sorted(active_streams.keys(), key=lambda x: active_streams[x]["start_time"])[0]
            old_info = active_streams[oldest_sid]
            old_info["auto_restart"] = False
            try:
                old_info["process"].terminate()
                old_info["process"].wait(timeout=2)
            except Exception:
                try:
                    old_info["process"].kill()
                except Exception:
                    pass
            try:
                if old_info.get("log_handle"):
                    old_info["log_handle"].close()
            except Exception:
                pass
            del active_streams[oldest_sid]

    with stream_lock:
        stream_id = str(len(active_streams) + 1)
        while stream_id in active_streams:
            stream_id = str(int(stream_id) + 1)

    proc, out_f, log_file = launch_ffmpeg_process(source_url, headers_str, destination, stream_id)

    time.sleep(3.5)
    poll_res = proc.poll()
    if poll_res is not None:
        try:
            out_f.close()
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-600:]
        except Exception:
            logs = "Sin logs"

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

    with stream_lock:
        active_streams[stream_id] = {
            "channel_input": clean_channel_input,
            "resolved_slug": resolved_slug,
            "channel_name": channel_name,
            "key": clean_key,
            "process": proc,
            "log_handle": out_f,
            "log_file": log_file,
            "chat_id": chat_id,
            "start_time": time.time(),
            "auto_restart": True,
            "restarts": 0
        }

    active_count = len(active_streams)
    return True, (
        f"✅ <b>TRANSMISIÓN EN VIVO INICIADA (#{stream_id})</b>\n\n"
        f"📺 <b>Canal:</b> {html.escape(channel_name)} [<code>{html.escape(resolved_slug)}</code>]\n"
        f"🌐 <b>Servidor:</b> IPTV Dedicado Xtream (0% Lag / HD)\n"
        f"🔑 <b>Stream Key:</b> <code>{clean_key[:12]}...</code>\n"
        f"📡 <b>Pantallas Activas:</b> {active_count}/{IPTV_MAX_CONNECTIONS} simultáneas\n"
        f"⚙️ <b>Audio/Video:</b> 720p @ 30fps (Sincronización AV Bloqueada)\n\n"
        f"🛑 <i>Para detener usa:</i> <code>/stop {stream_id}</code> o <code>/stopall</code>"
    )

def stop_single_stream(stream_id_or_key=None):
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay ninguna transmisión activa en este momento."

        target_sid = None
        if stream_id_or_key:
            clean_val = clean_arg(stream_id_or_key)
            if clean_val in active_streams:
                target_sid = clean_val
            else:
                for sid, info in active_streams.items():
                    if info["key"] == clean_val:
                        target_sid = sid
                        break
        else:
            target_sid = list(active_streams.keys())[0]

        if not target_sid or target_sid not in active_streams:
            return False, f"⚠️ No se encontró ninguna transmisión activa con ese ID o Key."

        info = active_streams[target_sid]
        info["auto_restart"] = False
        try:
            info["process"].terminate()
            info["process"].wait(timeout=2)
        except Exception:
            try:
                info["process"].kill()
            except Exception:
                pass

        try:
            if info.get("log_handle"):
                info["log_handle"].close()
        except Exception:
            pass

        ch_name = info["channel_name"]
        del active_streams[target_sid]
        return True, f"🛑 <b>Transmisión #{target_sid} ({html.escape(ch_name)}) detenida con éxito.</b>"

def stop_all_streams():
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay transmisiones activas para detener."

        count = len(active_streams)
        for sid, info in list(active_streams.items()):
            info["auto_restart"] = False
            try:
                info["process"].terminate()
                info["process"].wait(timeout=2)
            except Exception:
                try:
                    info["process"].kill()
                except Exception:
                    pass
            try:
                if info.get("log_handle"):
                    info["log_handle"].close()
            except Exception:
                pass
            del active_streams[sid]

        return True, f"🛑 <b>Se han detenido las {count} transmisiones activas.</b>"

# ==============================================================================
# SUPERVISOR AUTOMÁTICO DE RECONEXIÓN
# ==============================================================================
def supervisor_thread():
    while True:
        time.sleep(4)
        with stream_lock:
            for sid, info in list(active_streams.items()):
                proc = info.get("process")
                if proc and proc.poll() is not None:
                    if not info.get("auto_restart", False):
                        continue

                    if info.get("restarts", 0) >= 15:
                        continue

                    info["restarts"] = info.get("restarts", 0) + 1
                    slug = info["resolved_slug"]
                    dest = info['key'] if info['key'].startswith(('rtmp://', 'rtmps://')) else f"rtmps://dc4-1.rtmp.t.me/s/{info['key']}"

                    src_url, headers_str, ch_name, res_slug, ok = resolve_stream_source(slug)
                    if ok and src_url:
                        try:
                            if info.get("log_handle"):
                                info["log_handle"].close()
                        except Exception:
                            pass

                        new_proc, new_out_f, log_file = launch_ffmpeg_process(src_url, headers_str, dest, sid)
                        info["process"] = new_proc
                        info["log_handle"] = new_out_f
                        info["log_file"] = log_file

# Iniciar hilo supervisor
t_super = threading.Thread(target=supervisor_thread, daemon=True)
t_super.start()

# ==============================================================================
# AGENDA DINÁMICA DE PARTIDOS (MAPEO 100% A CANALES IPTV)
# ==============================================================================
MATCHES_AGENDA_CACHE = {"timestamp": 0, "messages": []}

def get_live_matches_agenda(curr_key):
    global MATCHES_AGENDA_CACHE
    now = time.time()
    if now - MATCHES_AGENDA_CACHE["timestamp"] < 90 and MATCHES_AGENDA_CACHE["messages"]:
        return MATCHES_AGENDA_CACHE["messages"]

    try:
        leagues = [
            ("esp.1", "🇪🇸 LaLiga"),
            ("eng.1", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"),
            ("ita.1", "🇮🇹 Serie A"),
            ("ger.1", "🇩🇪 Bundesliga"),
            ("arg.1", "🇦🇷 Liga Argentina"),
            ("col.1", "🇨🇴 Liga Colombia"),
            ("mex.1", "🇲🇽 Liga MX"),
            ("uefa.champions", "🏆 Champions League"),
            ("conmebol.libertadores", "🏆 Copa Libertadores"),
            ("uefa.europa", "🏆 Europa League")
        ]

        live_events = []
        upcoming_events = []
        
        for lcode, lname in leagues:
            try:
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lcode}/scoreboard"
                r = requests.get(url, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    for ev in data.get("events", []):
                        comps = ev.get("competitions", [{}])[0]
                        competitors = comps.get("competitors", [])
                        if len(competitors) == 2:
                            c1 = competitors[0].get("team", {}).get("displayName", "")
                            c2 = competitors[1].get("team", {}).get("displayName", "")
                            mname = f"{c1} vs {c2}"
                        else:
                            mname = ev.get("name", "")
                        
                        status_obj = ev.get("status", {}).get("type", {})
                        detail = status_obj.get("detail", "")
                        is_live = status_obj.get("state") == "in"
                        is_pre = status_obj.get("state") == "pre"
                        
                        # Mostrar solo partidos en vivo o programados para hoy
                        if not (is_live or is_pre):
                            continue
                        
                        time_display = ""
                        d_str = ev.get("date", "")
                        if d_str:
                            try:
                                dt = datetime.datetime.fromisoformat(d_str.replace("Z", "+00:00"))
                                dt_local = dt - datetime.timedelta(hours=3) # Horario Sudamérica (UTC-3)
                                time_display = dt_local.strftime("%H:%M")
                            except Exception:
                                time_display = ""

                        full_title = f"{lname}: {mname}"
                        iptv_channels = smart_match_channel_resolver(full_title)
                        if not iptv_channels:
                            continue

                        status_tag = f"🔴 EN VIVO ({detail})" if is_live else f"({detail})"
                        ev_data = {
                            "time": time_display,
                            "title": full_title,
                            "status_tag": status_tag,
                            "channels": iptv_channels
                        }
                        if is_live:
                            live_events.append(ev_data)
                        else:
                            upcoming_events.append(ev_data)
            except Exception:
                pass

        if live_events or upcoming_events:
            messages = []
            current_msg = ""
            
            if live_events:
                current_msg += "🔴 <b>PARTIDOS EN VIVO AHORA MISMO (IPTV DEDICADO - 0% LAG):</b>\n\n"
                for ev in live_events:
                    time_header = f"[{ev['time']}] " if ev['time'] else ""
                    block = f"🏆 <b>{time_header}{html.escape(ev['title'])}</b> {ev['status_tag']}\n"
                    for ch in ev["channels"]:
                        block += f"• 📺 <i>{html.escape(ch['name'])}:</i>\n  <code>/stream {ch['id']} {curr_key}</code>\n"
                    block += "\n"
                    
                    if len(current_msg) + len(block) > 3500:
                        messages.append(current_msg)
                        current_msg = block
                    else:
                        current_msg += block
                        
            if upcoming_events:
                up_header = "\n⏰ <b>PRÓXIMOS PARTIDOS DE HOY (IPTV DEDICADO):</b>\n\n"
                if len(current_msg) + len(up_header) > 3500:
                    messages.append(current_msg)
                    current_msg = up_header
                else:
                    current_msg += up_header
                    
                for ev in upcoming_events:
                    time_header = f"[{ev['time']}] " if ev['time'] else ""
                    block = f"🏆 <b>{time_header}{html.escape(ev['title'])}</b> {ev['status_tag']}\n"
                    for ch in ev["channels"]:
                        block += f"• 📺 <i>{html.escape(ch['name'])}:</i>\n  <code>/stream {ch['id']} {curr_key}</code>\n"
                    block += "\n"
                    
                    if len(current_msg) + len(block) > 3500:
                        messages.append(current_msg)
                        current_msg = block
                    else:
                        current_msg += block
                        
            if current_msg:
                messages.append(current_msg)
                
            MATCHES_AGENDA_CACHE["timestamp"] = now
            MATCHES_AGENDA_CACHE["messages"] = messages
            return messages
    except Exception as e:
        print("Error obteniendo agenda deportiva:", e)

    return get_sports_menu_messages(curr_key)

def get_sports_menu_messages(curr_key):
    msg1 = (
        "🏆 <b>DIRECTORIO DE CANALES DEPORTIVOS (IPTV DEDICADO - 0% LAG)</b>\n\n"
        "🇪🇸 <b>ESPAÑA, LALIGA & CHAMPIONS (FHD):</b>\n"
        f"• ⚽ <b>Movistar LaLiga HD:</b> <code>/stream movistarlaliga {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream daznlaliga {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 2 FHD:</b> <code>/stream daznlaliga2 {curr_key}</code>\n"
        f"• ⚽ <b>LaLiga TV Hypermotion FHD:</b> <code>/stream hypermotion1 {curr_key}</code>\n"
        f"• ⚽ <b>Movistar Liga de Campeones FHD:</b> <code>/stream campeones {curr_key}</code>\n\n"
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE (INGLATERRA):</b>\n"
        f"• ⚽ <b>Sky Sports Premier League FHD:</b> <code>/stream skysportspremier {curr_key}</code>\n"
        f"• ⚽ <b>Sky Sports Main Events FHD:</b> <code>/stream skysportsmain {curr_key}</code>\n"
        f"• ⚽ <b>Sky Sports Football FHD:</b> <code>/stream skysportsfootball {curr_key}</code>\n"
        f"• ⚽ <b>NBC Sports FHD:</b> <code>/stream nbcsports {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA & CONMEBOL (FÚTBOL PROFESIONAL):</b>\n"
        f"• ⚽ <b>ESPN Premium HD (Argentina):</b> <code>/stream espnpremium {curr_key}</code>\n"
        f"• ⚽ <b>TNT Sports HD (Argentina):</b> <code>/stream tntsports {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream tycsports {curr_key}</code>\n"
        f"• ⚽ <b>TNT Sports Chile HD:</b> <code>/stream tntsportschile {curr_key}</code>\n\n"
        "🦊 <b>SUITE FOX SPORTS (HD/FHD):</b>\n"
        f"• ⚽ <b>Fox Sports 1 (Argentina):</b> <code>/stream foxsports {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 2 (Argentina):</b> <code>/stream foxsports2 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 3 (Argentina):</b> <code>/stream foxsports3 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports Premium HD:</b> <code>/stream foxpremium {curr_key}</code>\n"
    )
    msg2 = (
        "🌎 <b>SUITE COMPLETA ESPN (IPTV DEDICADO):</b>\n"
        f"• ⚽ <b>ESPN 1 HD (Sur/Argentina):</b> <code>/stream espn {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream espn2 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream espn3 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream espn4 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN Extra HD:</b> <code>/stream espnextra {curr_key}</code>\n"
        f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>\n\n"
        "🇨🇴 <b>COLOMBIA, PERÚ & DIRECTV (DSPORTS & WIN):</b>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream dsports {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD (DSports 2):</b> <code>/stream dsports2 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports+ HD (DSports+):</b> <code>/stream dsportsplus {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports+ HD (Colombia):</b> <code>/stream winplus {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports Colombia HD:</b> <code>/stream winsports {curr_key}</code>\n"
        f"• ⚽ <b>Liga 1 MAX (Perú):</b> <code>/stream liga1max {curr_key}</code>\n"
        f"• ⚽ <b>Gol Perú HD:</b> <code>/stream golperu {curr_key}</code>\n\n"
        "🇲🇽 <b>MÉXICO & USA:</b>\n"
        f"• 🇲🇽 <b>TUDN USA HD:</b> <code>/stream tudn_usa {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ TUDN Deportes 1:</b> <code>/stream vix1 {curr_key}</code>\n"
        f"• 🇲🇽 <b>ViX+ Zona TUDN:</b> <code>/stream vix2 {curr_key}</code>\n\n"
        "🔍 <i>Buscar entre +27,000 canales IPTV:</i> <code>/buscar &lt;nombre&gt;</code>"
    )
    return [msg1, msg2]

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

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    try:
        curr_key = CONFIG.get("stream_key", "3936015063:nG8N_no46UfNuA6jXewiag")

        if text.startswith("/start") or text.startswith("/ayuda"):
            help_text = (
                "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (IPTV DEDICADO - 0% LAG)</b>\n\n"
                "📋 <b>COMANDOS PRINCIPALES:</b>\n"
                "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver partidos de hoy con enlaces listos en 1-click\n"
                "• <code>/canales</code> o <code>/deportes</code> $\\rightarrow$ Directorio de canales deportivos IPTV\n"
                "• <code>/buscar &lt;nombre&gt;</code> $\\rightarrow$ Buscar entre +27,000 canales IPTV en vivo\n"
                "• <code>/espn</code> $\\rightarrow$ Ver señales de ESPN (1, 2, 3, 4, Extra, Premium)\n"
                "• <code>/stream &lt;CANAL o ID&gt; [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión en directo\n"
                "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n"
                "• <code>/stop [ID]</code> $\\rightarrow$ Detener transmisión activa\n"
                "• <code>/stopall</code> $\\rightarrow$ Detener todas las transmisiones\n"
                f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar Stream Key por defecto\n\n"
                "🌐 <b>Servidor:</b> IPTV Dedicado Xtream Codes (0% Lag / HD / AV Sync)"
            )
            send_msg(chat_id, help_text)

        elif text.startswith("/buscar") or text.startswith("/search"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre del canal o evento&gt;</code>\nEjemplo: <code>/buscar dazn</code> o <code>/buscar espn</code> o <code>/buscar sky sports</code>")
                return
            q = parts[1].strip()
            send_msg(chat_id, f"🔍 <b>Buscando canales IPTV para '{q}'...</b>")
            res_text = search_iptv_channels(q, curr_key)
            send_msg(chat_id, res_text)

        elif text.startswith("/canales") or text.startswith("/deportes") or text.startswith("/menu"):
            msgs = get_sports_menu_messages(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/espn"):
            espn_msg = (
                "📺 <b>DIRECTORIO DE SEÑALES ESPN (IPTV DEDICADO):</b>\n\n"
                "🇦🇷 <b>SEÑALES ESPN (HD & PREMIUM):</b>\n"
                f"• ⚽ <b>ESPN 1 HD (Sur/Argentina):</b> <code>/stream espn {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream espn2 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream espn3 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream espn4 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN Extra HD:</b> <code>/stream espnextra {curr_key}</code>\n"
                f"• ⚽ <b>ESPN Premium HD (Argentina):</b> <code>/stream espnpremium {curr_key}</code>\n"
                f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>\n"
            )
            send_msg(chat_id, espn_msg)

        elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
            send_msg(chat_id, "⏳ <b>Cargando partidos de hoy (IPTV Dedicado)...</b>")
            msgs = get_live_matches_agenda(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/stream"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL o ID&gt; [STREAM_KEY]</code>\nEjemplo: <code>/stream dsports</code> o <code>/stream espn2</code>")
                return

            ch_input = parts[1].strip()
            s_key = parts[2].strip() if len(parts) >= 3 else curr_key

            send_msg(chat_id, f"🔄 <b>Conectando señal IPTV para {ch_input}...</b>")
            ok, response_msg = start_single_stream(ch_input, s_key, chat_id)
            send_msg(chat_id, response_msg)

        elif text.startswith("/status") or text.startswith("/logs"):
            with stream_lock:
                if not active_streams:
                    send_msg(chat_id, "ℹ️ No hay ninguna transmisión activa actualmente.")
                    return

                msg_status = f"📊 <b>ESTADO DE TRANSMISIONES EN VIVO ({len(active_streams)} activas):</b>\n\n"
                for sid, info in active_streams.items():
                    elapsed = int(time.time() - info["start_time"])
                    mins = elapsed // 60
                    secs = elapsed % 60
                    proc_state = "🟢 EN EJECUCIÓN (EMITIENDO)" if info["process"].poll() is None else "🔴 DETENIDO"
                    
                    last_log = ""
                    try:
                        log_file = info.get("log_file")
                        if log_file and os.path.exists(log_file):
                            with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                                last_log = lf.read()[-300:]
                    except Exception:
                        pass

                    msg_status += (
                        f"🔹 <b>Stream #{sid}:</b> {html.escape(info['channel_name'])}\n"
                        f"• 🌐 <b>Estado:</b> {proc_state}\n"
                        f"• ⏱️ <b>Tiempo activo:</b> {mins}m {secs}s\n"
                        f"• 🔑 <b>Key:</b> <code>{info['key'][:12]}...</code>\n"
                        f"• 🛑 <b>Detener:</b> <code>/stop {sid}</code>\n"
                    )
                    if last_log:
                        msg_status += f"• 📋 <b>Último log FFmpeg:</b>\n<code>{html.escape(last_log)}</code>\n\n"
                    else:
                        msg_status += "\n"

                msg_status += "🛑 <i>Para detener todas las transmisiones:</i> <code>/stopall</code>"
                send_msg(chat_id, msg_status)

        elif text.startswith("/stopall"):
            ok, response_msg = stop_all_streams()
            send_msg(chat_id, response_msg)

        elif text.startswith("/stop"):
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else None
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
    print("🤖 BOT DE TRANSMISIÓN DE FÚTBOL (100% IPTV DEDICADO - 0% LAG)")
    print("=" * 65)
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
            elif r.status_code in [401, 404]:
                print(f"Error fatal Telegram: {r.status_code}. Revisa el TELEGRAM_BOT_TOKEN.")
                time.sleep(10)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
