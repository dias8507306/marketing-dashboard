"""One database API for both homes of the bot.

On Vercel there is no disk that survives between requests, so data lives in Postgres
(DATABASE_URL, e.g. Neon from the Vercel Marketplace). Without it — local runs and
tests — a SQLite file in DATA_DIR is used. Queries are written once, SQLite-style
with «?» placeholders and SQL both engines understand; Postgres gets «%s».
"""
import os
import sqlite3
from pathlib import Path

def _clean(url: str) -> str:
    """Keep only the query parameters libpq knows (Supabase adds e.g. «supa=base-pooler.x», which psycopg rejects)."""
    if "?" not in url:
        return url
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    known = {"sslmode", "connect_timeout", "application_name", "options", "target_session_attrs", "channel_binding"}
    parts = urlsplit(url)
    return urlunsplit(parts._replace(query=urlencode([(k, v) for k, v in parse_qsl(parts.query) if k in known])))


# A second database connected with the «NEW» prefix wins over the old one (moved off Neon's free plan, October 2026).
PG_URL = _clean(os.getenv("NEW_POSTGRES_URL") or os.getenv("NEW_DATABASE_URL")
                or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "")

SCHEMA = [
    "create table if not exists seen (mid text primary key, ts bigint)",
    "create table if not exists users (igsid text primary key, topic text, awaiting text, ts bigint)",
    # Permanent funnel log for the stats page.
    "create table if not exists events (ts bigint, igsid text, event text, topic text, detail text)",
    "create index if not exists events_ts on events (ts)",
    "create table if not exists links (token text primary key, igsid text, topic text, detail text,"
    " label text, url text, ts bigint)",
    # Instagram usernames of people managers may need to contact.
    "create table if not exists profiles (igsid text primary key, username text, ts bigint)",
    "create table if not exists starts (igsid text, topic text, ts bigint, primary key (igsid, topic))",
    "create table if not exists leads (igsid text primary key, username text, topic text, city text,"
    " grade text, phone text, texts text, first_ts bigint, updated_ts bigint, thanked integer default 0,"
    " synced integer default 0)",
    # Small settings that must survive restarts: the Instagram token and when it was refreshed.
    "create table if not exists kv (k text primary key, v text, ts bigint)",
]


class _PG:
    """psycopg connection that accepts SQLite-style «?» placeholders."""

    def __init__(self, url):
        import psycopg
        self._psycopg = psycopg
        self._url = url
        self._con = None

    def _connect(self):
        if self._con is None or self._con.closed:
            self._con = self._psycopg.connect(self._url, autocommit=True, connect_timeout=10,
                                               prepare_threshold=None)  # safe behind the Neon pooler
        return self._con

    def execute(self, sql, params=()):
        sql = sql.replace("%", "%%").replace("?", "%s")
        try:
            return self._connect().execute(sql, tuple(params))
        except self._psycopg.OperationalError:
            # Neon closes idle connections; reconnect once and retry.
            self._con = None
            return self._connect().execute(sql, tuple(params))

    def executemany(self, sql, rows):
        sql = sql.replace("%", "%%").replace("?", "%s")
        with self._connect().cursor() as cur:
            cur.executemany(sql, [tuple(r) for r in rows])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Lite:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(path, check_same_thread=False)

    def execute(self, sql, params=()):
        return self._con.execute(sql, params)

    def executemany(self, sql, rows):
        self._con.executemany(sql, rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._con.commit()
        return False


_db = None


def db():
    """Shared connection for this process; tables are created on first use."""
    global _db
    if _db is None:
        conn = _PG(PG_URL) if PG_URL else _Lite(Path(os.getenv("DATA_DIR", "/data")) / "bot.db")
        for stmt in SCHEMA:
            conn.execute(stmt)
        if not PG_URL:
            conn._con.commit()
        _db = conn
    return _db
