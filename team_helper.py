import re
import html
import datetime
import unicodedata

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
# DICCIONARIOS DE ESCUDOS OFICIALES Y VERIFICADOS (ESPN / FOTMOB / FLAGCDN)
# ==============================================================================

# 1. ESPAÑA: LaLiga y LaLiga Hypermotion
LALIGA_BADGES = {
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
    "celta de vigo ii": "https://a.espncdn.com/i/teamlogos/soccer/500/85.png",
    "celta b": "https://a.espncdn.com/i/teamlogos/soccer/500/85.png",
    "girona": "https://a.espncdn.com/i/teamlogos/soccer/500/9812.png",
    "mallorca": "https://a.espncdn.com/i/teamlogos/soccer/500/84.png",
    "rcd mallorca": "https://a.espncdn.com/i/teamlogos/soccer/500/84.png",
    "osasuna": "https://a.espncdn.com/i/teamlogos/soccer/500/97.png",
    "getafe": "https://a.espncdn.com/i/teamlogos/soccer/500/2922.png",
    "rayo vallecano": "https://a.espncdn.com/i/teamlogos/soccer/500/101.png",
    "alaves": "https://a.espncdn.com/i/teamlogos/soccer/500/96.png",
    "deportivo alaves": "https://a.espncdn.com/i/teamlogos/soccer/500/96.png",
    "las palmas": "https://a.espncdn.com/i/teamlogos/soccer/500/90.png",
    "ud las palmas": "https://a.espncdn.com/i/teamlogos/soccer/500/90.png",
    "espanyol": "https://a.espncdn.com/i/teamlogos/soccer/500/88.png",
    "rcd espanyol": "https://a.espncdn.com/i/teamlogos/soccer/500/88.png",
    "valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/100.png",
    "real valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/100.png",
    "leganes": "https://a.espncdn.com/i/teamlogos/soccer/500/2924.png",
    "cadiz": "https://a.espncdn.com/i/teamlogos/soccer/500/3747.png",
    "almeria": "https://a.espncdn.com/i/teamlogos/soccer/500/3751.png",
    "ud almeria": "https://a.espncdn.com/i/teamlogos/soccer/500/3751.png",
    "granada": "https://a.espncdn.com/i/teamlogos/soccer/500/3749.png",
    "eibar": "https://a.espncdn.com/i/teamlogos/soccer/500/98.png",
    "tenerife": "https://a.espncdn.com/i/teamlogos/soccer/500/91.png",
    "racing santander": "https://a.espncdn.com/i/teamlogos/soccer/500/87.png",
    "real oviedo": "https://a.espncdn.com/i/teamlogos/soccer/500/95.png",
    "sporting gijon": "https://a.espncdn.com/i/teamlogos/soccer/500/99.png",
    "real zaragoza": "https://a.espncdn.com/i/teamlogos/soccer/500/92.png",
    "deportivo la coruna": "https://a.espncdn.com/i/teamlogos/soccer/500/82.png",
    "deportivo": "https://a.espncdn.com/i/teamlogos/soccer/500/82.png",
    "malaga": "https://a.espncdn.com/i/teamlogos/soccer/500/97.png",
    "levante": "https://a.espncdn.com/i/teamlogos/soccer/500/9811.png",
    "sabadell": "https://a.espncdn.com/i/teamlogos/soccer/500/3950.png",
    "ceuta": "https://a.espncdn.com/i/teamlogos/soccer/500/4220.png",
    "burgos": "https://a.espncdn.com/i/teamlogos/soccer/500/4004.png",
    "cd castellon": "https://a.espncdn.com/i/teamlogos/soccer/500/3939.png",
    "castellon": "https://a.espncdn.com/i/teamlogos/soccer/500/3939.png",
    "eldense": "https://a.espncdn.com/i/teamlogos/soccer/500/10609.png",
    "albacete": "https://a.espncdn.com/i/teamlogos/soccer/500/3748.png",
    "huesca": "https://a.espncdn.com/i/teamlogos/soccer/500/3750.png",
    "elche": "https://a.espncdn.com/i/teamlogos/soccer/500/3752.png",
    "mirandes": "https://a.espncdn.com/i/teamlogos/soccer/500/6114.png",
    "cartagena": "https://a.espncdn.com/i/teamlogos/soccer/500/6112.png",
    "ferrol": "https://a.espncdn.com/i/teamlogos/soccer/500/6113.png",
}

# 2. INGLATERRA: Premier League y Championship
PREMIER_BADGES = {
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
    "wolverhampton wanderers": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",
    "wolves": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",
    "bournemouth": "https://a.espncdn.com/i/teamlogos/soccer/500/349.png",
    "afc bournemouth": "https://a.espncdn.com/i/teamlogos/soccer/500/349.png",
    "leeds united": "https://a.espncdn.com/i/teamlogos/soccer/500/357.png",
    "leeds": "https://a.espncdn.com/i/teamlogos/soccer/500/357.png",
    "sunderland": "https://a.espncdn.com/i/teamlogos/soccer/500/366.png",
    "west bromwich albion": "https://a.espncdn.com/i/teamlogos/soccer/500/383.png",
    "west brom": "https://a.espncdn.com/i/teamlogos/soccer/500/383.png",
    "leicester city": "https://a.espncdn.com/i/teamlogos/soccer/500/375.png",
    "southampton": "https://a.espncdn.com/i/teamlogos/soccer/500/376.png",
    "ipswich town": "https://a.espncdn.com/i/teamlogos/soccer/500/374.png",
    "coventry city": "https://a.espncdn.com/i/teamlogos/soccer/500/390.png",
}

# 3. ITALIA: Serie A y Serie B
SERIEA_BADGES = {
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
    "frosinone": "https://a.espncdn.com/i/teamlogos/soccer/500/3794.png",
    "lecce": "https://a.espncdn.com/i/teamlogos/soccer/500/113.png",
    "cagliari": "https://a.espncdn.com/i/teamlogos/soccer/500/108.png",
    "empoli": "https://a.espncdn.com/i/teamlogos/soccer/500/2697.png",
    "sassuolo": "https://a.espncdn.com/i/teamlogos/soccer/500/3788.png",
    "salernitana": "https://a.espncdn.com/i/teamlogos/soccer/500/2824.png",
    "sampdoria": "https://a.espncdn.com/i/teamlogos/soccer/500/116.png",
}

# 4. ALEMANIA: Bundesliga y 2. Bundesliga
BUNDESLIGA_BADGES = {
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
    "schalke 04": "https://a.espncdn.com/i/teamlogos/soccer/500/133.png",
    "schalke": "https://a.espncdn.com/i/teamlogos/soccer/500/133.png",
    "hannover 96": "https://a.espncdn.com/i/teamlogos/soccer/500/128.png",
    "hannover": "https://a.espncdn.com/i/teamlogos/soccer/500/128.png",
    "bochum": "https://a.espncdn.com/i/teamlogos/soccer/500/122.png",
    "elversberg": "https://a.espncdn.com/i/teamlogos/soccer/500/6195.png",
    "paderborn": "https://a.espncdn.com/i/teamlogos/soccer/500/3122.png",
    "hoffenheim": "https://a.espncdn.com/i/teamlogos/soccer/500/7911.png",
    "hertha bsc": "https://a.espncdn.com/i/teamlogos/soccer/500/129.png",
    "dynamo dresden": "https://a.espncdn.com/i/teamlogos/soccer/500/3074.png",
    "st pauli": "https://a.espncdn.com/i/teamlogos/soccer/500/135.png",
    "union berlin": "https://a.espncdn.com/i/teamlogos/soccer/500/8980.png",
    "freiburg": "https://a.espncdn.com/i/teamlogos/soccer/500/127.png",
    "mainz": "https://a.espncdn.com/i/teamlogos/soccer/500/2950.png",
    "augsburg": "https://a.espncdn.com/i/teamlogos/soccer/500/3841.png",
    "heidenheim": "https://a.espncdn.com/i/teamlogos/soccer/500/8908.png",
}

# 5. FRANCIA: Ligue 1 y Ligue 2
LIGUE1_BADGES = {
    "paris saint-germain": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
    "psg": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
    "marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
    "olympique de marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
    "olympique marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
    "monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
    "as monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
    "olympique lyonnais": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
    "lyon": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
    "lille": "https://a.espncdn.com/i/teamlogos/soccer/500/164.png",
    "nice": "https://a.espncdn.com/i/teamlogos/soccer/500/168.png",
    "rennes": "https://a.espncdn.com/i/teamlogos/soccer/500/169.png",
    "lens": "https://a.espncdn.com/i/teamlogos/soccer/500/175.png",
    "auxerre": "https://a.espncdn.com/i/teamlogos/soccer/500/161.png",
    "brest": "https://a.espncdn.com/i/teamlogos/soccer/500/3433.png",
    "reims": "https://a.espncdn.com/i/teamlogos/soccer/500/3434.png",
    "strasbourg": "https://a.espncdn.com/i/teamlogos/soccer/500/171.png",
    "toulouse": "https://a.espncdn.com/i/teamlogos/soccer/500/178.png",
    "nantes": "https://a.espncdn.com/i/teamlogos/soccer/500/165.png",
    "angers sco": "https://a.espncdn.com/i/teamlogos/soccer/500/173.png",
    "angers": "https://a.espncdn.com/i/teamlogos/soccer/500/173.png",
    "troyes": "https://a.espncdn.com/i/teamlogos/soccer/500/177.png",
    "lorient": "https://a.espncdn.com/i/teamlogos/soccer/500/274.png",
    "le havre": "https://a.espncdn.com/i/teamlogos/soccer/500/3430.png",
}

# 6. PAÍSES BAJOS: Eredivisie
EREDIVISIE_BADGES = {
    "ajax": "https://a.espncdn.com/i/teamlogos/soccer/500/139.png",
    "feyenoord": "https://a.espncdn.com/i/teamlogos/soccer/500/140.png",
    "psv": "https://a.espncdn.com/i/teamlogos/soccer/500/148.png",
    "psv eindhoven": "https://a.espncdn.com/i/teamlogos/soccer/500/148.png",
    "utrecht": "https://a.espncdn.com/i/teamlogos/soccer/500/147.png",
    "az": "https://a.espncdn.com/i/teamlogos/soccer/500/144.png",
    "az alkmaar": "https://a.espncdn.com/i/teamlogos/soccer/500/144.png",
    "twente": "https://a.espncdn.com/i/teamlogos/soccer/500/149.png",
    "telstar": "https://a.espncdn.com/i/teamlogos/soccer/500/146.png",
    "excelsior": "https://a.espncdn.com/i/teamlogos/soccer/500/141.png",
    "heerenveen": "https://a.espncdn.com/i/teamlogos/soccer/500/142.png",
    "vitesse": "https://a.espncdn.com/i/teamlogos/soccer/500/145.png",
}

# 7. MÉXICO: Liga MX
LIGAMX_BADGES = {
    "america": "https://a.espncdn.com/i/teamlogos/soccer/500/227.png",
    "club america": "https://a.espncdn.com/i/teamlogos/soccer/500/227.png",
    "guadalajara": "https://a.espncdn.com/i/teamlogos/soccer/500/218.png",
    "chivas": "https://a.espncdn.com/i/teamlogos/soccer/500/218.png",
    "chivas guadalajara": "https://a.espncdn.com/i/teamlogos/soccer/500/218.png",
    "pachuca": "https://a.espncdn.com/i/teamlogos/soccer/500/224.png",
    "tijuana": "https://a.espncdn.com/i/teamlogos/soccer/500/6927.png",
    "toluca": "https://a.espncdn.com/i/teamlogos/soccer/500/232.png",
    "santos laguna": "https://a.espncdn.com/i/teamlogos/soccer/500/231.png",
    "santos": "https://a.espncdn.com/i/teamlogos/soccer/500/231.png",
    "queretaro": "https://a.espncdn.com/i/teamlogos/soccer/500/226.png",
    "leon": "https://a.espncdn.com/i/teamlogos/soccer/500/220.png",
    "monterrey": "https://a.espncdn.com/i/teamlogos/soccer/500/228.png",
    "tigres": "https://a.espncdn.com/i/teamlogos/soccer/500/233.png",
    "tigres uanl": "https://a.espncdn.com/i/teamlogos/soccer/500/233.png",
    "cruz azul": "https://a.espncdn.com/i/teamlogos/soccer/500/219.png",
    "pumas": "https://a.espncdn.com/i/teamlogos/soccer/500/229.png",
    "pumas unam": "https://a.espncdn.com/i/teamlogos/soccer/500/229.png",
    "atlas": "https://a.espncdn.com/i/teamlogos/soccer/500/215.png",
    "puebla": "https://a.espncdn.com/i/teamlogos/soccer/500/225.png",
    "necaxa": "https://a.espncdn.com/i/teamlogos/soccer/500/223.png",
    "atletico san luis": "https://a.espncdn.com/i/teamlogos/soccer/500/19036.png",
    "mazatlan": "https://a.espncdn.com/i/teamlogos/soccer/500/19992.png",
    "juarez": "https://a.espncdn.com/i/teamlogos/soccer/500/19047.png",
}

# 8. BRASIL: Brasileirão
BRASIL_BADGES = {
    "flamengo": "https://images.fotmob.com/image_resources/logo/teamlogo/5926.png",
    "palmeiras": "https://a.espncdn.com/i/teamlogos/soccer/500/2029.png",
    "gremio": "https://a.espncdn.com/i/teamlogos/soccer/500/1968.png",
    "corinthians": "https://a.espncdn.com/i/teamlogos/soccer/500/1957.png",
    "fluminense": "https://a.espncdn.com/i/teamlogos/soccer/500/1981.png",
    "botafogo": "https://images.fotmob.com/image_resources/logo/teamlogo/8517.png",
    "sao paulo": "https://a.espncdn.com/i/teamlogos/soccer/500/1980.png",
    "internacional": "https://a.espncdn.com/i/teamlogos/soccer/500/1967.png",
    "atletico mineiro": "https://a.espncdn.com/i/teamlogos/soccer/500/1977.png",
    "cruzeiro": "https://a.espncdn.com/i/teamlogos/soccer/500/1966.png",
    "vitoria": "https://a.espncdn.com/i/teamlogos/soccer/500/1983.png",
    "rb bragantino": "https://a.espncdn.com/i/teamlogos/soccer/500/19985.png",
    "bragantino": "https://a.espncdn.com/i/teamlogos/soccer/500/19985.png",
    "athletico-pr": "https://a.espncdn.com/i/teamlogos/soccer/500/3457.png",
    "athletico paranaense": "https://a.espncdn.com/i/teamlogos/soccer/500/3457.png",
    "bahia": "https://a.espncdn.com/i/teamlogos/soccer/500/1955.png",
    "fortaleza": "https://a.espncdn.com/i/teamlogos/soccer/500/6245.png",
    "vasco da gama": "https://a.espncdn.com/i/teamlogos/soccer/500/1970.png",
    "vasco": "https://a.espncdn.com/i/teamlogos/soccer/500/1970.png",
    "chapecoense": "https://a.espncdn.com/i/teamlogos/soccer/500/10043.png",
    "coritiba": "https://a.espncdn.com/i/teamlogos/soccer/500/1960.png",
}

# 9. ARGENTINA: Liga Profesional
ARGENTINA_BADGES = {
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
    "central cordoba": "https://a.espncdn.com/i/teamlogos/soccer/500/10323.png",
    "barracas central": "https://a.espncdn.com/i/teamlogos/soccer/500/11520.png",
    "instituto": "https://a.espncdn.com/i/teamlogos/soccer/500/19044.png",
    "sarmiento": "https://a.espncdn.com/i/teamlogos/soccer/500/9474.png",
    "deportivo riestra": "https://a.espncdn.com/i/teamlogos/soccer/500/19488.png",
}

# 10. URUGUAY: Liga Uruguaya
URUGUAY_BADGES = {
    "nacional": "https://a.espncdn.com/i/teamlogos/soccer/500/13.png",
    "penarol": "https://a.espncdn.com/i/teamlogos/soccer/500/15.png",
    "defensor sporting": "https://a.espncdn.com/i/teamlogos/soccer/500/247.png",
    "danubio": "https://a.espncdn.com/i/teamlogos/soccer/500/248.png",
    "wanderers": "https://a.espncdn.com/i/teamlogos/soccer/500/251.png",
    "montevideo wanderers": "https://a.espncdn.com/i/teamlogos/soccer/500/251.png",
    "liverpool": "https://a.espncdn.com/i/teamlogos/soccer/500/249.png",
    "cerro": "https://a.espncdn.com/i/teamlogos/soccer/500/250.png",
    "river plate": "https://a.espncdn.com/i/teamlogos/soccer/500/252.png",
    "fenix": "https://a.espncdn.com/i/teamlogos/soccer/500/253.png",
    "racing": "https://a.espncdn.com/i/teamlogos/soccer/500/254.png",
}

# 11. COLOMBIA: Liga BetPlay
COLOMBIA_BADGES = {
    "junior": "https://a.espncdn.com/i/teamlogos/soccer/500/208.png",
    "atletico nacional": "https://a.espncdn.com/i/teamlogos/soccer/500/205.png",
    "america de cali": "https://a.espncdn.com/i/teamlogos/soccer/500/204.png",
    "millonarios": "https://a.espncdn.com/i/teamlogos/soccer/500/206.png",
    "santa fe": "https://a.espncdn.com/i/teamlogos/soccer/500/207.png",
    "independiente santa fe": "https://a.espncdn.com/i/teamlogos/soccer/500/207.png",
    "deportes tolima": "https://a.espncdn.com/i/teamlogos/soccer/500/212.png",
    "tolima": "https://a.espncdn.com/i/teamlogos/soccer/500/212.png",
    "deportivo cali": "https://a.espncdn.com/i/teamlogos/soccer/500/209.png",
    "independiente medellin": "https://a.espncdn.com/i/teamlogos/soccer/500/210.png",
    "once caldas": "https://a.espncdn.com/i/teamlogos/soccer/500/211.png",
    "atletico bucaramanga": "https://a.espncdn.com/i/teamlogos/soccer/500/3765.png",
    "bucaramanga": "https://a.espncdn.com/i/teamlogos/soccer/500/3765.png",
    "deportivo pereira": "https://images.fotmob.com/image_resources/logo/teamlogo/6470.png",
}

# 12. OTROS TOP CLUBES (Turquía, Portugal, MLS, etc.)
OTROS_CLUBS = {
    "fenerbahce": "https://a.espncdn.com/i/teamlogos/soccer/500/436.png",
    "besiktas": "https://a.espncdn.com/i/teamlogos/soccer/500/435.png",
    "galatasaray": "https://a.espncdn.com/i/teamlogos/soccer/500/437.png",
    "trabzonspor": "https://a.espncdn.com/i/teamlogos/soccer/500/440.png",
    "porto": "https://a.espncdn.com/i/teamlogos/soccer/500/237.png",
    "fc porto": "https://a.espncdn.com/i/teamlogos/soccer/500/237.png",
    "benfica": "https://a.espncdn.com/i/teamlogos/soccer/500/236.png",
    "sporting cp": "https://a.espncdn.com/i/teamlogos/soccer/500/238.png",
    "sporting lisboa": "https://a.espncdn.com/i/teamlogos/soccer/500/238.png",
    "braga": "https://a.espncdn.com/i/teamlogos/soccer/500/2470.png",
    "inter miami": "https://images.fotmob.com/image_resources/logo/teamlogo/1083466.png",
    "la galaxy": "https://a.espncdn.com/i/teamlogos/soccer/500/187.png",
    "los angeles fc": "https://a.espncdn.com/i/teamlogos/soccer/500/189.png",
    "colo-colo": "https://images.fotmob.com/image_resources/logo/teamlogo/6448.png",
    "colo colo": "https://images.fotmob.com/image_resources/logo/teamlogo/6448.png",
    "universidad de chile": "https://images.fotmob.com/image_resources/logo/teamlogo/6451.png",
    "olimpia": "https://images.fotmob.com/image_resources/logo/teamlogo/6532.png",
    "cerro porteno": "https://images.fotmob.com/image_resources/logo/teamlogo/6530.png",
    "ldu quito": "https://images.fotmob.com/image_resources/logo/teamlogo/6487.png",
    "barcelona sc": "https://images.fotmob.com/image_resources/logo/teamlogo/6484.png",
    "alianza lima": "https://images.fotmob.com/image_resources/logo/teamlogo/6537.png",
    "universitario": "https://images.fotmob.com/image_resources/logo/teamlogo/6541.png",
}

# 13. MLS: Major League Soccer
MLS_BADGES = {
    "inter miami": "https://images.fotmob.com/image_resources/logo/teamlogo/1083466.png",
    "inter miami cf": "https://images.fotmob.com/image_resources/logo/teamlogo/1083466.png",
    "atlanta united": "https://a.espncdn.com/i/teamlogos/soccer/500/18418.png",
    "atlanta united fc": "https://a.espncdn.com/i/teamlogos/soccer/500/18418.png",
    "los angeles fc": "https://a.espncdn.com/i/teamlogos/soccer/500/18966.png",
    "lafc": "https://a.espncdn.com/i/teamlogos/soccer/500/18966.png",
    "la galaxy": "https://a.espncdn.com/i/teamlogos/soccer/500/187.png",
    "los angeles galaxy": "https://a.espncdn.com/i/teamlogos/soccer/500/187.png",
    "seattle sounders": "https://a.espncdn.com/i/teamlogos/soccer/500/9723.png",
    "new york city fc": "https://a.espncdn.com/i/teamlogos/soccer/500/17606.png",
    "nycfc": "https://a.espncdn.com/i/teamlogos/soccer/500/17606.png",
    "new york red bulls": "https://a.espncdn.com/i/teamlogos/soccer/500/190.png",
    "ny red bulls": "https://a.espncdn.com/i/teamlogos/soccer/500/190.png",
    "columbus crew": "https://a.espncdn.com/i/teamlogos/soccer/500/182.png",
    "orlando city": "https://a.espncdn.com/i/teamlogos/soccer/500/12011.png",
    "fc cincinnati": "https://a.espncdn.com/i/teamlogos/soccer/500/18267.png",
    "cincinnati": "https://a.espncdn.com/i/teamlogos/soccer/500/18267.png",
    "philadelphia union": "https://a.espncdn.com/i/teamlogos/soccer/500/10972.png",
    "nashville sc": "https://a.espncdn.com/i/teamlogos/soccer/500/19308.png",
    "houston dynamo": "https://a.espncdn.com/i/teamlogos/soccer/500/6077.png",
    "austin fc": "https://a.espncdn.com/i/teamlogos/soccer/500/20906.png",
    "portland timbers": "https://a.espncdn.com/i/teamlogos/soccer/500/9727.png",
    "vancouver whitecaps": "https://a.espncdn.com/i/teamlogos/soccer/500/9728.png",
    "toronto fc": "https://a.espncdn.com/i/teamlogos/soccer/500/7318.png",
    "cf montreal": "https://a.espncdn.com/i/teamlogos/soccer/500/9725.png",
    "sporting kansas city": "https://a.espncdn.com/i/teamlogos/soccer/500/186.png",
    "real salt lake": "https://a.espncdn.com/i/teamlogos/soccer/500/4771.png",
    "colorado rapids": "https://a.espncdn.com/i/teamlogos/soccer/500/181.png",
    "minnesota united": "https://a.espncdn.com/i/teamlogos/soccer/500/17362.png",
    "st louis city": "https://a.espncdn.com/i/teamlogos/soccer/500/21539.png",
    "fc dallas": "https://a.espncdn.com/i/teamlogos/soccer/500/183.png",
    "chicago fire": "https://a.espncdn.com/i/teamlogos/soccer/500/180.png",
    "san jose earthquakes": "https://a.espncdn.com/i/teamlogos/soccer/500/191.png",
    "new england revolution": "https://a.espncdn.com/i/teamlogos/soccer/500/189.png",
    "dc united": "https://a.espncdn.com/i/teamlogos/soccer/500/193.png",
    "charlotte fc": "https://a.espncdn.com/i/teamlogos/soccer/500/21212.png",
}

# 14. NFL: Fútbol Americano
NFL_BADGES = {
    "new england patriots": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
    "patriots": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
    "pittsburgh steelers": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
    "steelers": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
    "chicago bears": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
    "bears": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
    "minnesota vikings": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
    "vikings": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
    "cincinnati bengals": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
    "bengals": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
    "houston texans": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
    "texans": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
    "new orleans saints": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
    "saints": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
    "baltimore ravens": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
    "ravens": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
    "dallas cowboys": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
    "cowboys": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
    "washington commanders": "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
    "commanders": "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
    "denver broncos": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
    "broncos": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
    "jacksonville jaguars": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
    "jaguars": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
    "las vegas raiders": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
    "raiders": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
    "los angeles chargers": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
    "chargers": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
    "miami dolphins": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
    "dolphins": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
    "san francisco 49ers": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
    "49ers": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
    "kansas city chiefs": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    "chiefs": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    "indianapolis colts": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
    "colts": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
    "green bay packers": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
    "packers": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
    "philadelphia eagles": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
    "eagles": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
    "buffalo bills": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
    "bills": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
}

# 14. MLB: Béisbol
MLB_BADGES = {
    "baltimore orioles": "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png",
    "orioles": "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png",
    "milwaukee brewers": "https://a.espncdn.com/i/teamlogos/mlb/500/mil.png",
    "brewers": "https://a.espncdn.com/i/teamlogos/mlb/500/mil.png",
    "new york yankees": "https://a.espncdn.com/i/teamlogos/mlb/500/nyy.png",
    "yankees": "https://a.espncdn.com/i/teamlogos/mlb/500/nyy.png",
    "los angeles dodgers": "https://a.espncdn.com/i/teamlogos/mlb/500/lad.png",
    "dodgers": "https://a.espncdn.com/i/teamlogos/mlb/500/lad.png",
    "boston red sox": "https://a.espncdn.com/i/teamlogos/mlb/500/bos.png",
    "red sox": "https://a.espncdn.com/i/teamlogos/mlb/500/bos.png",
    "houston astros": "https://a.espncdn.com/i/teamlogos/mlb/500/hou.png",
    "astros": "https://a.espncdn.com/i/teamlogos/mlb/500/hou.png",
}

# 15. SELECCIONES NACIONALES / COPA DAVIS / PAÍSES (FlagCDN)
COUNTRY_FLAGS = {
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
    "alemania": "https://flagcdn.com/w80/de.png",
    "germany": "https://flagcdn.com/w80/de.png",
    "croacia": "https://flagcdn.com/w80/hr.png",
    "croatia": "https://flagcdn.com/w80/hr.png",
    "turquia": "https://flagcdn.com/w80/tr.png",
    "turkey": "https://flagcdn.com/w80/tr.png",
    "francia": "https://flagcdn.com/w80/fr.png",
    "france": "https://flagcdn.com/w80/fr.png",
    "italia": "https://flagcdn.com/w80/it.png",
    "italy": "https://flagcdn.com/w80/it.png",
    "inglaterra": "https://flagcdn.com/w80/gb-eng.png",
    "england": "https://flagcdn.com/w80/gb-eng.png",
    "portugal": "https://flagcdn.com/w80/pt.png",
    "paises bajos": "https://flagcdn.com/w80/nl.png",
    "holanda": "https://flagcdn.com/w80/nl.png",
    "estados unidos": "https://flagcdn.com/w80/us.png",
    "usa": "https://flagcdn.com/w80/us.png",
    "canada": "https://flagcdn.com/w80/ca.png",
}

# ==============================================================================
# MOTOR DE BÚSQUEDA INTELIGENTE DE LOGOS
# ==============================================================================
def get_team_badge(name, competition=""):
    """
    Retorna la URL del escudo oficial con precisión total.
    Toma en cuenta la competición para evitar cruces indebidos.
    """
    if not name:
        return None
        
    clean = clean_team_name(name)
    comp_clean = clean_team_name(competition)
    
    # 1. Comprobación contextual de NFL / Béisbol
    if "nfl" in comp_clean:
        if clean in NFL_BADGES:
            return NFL_BADGES[clean]
        for k, v in NFL_BADGES.items():
            if k in clean:
                return v
        return None
        
    if "mlb" in comp_clean or "beisbol" in comp_clean or "baseball" in comp_clean:
        if clean in MLB_BADGES:
            return MLB_BADGES[clean]
        for k, v in MLB_BADGES.items():
            if k in clean:
                return v
        return None

    # 2. Comprobación contextual de Selecciones Nacionales / Copa Davis
    if "davis" in comp_clean or "seleccion" in comp_clean or "mundial" in comp_clean or "copa america" in comp_clean or "euro" in comp_clean:
        if clean in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[clean]
            
    # 3. Comprobación contextual por liga
    if "uruguay" in comp_clean:
        if clean in URUGUAY_BADGES:
            return URUGUAY_BADGES[clean]
            
    if "colombia" in comp_clean:
        if clean in COLOMBIA_BADGES:
            return COLOMBIA_BADGES[clean]
            
    if "mex" in comp_clean or "mx" in comp_clean:
        if clean in LIGAMX_BADGES:
            return LIGAMX_BADGES[clean]
            
    if "mls" in comp_clean or "major league" in comp_clean:
        if clean in MLS_BADGES:
            return MLS_BADGES[clean]
            
    if "brasil" in comp_clean:
        if clean in BRASIL_BADGES:
            return BRASIL_BADGES[clean]
            
    if "argentina" in comp_clean or "profesional" in comp_clean:
        if clean in ARGENTINA_BADGES:
            return ARGENTINA_BADGES[clean]
            
    if "eredivisie" in comp_clean or "holanda" in comp_clean or "paises bajos" in comp_clean:
        if clean in EREDIVISIE_BADGES:
            return EREDIVISIE_BADGES[clean]
            
    if "premier" in comp_clean or "championship" in comp_clean:
        if clean in PREMIER_BADGES:
            return PREMIER_BADGES[clean]
            
    if "serie a" in comp_clean or "italia" in comp_clean:
        if clean in SERIEA_BADGES:
            return SERIEA_BADGES[clean]
            
    if "bundesliga" in comp_clean or "alemania" in comp_clean:
        if clean in BUNDESLIGA_BADGES:
            return BUNDESLIGA_BADGES[clean]
            
    if "ligue 1" in comp_clean or "francia" in comp_clean:
        if clean in LIGUE1_BADGES:
            return LIGUE1_BADGES[clean]
            
    if "laliga" in comp_clean or "espana" in comp_clean or "hypermotion" in comp_clean:
        if clean in LALIGA_BADGES:
            return LALIGA_BADGES[clean]

    # 4. Comprobación global exacta en diccionarios
    all_dicts = [
        LALIGA_BADGES, PREMIER_BADGES, SERIEA_BADGES, BUNDESLIGA_BADGES,
        LIGUE1_BADGES, EREDIVISIE_BADGES, LIGAMX_BADGES, MLS_BADGES, BRASIL_BADGES,
        ARGENTINA_BADGES, OTROS_CLUBS, COUNTRY_FLAGS, URUGUAY_BADGES,
        COLOMBIA_BADGES, NFL_BADGES, MLB_BADGES
    ]
    
    for d in all_dicts:
        if clean in d:
            return d[clean]
            
    # 5. Coincidencia por palabras completas (SOLO para nombres compuestos de 2+ palabras)
    # Ejemplo: 'borussia dortmund' dentro de 'borussia dortmund fc'
    # NUNCA para palabras genéricas individuales como 'city', 'real', 'wanderers', 'racing', etc.
    words = clean.split()
    if len(words) >= 2:
        for d in all_dicts:
            for k, url in d.items():
                if len(k.split()) >= 2 and k in clean:
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
