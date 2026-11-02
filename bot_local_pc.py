import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import subprocess
from stream_runtime import build_command
import time
import requests
import json
import os
import sys
import re
from urllib.parse import urlparse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "9281285181:AAEo_hAjJo-zd537Kvz-f4QcU3iG-aUNGzo").strip()
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels_local.json")

IPTV_USER = "96PX3Q2J"
IPTV_PASS = "24V7N2A1"
IPTV_SERVER = "http://qpyzyvkm.cdngold.info"

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "1": "4394528713:myDTS60UhFs8Q1cpXDDyaQ",
        "2": "4400198885:PcUiiv-__sV28_Hnyq83Ew",
        "3": "3936015063:nG8N_no46UfNuA6jXewiag"
    }

def save_channels(channels_dict):
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels_dict, f, indent=2)
    except Exception:
        pass

CHANNELS = load_channels()
ADMIN_USER_ID = None
active_streams = {}

TOP_SPORTS_CHANNELS = [
    {"name": "ESPN HD (Principal)", "id": "34050", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34050.ts"},
    {"name": "ESPN 2 HD", "id": "34048", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34048.ts"},
    {"name": "ESPN 3 HD", "id": "34049", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34049.ts"},
    {"name": "ESPN 4 HD", "id": "1201550", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/1201550.ts"},
    {"name": "ESPN Extra HD", "id": "34051", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34051.ts"},
    {"name": "ESPN Deportes HD", "id": "32038", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32038.ts"},
    {"name": "TyC Sports HD (Argentina)", "id": "30365", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/30365.ts"},
    {"name": "Directv Sports 1 (DSPORTS)", "id": "33933", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts"},
    {"name": "Directv Sports 2 (DSPORTS 2)", "id": "33932", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33932.ts"},
    {"name": "LaLiga TV (FHD)", "id": "33866", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts"},
    {"name": "LaLiga TV (HD)", "id": "34105", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34105.ts"},
]

cached_streams = []

def get_iptv_streams():
    global cached_streams
    if cached_streams:
        return cached_streams
    try:
        api_url = f"{IPTV_SERVER}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(api_url, timeout=15, headers={"User-Agent": "IPTVSmartersPro"})
        if r.status_code == 200:
            cached_streams = r.json()
            return cached_streams
    except Exception as e:
        print(f"Error cargando canales IPTV: {e}")
    return []

def search_iptv_channels(query, max_results=8):
    streams = get_iptv_streams()
    results = []
    query_clean = query.lower().strip()
    for ch in streams:
        name = ch.get("name", "")
        sid = ch.get("stream_id")
        clean_name = re.sub(r'[^\x00-\x7F]+', ' ', name).strip()
        if query_clean in clean_name.lower():
            link = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{sid}.ts"
            results.append((clean_name, sid, link))
            if len(results) >= max_results:
                break
    return results

def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def extract_referer(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        pass
    return "https://google.com/"

def start_single_stream(stream_id, source_url, stream_key, label=None):
    if stream_id in active_streams:
        stop_single_stream(stream_id)

    source_url = clean_arg(source_url)
    stream_key = clean_arg(stream_key)

    destination = RTMP_SERVER + stream_key
    referer = extract_referer(source_url)
    
    headers = (
        f"Referer: {referer}\r\n"
        f"Origin: {referer.rstrip('/')}\r\n"
    )

    cmd = build_command(source_url, headers, destination)

    log_file = "stream_local.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    
    time.sleep(1.5)
    if proc.poll() is not None:
        out_f.close()
        return False, "FFmpeg no pudo conectar a la señal."

    active_streams[stream_id] = {
        "process": proc,
        "log_file": out_f,
        "url": source_url,
        "key": stream_key,
        "name": label if label else f"Canal {stream_id}",
        "start_time": time.time()
    }
    return True, "OK"

def stop_single_stream(stream_id):
    if stream_id in active_streams:
        info = active_streams[stream_id]
        proc = info["process"]
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        try:
            if "log_file" in info and not info["log_file"].closed:
                info["log_file"].close()
        except Exception:
            pass
        del active_streams[stream_id]
        return True
    return False

def stop_all_streams():
    ids = list(active_streams.keys())
    for sid in ids:
        stop_single_stream(sid)
    return len(ids)

def send_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def handle_message(msg):
    global CHANNELS
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    if text.startswith("/start") or text.startswith("/ayuda"):
        help_text = (
            "⚽ *BOT DE TRANSMISIÓN DEPORTIVA MULTI-CANAL*\n\n"
            "📋 *GUÍA DE CANALES Y PARTIDOS:*\n"
            "• `/top` $\\rightarrow$ Ver todos los canales deportivos top con sus URLs\n"
            "• `/buscar <nombre>` $\\rightarrow$ Buscar cualquier canal en tu IPTV (ej. `/buscar dazn`)\n"
            "• `/partidos` $\\rightarrow$ Cartelera y enlaces de los partidos de hoy\n\n"
            "📺 *TRANSMITIR EN CANALES:*\n"
            "• `/c1 <URL>` $\\rightarrow$ Transmitir en Canal 1\n"
            "• `/c2 <URL>` $\\rightarrow$ Transmitir en Canal 2\n"
            "• `/stream <URL> <STREAM_KEY>` $\\rightarrow$ Personalizado\n\n"
            "🔑 *GESTIÓN DE CLAVES:*\n"
            "• `/set1 <KEY>` | `/set2 <KEY>` | `/canales`\n\n"
            "🛑 *DETENER:*\n"
            "• `/stop1` | `/stop2` | `/stopall`\n\n"
            "📊 *ESTADO:*\n"
            "• `/status` $\\rightarrow$ Ver qué partidos están emitiéndose"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/top") or text.startswith("/deportes"):
        msg_txt = "🌟 *CANALES DEPORTIVOS PRINCIPALES:*\n\n"
        for ch in TOP_SPORTS_CHANNELS:
            msg_txt += f"📺 *{ch['name']}*\n🔗 `{ch['url']}`\n\n"
        msg_txt += "💡 _Toca cualquier enlace para copiarlo y envíalo con `/c1 <enlace>`_"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ *Uso:* `/buscar <palabra>` (ejemplo: `/buscar espn`, `/buscar tyc`, `/buscar fox`)")
            return
        query = parts[1].strip()
        send_msg(chat_id, f"🔍 *Buscando canales con:* `{query}`...")
        results = search_iptv_channels(query)
        if not results:
            send_msg(chat_id, f"❌ No se encontraron canales con `{query}`.")
            return

        resp_txt = f"🎯 *RESULTADOS PARA:* `{query}`\n\n"
        for name, sid, link in results:
            resp_txt += f"• *{name}* (ID `{sid}`):\n🔗 `{link}`\n\n"
        resp_txt += "💡 _Toca el enlace para copiarlo y envíalo con `/c1 <enlace>`_"
        send_msg(chat_id, resp_txt)

    elif text.startswith("/partidos") or text.startswith("/hoy"):
        partidos_txt = (
            "⚽ *CARTELERA DE PARTIDOS TOP DE HOY:*\n\n"
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 *Premier League: Fulham vs. Chelsea*\n"
            "• 📺 Canal: ESPN HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/34050.ts`\n\n"
            "🇪🇸 *LaLiga: Osasuna vs. Levante*\n"
            "• 📺 Canal: ESPN 4 HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/1201550.ts`\n\n"
            "🇪🇸 *LaLiga: Málaga vs. Deportivo La Coruña*\n"
            "• 📺 Canal: Directv Sports 1 (DSPORTS)\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/33933.ts`\n\n"
            "🇮🇹 *Serie A: Bologna vs. Lazio*\n"
            "• 📺 Canal: ESPN 2 HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/34048.ts`\n\n"
            "🇮🇹 *Serie A: AS Roma vs. Fiorentina*\n"
            "• 📺 Canal: ESPN 2 HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/34048.ts`\n\n"
            "🇦🇷 *Liga Argentina: Tigre vs. Central Córdoba*\n"
            "• 📺 Canal: TyC Sports HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/30365.ts`\n\n"
            "🇦🇷 *Liga Argentina: Talleres vs. Rosario Central*\n"
            "• 📺 Canal: ESPN HD\n"
            "• 🔗 `http://evestv.leptis.live/live/BE15ERDV/PXELERB9/34050.ts`\n\n"
            "💡 _Toca cualquier enlace para copiarlo y transmitir con `/c1 <enlace>`_"
        )
        send_msg(chat_id, partidos_txt)

    elif text.startswith("/canales"):
        txt = "📋 *CANALES CONFIGURADOS ACTUALMENTE:*\n\n"
        for cid, k in sorted(CHANNELS.items()):
            txt += f"• *Canal {cid}:* `{k}`\n"
        txt += "\n💡 Para cambiar una clave escribe: `/set1 <nueva_clave>`"
        send_msg(chat_id, txt)

    elif text.startswith("/set"):
        parts = text.split()
        if text.startswith("/set1") or text.startswith("/set2") or text.startswith("/set3"):
            cid = text[4:5]
            if len(parts) < 2:
                send_msg(chat_id, f"⚠️ *Uso:* `/set{cid} NUEVA_STREAM_KEY`")
                return
            new_key = clean_arg(parts[1])
        else:
            if len(parts) < 3:
                send_msg(chat_id, "⚠️ *Uso:* `/set NUMERO_CANAL STREAM_KEY`")
                return
            cid = clean_arg(parts[1])
            new_key = clean_arg(parts[2])

        CHANNELS[cid] = new_key
        save_channels(CHANNELS)
        send_msg(chat_id, f"✅ *¡Clave del Canal {cid} actualizada!*\n🔑 Nueva Stream Key: `{new_key}`")

    elif text.startswith("/c"):
        parts = text.split()
        cid = parts[0][2:]
        if not cid.isalnum():
            return
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ *Uso:* `/c{cid} URL_DEL_CANAL`")
            return
        
        m3u8_url = clean_arg(parts[1])
        stream_key = clean_arg(CHANNELS.get(cid))
        if not stream_key:
            send_msg(chat_id, f"❌ El Canal {cid} no tiene clave.\nConfigúrala con: `/set{cid} <STREAM_KEY>`")
            return

        send_msg(chat_id, f"⏳ *Iniciando transmisión ultra-fluida en Canal {cid}...*")
        ok, res = start_single_stream(cid, m3u8_url, stream_key, f"Canal {cid}")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA en Canal {cid}!* 🚀\n📡 Key: `{stream_key[:8]}...`\n🛡️ Motor: Blindado 0% Cortes")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 3:
            send_msg(chat_id, "⚠️ *Uso:* `/stream URL_DEL_CANAL STREAM_KEY`")
            return
        m3u8_url = clean_arg(parts[1])
        custom_key = clean_arg(parts[2])
        custom_id = f"custom_{len(active_streams) + 1}"
        send_msg(chat_id, "⏳ *Iniciando transmisión personalizada...*")
        ok, res = start_single_stream(custom_id, m3u8_url, custom_key, f"Personalizado ({custom_id})")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA!* 🚀\nID: `{custom_id}`\n📡 Key: `{custom_key[:8]}...`\n🛡️ Motor: Blindado 0% Cortes")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stop") and text != "/stopall":
        cid = clean_arg(text[5:])
        if not cid:
            send_msg(chat_id, "⚠️ *Uso:* `/stop1`, `/stop2` o `/stopall`")
            return
        if stop_single_stream(cid):
            send_msg(chat_id, f"🛑 *Canal {cid} detenido correctamente.*")
        else:
            send_msg(chat_id, "ℹ️ Ese canal no estaba transmitiendo.")

    elif text.startswith("/stopall"):
        count = stop_all_streams()
        send_msg(chat_id, f"🛑 *Se han detenido todas las transmisiones ({count} canales cerrados).*")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 *No hay ninguna transmisión activa actualmente.*")
            return

        status_text = "🟢 *CANALES EN DIRECTO EN TELEGRAM:*\n\n"
        for sid, info in active_streams.items():
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += f"📺 *{info['name']}:*\n• ⏱️ Tiempo: `{mins}m {secs}s`\n• 📡 Key: `{info['key'][:8]}...`\n• 🔗 URL: `{info['url'][:35]}...`\n\n"
        send_msg(chat_id, status_text)

def main():
    print("=" * 65)
    print("     BOT @Elasdelfutbolbot CON BUSCADOR DE CANALES Y CARTELERA ")
    print("=" * 65)
    print("\nEl bot está escuchando tus comandos en Telegram...")
    
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35).json()
            if resp.get("ok"):
                for update in resp.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
