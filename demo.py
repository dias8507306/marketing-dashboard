"""Run the dashboard locally in DEMO mode — no Instagram, amoCRM, Meta, Telegram, Gemini or Postgres needed.

    python demo.py                 # http://127.0.0.1:8000  (login: demo / demo)
    python demo.py --port 8080
    python demo.py --render out/   # render every page to static HTML files and exit (used as a smoke test)

What it does:
* points the app at a throwaway SQLite file (demo/.data/bot.db) and seeds it from demo/demo_data.json
  (made by scripts/generate_demo_data.py; dates are relative to today, so the demo always looks current);
* replaces the Instagram Graph API readers (igdata.*) and the amoCRM sync with functions that serve that data;
* blocks every outgoing network connection, so a stray API call fails fast instead of leaking anywhere.
The production code paths are untouched: set the real environment variables and run `uvicorn app:app` instead.
"""
import argparse
import json
import os
import socket
import sys
import time
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "demo" / "demo_data.json"

# ---- 1. environment: demo credentials only, never real keys
for k in list(os.environ):
    if any(x in k for x in ("POSTGRES", "DATABASE", "AMO_", "META_", "TOKEN", "SECRET", "GEMINI", "ANTHROPIC", "TELEGRAM", "SHEETS", "YOUTUBE")):
        del os.environ[k]
DATA_DIR = HERE / "demo" / ".data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.update(DATA_DIR=str(DATA_DIR), CONF_DIR=str(HERE / "conf"), IG_TOKEN="demo", STATS_USER="demo",
                  STATS_PASSWORD="demo", SESSION_SECRET="demo-only-not-a-secret", BOT_ENABLED="false", DEMO_MODE="1")
db_file = DATA_DIR / "bot.db"
if db_file.exists():
    db_file.unlink()

# ---- 2. offline guard: only loopback connections are allowed
BLOCKED = []
_connect, _resolve = socket.socket.connect, socket.getaddrinfo
LOCAL = ("127.0.0.1", "::1", "localhost", "0.0.0.0")


def _guard(host):
    if host not in LOCAL:
        BLOCKED.append(str(host)[:60])
        raise OSError("demo mode: outgoing network is blocked")


def _guarded_connect(self, addr):
    _guard(addr[0] if isinstance(addr, tuple) else addr)
    return _connect(self, addr)


def _guarded_resolve(host, *a, **k):
    _guard(host)
    return _resolve(host, *a, **k)


socket.socket.connect, socket.getaddrinfo = _guarded_connect, _guarded_resolve

sys.path.insert(0, str(HERE))
os.chdir(HERE)
import amo  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402
import dept  # noqa: E402
import extras  # noqa: E402
import history  # noqa: E402
import igdata  # noqa: E402

D = json.loads(DATA.read_text(encoding="utf-8"))
TODAY = igdata.today()
DAYS = {igdata.key(TODAY - timedelta(days=d["ago"])): {k: v for k, v in d.items() if k != "ago"} for d in D["ig_days"]}


# ---- 3. stand-ins for the outside services
async def days(http, api, a, con, first, last):
    out, d = {}, first
    while d <= last:
        k = igdata.key(d)
        if k in DAYS:
            row = DAYS[k]
            out[k] = {**row, "new_followers": max(0, row["follows"] - row["unfollows"])}
        d += timedelta(days=1)
    return out


async def profile(*a, **k):
    return {"followers_count": D["followers_now"], "media_count": 640, "username": "eduapp_demo", "name": "EduApp"}


async def media(http, api, a, con, first, last):
    out = []
    for m in D["media"]:
        day = TODAY - timedelta(days=m["ago"]) + timedelta(hours=12)
        if first <= day <= last + timedelta(days=1):
            out.append({"id": m["id"], "timestamp": day.strftime("%Y-%m-%dT%H:%M:%S+0000"), "ts": day.timestamp(),
                        "media_product_type": m["type"], "media_type": "VIDEO" if m["type"] == "REELS" else "IMAGE",
                        "like_count": m["likes"], "comments_count": m["comments"], "permalink": "#", "caption": m["caption"],
                        "views": m["views"], "reach": m["reach"], "saved": m["saved"], "shares": m["shares"],
                        "total_interactions": m["likes"] + m["comments"] + m["saved"] + m["shares"]})
    return out


async def follow_stats(http, api, a, con, day, cache=None):
    row = DAYS.get(igdata.key(day)) or {"follows": 0, "unfollows": 0}
    return row["follows"], row["unfollows"]


async def noop(*a, **k):
    return None


async def no_sync(*a, **k):
    return {"ok": True, "error": None, "count": 0}


async def no_status(*a, **k):
    return []


async def no_thumbs():
    return {}


igdata.days, igdata.profile, igdata.media, igdata.follow_stats = days, profile, media, follow_stats
app.watchdog_tick = noop
app.ensure_ready = noop
app.system_status = no_status
app.post_thumbs = no_thumbs
amo.sync = no_sync
extras.status_banner = lambda items: ""


# ---- 4. seed the throwaway database
def seed():
    with app.db() as con:
        amo.ensure_tables(con)
        dept.ensure_tables(con)
        auth.ensure_table(con)
        history.ensure_table(con)
        plan = {**D["plan"], "by": "demo", "at": int(time.time())}
        amo.kv_set(con, "dept_plan", {dept.month_key(TODAY): {"approved": plan, "draft": dict(D["plan"])}})
        amo.kv_set(con, "mkt_settings", D["mkt_settings"])
        amo.kv_set(con, "ad_spend", {igdata.key(TODAY - timedelta(days=s["ago"])): s["amount"] for s in D["ad_spend"] if s["ago"] > 0})
        field, sources, st = D["mkt_settings"]["source_field"], D["sources"], amo.settings(con)
        rows = []
        for did, ago, sec, won, price, close_after, src, resp in D["deals"]:
            created = int((TODAY - timedelta(days=ago)).timestamp()) + sec
            closed = min(created + close_after, int(time.time())) if won else None
            cf = json.dumps({field: [sources[src]]}, ensure_ascii=False)
            rows.append((did, price, amo.WON if won else 1, 1, created, closed, closed or created, cf,
                         1 if amo._is_marketing(cf, 1, st) else 0, resp))
        con.executemany("insert into amo_deals (id, price, status, pipeline, created, closed, updated, cf, mkt, resp)"
                        " values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        for s in D["staff"]:
            auth.save_staff(con, s["login"], s["name"], s["role"], {}, "demo-pass")
        for t in D["tasks"]:
            dept.add_task(con, t["login"], t["title"], igdata.key(TODAY + timedelta(days=t["due_in"])), "demo")
        for tid, title in con.execute("select id, title from tasks").fetchall():
            if any(t["done"] and t["title"] == title for t in D["tasks"]):
                dept.set_task(con, tid, "done", "demo")
        for i in range(1, 31):  # a month of nightly snapshots for the archive page
            k = igdata.key(TODAY - timedelta(days=i))
            if k in DAYS:
                history.save(con, k, {**DAYS[k], "followers": D["followers_now"] - i * 25, "direct": 30 + i % 17}, "auto")
        for p in D["bot_people"]:
            ts = int((TODAY - timedelta(days=p["ago"])).timestamp()) + p["sec"]
            con.execute("insert into profiles values (?, ?, ?) on conflict (igsid) do nothing", (p["igsid"], p["username"], ts))
            for j, ev in enumerate(p["steps"]):
                con.execute("insert into events values (?, ?, ?, ?, ?)", (ts + j * 240, p["igsid"], ev, p["topic"], "demo_media_0"))
            if "lead_answer" in p["steps"]:
                con.execute("insert into leads (igsid, username, topic, city, grade, phone, texts, first_ts, updated_ts, thanked, synced)"
                            " values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (p["igsid"], p["username"], p["topic"], p["city"], p["grade"], p.get("phone"),
                             f"{p['city']} | {p['grade']} сынып", ts, ts + 600, 1 if p.get("phone") else 0, 1))


PAGES = {"home": "/?p=month", "instagram": "/api/igbot/stats?p=30", "content": "/content?days=30", "bot": "/bot?p=30d",
         "archive": "/api/igbot/archive", "dept": "/dept", "ads": "/ads", "team": "/team", "settings": "/settings", "status": "/status"}


def render(out: Path):
    from fastapi.testclient import TestClient
    out.mkdir(parents=True, exist_ok=True)
    with TestClient(app.app, raise_server_exceptions=False) as c:
        r = c.get("/login")
        (out / "login.html").write_text(r.text, encoding="utf-8")
        print(f"{'login':10} {r.status_code} {len(r.text):>8}")
        c.cookies.set(auth.COOKIE, auth.sign({"u": "demo", "n": "Диас", "r": "admin", "exp": int(time.time()) + 3600}))
        bad = 0
        for name, url in PAGES.items():
            r = c.get(url, follow_redirects=True)
            (out / f"{name}.html").write_text(r.text, encoding="utf-8")
            bad += r.status_code != 200
            print(f"{name:10} {r.status_code} {len(r.text):>8}")
    print("blocked outgoing connections:", len(BLOCKED), sorted(set(BLOCKED))[:5])
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--render", metavar="DIR", help="write every page as HTML into DIR and exit")
    a = ap.parse_args()
    seed()
    if a.render:
        sys.exit(1 if render(Path(a.render)) else 0)
    import uvicorn
    print(f"EduApp Marketing demo: http://127.0.0.1:{a.port}  (login: demo / demo)")
    uvicorn.run(app.app, host="127.0.0.1", port=a.port, log_level="warning")
