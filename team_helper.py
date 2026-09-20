import re
import datetime
import unicodedata

# Diccionario curado de escudos oficiales en alta resolución (ESPN CDN / FotMob CDN / Flag CDN)
CLUB_BADGES = {
    # España - LaLiga y Segunda
    "real madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
    "barcelona": "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
    "fc barcelona": "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
    "atletico madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
    "atletico de madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
    "sevilla": "https://a.espncdn.com/i/teamlogos/soccer/500/243.png",
    "real betis": "https://a.espncdn.com/i/teamlogos/soccer/500/244.png",
    "betis": "https://a.espncdn.com/i/teamlogos/soccer/500/244.png",
    "athletic club": "https://a.espncdn.com/i/teamlogos/soccer/500/93.png",
    "athletic bilbao": "https://a.espncdn.com/i/teamlogos/soccer/500/93.png",
    "real sociedad": "https://a.espncdn.com/i/teamlogos/soccer/500/89.png",
    "valencia": "https://a.espncdn.com/i/teamlogos/soccer/500/94.png",
    "villarreal": "https://a.espncdn.com/i/teamlogos/soccer/500/102.png",
    "celta de vigo": "https://a.espncdn.com/i/teamlogos/soccer/500/85.png",
    "celta": "https://a.espncdn.com/i/teamlogos/soccer/500/85.png",
    "girona": "https://a.espncdn.com/i/teamlogos/soccer/500/9812.png",
    "mallorca": "https://a.espncdn.com/i/teamlogos/soccer/500/84.png",
    "osasuna": "https://a.espncdn.com/i/teamlogos/soccer/500/97.png",
    "getafe": "https://a.espncdn.com/i/teamlogos/soccer/500/2922.png",
    "rayo vallecano": "https://a.espncdn.com/i/teamlogos/soccer/500/101.png",
    "alaves": "https://a.espncdn.com/i/teamlogos/soccer/500/96.png",
    "deportivo alaves": "https://a.espncdn.com/i/teamlogos/soccer/500/96.png",
    "las palmas": "https://a.espncdn.com/i/teamlogos/soccer/500/90.png",
    "espanyol": "https://a.espncdn.com/i/teamlogos/soccer/500/88.png",
    "valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/100.png",
    "real valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/100.png",
    "leganes": "https://a.espncdn.com/i/teamlogos/soccer/500/2924.png",
    "cadiz": "https://a.espncdn.com/i/teamlogos/soccer/500/3747.png",
    "almeria": "https://a.espncdn.com/i/teamlogos/soccer/500/3751.png",
    "granada": "https://a.espncdn.com/i/teamlogos/soccer/500/3749.png",
    "eibar": "https://a.espncdn.com/i/teamlogos/soccer/500/98.png",
    "tenerife": "https://a.espncdn.com/i/teamlogos/soccer/500/91.png",
    "racing santander": "https://a.espncdn.com/i/teamlogos/soccer/500/87.png",
    "real oviedo": "https://a.espncdn.com/i/teamlogos/soccer/500/95.png",
    "sporting gijon": "https://a.espncdn.com/i/teamlogos/soccer/500/99.png",
    "real zaragoza": "https://a.espncdn.com/i/teamlogos/soccer/500/92.png",
    "deportivo la coruna": "https://a.espncdn.com/i/teamlogos/soccer/500/82.png",
    "deportivo": "https://a.espncdn.com/i/teamlogos/soccer/500/82.png",

    # Argentina - Liga Profesional
    "boca juniors": "https://a.espncdn.com/i/teamlogos/soccer/500/5.png",
    "boca": "https://a.espncdn.com/i/teamlogos/soccer/500/5.png",
    "river plate": "https://a.espncdn.com/i/teamlogos/soccer/500/16.png",
    "river": "https://a.espncdn.com/i/teamlogos/soccer/500/16.png",
    "racing club": "https://a.espncdn.com/i/teamlogos/soccer/500/14.png",
    "racing": "https://a.espncdn.com/i/teamlogos/soccer/500/14.png",
    "independiente": "https://a.espncdn.com/i/teamlogos/soccer/500/10.png",
    "san lorenzo": "https://a.espncdn.com/i/teamlogos/soccer/500/18.png",
    "velez sarsfield": "https://a.espncdn.com/i/teamlogos/soccer/500/20.png",
    "velez": "https://a.espncdn.com/i/teamlogos/soccer/500/20.png",
    "estudiantes de la plata": "https://a.espncdn.com/i/teamlogos/soccer/500/8.png",
    "estudiantes": "https://a.espncdn.com/i/teamlogos/soccer/500/8.png",
    "gimnasia la plata": "https://a.espncdn.com/i/teamlogos/soccer/500/9.png",
    "gimnasia": "https://a.espncdn.com/i/teamlogos/soccer/500/9.png",
    "rosario central": "https://a.espncdn.com/i/teamlogos/soccer/500/17.png",
    "newells old boys": "https://a.espncdn.com/i/teamlogos/soccer/500/12.png",
    "newells": "https://a.espncdn.com/i/teamlogos/soccer/500/12.png",
    "talleres": "https://a.espncdn.com/i/teamlogos/soccer/500/19.png",
    "talleres de cordoba": "https://a.espncdn.com/i/teamlogos/soccer/500/19.png",
    "belgrano": "https://a.espncdn.com/i/teamlogos/soccer/500/4.png",
    "lanus": "https://a.espncdn.com/i/teamlogos/soccer/500/11.png",
    "banfield": "https://a.espncdn.com/i/teamlogos/soccer/500/2.png",
    "huracan": "https://a.espncdn.com/i/teamlogos/soccer/500/1.png",
    "argentinos juniors": "https://a.espncdn.com/i/teamlogos/soccer/500/3.png",
    "defensa y justicia": "https://a.espncdn.com/i/teamlogos/soccer/500/6.png",
    "godoy cruz": "https://a.espncdn.com/i/teamlogos/soccer/500/7.png",
    "platense": "https://a.espncdn.com/i/teamlogos/soccer/500/13.png",
    "tigre": "https://a.espncdn.com/i/teamlogos/soccer/500/21.png",
    "union": "https://a.espncdn.com/i/teamlogos/soccer/500/22.png",
    "union de santa fe": "https://a.espncdn.com/i/teamlogos/soccer/500/22.png",

    # Inglaterra - Premier League
    "manchester city": "https://a.espncdn.com/i/teamlogos/soccer/500/382.png",
    "man city": "https://a.espncdn.com/i/teamlogos/soccer/500/382.png",
    "liverpool": "https://a.espncdn.com/i/teamlogos/soccer/500/364.png",
    "arsenal": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
    "manchester united": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "man united": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "chelsea": "https://a.espncdn.com/i/teamlogos/soccer/500/363.png",
    "tottenham": "https://a.espncdn.com/i/teamlogos/soccer/500/367.png",
    "tottenham hotspur": "https://a.espncdn.com/i/teamlogos/soccer/500/367.png",
    "aston villa": "https://a.espncdn.com/i/teamlogos/soccer/500/362.png",
    "newcastle": "https://a.espncdn.com/i/teamlogos/soccer/500/361.png",
    "newcastle united": "https://a.espncdn.com/i/teamlogos/soccer/500/361.png",
    "brighton": "https://a.espncdn.com/i/teamlogos/soccer/500/331.png",
    "west ham": "https://a.espncdn.com/i/teamlogos/soccer/500/371.png",
    "west ham united": "https://a.espncdn.com/i/teamlogos/soccer/500/371.png",
    "nottingham forest": "https://a.espncdn.com/i/teamlogos/soccer/500/393.png",
    "everton": "https://a.espncdn.com/i/teamlogos/soccer/500/368.png",
    "fulham": "https://a.espncdn.com/i/teamlogos/soccer/500/370.png",
    "brentford": "https://a.espncdn.com/i/teamlogos/soccer/500/337.png",
    "crystal palace": "https://a.espncdn.com/i/teamlogos/soccer/500/384.png",
    "wolverhampton": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",
    "wolves": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",

    # Italia - Serie A
    "internazionale": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
    "inter": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
    "inter milan": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
    "ac milan": "https://a.espncdn.com/i/teamlogos/soccer/500/103.png",
    "milan": "https://a.espncdn.com/i/teamlogos/soccer/500/103.png",
    "juventus": "https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
    "roma": "https://a.espncdn.com/i/teamlogos/soccer/500/104.png",
    "as roma": "https://a.espncdn.com/i/teamlogos/soccer/500/104.png",
    "napoli": "https://a.espncdn.com/i/teamlogos/soccer/500/114.png",
    "lazio": "https://a.espncdn.com/i/teamlogos/soccer/500/112.png",
    "atalanta": "https://a.espncdn.com/i/teamlogos/soccer/500/1255.png",
    "fiorentina": "https://a.espncdn.com/i/teamlogos/soccer/500/109.png",
    "bologna": "https://a.espncdn.com/i/teamlogos/soccer/500/107.png",
    "torino": "https://a.espncdn.com/i/teamlogos/soccer/500/118.png",
    "venezia": "https://a.espncdn.com/i/teamlogos/soccer/500/122.png",
    "como": "https://a.espncdn.com/i/teamlogos/soccer/500/2822.png",
    "parma": "https://a.espncdn.com/i/teamlogos/soccer/500/115.png",
    "genoa": "https://a.espncdn.com/i/teamlogos/soccer/500/3263.png",
    "udinese": "https://a.espncdn.com/i/teamlogos/soccer/500/119.png",
    "monza": "https://a.espncdn.com/i/teamlogos/soccer/500/2825.png",

    # Alemania - Bundesliga
    "bayern munich": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
    "bayern munchen": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
    "bayern": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
    "borussia dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/124.png",
    "dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/124.png",
    "bayer leverkusen": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
    "leverkusen": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
    "rb leipzig": "https://a.espncdn.com/i/teamlogos/soccer/500/11420.png",
    "leipzig": "https://a.espncdn.com/i/teamlogos/soccer/500/11420.png",
    "stuttgart": "https://a.espncdn.com/i/teamlogos/soccer/500/134.png",
    "vfb stuttgart": "https://a.espncdn.com/i/teamlogos/soccer/500/134.png",
    "eintracht frankfurt": "https://a.espncdn.com/i/teamlogos/soccer/500/125.png",
    "frankfurt": "https://a.espncdn.com/i/teamlogos/soccer/500/125.png",
    "wolfsburg": "https://a.espncdn.com/i/teamlogos/soccer/500/138.png",
    "borussia monchengladbach": "https://a.espncdn.com/i/teamlogos/soccer/500/268.png",
    "werder bremen": "https://a.espncdn.com/i/teamlogos/soccer/500/137.png",

    # Francia - Ligue 1
    "paris saint-germain": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
    "psg": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
    "marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
    "olympique de marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
    "monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
    "as monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
    "olympique lyonnais": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
    "lyon": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
    "lille": "https://a.espncdn.com/i/teamlogos/soccer/500/164.png",
    "rennes": "https://a.espncdn.com/i/teamlogos/soccer/500/169.png",
    "nice": "https://a.espncdn.com/i/teamlogos/soccer/500/168.png",
    "lens": "https://a.espncdn.com/i/teamlogos/soccer/500/175.png",

    # Sudamérica - Brasil, Uruguay, Colombia, Chile, México, MLS
    "flamengo": "https://images.fotmob.com/image_resources/logo/teamlogo/5926.png",
    "palmeiras": "https://a.espncdn.com/i/teamlogos/soccer/500/2029.png",
    "botafogo": "https://images.fotmob.com/image_resources/logo/teamlogo/8517.png",
    "fluminense": "https://images.fotmob.com/image_resources/logo/teamlogo/1981.png",
    "corinthians": "https://images.fotmob.com/image_resources/logo/teamlogo/1957.png",
    "sao paulo": "https://images.fotmob.com/image_resources/logo/teamlogo/1980.png",
    "gremio": "https://images.fotmob.com/image_resources/logo/teamlogo/5927.png",
    "internacional": "https://images.fotmob.com/image_resources/logo/teamlogo/1967.png",
    "atletico mineiro": "https://images.fotmob.com/image_resources/logo/teamlogo/1977.png",
    "cruzeiro": "https://images.fotmob.com/image_resources/logo/teamlogo/1966.png",
    "penarol": "https://a.espncdn.com/i/teamlogos/soccer/500/15.png",
    "nacional": "https://a.espncdn.com/i/teamlogos/soccer/500/13.png",
    "club nacional de football": "https://a.espncdn.com/i/teamlogos/soccer/500/13.png",
    "colo-colo": "https://images.fotmob.com/image_resources/logo/teamlogo/6448.png",
    "colo colo": "https://images.fotmob.com/image_resources/logo/teamlogo/6448.png",
    "universidad de chile": "https://images.fotmob.com/image_resources/logo/teamlogo/6451.png",
    "olimpia": "https://images.fotmob.com/image_resources/logo/teamlogo/6532.png",
    "cerro porteno": "https://images.fotmob.com/image_resources/logo/teamlogo/6530.png",
    "alianza lima": "https://images.fotmob.com/image_resources/logo/teamlogo/6537.png",
    "universitario": "https://images.fotmob.com/image_resources/logo/teamlogo/6541.png",
    "atletico nacional": "https://images.fotmob.com/image_resources/logo/teamlogo/6468.png",
    "millonarios": "https://images.fotmob.com/image_resources/logo/teamlogo/6474.png",
    "america de cali": "https://images.fotmob.com/image_resources/logo/teamlogo/6467.png",
    "junior": "https://images.fotmob.com/image_resources/logo/teamlogo/6473.png",
    "santa fe": "https://images.fotmob.com/image_resources/logo/teamlogo/6475.png",
    "deportivo cali": "https://images.fotmob.com/image_resources/logo/teamlogo/6471.png",
    "ldu quito": "https://images.fotmob.com/image_resources/logo/teamlogo/6487.png",
    "liga de quito": "https://images.fotmob.com/image_resources/logo/teamlogo/6487.png",
    "barcelona sc": "https://images.fotmob.com/image_resources/logo/teamlogo/6484.png",
    "emelec": "https://images.fotmob.com/image_resources/logo/teamlogo/6485.png",
    "independiente del valle": "https://images.fotmob.com/image_resources/logo/teamlogo/188632.png",
    "america": "https://a.espncdn.com/i/teamlogos/soccer/500/227.png",
    "club america": "https://a.espncdn.com/i/teamlogos/soccer/500/227.png",
    "chivas": "https://a.espncdn.com/i/teamlogos/soccer/500/218.png",
    "guadalajara": "https://a.espncdn.com/i/teamlogos/soccer/500/218.png",
    "cruz azul": "https://a.espncdn.com/i/teamlogos/soccer/500/219.png",
    "tigres": "https://a.espncdn.com/i/teamlogos/soccer/500/233.png",
    "tigres uanl": "https://a.espncdn.com/i/teamlogos/soccer/500/233.png",
    "monterrey": "https://a.espncdn.com/i/teamlogos/soccer/500/228.png",
    "pumas unam": "https://a.espncdn.com/i/teamlogos/soccer/500/229.png",
    "toluca": "https://a.espncdn.com/i/teamlogos/soccer/500/232.png",
    "inter miami": "https://images.fotmob.com/image_resources/logo/teamlogo/1083466.png",
    "la galaxy": "https://a.espncdn.com/i/teamlogos/soccer/500/187.png",
    "los angeles fc": "https://a.espncdn.com/i/teamlogos/soccer/500/189.png",
    "lafc": "https://a.espncdn.com/i/teamlogos/soccer/500/189.png",
    "ajax": "https://a.espncdn.com/i/teamlogos/soccer/500/139.png",
    "benfica": "https://a.espncdn.com/i/teamlogos/soccer/500/236.png",
    "porto": "https://a.espncdn.com/i/teamlogos/soccer/500/237.png",
    "sporting cp": "https://a.espncdn.com/i/teamlogos/soccer/500/238.png",
    "sporting lisboa": "https://a.espncdn.com/i/teamlogos/soccer/500/238.png",

    # Selecciones Nacionales (Bandera Oficial en FlagCDN)
    "argentina": "https://flagcdn.com/w80/ar.png",
    "brasil": "https://flagcdn.com/w80/br.png",
    "brazil": "https://flagcdn.com/w80/br.png",
    "espana": "https://flagcdn.com/w80/es.png",
    "spain": "https://flagcdn.com/w80/es.png",
    "chile": "https://flagcdn.com/w80/cl.png",
    "colombia": "https://flagcdn.com/w80/co.png",
    "uruguay": "https://flagcdn.com/w80/uy.png",
    "mexico": "https://flagcdn.com/w80/mx.png",
    "peru": "https://flagcdn.com/w80/pe.png",
    "ecuador": "https://flagcdn.com/w80/ec.png",
    "venezuela": "https://flagcdn.com/w80/ve.png",
    "paraguay": "https://flagcdn.com/w80/py.png",
    "bolivia": "https://flagcdn.com/w80/bo.png",
    "estados unidos": "https://flagcdn.com/w80/us.png",
    "usa": "https://flagcdn.com/w80/us.png",
    "canada": "https://flagcdn.com/w80/ca.png",
    "francia": "https://flagcdn.com/w80/fr.png",
    "france": "https://flagcdn.com/w80/fr.png",
    "alemania": "https://flagcdn.com/w80/de.png",
    "germany": "https://flagcdn.com/w80/de.png",
    "italia": "https://flagcdn.com/w80/it.png",
    "italy": "https://flagcdn.com/w80/it.png",
    "inglaterra": "https://flagcdn.com/w80/gb-eng.png",
    "england": "https://flagcdn.com/w80/gb-eng.png",
    "portugal": "https://flagcdn.com/w80/pt.png",
    "paises bajos": "https://flagcdn.com/w80/nl.png",
    "holanda": "https://flagcdn.com/w80/nl.png",
    "netherlands": "https://flagcdn.com/w80/nl.png",
    "croacia": "https://flagcdn.com/w80/hr.png",
    "marruecos": "https://flagcdn.com/w80/ma.png",
    "japon": "https://flagcdn.com/w80/jp.png",
}

# Abreviaciones emblemáticas para el fallback de avatar
KNOWN_SHORTS = {
    "real madrid": "RMA",
    "barcelona": "BAR",
    "fc barcelona": "BAR",
    "atletico madrid": "ATM",
    "manchester city": "MCI",
    "manchester united": "MUN",
    "liverpool": "LIV",
    "arsenal": "ARS",
    "chelsea": "CHE",
    "tottenham": "TOT",
    "inter": "INT",
    "internazionale": "INT",
    "milan": "MIL",
    "ac milan": "MIL",
    "juventus": "JUV",
    "roma": "ROM",
    "napoli": "NAP",
    "boca juniors": "BOC",
    "river plate": "RIV",
    "racing club": "RAC",
    "independiente": "IND",
    "san lorenzo": "SLO",
    "bayern munich": "FCB",
    "borussia dortmund": "BVB",
    "bayer leverkusen": "B04",
    "stuttgart": "VFB",
    "paris saint-germain": "PSG",
    "psg": "PSG",
    "palmeiras": "PAL",
    "flamengo": "FLA",
}

def clean_team_name(name):
    if not name:
        return ""
    # Quitar acentos y caracteres raros
    s = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', s)
    return " ".join(s.split()).lower()

def parse_match_teams(match_title):
    """
    Separa un partido en (equipo_local, equipo_visitante).
    Si no contiene 'vs', devuelve (match_title, "").
    """
    if not match_title:
        return "", ""
    parts = re.split(r'\s+vs\.?\s+|\s+-\s+|\s+v\s+', match_title, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return match_title.strip(), ""

def get_team_short(name):
    """Genera una sigla de 2 o 3 letras elegante para badges sin logo oficial."""
    if not name:
        return "⚽"
    clean = clean_team_name(name)
    if clean in KNOWN_SHORTS:
        return KNOWN_SHORTS[clean]
    words = [w for w in clean.split() if w not in ("fc", "cf", "cd", "ca", "de", "del", "la", "el", "los", "las")]
    if len(words) >= 2:
        return (words[0][:1] + words[1][:2]).upper()
    elif words:
        return words[0][:3].upper()
    return name[:3].upper()

def get_team_badge(name):
    """Retorna la URL del escudo oficial si existe en nuestro registro curado."""
    if not name:
        return None
    clean = clean_team_name(name)
    
    # 1. Búsqueda exacta
    if clean in CLUB_BADGES:
        return CLUB_BADGES[clean]
    
    # 2. Búsqueda por subcadena / palabras clave
    for k, url in CLUB_BADGES.items():
        if len(k) >= 4 and (k in clean or clean in k):
            return url
            
    return None

def is_match_live(ev_time, viewers_count=0):
    """
    Determina si un partido está actualmente EN VIVO basándose en espectadores activos
    o en el horario de inicio (UTC-3 Buenos Aires / agenda Tarjetaroja).
    """
    if viewers_count and viewers_count > 0:
        return True
    
    if not ev_time:
        return False
    
    time_str = str(ev_time).strip().lower()
    if "vivo" in time_str or "directo" in time_str:
        return True
    
    # Evaluar hora HH:MM contra hora actual de Argentina (UTC-3)
    m = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if not m:
        return False
        
    try:
        h = int(m.group(1))
        minute = int(m.group(2))
        match_total_mins = h * 60 + minute

        # Hora actual UTC-3
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_arg = now_utc - datetime.timedelta(hours=3)
        now_total_mins = now_arg.hour * 60 + now_arg.minute

        diff = (now_total_mins - match_total_mins) % 1440
        if diff > 720:
            diff -= 1440

        # Consideramos EN VIVO desde 15 min antes del inicio (previa)
        # hasta 135 minutos después del inicio (partido completo + entretiempo + alargue)
        return -15 <= diff <= 135
    except Exception:
        return False
