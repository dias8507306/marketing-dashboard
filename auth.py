"""Logins for the marketing dashboard.

The admin is STATS_USER / STATS_PASSWORD from the environment (the same login as before).
Employees (Айгерім, Дана…) are created by the admin on the team page; their passwords
are typed by the admin and stored only as PBKDF2 hashes. A login gives a signed cookie.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

COOKIE = "zsess"
SESSION_DAYS = 30
_SECRET = hashlib.sha256(("eduapp-session|" + (os.getenv("SESSION_SECRET") or os.getenv("INSTAGRAM_APP_SECRET")
                                                  or os.getenv("STATS_PASSWORD") or "dev")).encode()).digest()


_READY = False  # tables are created once per process: each statement is a round trip to the database


def ensure_table(con):
    global _READY
    if _READY:
        return
    _READY = True
    con.execute("create table if not exists staff (login text primary key, name text, pwd text, role text,"
                " plans text, active integer default 1, ts bigint)")


def hash_password(pwd: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def check_password(pwd: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pwd.encode(), base64.b64decode(salt), 200_000)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False


def sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    mac = hmac.new(_SECRET, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{mac}"


def unsign(token: str):
    try:
        raw, mac = token.rsplit(".", 1)
        if not hmac.compare_digest(mac, hmac.new(_SECRET, raw.encode(), hashlib.sha256).hexdigest()[:32]):
            return None
        data = json.loads(base64.urlsafe_b64decode(raw.encode()))
        return data if data.get("exp", 0) > time.time() else None
    except Exception:
        return None


def login(con, user: str, pwd: str):
    """Session payload for good credentials, else None."""
    admin_user, admin_pwd = os.getenv("STATS_USER", "eduapp"), os.getenv("STATS_PASSWORD", "")
    if admin_pwd and hmac.compare_digest(user, admin_user) and hmac.compare_digest(pwd, admin_pwd):
        return {"u": admin_user, "n": "Әкімші", "r": "admin", "exp": int(time.time()) + SESSION_DAYS * 86400}
    ensure_table(con)
    row = con.execute("select login, name, pwd, role from staff where login = ? and active = 1", (user.lower(),)).fetchone()
    if row and check_password(pwd, row[2]):
        return {"u": row[0], "n": row[1], "r": row[3] or "smm", "exp": int(time.time()) + SESSION_DAYS * 86400}
    return None


def staff(con, active_only=True) -> list:
    ensure_table(con)
    q = "select login, name, role, plans, active from staff" + (" where active = 1" if active_only else "") + " order by name"
    return [{"login": r[0], "name": r[1], "role": r[2], "plans": json.loads(r[3] or "{}"), "active": r[4]}
            for r in con.execute(q)]


def get_staff(con, login: str):
    return next((s for s in staff(con, False) if s["login"] == login), None)


def save_staff(con, login: str, name: str, role: str, plans: dict, pwd: str | None):
    ensure_table(con)
    login = login.strip().lower()
    old = con.execute("select pwd from staff where login = ?", (login,)).fetchone()
    pw = hash_password(pwd) if pwd else (old[0] if old else None)
    if not pw:
        raise ValueError("password required")
    con.execute("insert into staff values (?, ?, ?, ?, ?, 1, ?) on conflict (login) do update set name = excluded.name,"
                " pwd = excluded.pwd, role = excluded.role, plans = excluded.plans, active = 1, ts = excluded.ts",
                (login, name.strip(), pw, role, json.dumps(plans), int(time.time())))


def deactivate(con, login: str):
    ensure_table(con)
    con.execute("update staff set active = 0 where login = ?", (login,))
