"""Daily schedule shared by the bots and web app, in Venezuela time."""
import base64
import copy
import hashlib
import html
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

LOCAL_TZ = timezone(timedelta(hours=-4), "America/Caracas")
SOURCE_TZ = timezone(timedelta(hours=-5), "America/Lima")
AGENDA_URL = os.environ.get("AGENDA_URL", "https://api.wqxag.com/diaries.json")
TARJETA_DIGITAL_AGENDA_URL = os.environ.get("TARJETA_DIGITAL_AGENDA_URL", "https://tarjetadigital.club/api/agenda")


class ScheduleUnavailable(RuntimeError):
    pass


def chronological(events):
    """Order the already-local schedule by clock time; unknown times go last."""
    def key(event):
        clock = re.fullmatch(r"(\d{1,2}):(\d{2})", str(event.get("time", "")))
        minutes = 24 * 60
        if clock and int(clock[1]) < 24 and int(clock[2]) < 60:
            minutes = int(clock[1]) * 60 + int(clock[2])
        return minutes, str(event.get("match", "")).casefold()
    return sorted(events, key=key)


def slugify(text):
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def simplified_slug(slug):
    tokens = [w for w in slug.split("-") if w not in ("fc", "cf", "cd", "real", "club", "deportivo", "atletico", "inter")]
    return "-".join(tokens) or slug


def attributes(item):
    if not isinstance(item, dict):
        return {}
    value = item.get("attributes", item)
    return value if isinstance(value, dict) else {}


def items(value):
    value = value.get("data", []) if isinstance(value, dict) else value
    return value if isinstance(value, list) else []


def unwrap_player(value):
    value = html.unescape(str(value or "")).strip()
    # Public wrapper parameter: a base64-encoded player URL, not executable code.
    encoded = parse_qs(urlsplit(value).query).get("r", [""])[0]
    if encoded:
        try:
            candidate = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
            if urlsplit(candidate).scheme in ("http", "https"):
                return candidate
        except (ValueError, UnicodeError):
            pass
    if value.startswith(("http://", "https://")):
        return value
    return urljoin("https://rojadirectatvplay.org/", value) if value else ""


def normalize_schedule(payload, now=None):
    now = now or datetime.now(LOCAL_TZ)
    today = now.astimezone(LOCAL_TZ).date()
    raw = payload.get("data", payload.get("events")) if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    events = []
    seen = set()
    for item in raw:
        a = attributes(item)
        title = " ".join(str(a.get("diary_description") or a.get("title") or "").split())
        if not title:
            continue
        strapi = "diary_description" in a
        date = str(a.get("date_diary") or a.get("date") or "")[:10]
        if not date:
            date = today.isoformat()
        hour = str(a.get("diary_hour") or a.get("time") or "")
        try:
            if "T" in hour:
                starts = datetime.fromisoformat(hour.replace("Z", "+00:00"))
                if starts.tzinfo is None:
                    starts = starts.replace(tzinfo=SOURCE_TZ)
            else:
                h_clean = hour[:8].strip() if hour else "12:00:00"
                if len(h_clean.split(":")) == 2:
                    h_clean += ":00"
                starts = datetime.fromisoformat(f"{date}T{h_clean}").replace(tzinfo=SOURCE_TZ if strapi else timezone.utc)
            starts = starts.astimezone(LOCAL_TZ)
        except (ValueError, TypeError):
            continue  # An undated row cannot safely be advertised as today's event.
        if starts.date() != today:
            continue
        competition, sep, match = title.partition(":")
        if not sep:
            competition, match = str(a.get("sport") or "Deportes"), title
        match = match.strip()
        identity = (starts.isoformat(), slugify(title))
        if identity in seen:
            continue
        seen.add(identity)
        channels = []
        channel_seen = set()
        for index, embed in enumerate(items(a.get("embeds", []))):
            e = attributes(embed)
            name = str(e.get("embed_name") or e.get("name") or f"Opción {index + 1}").strip()
            player = unwrap_player(e.get("embed_iframe") or e.get("iframe") or e.get("url"))
            parsed = urlsplit(player)
            stream = parse_qs(parsed.query).get("stream", [""])[0].lower()
            slug = stream if re.fullmatch(r"[a-z0-9_-]+", stream) else "evento-" + hashlib.sha256(player.encode()).hexdigest()[:12]
            if not player or player in channel_seen or parsed.scheme not in ("http", "https"):
                continue
            channel_seen.add(player)
            channels.append(dict(name=name, slug=slug, iframe=player, lang=e.get("lang", "")))
        country = attributes(a.get("country", {}).get("data", {})) if isinstance(a.get("country"), dict) else {}
        image = attributes(country.get("image", {}).get("data", {})) if isinstance(country.get("image"), dict) else {}
        events.append(dict(id=item.get("id") if isinstance(item, dict) else None,
                           date=starts.date().isoformat(), time=starts.strftime("%H:%M") if hour else "--:--",
                           starts_at=starts.isoformat(), competition=competition.strip(), match=match,
                           match_slug=slugify(match), comp_img=urljoin("https://img.wqxag.com", image.get("url", "")) if image else "",
                           channels=channels))
    return sorted(events, key=lambda event: (event["starts_at"], event["match"]))


class ScheduleService:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = []
        self.day = None
        self.loaded = 0
        self.attempted = 0
        self.stale = False

    def get(self, now=None):
        now = now or datetime.now(LOCAL_TZ)
        day = now.astimezone(LOCAL_TZ).date()
        with self.lock:
            age = time.monotonic() - self.loaded
            if self.day == day and age < 90 and not self.stale:
                return copy.deepcopy(self.events)
            if self.day == day and self.stale and age < 1800 and time.monotonic() - self.attempted < 15:
                return copy.deepcopy(self.events)
            self.attempted = time.monotonic()
            
            all_events = []
            failures = []
            successes = 0

            # 1. Tarjeta Digital agenda
            try:
                r_td = requests.get(
                    TARJETA_DIGITAL_AGENDA_URL,
                    timeout=(5, 8),
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://tarjetadigital.club/"
                    }
                )
                r_td.raise_for_status()
                if r_td.status_code == 200:
                    successes += 1
                    td_events = normalize_schedule(r_td.json(), now)
                    all_events.extend(td_events)
            except Exception as exc:
                failures.append(type(exc).__name__)

            # 2. Roja / WQXAG agenda
            try:
                response = requests.get(AGENDA_URL, timeout=(5, 10), headers={"Accept": "application/json"})
                response.raise_for_status()
                if response.status_code == 200:
                    successes += 1
                    roja_events = normalize_schedule(response.json(), now)
                    # Merge evitando duplicados pero combinando todas las señales de transmisión disponibles
                    events_by_slug = {e["match_slug"]: e for e in all_events}
                    events_by_simple = {simplified_slug(e["match_slug"]): e for e in all_events}
                    for rev in roja_events:
                        slug = rev["match_slug"]
                        simple = simplified_slug(slug)
                        existing = events_by_slug.get(slug) or events_by_simple.get(simple)
                        if not existing:
                            all_events.append(rev)
                            events_by_slug[slug] = rev
                            events_by_simple[simple] = rev
                        else:
                            # Combinar canales evitando duplicados de señal
                            existing_keys = {(c["slug"], slugify(c["name"])) for c in existing["channels"]}
                            for ch in rev["channels"]:
                                key = (ch["slug"], slugify(ch["name"]))
                                if key not in existing_keys:
                                    existing["channels"].append(ch)
                                    existing_keys.add(key)
            except Exception as exc:
                failures.append(type(exc).__name__)

            if not all_events and failures and not successes:
                if self.day == day and age < 1800:
                    self.stale = True
                    return copy.deepcopy(self.events)
                raise ScheduleUnavailable("No se pudo actualizar la agenda (" + ", ".join(failures) + ")")

            all_events = sorted(all_events, key=lambda event: (event["starts_at"], event["match"]))
            self.events, self.day, self.loaded, self.stale = all_events, day, time.monotonic(), False
            return copy.deepcopy(all_events)

    def channel(self, slug):
        with self.lock:
            # Do not resolve an event from yesterday's cached schedule.
            if self.day != datetime.now(LOCAL_TZ).date():
                return None
            for event in self.events:
                for channel in event["channels"]:
                    if channel["slug"] == slug:
                        return dict(channel)
        return None


schedule = ScheduleService()
