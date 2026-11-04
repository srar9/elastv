"""Persistent public-bot visits and playback presence, shared with the web workers."""
import os
import sqlite3
import time
import secrets
from contextlib import closing

OWNER_ID = 6467102546
DB_PATH = os.environ.get("AUDIENCE_DB_PATH", os.path.join(os.path.dirname(__file__), "audience.db"))


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    with closing(connect()) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY, first_seen REAL, last_seen REAL, entries INTEGER);
            CREATE TABLE IF NOT EXISTS visits (
                session_id TEXT PRIMARY KEY, client_id TEXT, match_id TEXT, title TEXT,
                opened REAL, last_seen REAL, playing INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS visits_active ON visits(last_seen, playing);
            CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('proxy_secret', ?)", (secrets.token_hex(32),))


def proxy_key():
    with closing(connect()) as conn:
        return conn.execute("SELECT value FROM settings WHERE name='proxy_secret'").fetchone()[0]


def bot_entry(user_id):
    now = time.time()
    with closing(connect()) as conn, conn:
        conn.execute("""INSERT INTO bot_users VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET last_seen=excluded.last_seen, entries=entries+1""",
                     (user_id, now, now))


def playback(session_id, client_id, match_id, title, playing):
    now = time.time()
    with closing(connect()) as conn, conn:
        conn.execute("""INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET last_seen=excluded.last_seen,
            playing=excluded.playing WHERE visits.client_id=excluded.client_id
            AND visits.match_id=excluded.match_id""",
                     (session_id, client_id, match_id, title, now, now, int(playing)))


def summary():
    cutoff = time.time() - 45
    with closing(connect()) as conn:
        users = conn.execute("SELECT COUNT(*) FROM bot_users").fetchone()[0]
        entries = conn.execute("SELECT COALESCE(SUM(entries),0) FROM bot_users").fetchone()[0]
        app_entries = conn.execute("SELECT COUNT(*) FROM visits WHERE match_id='__app__'").fetchone()[0]
        visits = conn.execute("SELECT COUNT(*), COUNT(DISTINCT client_id) FROM visits WHERE match_id!='__app__'").fetchone()
        active = conn.execute("SELECT COUNT(DISTINCT client_id) FROM visits WHERE match_id!='__app__' AND playing=1 AND last_seen>=?", (cutoff,)).fetchone()[0]
        matches = conn.execute("""SELECT match_id, MAX(title) AS title, COUNT(*) AS entries,
            COUNT(DISTINCT client_id) AS visitors,
            COUNT(DISTINCT CASE WHEN playing=1 AND last_seen>=? THEN client_id END) AS watching
            FROM visits WHERE match_id!='__app__' GROUP BY match_id ORDER BY watching DESC, entries DESC""", (cutoff,)).fetchall()
    return dict(bot_users=users, bot_entries=entries, app_entries=app_entries, player_entries=visits[0],
                player_visitors=visits[1], watching=active, matches=[dict(r) for r in matches])


initialize()
