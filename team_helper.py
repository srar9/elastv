# -*- coding: utf-8 -*-
import re
import html
import datetime
import unicodedata
import badges_db

# ==============================================================================
# DEPORTES QUE NO SON ENFRENTAMIENTOS 1 VS 1 (MOTORSPORT, CICLISMO, GOLF, ETC.)
# ==============================================================================
NON_VS_SPORTS = {
    "f1", "formula 1", "formula1", "motogp", "moto 2", "moto 3", "moto2", "moto3",
    "indycar", "nascar", "superbike", "ciclismo", "cycling", "tour de france",
    "giro", "vuelta", "rally", "wrc", "dakar", "golf", "atletismo", "maraton"
}

def is_non_vs_competition(competition, match_title=""):
    comp = str(competition or "").strip().lower()
    title = str(match_title or "").strip().lower()
    for sport in NON_VS_SPORTS:
        if sport in comp or sport in title:
            return True
    return False

def clean_team_name(name):
    if not name:
        return ""
    # Decodificar entidades HTML (ej. &#039; -> ')
    raw = html.unescape(str(name))
    # Quitar tildes y caracteres especiales
    s = unicodedata.normalize('NFKD', raw).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
    return " ".join(s.split()).lower()

def parse_match_teams(match_title, competition=""):
    """
    Separa un partido en (equipo_local, equipo_visitante).
    Solo separa si contiene 'vs' o 'vs.' explícito y NO es deporte de carreras/individual.
    JAMÁS separa con guiones '-', para no romper eventos como 'GP Austria - Carrera Moto3'.
    """
    if not match_title:
        return "", ""
        
    if is_non_vs_competition(competition, match_title):
        return match_title.strip(), ""
        
    # Buscar 'vs' o 'vs.' con espacios
    m = re.search(r'\s+(?:vs\.?|v)\s+', match_title, flags=re.IGNORECASE)
    if m:
        t1 = match_title[:m.start()].strip()
        t2 = match_title[m.end():].strip()
        if t1 and t2:
            return t1, t2
            
    return match_title.strip(), ""

# ==============================================================================
# MOTOR DE BÚSQUEDA INTELIGENTE DE LOGOS CON COBERTURA DE 28 LIGAS
# ==============================================================================
def get_team_badge(name, competition=""):
    """
    Retorna la URL del escudo oficial con precisión total.
    Toma en cuenta la competición para evitar cruces indebidos y luego recurre
    a la base global de más de 400 clubes verificados (ESPN, FotMob, FlagCDN).
    """
    if not name:
        return None
        
    clean = clean_team_name(name)
    comp_clean = clean_team_name(competition)
    
    # Variante sin sufijos comunes ("fc", "cf", "ud", "sk", "jk", etc.)
    clean_stripped = re.sub(r'\b(fc|cf|cd|ud|sd|ca|sk|fk|jk|sc|sad|ac|rc|afc|de futbol)\b', '', clean).strip()
    clean_stripped = " ".join(clean_stripped.split())

    # 1. Comprobación contextual de NFL / Béisbol
    if "nfl" in comp_clean:
        return badges_db.NFL_BADGES.get(clean) or badges_db.NFL_BADGES.get(clean_stripped)
        
    if any(x in comp_clean for x in ["mlb", "beisbol", "baseball"]):
        return badges_db.MLB_BADGES.get(clean) or badges_db.MLB_BADGES.get(clean_stripped)

    # 2. Comprobación contextual de Selecciones Nacionales / Copa Davis
    if any(x in comp_clean for x in ["davis", "seleccion", "mundial", "copa america", "euro"]):
        return badges_db.COUNTRY_FLAGS.get(clean) or badges_db.COUNTRY_FLAGS.get(clean_stripped)
            
    # 3. Comprobación contextual por liga
    league_map = [
        (["laliga", "espana", "hypermotion"], badges_db.LALIGA_BADGES),
        (["premier", "championship", "inglaterra"], badges_db.PREMIER_BADGES),
        (["serie a", "serie b", "italia"], badges_db.SERIEA_BADGES),
        (["bundesliga", "alemania"], badges_db.BUNDESLIGA_BADGES),
        (["ligue 1", "ligue 2", "francia"], badges_db.LIGUE1_BADGES),
        (["super lig", "turquia", "turkey"], badges_db.SUPERLIG_BADGES),
        (["eredivisie", "holanda", "paises bajos"], badges_db.EREDIVISIE_BADGES),
        (["portugal", "primeira"], badges_db.PORTUGAL_BADGES),
        (["mex", "liga mx"], badges_db.LIGAMX_BADGES),
        (["argentina", "profesional"], badges_db.ARGENTINA_BADGES),
        (["brasil", "brasileirao"], badges_db.BRASIL_BADGES),
        (["colombia", "betplay"], badges_db.COLOMBIA_BADGES),
        (["uruguay", "auf"], badges_db.URUGUAY_BADGES),
        (["peru", "liga 1"], badges_db.PERU_BADGES),
        (["ecuador", "liga pro"], badges_db.ECUADOR_BADGES),
        (["paraguay"], badges_db.PARAGUAY_BADGES),
        (["chile"], badges_db.CHILE_BADGES),
        (["venezuela", "futve"], badges_db.VENEZUELA_BADGES),
        (["bolivia"], badges_db.BOLIVIA_BADGES),
        (["mls", "major league", "apple tv"], badges_db.MLS_BADGES),
        (["champions", "europa", "uefa", "conference"], badges_db.UEFA_BADGES),
    ]

    for keywords, dict_table in league_map:
        if any(k in comp_clean for k in keywords):
            if clean in dict_table:
                return dict_table[clean]
            if clean_stripped and clean_stripped in dict_table:
                return dict_table[clean_stripped]
            break

    # 4. Comprobación global exacta en diccionarios
    if clean in badges_db.GLOBAL_BADGES:
        return badges_db.GLOBAL_BADGES[clean]
    if clean_stripped and clean_stripped in badges_db.GLOBAL_BADGES:
        return badges_db.GLOBAL_BADGES[clean_stripped]

    # 5. Comprobación en selecciones / banderas
    if clean in badges_db.COUNTRY_FLAGS:
        return badges_db.COUNTRY_FLAGS[clean]
            
    # 6. Coincidencia por palabras completas (SOLO para nombres compuestos de 2+ palabras)
    words = clean.split()
    if len(words) >= 2:
        for k, url in badges_db.GLOBAL_BADGES.items():
            if len(k.split()) >= 2 and (k in clean or clean in k):
                return url
                    
    return None

def get_team_short(name):
    """Genera una sigla de 2 o 3 letras elegante para badges sin logo oficial."""
    if not name:
        return "⚽"
    clean = clean_team_name(name)
    words = [w for w in clean.split() if w not in ("fc", "cf", "cd", "ca", "de", "del", "la", "el", "los", "las")]
    if len(words) >= 2:
        return (words[0][:1] + words[1][:2]).upper()
    elif words:
        return words[0][:3].upper()
    return name[:3].upper()

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

        return -15 <= diff <= 135
    except Exception:
        return False
