"""EduApp Instagram Direct bot.

Flow: ad pre-filled message with a topic word -> follow gate ("Тексеру") ->
math: training type -> grade -> links of that grade only;
english: language level -> link of that level.

Button payloads carry the whole choice (e.g. "G:quarter:4"), so taps work
statelessly; the small state table only helps when someone types "4" instead
of tapping, or "тексеру" instead of pressing the button.
"""
import asyncio
import base64
import hashlib
import html
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

import httpx
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

import admin
import ads
import dept
import amo
import ask
import archive
import auth as staffauth
import competitors
import trends
import dashboard
import extras
import home
import history
import igdata
import leads
import mkt
import plan
import preview
import report
import stats
import botpage
import motiv
import tg
import ui
from store import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("igbot")
# httpx logs full URLs at INFO, and the token refresh URL carries the token.
logging.getLogger("httpx").setLevel(logging.WARNING)

CONF = Path(os.getenv("CONF_DIR") or Path(__file__).parent / "conf")
API = f"https://graph.instagram.com/{os.getenv('META_GRAPH_API_VERSION', 'v25.0')}"
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
APP_SECRETS = [s for s in (os.getenv("INSTAGRAM_APP_SECRET"), os.getenv("FACEBOOK_APP_SECRET")) if s]
BOT_ENABLED = os.getenv("BOT_ENABLED", "true").lower() == "true"
# Test mode: when set (comma-separated @usernames), the bot answers only these people; everyone else is just counted
BOT_ONLY = {u.strip().lstrip("@").lower() for u in os.getenv("BOT_ONLY", "").split(",") if u.strip()}
# The first token comes from IG_TOKEN; refreshed tokens are kept in the database.
IG_TOKEN = os.getenv("IG_TOKEN", "").strip()
TOKEN_REFRESH_AFTER = 3 * 24 * 3600  # long-lived token lives 60 days; refresh early and often
REPEAT_COOLDOWN = int(os.getenv("REPEAT_COOLDOWN_HOURS", "24")) * 3600
# Training buttons point at TRACK_BASE_URL/r/<token>, which counts the click and
# redirects to the platform. Empty = buttons link to the platform directly (no click count).
TRACK_BASE_URL = os.getenv("TRACK_BASE_URL", "").rstrip("/")
STATS_USER = os.getenv("STATS_USER", "eduapp")
STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")
UTM = {"utm_source": "instagram_bot", "utm_medium": "dm"}
# «welcome»: after the follow check send only the welcome text with three questions and collect the
# answers into Google Sheets. «menu»: the older training menu → grade → links flow.
FLOW = os.getenv("FLOW", "welcome")
CRON_SECRET = os.getenv("CRON_SECRET", "")
SHEETS_WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL", "")
SHEETS_SECRET = os.getenv("SHEETS_SECRET", "")
LEAD_WINDOW = 72 * 3600  # answers to the welcome questions are collected for 3 days

GRADES = ["3", "4", "5", "6"]
MATH_KINDS = ["quarter", "mega", "altyn_saka"]
MATH_MENU = ["quarter", "mega"]  # «Алтын сақа» is its own ad and topic, not a math menu item
EN_LEVELS = ["A0", "Low A1", "Mid A1"]
STAGE_ORDER = {"I": 1, "II": 2, "III": 3}
KIND_TOPIC = {"quarter": "math", "mega": "math", "altyn_saka": "saka", "english": "english"}

app = FastAPI()

# One period choice for every page: the last one picked (day / week / month) is kept in a cookie, and a page
# opened without a period gets it in its own words (Instagram «7», Bot «7d», Content «days=7»…).
PER_COOKIE = "zper"
ADMIN_NAME = "Диас"  # how the home page greets the owner
PER_PAGES = {"/": ("p", {"day": "day", "week": "week", "month": "month"}),
             "/api/igbot/stats": ("p", {"day": "today", "week": "7", "month": "30"}),
             "/bot": ("p", {"day": "day", "week": "7d", "month": "30d"}),
             "/content": ("days", {"day": "7", "week": "7", "month": "30"})}
PER_BACK = {"day": "day", "today": "day", "yesterday": "day", "week": "week", "7": "week", "7d": "week",
            "month": "month", "30": "month", "30d": "month", "90": "month"}


@app.middleware("http")
async def shared_period(request: Request, call_next):
    page = PER_PAGES.get(request.url.path) if request.method == "GET" else None
    if not page:
        return await call_next(request)
    param, words = page
    q = request.query_params
    saved = request.cookies.get(PER_COOKIE)
    if param not in q and "d" not in q and "d1" not in q and saved in words:
        sep = "&" if request.url.query else ""
        return RedirectResponse(f"{request.url.path}?{request.url.query}{sep}{param}={words[saved]}", status_code=303)
    resp = await call_next(request)
    chosen = PER_BACK.get(q.get(param) or "")
    if chosen and chosen != saved:
        resp.set_cookie(PER_COOKIE, chosen, max_age=365 * 86400, samesite="lax", httponly=True)
    return resp

# Keep connections to Instagram open between messages: no new DNS/TLS per reply.
http = httpx.AsyncClient(timeout=20, limits=httpx.Limits(keepalive_expiry=300))
ME: dict = {}


# ---------- config files (re-read when changed on disk) ----------

_cache: dict = {}


def _load(name, parser):
    path = CONF / name
    mtime = path.stat().st_mtime
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    value = parser(path)
    _cache[name] = (mtime, value)
    return value


_tx_cache = {"at": 0.0, "texts": {}, "rules": []}
EDITABLE = ["welcome_text", "welcome_extra", "welcome_extra_until", "comment_reply", "comment_reply_blocked", "lead_thanks"]
BLOCKED_REPLY = "Сәлеметсіз бе! Сілтеме мен толық ақпаратты алу үшін бізге Direct-ке «САҚА» деп жазыңыз 📩"
BLOCK_HOURS = 3


def pr_blocked() -> bool:
    """Instagram said «we limit how often…» to private replies: pause them (each try can lengthen the block)."""
    try:
        with db() as con:
            return (amo.kv_get(con, "pr_block_until", 0) or 0) > time.time()
    except Exception:
        return False


def block_private_replies():
    with db() as con:
        amo.kv_set(con, "pr_block_until", int(time.time()) + BLOCK_HOURS * 3600)
    log.warning("private replies paused for %s h (Instagram rate limit)", BLOCK_HOURS)


def queue_dm(uid: str, cid: str, media: str):
    with db() as con:
        q = amo.kv_get(con, "dm_queue", []) or []
        if uid not in {x["uid"] for x in q}:
            q.append({"uid": uid, "cid": cid, "media": media})
            amo.kv_set(con, "dm_queue", q)


DM_WORDS = ("сака", "вебинар", "силтеме", "дайынд", "даиынд")


def dm_rule(text: str):
    """A post rule whose Direct text a person asks for in Direct (writes «САҚА», «вебинар», the rule's keyword…)."""
    f = fold(text)
    for r in _site_settings()["rules"]:
        kw = fold((r.get("keyword") or "").strip())
        if (r.get("dm") or "").strip() and ((kw and kw in f) or any(w in f for w in DM_WORDS)):
            return r
    return None


def _site_settings():
    """Texts edited on the Bot page and the per-post rules, re-read at most every 20 seconds."""
    if time.time() - _tx_cache["at"] > 20:
        try:
            with db() as con:
                _tx_cache.update(texts=amo.kv_get(con, "texts", {}) or {}, rules=amo.kv_get(con, "post_rules", []) or [])
            with db() as con:
                _tx_cache["bot"] = amo.kv_get(con, "bot_enabled")
                _tx_cache["kw"] = amo.kv_get(con, "kw_mode")
                _tx_cache["solo_only"] = [u.strip().lstrip("@").lower() for u in (amo.kv_get(con, "solo_only", []) or []) if u.strip()]
        except Exception:
            log.exception("site texts")  # the file texts still work
        _tx_cache["at"] = time.time()
    return _tx_cache


KW_WORDS = ("сака", "дайынд", "даиынд", "дaйынд", "вебинар")
KW_DM = ("Сәлеметсіз бе! 😊 Вебинарға тіркелу үшін стористегі сілтеме арқылы өтуіңізді сұраймыз.\n\n"
         "Instagram-дағы уақытша техникалық ақауларға байланысты сілтемені Direct арқылы жіберу мүмкін болмай тұр. "
         "Түсіністік танытқаныңызға рақмет! 💜")
KW_REPLY = "Сәлеметсіз бе!\nТолық ақпаратты direct-ке жібердік📩"


KW_BTN_TEXT = "Сәлеметсіз бе! 😊 Вебинарға тіркелу сілтемесін алу үшін төмендегі батырманы басыңыз 👇"
KW_BTN = "Сілтемені алу"
LINK_PAYLOAD = "WEBLINK"


def link_text() -> str:
    """The webinar text with the link: the Direct text of the post rule that carries the webinar link."""
    for r in _site_settings()["rules"]:
        if "webinar.eduapp.example.com" in (r.get("dm") or ""):
            return r["dm"].strip()
    return "Вебинарға тіркелу сілтемесі: https://webinar.eduapp.example.com/"


WA_DIRECT_TEXT = "Сәлеметсіз бе! 💜" + chr(10) + "«Алтын сақа» тегін вебинары 23 қазан, 19:00-де өтеді. Тіркелу үшін төмендегі батырманы басып, парақшадағы ақпаратты толтырыңыз."


def button_msg(direct_wa: bool = False) -> dict:
    """First message: «Сілтемені алу» (the link comes after the tap), or with direct_wa the WhatsApp group button at once."""
    if direct_wa and wa_link():
        return buttons_msg(WA_DIRECT_TEXT, [("url", WA_BTN, wa_link())])
    return buttons_msg(KW_BTN_TEXT, [("postback", KW_BTN, LINK_PAYLOAD)])


WA_TEXT = "Сәлеметсіз бе! 💜" + chr(10) + "«Алтын сақа» тегін вебинары 23 қазан, 19:00-де өтеді. Тіркелу үшін төмендегі батырманы басып, парақшадағы ақпаратты толтырыңыз."
WA_BTN = "Тіркелу"


def wa_link() -> str:
    with db() as con:
        return (amo.kv_get(con, "wa_link") or "").strip()


async def on_link_tap(igsid: str):
    """The person pressed «Сілтемені алу»: now they wrote to us, so the link goes as a reply in their own chat —
    a button to the WhatsApp group when its invite link is set, otherwise the webinar text with the link."""
    wa = wa_link()
    msg = buttons_msg(WA_TEXT, [("url", WA_BTN, wa)]) if wa else text_msg(link_text())
    if await send(igsid, msg):
        track(igsid, "link_sent")
        await fill_username(igsid)
    else:
        track(igsid, "link_fail")


def link_tap(ev: dict) -> bool:
    pb = (ev.get("postback") or {}).get("payload") or ((ev.get("message") or {}).get("quick_reply") or {}).get("payload")
    return pb == LINK_PAYLOAD


def kw_on() -> bool:
    """Keyword mode: with the main bot off, comments with «сақа» / «дайындық» still get the Direct text and a reply."""
    return bool(_site_settings().get("kw"))


KW_GAP = 30  # seconds between automatic first messages (button), so a burst of comments goes out slowly
# words that show a person asks about this webinar (folded: қ→к, ы→ы…); other questions are left for managers
WEBINAR_WORDS = ("сака", "дайынд", "даиынд", "вебинар", "силтеме", "ссылк", "тиркел", "катыс")


def about_webinar(text: str) -> bool:
    return any(w in fold(text or "") for w in WEBINAR_WORDS)


def got_button(con, who: str) -> bool:
    return bool(con.execute("select 1 from events where igsid = ? and event in ('kw_btn', 'link_sent') limit 1", (who,)).fetchone())


async def kw_send(item: dict) -> str:
    """Send the «Сілтемені алу» button: as a private reply to a comment (cid) or into an open chat (uid).
    Returns ok / limit / fail."""
    recipient = {"comment_id": item["cid"]} if item.get("cid") else {"id": item["uid"]}
    pr = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": recipient, "message": button_msg()})
    if pr.status_code < 400:
        track(item["who"], "kw_btn", None, item.get("mid"))
        with db() as con:
            amo.kv_set(con, "kw_last", int(time.time()))
        if item.get("cid"):
            r = await http.post(f"{API}/{item['cid']}/replies", headers=auth(), params={"message": KW_REPLY})
            if r.status_code < 400:
                track(item["who"], "comment_reply", None, item.get("mid"))
        await fill_username(item["who"])
        return "ok"
    log.error("kw button failed %s: %s", pr.status_code, pr.text[:300])
    if "limit how often" in pr.text:
        block_private_replies()
        return "limit"
    track(item["who"], "kw_btn_fail", None, item.get("mid"))
    return "fail"


async def kw_drain():
    """Send one waiting button if the last one went out more than KW_GAP seconds ago and Instagram is not limiting us."""
    if pr_blocked():
        return
    with db() as con:
        q = amo.kv_get(con, "kw_queue", []) or []
        if not q or time.time() - (amo.kv_get(con, "kw_last", 0) or 0) < KW_GAP:
            return
        item = q.pop(0)
        amo.kv_set(con, "kw_queue", q)
        amo.kv_set(con, "kw_last", int(time.time()))
        if got_button(con, item["who"]):
            return
    if await kw_send(item) == "limit":
        with db() as con:
            amo.kv_set(con, "kw_queue", [item] + (amo.kv_get(con, "kw_queue", []) or []))


def kw_enqueue(item: dict):
    with db() as con:
        q = amo.kv_get(con, "kw_queue", []) or []
        if item["who"] not in {x["who"] for x in q}:
            q.append(item)
            amo.kv_set(con, "kw_queue", q)


async def on_kw_comment(value: dict):
    """Comment about the webinar (сақа, дайындық…), any post: the «Сілтемені алу» button in Direct, then
    «we sent it to Direct» under the comment. Once per person; at most one every KW_GAP seconds (the rest wait in kw_queue)."""
    cid, who = value.get("id"), (value.get("from") or {}).get("id")
    mid = (value.get("media") or {}).get("id")
    if not cid or not who or who == ME.get("id") or value.get("parent_id"):
        return
    if not about_webinar(value.get("text") or "") or not first_time(f"kw:{cid}"):
        return
    track(who, "comment", None, mid)
    with db() as con:
        if got_button(con, who):
            return
    kw_enqueue({"cid": cid, "who": who, "mid": mid})
    await kw_drain()


async def on_kw_dm(igsid: str, text: str):
    """Someone writes in Direct about the webinar — or answers at all after getting the «link in stories» text or our
    manual invitation («+», «рақмет»…): the chat is open, so the button goes there (once per person)."""
    with db() as con:
        if got_button(con, igsid):
            return
        invited = con.execute("select 1 from events where igsid = ? and event in ('text_dm', 'rule_dm_fail', 'dm_fail') limit 1",
                              (igsid,)).fetchone()
    plus = re.fullmatch(r"\s*\++\s*", text or "") is not None
    if not (about_webinar(text) or plus or invited):
        return
    kw_enqueue({"uid": igsid, "who": igsid})
    await kw_drain()


def bot_on() -> bool:
    """The bot switch on the Bot page; until it is used, the BOT_ENABLED variable decides."""
    v = _site_settings().get("bot")
    return BOT_ENABLED if v is None else bool(v)


def texts() -> dict:
    base = _load("texts.yml", lambda p: yaml.safe_load(p.read_text(encoding="utf-8")))
    return {**base, **{k: v for k, v in _site_settings()["texts"].items() if k in EDITABLE}}


_FOLD = str.maketrans("қғұүіңәөһёй", "кгууинаоhеи")


def fold(text: str) -> str:
    """Lower case with Kazakh letters folded to Russian ones: «дайындық» matches «Дайындык», «ДАЙЫНДЫҚ»."""
    return (text or "").lower().translate(_FOLD)


def post_rule(media_id: str | None, text: str | None = None):
    """Special texts for comments under one post (e.g. a webinar: its own Direct text instead of the welcome).
    A rule with a keyword applies only to comments that contain it; pass text=None to get the rule regardless."""
    r = next((r for r in _site_settings()["rules"] if media_id and r.get("media_id") == media_id), None)
    if r and text is not None and (r.get("keyword") or "").strip() and fold(r["keyword"].strip()) not in fold(text):
        return None
    return r


def solo_rule(value: dict):
    """A post rule marked «solo» answers comments under its post even while the bot is off.
    kv solo_only (usernames) limits it to those people — a test before everyone gets answers."""
    media_id = (value.get("media") or {}).get("id")
    r = next((r for r in _site_settings()["rules"] if media_id and r.get("solo") and r.get("media_id") == media_id), None)
    if not r:
        return None
    only = _site_settings().get("solo_only") or []
    if only and ((value.get("from") or {}).get("username") or "").lower() not in only:
        return None
    return r


def _parse_catalog(path: Path) -> list:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) < 9 or p[7].strip() != "yes":
            continue
        rows.append({
            "kind": p[0].strip(),
            "grades": [g.strip() for g in p[1].split(",")],
            "level": p[2].strip(),
            "title": p[4].strip(),
            "url": p[8].strip(),
        })
    return rows


def catalog() -> list:
    return _load("trainings.tsv", _parse_catalog)


def math_links(kind: str, grade: str) -> list:
    """[(button title, url)] for one training type and one grade, in order."""
    t = texts()
    rows = [r for r in catalog() if r["kind"] == kind and grade in r["grades"]]
    if kind == "altyn_saka":
        rows.sort(key=lambda r: STAGE_ORDER.get(r["level"].split()[0], 9))
        return [(t["stage_button"].format(stage=r["level"].split()[0],
                                          num=STAGE_ORDER.get(r["level"].split()[0], "")), r["url"])
                for r in rows]
    rows.sort(key=lambda r: r["level"])
    return [(t.get(f"level_button_{r['level']}", r["level"]), r["url"]) for r in rows]


def english_link(level: str):
    for r in catalog():
        if r["kind"] == "english" and r["title"].endswith(f"English {level}"):
            return r["url"]
    return None


# ---------- storage ----------

async def remember_username(igsid: str):
    """Store the @username once, so the stats page can list people by name."""
    try:
        with db() as con:
            if con.execute("select 1 from profiles where igsid = ?", (igsid,)).fetchone():
                return
        r = await http.get(f"{API}/{igsid}", headers=auth(), params={"fields": "username"})
        if r.status_code == 200 and r.json().get("username"):
            with db() as con:
                con.execute("insert into profiles values (?, ?, ?) on conflict (igsid) do update set username = excluded.username, ts = excluded.ts",
                            (igsid, r.json()["username"], int(time.time())))
    except Exception:
        log.exception("username lookup failed")  # a missing name must never break a reply


def track(igsid: str, event: str, topic: str | None = None, detail: str | None = None):
    try:
        with db() as con:
            con.execute("insert into events values (?, ?, ?, ?, ?)", (int(time.time()), igsid, event, topic, detail))
    except Exception:
        log.exception("track failed")  # statistics must never break a reply


def with_utm(url: str, campaign: str, content: str) -> str:
    parts = urlsplit(url)
    query = "&".join(q for q in (parts.query, urlencode({**UTM, "utm_campaign": campaign, "utm_content": content})) if q)
    return urlunsplit(parts._replace(query=query))


def tracked_url(igsid: str, topic: str, detail: str, label: str, url: str) -> str:
    """Button URL: our counting redirect when enabled, else the training itself."""
    target = with_utm(url, topic, detail)
    if not TRACK_BASE_URL:
        return target
    token = secrets.token_urlsafe(6)
    with db() as con:
        con.execute("insert into links values (?, ?, ?, ?, ?, ?, ?)",
                    (token, igsid, topic, detail, label, target, int(time.time())))
    return f"{TRACK_BASE_URL}/r/{token}"


def first_time(mid: str) -> bool:
    """Meta re-delivers webhooks; handle each message id once."""
    if not mid:
        return True
    with db() as con:
        cur = con.execute("insert into seen values (?, ?) on conflict (mid) do nothing", (mid, int(time.time())))
        return cur.rowcount == 1


def recently_started(igsid: str, topic: str) -> bool:
    """A keyword starts a topic once per REPEAT_COOLDOWN; later mentions of the
    same word mid-conversation are for the managers, not a fresh menu."""
    with db() as con:
        row = con.execute("select ts from starts where igsid = ? and topic = ?", (igsid, topic)).fetchone()
        if row and time.time() - row[0] < REPEAT_COOLDOWN:
            return True
        con.execute("insert into starts values (?, ?, ?) on conflict (igsid, topic) do update set ts = excluded.ts",
                    (igsid, topic, int(time.time())))
        return False


def get_user(igsid: str) -> dict:
    with db() as con:
        row = con.execute("select topic, awaiting from users where igsid = ?", (igsid,)).fetchone()
    return {"topic": row[0], "awaiting": row[1]} if row else {"topic": None, "awaiting": None}


def set_user(igsid: str, topic=None, awaiting=None):
    with db() as con:
        con.execute("insert into users values (?, ?, ?, ?) on conflict (igsid) do update set topic = excluded.topic,"
                    " awaiting = excluded.awaiting, ts = excluded.ts", (igsid, topic, awaiting, int(time.time())))


# ---------- Instagram API ----------

_token: dict = {}


def token() -> str:
    """Current Instagram token: the stored (refreshed) one, else IG_TOKEN."""
    if "v" not in _token:
        with db() as con:
            row = con.execute("select v, ts from kv where k = 'ig_token'").fetchone()
        if row and row[0]:
            _token.update(v=row[0], ts=row[1])
        else:
            _token.update(v=IG_TOKEN, ts=0)
    return _token["v"]


def auth() -> dict:
    return {"Authorization": f"Bearer {token()}"}


async def send(igsid: str, message: dict) -> bool:
    r = await http.post(f"{API}/me/messages", headers=auth(),
                        json={"recipient": {"id": igsid}, "message": message})
    if r.status_code >= 400:
        log.error("send to ..%s failed %s: %s", igsid[-4:], r.status_code, r.text[:300])
        return False
    return True


def text_msg(text: str, quick: list | None = None) -> dict:
    msg = {"text": text}
    if quick:
        msg["quick_replies"] = [{"content_type": "text", "title": title[:20], "payload": payload}
                                for title, payload in quick]
    return msg


def buttons_msg(text: str, buttons: list) -> dict:
    """buttons: [("url", title, url) | ("postback", title, payload)], at most 3."""
    out = []
    for kind, title, value in buttons[:3]:
        if kind == "url":
            out.append({"type": "web_url", "title": title[:20], "url": value})
        else:
            out.append({"type": "postback", "title": title[:20], "payload": value})
    return {"attachment": {"type": "template", "payload": {
        "template_type": "button", "text": text[:640], "buttons": out}}}


async def follows(igsid: str):
    """True/False, or None when Instagram would not tell us."""
    r = await http.get(f"{API}/{igsid}", headers=auth(),
                       params={"fields": "is_user_follow_business,username"})
    if r.status_code != 200:
        log.warning("follow check ..%s failed %s: %s", igsid[-4:], r.status_code, r.text[:200])
        return None
    return bool(r.json().get("is_user_follow_business"))


# ---------- conversation ----------

KZ = str.maketrans("әғқңөұүһі", "агкноуухи")


def norm(s: str) -> str:
    return (s or "").lower().translate(KZ)


def detect_topic(text: str):
    t = norm(text)
    if re.search(r"алтын\s*сак", t):
        return "saka"
    # Meta's stock ad question «Здравствуйте! Можно узнать об этом подробнее?»
    # comes from the «Алтын сақа» ad, so it opens the «Алтын сақа» flow.
    if re.search(r"узнать\s+об\s+этом\s+подробнее", t):
        return "saka"
    if re.search(r"матем", t):
        return "math"
    if re.search(r"агылшын|англ|english|инглиш", t):
        return "english"
    return None


async def start(igsid: str, topic: str):
    t = texts()
    set_user(igsid, topic=topic)
    topic_line = t[f"topic_{topic}"]
    following = await follows(igsid)
    track(igsid, "start", topic)
    if following is False:
        log.info("..%s topic=%s -> follow gate", igsid[-4:], topic)
        track(igsid, "gate", topic)
        await send(igsid, buttons_msg(t["follow_gate"].format(topic=topic_line),
                                      [("postback", t["check_button"], f"CHECK:{topic}")]))
        return
    if following is None:
        log.warning("..%s follow status unknown, letting through", igsid[-4:])
    track(igsid, "already_follower" if following else "follow_unknown", topic)
    await after_follow(igsid, topic, t["hello_follower"].format(topic=topic_line).strip())


async def on_check(igsid: str, topic: str):
    t = texts()
    following = await follows(igsid)
    if following is False:
        log.info("..%s pressed check, still not following", igsid[-4:])
        track(igsid, "check_fail", topic)
        await send(igsid, buttons_msg(t["not_following"],
                                      [("postback", t["check_button"], f"CHECK:{topic}")]))
        return
    track(igsid, "subscribed", topic)
    await after_follow(igsid, topic, t["thanks_follow"].strip(), just_subscribed=True)


def welcome_body(t: dict) -> str:
    """The welcome text, plus a time-limited addition (e.g. a webinar invite) until its end date."""
    text = t["welcome_text"].strip()
    extra = (t.get("welcome_extra") or "").strip()
    until = str(t.get("welcome_extra_until") or "")
    if extra and (not until or igdata.key(igdata.today()) <= until):
        text += "\n\n" + extra
    return text


async def send_welcome(igsid: str, topic: str | None, prefix: str = "") -> bool:
    """Welcome text with the three questions; from now on this person's replies are collected."""
    t = texts()
    ok = await send(igsid, text_msg((prefix + "\n\n" if prefix else "") + welcome_body(t)))
    if ok:
        with db() as con:
            leads.start_lead(con, igsid, topic)
        set_user(igsid, topic=topic, awaiting="profile")
        track(igsid, "welcome", topic)
        log.info("..%s -> welcome (%s)", igsid[-4:], topic)
        await fill_username(igsid)
        await sync_sheet()
    return ok


async def fill_username(igsid: str):
    """Put the @username on the sheet row right away, before the person answers."""
    await remember_username(igsid)
    with db() as con:
        row = con.execute("select username from profiles where igsid = ?", (igsid,)).fetchone()
        if row and row[0]:
            con.execute("update leads set username = ?, synced = 0 where igsid = ? and username is null", (row[0], igsid))


async def capture_answer(igsid: str, text: str):
    """Store a reply to the welcome questions; thank the person once a phone number arrives."""
    await remember_username(igsid)
    with db() as con:
        username = (con.execute("select username from profiles where igsid = ?", (igsid,)).fetchone() or [None])[0]
        lead = leads.add_answer(con, igsid, text, username)
    track(igsid, "lead_answer", lead.get("topic"))
    log.info("..%s lead answer (phone=%s grade=%s city=%s)", igsid[-4:], bool(lead["phone"]), lead["grade"], bool(lead["city"]))
    if lead["new_phone"] and not lead["thanked"]:
        if await send(igsid, text_msg(texts()["lead_thanks"].strip())):
            with db() as con:
                leads.mark_thanked(con, igsid)
            track(igsid, "lead_phone", lead.get("topic"))
    await sync_sheet()


def collecting_answers(igsid: str) -> bool:
    with db() as con:
        lead = leads.get_lead(con, igsid)
    return bool(lead) and time.time() - lead["first_ts"] < LEAD_WINDOW


async def sync_sheet():
    """Mirror changed lead rows to Google Sheets. Runs after every lead change, on the stats
    page and in the daily cron; rows that failed stay unsynced and go on the next run."""
    if not SHEETS_WEBHOOK_URL:
        return
    try:
        with db() as con:
            rows = leads.unsynced(con)
        for lead in rows:
            r = await http.post(SHEETS_WEBHOOK_URL, json={"secret": SHEETS_SECRET, **leads.sheet_row(lead)},
                                follow_redirects=True, timeout=30)
            ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json") \
                and r.json().get("ok")
            if not ok:
                log.warning("sheet sync failed %s: %s", r.status_code, r.text[:200])
                break
            with db() as con:
                leads.mark_synced(con, lead["igsid"], lead["updated_ts"])
    except Exception:
        log.exception("sheet sync")


async def after_follow(igsid: str, topic: str, first_line: str, just_subscribed: bool = False):
    """One message: greeting/thanks line on top of the topic menu."""
    t = texts()
    if FLOW == "welcome":
        # The welcome text already greets; only a fresh subscriber also gets the «сәтті тіркелдіңіз» line.
        await send_welcome(igsid, topic, first_line if just_subscribed else "")
        return

    def with_top(menu_key):
        return f"{first_line}\n\n{t[menu_key].strip()}"

    # Menus with up to 3 choices use template buttons: they stack under the message
    # and are all visible, while quick replies sit in one row that parents must scroll.
    if topic == "english":
        set_user(igsid, topic=topic, awaiting="en_level")
        await send(igsid, buttons_msg(with_top("english_menu"),
                                      [("postback", t["english_buttons"][lv], f"EN:{lv}") for lv in EN_LEVELS]))
    elif topic == "saka":
        await ask_grade(igsid, "altyn_saka", with_top("saka_menu"))
    else:
        set_user(igsid, topic=topic, awaiting="math_kind")
        await send(igsid, buttons_msg(with_top("math_menu"),
                                      [("postback", t["math_buttons"][k], f"T:{k}") for k in MATH_MENU]))


async def ask_grade(igsid: str, kind: str, question: str | None = None):
    t = texts()
    set_user(igsid, topic="math", awaiting=f"grade:{kind}")
    await send(igsid, text_msg(question or t["ask_grade"],
                               [(t["grade_button"].format(grade=g), f"G:{kind}:{g}") for g in GRADES]))


async def send_math_links(igsid: str, kind: str, grade: str):
    t = texts()
    links = math_links(kind, grade)
    if not links:
        log.error("no links for %s grade %s", kind, grade)
        return
    log.info("..%s -> links %s grade %s", igsid[-4:], kind, grade)
    topic, detail = KIND_TOPIC[kind], f"{kind}:{grade}"
    track(igsid, "links", topic, detail)
    await send(igsid, buttons_msg(t[f"links_{kind}"].format(grade=grade).strip(),
                                  [("url", title, tracked_url(igsid, topic, detail, title, url))
                                   for title, url in links]))
    await send(igsid, text_msg(t["after_links"].strip()))
    set_user(igsid, topic="math")


async def send_english_link(igsid: str, level: str):
    t = texts()
    url = english_link(level)
    if not url:
        log.error("no english link for %s", level)
        return
    log.info("..%s -> english %s", igsid[-4:], level)
    detail = f"english:{level}"
    track(igsid, "links", "english", detail)
    title = t["english_link_button"]
    await send(igsid, buttons_msg(t["links_english"].format(level=level).strip(),
                                  [("url", title, tracked_url(igsid, "english", detail, title, url))]))
    await send(igsid, text_msg(t["after_links"].strip()))
    set_user(igsid, topic="english")


# ---------- follow-up broadcast («тіркелдіңіз бе?») ----------

FOLLOWUP_ANSWERS = ["done", "help", "notyet"]
FOLLOWUP_WINDOW = 23 * 3600  # Meta allows automated messages only 24 h after the person's last message


def last_activity() -> dict:
    """igsid -> unix time of that person's latest message or button tap we saw.
    Link clicks happen outside Instagram and our own sends (broadcasts, the welcome
    text) are not the person writing, so none of them opens Meta's messaging window.
    Every incoming message is logged as «msg» and every tap has its own event."""
    last: dict = {}
    with db() as con:
        for igsid, ts in con.execute("select igsid, max(ts) from events where event not like 'fu_sent%'"
                                     " and event not like 'fu_fail%' and event not in ('click', 'welcome')"
                                     " group by igsid"):
            last[igsid] = ts
    return last


PICK_TOPICS = ["math", "english", "saka"]


def is_pick(campaign: str) -> bool:
    """«pick…» campaigns go to people who stopped before the links and ask for a direction."""
    return "pick" in campaign


def followup_recipients(campaign: str, exclude=()) -> list:
    """People inside the 24 h window who never got this campaign: for «тіркелдіңіз бе?»
    those who got training links, for «pick» those who never got that far."""
    now = time.time()
    # «registered_check@2026-09-29» is one send of the «registered_check» kind: each send is
    # its own campaign in the stats, but nobody gets the same kind of message twice.
    kind = campaign.split("@")[0]
    with db() as con:
        got_links = {r[0] for r in con.execute("select distinct igsid from events where event = 'links'")}
        already = {r[0] for r in con.execute("select distinct igsid from events where event = ? or event like ?",
                                              (f"fu_sent:{kind}", f"fu_sent:{kind}@%"))}
    if "welcome" in campaign:  # everyone in the window who has not had the welcome questions yet
        with db() as con:
            leads.ensure_table(con)
            welcomed = {r[0] for r in con.execute("select igsid from leads")}
        wanted = lambda k: k not in welcomed
    else:
        wanted = (lambda k: k not in got_links) if is_pick(campaign) else (lambda k: k in got_links)
    return sorted(k for k, ts in last_activity().items()
                  if now - ts < FOLLOWUP_WINDOW and wanted(k) and k not in already and k not in exclude)


async def send_followup(igsid: str, campaign: str) -> bool:
    t = texts()
    if "welcome" in campaign:
        ok = await send_welcome(igsid, get_user(igsid)["topic"])
        track(igsid, f"fu_sent:{campaign}" if ok else f"fu_fail:{campaign}")
        return ok
    if is_pick(campaign):
        msg = buttons_msg(t["pick_text"].strip(), [("postback", t["pick_buttons"][p], f"PICK:{p}") for p in PICK_TOPICS])
    else:
        msg = buttons_msg(t["followup_text"].strip(),
                          [("postback", t["followup_buttons"][a], f"FU:{a}") for a in FOLLOWUP_ANSWERS])
    ok = await send(igsid, msg)
    track(igsid, f"fu_sent:{campaign}" if ok else f"fu_fail:{campaign}")
    return ok


async def on_followup_answer(igsid: str, answer: str):
    t = texts()
    track(igsid, f"fu_{answer}")
    log.info("..%s followup answer: %s", igsid[-4:], answer)
    if answer == "notyet":
        title = t["followup_login_button"]
        await send(igsid, buttons_msg(t["followup_notyet"].strip(),
                                      [("url", title, tracked_url(igsid, "followup", "login", title, "https://eduapp.example.com/login"))]))
    else:
        await send(igsid, text_msg(t[f"followup_{answer}"].strip()))
    await remember_username(igsid)


async def on_payload(igsid: str, payload: str):
    if payload == LINK_PAYLOAD:
        await on_link_tap(igsid)
        return
    parts = payload.split(":")
    if parts[0] == "CHECK" and len(parts) == 2:
        await on_check(igsid, parts[1])
    elif parts[0] == "T" and parts[1] in MATH_KINDS:
        track(igsid, "choice", KIND_TOPIC[parts[1]], parts[1])
        await ask_grade(igsid, parts[1])
    elif parts[0] == "G" and len(parts) == 3 and parts[1] in MATH_KINDS and parts[2] in GRADES:
        await send_math_links(igsid, parts[1], parts[2])
    elif parts[0] == "EN" and ":".join(parts[1:]) in EN_LEVELS:
        await send_english_link(igsid, ":".join(parts[1:]))
    elif parts[0] == "FU" and len(parts) == 2 and parts[1] in FOLLOWUP_ANSWERS:
        await on_followup_answer(igsid, parts[1])
    elif parts[0] == "PICK" and len(parts) == 2 and parts[1] in PICK_TOPICS:
        # An explicit tap on the direction: run that topic's normal flow (follow check included).
        track(igsid, "fu_pick", parts[1])
        recently_started(igsid, parts[1])  # records the start, so a later keyword won't reopen the menu
        await start(igsid, parts[1])
    else:
        log.warning("unknown payload %r", payload)


def is_new_person(igsid: str) -> bool:
    """Never welcomed and never wrote before: people already talking to a manager are left alone."""
    with db() as con:
        if leads.get_lead(con, igsid):
            return False
        row = con.execute("select count(*) from events where igsid = ? and event = 'msg' and ts < ?",
                          (igsid, int(time.time()) - 60)).fetchone()
    return not (row and row[0])


async def talked_before(igsid: str) -> bool:
    """Instagram's own record of the chat: messages older than two minutes mean an earlier conversation.
    Our database started empty on 19.10.2026, so this keeps the welcome away from people already talking
    to a manager. When Instagram does not answer, assume an old chat (better silent than repeated)."""
    try:
        r = await http.get(f"{API}/me/conversations", headers=auth(),
                           params={"platform": "instagram", "user_id": igsid, "fields": "messages.limit(10){created_time}"})
        if r.status_code != 200:
            log.warning("conversation lookup ..%s %s: %s", igsid[-4:], r.status_code, r.text[:200])
            return True
        cutoff = time.time() - 120
        for conv in r.json().get("data", []):
            for msg in (conv.get("messages") or {}).get("data", []):
                t = msg.get("created_time") or ""
                if t and datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() < cutoff:
                    return True
        return False
    except Exception:
        log.exception("conversation lookup")
        return True


async def first_contact(igsid: str, text: str = "") -> bool:
    """Welcome a new person on their first message (any text, photo or story reply)."""
    if FLOW != "welcome":
        return False
    if is_new_person(igsid) and not BOT_ONLY and await talked_before(igsid):
        return False
    if not is_new_person(igsid):
        with db() as con:
            greeted = leads.get_lead(con, igsid)
        if not (BOT_ONLY and not greeted):
            return False
    return await send_welcome(igsid, detect_topic(text) if text else None)


async def on_text(igsid: str, text: str):
    rule = dm_rule(text)
    if rule:
        with db() as con:
            done = con.execute("select 1 from events where igsid = ? and event = 'rule_dm' and detail = ?",
                               (igsid, rule["media_id"])).fetchone()
        if not done and await send(igsid, text_msg(rule["dm"].strip())):
            track(igsid, "rule_dm", None, rule["media_id"])
            with db() as con:  # no need to send it again from the queue
                q = [x for x in (amo.kv_get(con, "dm_queue", []) or []) if x["uid"] != igsid]
                amo.kv_set(con, "dm_queue", q)
            return
    # Replies to the welcome questions (city / grade / phone) go to the sheet, even if they
    # happen to contain a topic word like «математика».
    if collecting_answers(igsid):
        await capture_answer(igsid, text)
        return
    if await first_contact(igsid, text):
        return
    topic = detect_topic(text)
    if topic:
        if recently_started(igsid, topic):
            log.info("..%s mentioned %s again within cooldown, left for managers", igsid[-4:], topic)
            track(igsid, "repeat_ignored", topic)
        else:
            await start(igsid, topic)
        return
    # Typed answers instead of taps. Anything else is left for the managers.
    user = get_user(igsid)
    t = norm(text).strip()
    awaiting = user["awaiting"] or ""
    if awaiting.startswith("grade:"):
        m = re.search(r"\b([3-6])\b", t)
        if m:
            await send_math_links(igsid, awaiting.split(":", 1)[1], m.group(1))
    elif user["topic"] and not awaiting and t.startswith("тексеру"):
        await on_check(igsid, user["topic"])


async def handle_event(ev: dict):
    sender = (ev.get("sender") or {}).get("id")
    if not sender or sender == ME.get("id"):
        return
    msg = ev.get("message") or {}
    if msg.get("is_echo") or msg.get("is_deleted"):
        return
    if "postback" in ev:
        pb = ev["postback"]
        if first_time(pb.get("mid") or f"pb:{sender}:{ev.get('timestamp')}"):
            await on_payload(sender, pb.get("payload", ""))
    elif msg:
        if not first_time(msg.get("mid")):
            return
        # Any message the person writes (even «рахмет» to a manager) reopens Meta's
        # 24 h window; remember it so follow-ups reach everyone who is allowed.
        track(sender, "msg")
        qr = msg.get("quick_reply")
        if qr:
            await on_payload(sender, qr.get("payload", ""))
        elif msg.get("text"):
            await on_text(sender, msg["text"])
        else:  # photo, voice, story reply without text
            await first_contact(sender)


# Comments that ask for information get the auto-reply; quiz answers («19», «1800 см³»), emoji,
# praise, friend tags and questions about olympiad results are left for people.
INFO_WORDS = ("ақпарат", "акпарат", "инфо", "толығырақ", "толыгырак", "толық", "толык", "қалай ал", "калай ал",
              "қанша", "канша", "баға", "бага", "цена", "сколько", "стоимост", "купить", "тегін", "тегин", "сынып",
              "класс", "керек", "хочу", "қатыс", "катыс", "тіркел", "тиркел", "курс", "тренинг", "сабақ", "сабак",
              "подробн", "как попасть", "қайдан ал", "кайдан ал", "жазыл", "сақа", "сака", "вебинар", "сілтеме", "ссылк")
RESULT_WORDS = ("нәтиже", "натиже", "нэтиже", "результ", "резул", "резудьт")


def wants_info(text: str) -> bool:
    t = norm(text or "").strip()
    if re.fullmatch(r"\+{1,5}", t):
        return True
    if any(w in t for w in RESULT_WORDS):
        return False
    return any(w in t for w in INFO_WORDS)


async def on_comment(value: dict, backlog: bool = False, force: bool = False):
    """New comment under a post: a short public reply, and the welcome text in Direct (once per person)."""
    cid, who = value.get("id"), (value.get("from") or {}).get("id")
    if not cid or not who or who == ME.get("id") or value.get("parent_id"):
        return  # our own replies and replies inside threads are left alone
    rule = post_rule((value.get("media") or {}).get("id"), value.get("text") or "")
    if not rule and not force and not wants_info(value.get("text") or ""):
        return
    if not first_time(f"c:{cid}"):
        return
    t = texts()
    uname = (value.get("from") or {}).get("username")
    if uname:  # the comment already carries the @username: keep it for the stats and the sheet
        with db() as con:
            con.execute("insert into profiles values (?, ?, ?) on conflict (igsid) do update set username = excluded.username, ts = excluded.ts",
                        (who, uname, int(time.time())))
    track(who, "comment", None, (value.get("media") or {}).get("id"))
    blocked = pr_blocked()
    reply = ((rule or {}).get("reply") or t["comment_reply"]).strip()
    if blocked:  # we cannot send the Direct message now: tell them how to get it instead of «we sent it»
        reply = (t.get("comment_reply_blocked") or BLOCKED_REPLY).strip()
    r = await http.post(f"{API}/{cid}/replies", headers=auth(), params={"message": reply})
    if r.status_code >= 400:
        log.error("comment reply failed %s: %s", r.status_code, r.text[:300])
        track(who, "comment_reply_fail")
    else:
        track(who, "comment_reply", None, (value.get("media") or {}).get("id"))
    if rule:  # the post's own Direct text, once per person and post
        mid = rule["media_id"]
        with db() as con:
            done = con.execute("select 1 from events where igsid = ? and event = 'rule_dm' and detail = ?", (who, mid)).fetchone()
        if rule.get("solo") and (uname or "").lower() in (_site_settings().get("solo_only") or []):
            done = None  # a tester gets the Direct text on every comment, so the test can be repeated
        if not done and (rule.get("dm") or "").strip() and blocked:
            queue_dm(who, cid, mid)
        elif not done and (rule.get("dm") or "").strip():
            pr = await http.post(f"{API}/me/messages", headers=auth(),
                                 json={"recipient": {"comment_id": cid}, "message": {"text": rule["dm"].strip()}})
            if pr.status_code >= 400:
                log.error("rule reply failed %s: %s", pr.status_code, pr.text[:300])
                track(who, "dm_fail")
                if "limit how often" in pr.text:
                    block_private_replies()
                    queue_dm(who, cid, mid)
            else:
                track(who, "rule_dm", None, mid)
                await fill_username(who)
        return
    with db() as con:
        greeted = leads.get_lead(con, who)
        got_extra = con.execute("select 1 from events where igsid = ? and event = 'extra_sent'", (who,)).fetchone()
    extra = welcome_body(t)[len(t["welcome_text"].strip()):].strip()
    if greeted and extra and not got_extra:  # welcomed earlier: send only the time-limited addition (webinar link), once
        pr = await http.post(f"{API}/me/messages", headers=auth(),
                             json={"recipient": {"comment_id": cid}, "message": {"text": "Сәлеметсіз бе!\n\n" + extra}})
        track(who, "extra_sent" if pr.status_code < 400 else "dm_fail")
        return
    # the backlog run greets everyone who has not had the welcome yet, as asked
    if FLOW != "welcome" or greeted or (not is_new_person(who) and not BOT_ONLY and not backlog):
        return
    if not backlog and not BOT_ONLY and await talked_before(who):  # already chatting with us in Direct
        return
    if blocked:
        return  # the public reply already asked them to write to us in Direct
    pr = await http.post(f"{API}/me/messages", headers=auth(),
                         json={"recipient": {"comment_id": cid}, "message": {"text": welcome_body(t)}})
    if pr.status_code >= 400:
        log.error("private reply failed %s: %s", pr.status_code, pr.text[:300])
        track(who, "dm_fail")
        return
    with db() as con:
        leads.start_lead(con, who, None)
    set_user(who, topic=None, awaiting="profile")
    track(who, "welcome", None, "comment")
    if extra:
        track(who, "extra_sent")
    await fill_username(who)
    await sync_sheet()


def count_only(ev: dict):
    """Bot switched off: no replies, but incoming Direct messages still count for the report."""
    sender = (ev.get("sender") or {}).get("id")
    msg = ev.get("message") or {}
    if sender and sender != ME.get("id") and msg and not msg.get("is_echo") and not msg.get("is_deleted") \
            and first_time(msg.get("mid")):
        track(sender, "msg")


async def username_of(igsid: str) -> str:
    await remember_username(igsid)
    with db() as con:
        row = con.execute("select username from profiles where igsid = ?", (igsid,)).fetchone()
    return (row[0] if row and row[0] else "").lower()


async def allowed(igsid: str, username: str | None = None) -> bool:
    """Outside test mode everyone; in test mode only the listed @usernames."""
    if not BOT_ONLY:
        return True
    return (username or await username_of(igsid)).lower() in BOT_ONLY


QUEUE_GAP = 120  # seconds between queued sends


async def drain_queue():
    """Send one queued post Direct text if the last one went out more than QUEUE_GAP seconds ago.
    Runs on incoming Instagram events and page views, so the queue empties slowly without a burst."""
    try:
        with db() as con:
            q = amo.kv_get(con, "dm_queue", []) or []
            last = amo.kv_get(con, "dm_queue_last", 0) or 0
            if not q or time.time() - last < QUEUE_GAP or (amo.kv_get(con, "pr_block_until", 0) or 0) > time.time():
                return
            item = q.pop(0)
            amo.kv_set(con, "dm_queue_last", int(time.time()))
            amo.kv_set(con, "dm_queue", q)
        rule = post_rule(item["media"])
        if not rule:
            return
        pr = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": {"comment_id": item["cid"]}, "message": {"text": rule["dm"]}})
        if pr.status_code < 400:
            track(item["uid"], "rule_dm", None, item["media"])
        elif "limit how often" in pr.text:  # still rate-limited: put it back and pause all private replies
            with db() as con:
                amo.kv_set(con, "dm_queue", [item] + (amo.kv_get(con, "dm_queue", []) or []))
            block_private_replies()
        else:
            track(item["uid"], "rule_dm_fail", None, item["media"])
            log.warning("queued dm failed: %s", pr.text[:200])
    except Exception:
        log.exception("dm queue")


async def process(data: dict):
    await watchdog_tick()
    if not bot_on():
        for entry in data.get("entry", []):
            for ev in entry.get("messaging", []):
                try:
                    count_only(ev)
                except Exception:
                    log.exception("count failed")
            solo = [ch.get("value") or {} for ch in entry.get("changes", []) if ch.get("field") == "comments" and solo_rule(ch.get("value") or {})]
            if solo:
                await ensure_ready()
                for v in solo:
                    try:
                        await on_comment(v)
                    except Exception:
                        log.exception("solo post comment failed")
                entry = {**entry, "changes": [ch for ch in entry.get("changes", []) if (ch.get("value") or {}) not in solo]}
            if kw_on():
                await ensure_ready()
                for ev in entry.get("messaging", []):
                    sender = (ev.get("sender") or {}).get("id")
                    msg = ev.get("message") or {}
                    mid = (ev.get("postback") or {}).get("mid") or msg.get("mid") or f"pb:{sender}:{ev.get('timestamp')}"
                    if not sender or sender == ME.get("id") or msg.get("is_echo"):
                        continue
                    try:
                        if link_tap(ev):
                            if first_time("lt:" + mid):
                                await on_link_tap(sender)
                        elif msg.get("text") and first_time("kd:" + mid):
                            await on_kw_dm(sender, msg["text"])
                    except Exception:
                        log.exception("keyword mode event failed")
                for ch in entry.get("changes", []):
                    if ch.get("field") == "comments":
                        try:
                            await on_kw_comment(ch.get("value") or {})
                        except Exception:
                            log.exception("kw comment failed")
                try:
                    await kw_drain()
                except Exception:
                    log.exception("kw queue")
        return
    await ensure_ready()
    for entry in data.get("entry", []):
        for ev in entry.get("messaging", []):
            try:
                sender = (ev.get("sender") or {}).get("id")
                if sender and sender != ME.get("id") and not await allowed(sender):
                    count_only(ev)
                    continue
                await handle_event(ev)
            except Exception:
                log.exception("event failed: %s", json.dumps(ev)[:500])
        await drain_queue()
        for ch in entry.get("changes", []):
            v = ch.get("value") or {}
            if BOT_ONLY and ((v.get("from") or {}).get("username") or "").lower() not in BOT_ONLY:
                continue
            if ch.get("field") == "comments":
                try:
                    await on_comment(ch.get("value") or {})
                except Exception:
                    log.exception("comment failed: %s", json.dumps(ch)[:500])


# ---------- HTTP ----------

@app.get("/api/webhook")
async def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and VERIFY_TOKEN and q.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)


def signature_ok(raw: bytes, header: str) -> bool:
    if not header.startswith("sha256="):
        return False
    got = header[7:]
    return any(hmac.compare_digest(hmac.new(s.encode(), raw, hashlib.sha256).hexdigest(), got)
               for s in APP_SECRETS)


@app.post("/api/webhook")
async def webhook(request: Request):
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("x-hub-signature-256", "")):
        log.warning("bad webhook signature, dropped")
        return JSONResponse({"ok": False}, status_code=403)
    # Serverless: work left for after the response may be frozen, so reply only when finished.
    await process(json.loads(raw or b"{}"))
    return {"ok": True}


@app.get("/r/{token}")
async def click(token: str):
    """Count a training-button tap, then send the parent on to the platform."""
    with db() as con:
        row = con.execute("select igsid, topic, detail, label, url from links where token = ?", (token,)).fetchone()
    if not row:
        return RedirectResponse("https://eduapp.example.com/login", status_code=302)
    igsid, topic, detail, label, url = row
    track(igsid, "click", topic, f"{detail}|{label}")
    return RedirectResponse(url, status_code=302)


VIEW_COOKIE = "zview"


def real_session(request: Request):
    """The person really logged in (ignores «view as»)."""
    return staffauth.unsign(request.cookies.get(staffauth.COOKIE, ""))


def session(request: Request):
    """Logged-in user from the cookie: {"u": login, "n": name, "r": "admin"|"lead"|"smm"} or None.
    The admin can look at the site through an employee's eyes («view as», cookie zview): then this returns that
    employee (with "viewas": True), so every page shows exactly their menu and rights; saving is blocked meanwhile."""
    u = real_session(request)
    if not u or u.get("r") != "admin":
        return u
    try:
        with db() as con:
            team = staffauth.staff(con)
    except Exception:
        return u
    u = {**u, "_staff": [(s["login"], s["name"], s.get("role") or "smm") for s in team]}
    view = request.cookies.get(VIEW_COOKIE)
    s = next((x for x in team if x["login"] == view), None) if view else None
    if not s:
        return u
    return {"u": s["login"], "n": s["name"], "r": s.get("role") or "smm", "exp": u.get("exp"), "viewas": True, "_staff": u["_staff"]}


@app.get("/viewas")
async def view_as(request: Request, u: str = ""):
    """Admin only: look at the site as one employee (u=login), or back to yourself (u empty)."""
    real = real_session(request)
    if not real or real.get("r") != "admin":
        return RedirectResponse("/", status_code=303)
    back = request.headers.get("referer") or "/"
    if not back.startswith(str(request.base_url)):
        back = "/"
    resp = RedirectResponse(back, status_code=303)
    if u:
        resp.set_cookie(VIEW_COOKIE, u, max_age=4 * 3600, samesite="lax", httponly=True)
    else:
        resp.delete_cookie(VIEW_COOKIE)
    return resp


@app.middleware("http")
async def view_as_read_only(request: Request, call_next):
    """While the admin looks through someone's eyes, nothing can be saved in their name."""
    if request.method == "POST" and request.cookies.get(VIEW_COOKIE) and request.url.path not in ("/ask", "/login") \
            and not request.url.path.startswith("/api/"):
        real = real_session(request)
        if real and real.get("r") == "admin":
            return HTMLResponse('<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;padding:40px">'
                                '<h2>Көру режимі</h2><p>Сіз басқа адамның көзімен қарап тұрсыз — бұл режимде ештеңе сақталмайды.</p>'
                                '<p><a href="/viewas">Өз аккаунтыма қайту</a></p></body>', status_code=403)
    return await call_next(request)


def stats_auth_ok(request: Request) -> bool:
    if session(request):
        return True
    if not STATS_PASSWORD:
        return False
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        user, _, pwd = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return hmac.compare_digest(user, STATS_USER) and hmac.compare_digest(pwd, STATS_PASSWORD)


PAGE_CACHE: dict = {}  # url -> (time, html): repeat opens within a few minutes are instant
PAGE_TTL = 180


def need_login(request: Request | None = None):
    """Send the browser to the login page and back to where it was going."""
    nxt = (request.url.path + ("?" + request.url.query if request.url.query else "")) if request else "/"
    return RedirectResponse(f"/login?next={quote(nxt, safe='')}", status_code=303)


def form_data(raw: bytes) -> dict:
    return {k: v if len(v) > 1 else v[0] for k, v in parse_qs(raw.decode(), keep_blank_values=True).items()}


def parse_range(p: str | None, d: str | None, end: str | None, d1: str | None = None, d2: str | None = None):
    """(period, first day, last day) in Astana time; never past today. Picked days d1…d2: at most 92 (Instagram is asked per day)."""
    today = igdata.today()
    if p == "range":
        kind, _, span_days = picked_days(p, None, d1, d2, "")
        if span_days:
            return "range", max(span_days[0], span_days[1] - timedelta(days=91)), span_days[1]
        d = d1 if kind == "day" else d
    try:
        if d:
            day = min(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=igdata.TZ), today)
            return ("today" if day == today else "yesterday" if day == today - timedelta(days=1) else "day"), day, day
        last = min(datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=igdata.TZ), today) if end else today
    except ValueError:
        last = today
    if p == "yesterday":
        return p, today - timedelta(days=1), today - timedelta(days=1)
    if p in ("7", "30"):
        return p, last - timedelta(days=int(p) - 1), last
    return "today", today, today


@app.get("/api/igbot/stats")
async def dashboard_page(request: Request, p: str | None = None, d: str | None = None, end: str | None = None,
                         d1: str | None = None, d2: str | None = None):
    """Instagram dashboard: followers, reach, likes, comments, posts."""
    if not stats_auth_ok(request):
        return need_login(request)
    await ensure_ready()
    period, first, last = parse_range(p, d, end, d1, d2)
    span = (last - first).days + 1
    pfirst, plast = first - timedelta(days=span), first - timedelta(days=1)
    chart_first = min(first, last - timedelta(days=13))  # charts show at least two weeks
    cache_key = str(request.url) + "|" + ((session(request) or {}).get("u") or "")
    hit = PAGE_CACHE.get(cache_key)
    if hit and time.time() - hit[0] < PAGE_TTL:
        return HTMLResponse(hit[1], headers={"Cache-Control": "no-store"})
    skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    with db() as con:
        # Profile, day numbers and posts are independent: ask Instagram for all three at once.
        me, rows, posts = await asyncio.gather(
            igdata.profile(http, API, auth()),
            igdata.days(http, API, auth(), con, min(chart_first, pfirst), last),
            igdata.media(http, API, auth(), con, first, last))
        errors = [] if me else ["Instagram профилін алу мүмкін болмады — токенді тексеру керек."]
        if me.get("followers_count") is not None:
            igdata.snapshot(con, me["followers_count"], me.get("media_count"))
        today_key = igdata.key(igdata.today())
        y = igdata.followers_on(con, igdata.key(igdata.today() - timedelta(days=1)))
        net_today = me["followers_count"] - y if y is not None and me.get("followers_count") is not None else None
        # past range: growth from our own end-of-day totals, for days Instagram has not counted yet
        end_total = igdata.followers_on(con, igdata.key(last)) if last < igdata.today() else None
        start_total = igdata.followers_on(con, igdata.key(first - timedelta(days=1)))
        net_range = end_total - start_total if end_total is not None and start_total is not None else None

        def agg(a, b):
            part = {k: v for k, v in rows.items() if igdata.key(a) <= k <= igdata.key(b)}
            out = {m: igdata.total(part, m) for m in igdata.DAY_METRICS + ["new_followers"]}
            out["direct"] = igdata.direct_messages(con, int(a.timestamp()), int((b + timedelta(days=1)).timestamp()), skip)
            return out

        cur, prev = agg(first, last), agg(pfirst, plast)
        saved = None
        if first == last:
            saved = history.get(con, igdata.key(first))
            if saved:
                before = history.get(con, igdata.key(first - timedelta(days=1)))
                saved.update(prev=(before or {}).get("data"), prev_label=dashboard.day_label(first - timedelta(days=1)))
    chart = {k: v for k, v in rows.items() if k >= igdata.key(chart_first)}
    page = dashboard.render(me=me, period=period, first=first, last=last, cur=cur, prev=prev, chart_days=chart, all_days=rows,
                            posts=posts, today_key=today_key, net_today=net_today, net_range=net_range, errors=errors,
                            updated=datetime.now(igdata.TZ).strftime("%d.%m.%Y, %H:%M"), saved=saved,
                            user=session(request))
    PAGE_CACHE[cache_key] = (time.time(), page)
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@app.get("/api/igbot/archive")
async def archive_page(request: Request, m: str | None = None, ok: str | None = None):
    """Saved daily reports: calendar of saved days and one card per day."""
    if not stats_auth_ok(request):
        return need_login(request)
    await ensure_ready()
    skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    with db() as con:
        history.ensure_table(con)
        if con.execute("select count(*) from reports where kind = 'restored'").fetchone()[0] == 0:
            await history.restore(http, API, auth(), con, 30, skip)  # first visit: fill the last month
        reports = history.all_reports(con)
        days = [datetime.strptime(r["day"], "%Y-%m-%d").replace(tzinfo=igdata.TZ) for r in reports]
        fu_cache = {k: v for k, v in con.execute("select k, v from kv where k like 'fu:%'")}  # one query for all days
        stats = await asyncio.gather(*[igdata.follow_stats(http, API, auth(), con, d, fu_cache) for d in days], return_exceptions=True)
        fu = {igdata.key(d): s for d, s in zip(days, stats) if isinstance(s, tuple)}
    today = igdata.today()
    try:
        month = datetime.strptime(m, "%Y-%m").replace(tzinfo=igdata.TZ) if m else today
    except ValueError:
        month = today
    flash = "Бүгінгі снимок сақталды." if ok else ""
    return HTMLResponse(archive.render(reports, month, igdata.key(today), flash, session(request), fu=fu), headers={"Cache-Control": "no-store"})


@app.post("/api/igbot/snapshot")
async def snapshot_now(request: Request):
    """«Снимок жасау»: save today's numbers as they are right now."""
    if not stats_auth_ok(request):
        return need_login(request)
    await ensure_ready()
    skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    me = await igdata.profile(http, API, auth())
    day = igdata.today()
    with db() as con:
        if me.get("followers_count") is not None:
            igdata.snapshot(con, me["followers_count"], me.get("media_count"))
        data = await history.summary(http, API, auth(), con, day, me.get("followers_count"), skip)
        old = history.get(con, igdata.key(day))
        if not (old and old["kind"] == "auto"):
            history.save(con, igdata.key(day), data, "manual")
    return RedirectResponse(f"archive?ok=1#r{igdata.key(day)}", status_code=303)


@app.get("/api/igbot/plan")
async def plan_page(request: Request, ok: str | None = None):
    """Daily targets: leads by hand, the rest by hand or worked out from leads."""
    if not stats_auth_ok(request):
        return need_login(request)
    skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    with db() as con:
        current, tg = plan.load(con), await plan.targets(http, API, auth(), con, skip)
    return HTMLResponse(plan.render(current, tg, bool(ok), session(request)), headers={"Cache-Control": "no-store"})


@app.post("/api/igbot/plan")
async def plan_save(request: Request):
    if not stats_auth_ok(request):
        return need_login(request)
    form = dict(x.split("=", 1) for x in (await request.body()).decode().split("&") if "=" in x)
    new = {m: int(form[m]) for m, _ in plan.METRICS if form.get(m, "").isdigit() and int(form[m]) > 0}
    with db() as con:
        plan.save(con, new)
    return RedirectResponse("plan?ok=1", status_code=303)


# ---------- marketing dashboard (the default page) ----------

@app.get("/login")
async def login_form(next: str = "/"):
    return HTMLResponse(admin.login_page(nxt=next))


@app.post("/login")
async def login_submit(request: Request):
    f = form_data(await request.body())
    with db() as con:
        sess = staffauth.login(con, (f.get("user") or "").strip(), f.get("pwd") or "")
    nxt = f.get("next") or "/"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    if not sess:
        return HTMLResponse(admin.login_page("Логин немесе құпиясөз қате", nxt), status_code=401)
    r = RedirectResponse(nxt, status_code=303)
    r.set_cookie(staffauth.COOKIE, staffauth.sign(sess), max_age=staffauth.SESSION_DAYS * 86400,
                 httponly=True, secure=True, samesite="lax")
    return r


@app.get("/logout")
async def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(staffauth.COOKIE)
    return r


def picked_days(p: str, d: str | None, d1: str | None, d2: str | None, default: str) -> tuple:
    """(period, anchor, (first, last) or None) from the query: a day / week / month around `d`, or the days d1…d2.
    Never past today, at most a year; one picked day is simply that day."""
    today = igdata.today()

    def day(v):
        return min(datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=igdata.TZ), today)
    if p == "range":
        try:
            a, b = sorted((day(d1), day(d2)))
        except (TypeError, ValueError):
            return default, today, None
        a = max(a, b - timedelta(days=365))
        return ("day", a, None) if a == b else ("range", b, (a, b))
    try:
        anchor = day(d) if d else today
    except ValueError:
        anchor = today
    return (p if p in ("day", "week", "month") else default), anchor, None


def home_trend(con, m: dict, anchor) -> dict:
    """Numbers for the canvas line and the bento cards on the overview: the previous month day by day,
    this week day by day, and where the period's leads came from (one amoCRM source value each)."""
    import calendar as _cal
    mfirst = anchor.replace(day=1)
    pm_first = (mfirst - timedelta(days=1)).replace(day=1)
    prev_days = amo.daily(con, int(pm_first.timestamp()), _cal.monthrange(pm_first.year, pm_first.month)[1])
    range_prev = []
    if m["period"] == "range":  # the same number of days right before the picked ones
        n_days = (m["last"] - m["first"]).days + 1
        range_prev = amo.daily(con, int((m["first"] - timedelta(days=n_days)).timestamp()), n_days)
    wfirst = anchor - timedelta(days=anchor.weekday())
    week_days = amo.daily(con, int(wfirst.timestamp()), 7)
    st = amo.settings(con)
    since, until = int(m["first"].timestamp()), int((m["last"] + timedelta(days=1)).timestamp())
    src = [(v, amo.numbers(con, since, until, {"field": st["source_field"], "values": [v]})["leads"])
           for v in (st.get("sources") or [])] if st.get("source_field") else []
    return {"prev_days": prev_days, "week_days": week_days, "week_first": wfirst, "sources": src, "range_prev": range_prev}


@app.get("/")
async def home_page(request: Request, p: str = "month", d: str | None = None, who: str | None = None,
                    d1: str | None = None, d2: str | None = None):
    user = session(request)
    if not user:
        return need_login(request)
    today = igdata.today()
    period, anchor, picked = picked_days(p, d, d1, d2, "month")
    T = [("start", time.perf_counter())]
    await ensure_ready()
    await watchdog_tick()
    T.append(("ready", time.perf_counter()))
    with db() as con:
        T.append(("db", time.perf_counter()))
        team = staffauth.staff(con)
        if user["r"] == "admin":
            person = next((x for x in team if x["login"] == who), team[0] if team else None)
        else:
            person = staffauth.get_staff(con, user["u"])
        plans = (person or {}).get("plans") or {}
        # the owner is greeted by name on their own view; an employee's name only when the owner opens that employee
        name = person["name"] if person and (user["r"] != "admin" or who) else ADMIN_NAME if user["r"] == "admin" else user["n"]
        T.append(("staff", time.perf_counter()))
        amo_state = await amo.sync(http, con)
        T.append(("amo", time.perf_counter()))
        own = (person or {}).get("login") if user["r"] != "admin" or who else None  # whose personal plan the page shows
        m = await mkt.build(http, API, auth(), con, period=period, anchor=anchor, plans=plans, name=name, login=own, span_days=picked)
        rtpl = mkt.report_tpl(con)
        T.append(("build", time.perf_counter()))
        days14 = amo.daily(con, int((min(anchor, today) - timedelta(days=13)).timestamp()), 14)
        T.append(("days14", time.perf_counter()))
        igx = await report_igx(con, m, today, period)
        T.append(("igx", time.perf_counter()))
        trend = home_trend(con, m, anchor)
        T.append(("trend", time.perf_counter()))
        if user["r"] == "admin":
            await ads.sync_meta(http, con)
        ads_html = (ads.card(ads.summary(con, m["first"], min(m["last"], today))) + f"<style>{ads.CSS}</style>") if user["r"] == "admin" else ""
        best_html = ""
        try:
            weeks = 8
            grid = amo.week_hours(con, int((today - timedelta(days=7 * weeks)).timestamp()), int(today.timestamp()))
            best_html = extras.best_time_card(grid, min(weeks, grid["weeks"])) + f"<style>{extras.BEST_CSS}</style>"
        except Exception:
            log.exception("best time")
        try:
            task_rows = dept.tasks(con, None if dept.can(user, "tasks.edit") else user["u"])
        except Exception:
            log.exception("home tasks")
            task_rows = []
        status_html = ""
        if user["r"] == "admin":
            try:
                status_html = extras.status_banner(await system_status(con, deep=False))
            except Exception:
                log.exception("status banner")
    spark14 = {"amount": [x["amount"] for x in days14], "sales": [x["sales"] for x in days14], "leads": [x["leads"] for x in days14],
               "avg": [round(x["amount"] / x["sales"]) if x["sales"] else 0 for x in days14],
               "conv": [round(x["sales"] / x["leads"] * 100, 1) if x["leads"] else 0 for x in days14]}
    url = f"{str(request.base_url).rstrip('/')}/?" + (f"p=range&d1={igdata.key(picked[0])}&d2={igdata.key(picked[1])}" if picked else f"p={period}&d={igdata.key(anchor)}")
    page = home.render(m, trend=trend, ads_html=ads_html, user=user, staff=team, who=who if user["r"] == "admin" and who else None,
                       anchor_key=igdata.key(anchor), today_key=igdata.key(today), amo_state=amo_state,
                       report_text=mkt.short_report(m, url, igx, rtpl), spark14=spark14, demo_ok=user["r"] == "admin",
                       planok=bool(request.query_params.get("planok")), top_html=status_html,
                       best_html=best_html, tasks=task_rows)
    T.append(("render", time.perf_counter()))
    timing = ", ".join(f"{T[i][0]};dur={(T[i][1] - T[i - 1][1]) * 1000:.0f}" for i in range(1, len(T)))
    log.info("timing / total=%.0fms %s", (T[-1][1] - T[0][1]) * 1000, timing)  # read with `vercel logs` to see what is slow
    return HTMLResponse(page, headers={"Cache-Control": "no-store", "Server-Timing": timing})


def admin_only(request: Request):
    user = session(request)
    if not user:
        return None, need_login(request)
    if user["r"] != "admin":
        return None, RedirectResponse("/", status_code=303)
    return user, None


@app.get("/team")
async def team_page(request: Request, edit: str | None = None, ok: str | None = None):
    _, deny = admin_only(request)
    if deny:
        return deny
    with db() as con:
        people, person = staffauth.staff(con), staffauth.get_staff(con, edit) if edit else None
        st = amo.settings(con)
    users = await amo.users(http)
    src = {}
    if st.get("source_field"):
        fl = next((x for x in await amo.fields(http) if x["id"] == str(st["source_field"])), None)
        if fl:
            src = {"id": fl["id"], "name": fl["name"], "values": fl["values"]}
    return HTMLResponse(admin.team_page(people, person, "Сақталды" if ok else "", user=session(request), amo_users=users, src=src),
                        headers={"Cache-Control": "no-store"})


@app.post("/team")
async def team_save(request: Request):
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    login_name = (f.get("login") or "").strip().lower()

    def number(k, cast=int):
        try:
            return cast(f.get(k) or 0)
        except ValueError:
            return 0

    with db() as con:
        if f.get("deactivate"):
            staffauth.deactivate(con, login_name)
            return RedirectResponse("/team?ok=1", status_code=303)
        try:
            def many(k):
                v = f.get(k) or []
                return [v] if isinstance(v, str) else v
            attr = {"users": [int(x) for x in many("attr_user") if x.isdigit()], "field": f.get("attr_field") or None,
                    "values": many("attr_value")}
            old = staffauth.get_staff(con, login_name)
            role = f.get("role") if f.get("role") in ("smm", "lead") else "smm"
            staffauth.save_staff(con, login_name, f.get("name") or login_name, role,
                                 (old or {}).get("plans") or {}, f.get("pwd") or None)
            dept.log(con, session(request)["u"], "staff.save", login_name, dept.ROLES and dict(dept.ROLES).get(role, role))
        except ValueError:
            return HTMLResponse(admin.team_page(staffauth.staff(con), None, err="Жаңа қызметкерге құпиясөз керек", user=session(request)), status_code=400)
    return RedirectResponse("/team?ok=1", status_code=303)


@app.post("/plan-quick")
async def plan_quick(request: Request):
    """Admin sets one employee's plans from the dashboard; the password stays as it is."""
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    login_name = (f.get("login") or "").strip().lower()

    def number(k, cast=int):
        raw = (f.get(k) or "").replace(" ", "").replace("\u00a0", "").replace(",", ".")
        if cast is int:
            raw = "".join(ch for ch in raw if ch.isdigit())
        try:
            return cast(raw or 0)
        except ValueError:
            return 0

    back = f.get("back") or "/"
    if not back.startswith("?"):
        back = "?"
    with db() as con:
        s = staffauth.get_staff(con, login_name)
        if not s:
            return RedirectResponse("/" + back, status_code=303)
        amount = number("amount")
        plans = {**(s.get("plans") or {}), "amount": amount if amount >= 1000 else 0,
                 "leads_day": number("leads_day") or 100, "bonus_pct": max(0.0, min(100.0, number("bonus_pct", float)))}
        staffauth.save_staff(con, s["login"], s["name"], s["role"], plans, None)
    return RedirectResponse("/" + back + "&planok=1", status_code=303)



async def report_igx(con, m: dict, today, period: str) -> dict:
    """Instagram part of the WhatsApp report: followers at the end of the range vs the day before it, Direct, posts."""
    first_d, last_d = m["first"], m["last"]
    igx = {"is_today": first_d == last_d == today}
    try:
        if last_d >= today:
            me = await igdata.profile(http, API, auth())
            igx["followers"] = me.get("followers_count")
            if igx["followers"] is not None:
                igdata.snapshot(con, igx["followers"], me.get("media_count"))
        else:
            igx["followers"] = igdata.followers_on(con, igdata.key(last_d))
        igx["prev"] = igdata.followers_on(con, igdata.key(first_d - timedelta(days=1)))
        if igx["prev"] is None and first_d == last_d:  # no total for the day before: Instagram's follows − unfollows
            fu = await igdata.follow_stats(http, API, auth(), con, first_d)
            if fu:
                igx["growth"] = fu[0] - fu[1]
        # Direct is only counted since the webhook started saving messages; earlier days stay out of the report
        row = con.execute("select min(ts) from events where event = 'msg'").fetchone()
        end_ts = int((min(last_d, today) + timedelta(days=1)).timestamp())
        if row and row[0] and int(first_d.timestamp()) >= row[0] - 86400:
            skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
            igx["direct"] = igdata.direct_messages(con, int(first_d.timestamp()), end_ts, skip)
        if period == "day":
            igx["posts"] = len(await igdata.media(http, API, auth(), con, first_d, last_d))
    except Exception:
        pass
    return igx


async def morning_text(con, base_url: str, day) -> str:
    return (await morning_payload(con, base_url, day))[0]


async def morning_payload(con, base_url: str, day) -> tuple[str, list]:
    """Yesterday (a finished day): who closed the plan, who did not, then the full report;
    plus one button per employee for warm words the director can forward."""
    team = staffauth.staff(con)
    people = team or [{"name": "Команда", "plans": {}}]
    status, first_m, buttons = [], None, []
    for person in people:
        plans = person.get("plans") or {}
        m = await mkt.build(http, API, auth(), con, period="day", anchor=day, plans=plans, name=person["name"])
        first_m = first_m or m
        leads, goal = m["crm"]["leads"] or 0, m["lead_day"]
        if leads >= goal:
            line = f"{person['name']} — жоспарды жапты ✓ (лид: {leads} / {goal})"
        else:
            line = f"{person['name']} — жоспарды жаппады (лид: {leads} / {goal}, {round(leads / goal * 100) if goal else 0}%)"
        mp = m["month_pct"]["amount"]
        if m["month_plan"]["amount"]:
            line += " · айлық сатылым: " + ("орындалды ✓" if (mp or 0) >= 100 else f"{mp}%")
        status.append(line)
        if person.get("login"):
            first = person["name"].split()[0]
            label = f"{first}: мақтау мәтіні" if leads >= goal else f"{first}: қолдау мәтіні"
            buttons.append((label, f"m:{person['login']}:{day:%Y%m%d}:0"))
    igx = await report_igx(con, first_m, igdata.today(), "day")
    url = f"{base_url.rstrip('/')}/?p=day&d={igdata.key(day)}"
    text = (f"*Кешегі күн · {day:%d.%m.%Y}*\n\n*Кім жоспарды жапты:*\n" + "\n".join(status)
            + "\n\n" + mkt.short_report(first_m, url, igx, mkt.report_tpl(con)))
    f, plan_amount = first_m.get("forecast"), first_m["month_plan"]["amount"]
    if f and not f["final"] and plan_amount:
        text += (f"\n\n*Ай соңына болжам:* {home.money(f['amount'])} — жоспардың {f['pct']}%"
                 + ("" if (f["pct"] or 0) >= 100 else f"\nЖоспарға жету үшін күніне: {home.money(f['amount_need'])}"
                    + (f" (≈ {f['leads_for_sales']} лид)" if f.get("leads_for_sales") else "")))
    try:
        text += "\n\n" + insights(con)
    except Exception:
        log.exception("insights")
    return text, buttons


@app.get("/api/igbot/morning")
async def morning(request: Request, force: str | None = None):
    """08:00 Astana (vercel.json): send yesterday's report to every Telegram recipient, once a day."""
    if CRON_SECRET and request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    try:  # the Trends page: today's stories and ideas, once a morning (a second call the same morning reuses them)
        with db() as con:
            await trends.refresh(http, con, max_age=6 * 3600)
    except Exception:
        log.exception("trends refresh")
    if not tg.configured():
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not set"}
    await ensure_ready()
    day = igdata.today() - timedelta(days=1)
    with db() as con:
        if amo.configured():
            await amo.sync(http, con, force=True, budget=60)
        if amo.kv_get(con, "tg_sent") == igdata.key(day) and not force:
            return {"ok": True, "skipped": "already sent"}
        chats = tg.recipients(con)
        text, buttons = await morning_payload(con, PUBLIC_URL, day)
        sent = [(await tg.send(http, c["id"], text, buttons))[0] for c in chats]
        if any(sent):
            amo.kv_set(con, "tg_sent", igdata.key(day))
        backup = await send_backup(con)
    await watchdog()
    return {"ok": any(sent), "sent": sum(sent), "of": len(chats), "backup": backup}


BACKUP_TABLES = ("leads", "events", "staff", "reports", "profiles", "users")
BACKUP_KV = ("mkt_settings", "texts", "post_rules", "tg_chats", "tg_staff", "tg_owner", "dm_queue")
DB_LIMIT_MB = 500  # Supabase free plan


def db_size_mb(con):
    try:
        return round(con.execute("select pg_database_size(current_database())").fetchone()[0] / 1048576, 1)
    except Exception:
        return None


def make_backup(con) -> tuple[bytes, dict]:
    """Everything that cannot be fetched again from amoCRM or Instagram, as gzipped JSON."""
    import gzip
    data, counts = {"made": datetime.now(igdata.TZ).isoformat(), "tables": {}, "kv": {}}, {}
    history.ensure_table(con)
    leads.ensure_table(con)
    staffauth.ensure_table(con)
    for t in BACKUP_TABLES:
        try:
            cur = con.execute(f"select * from {t}")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            data["tables"][t] = rows
            counts[t] = len(rows)
        except Exception as e:
            counts[t] = f"error: {str(e)[:60]}"
    for k in BACKUP_KV:
        v = amo.kv_get(con, k)
        if v is not None:
            data["kv"][k] = v
    for (k,) in con.execute("select k from kv where k like 'motiv_used:%'"):
        data["kv"][k] = amo.kv_get(con, k)
    return gzip.compress(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")), counts


async def send_backup(con) -> dict:
    """Nightly copy of the data to the owner's Telegram (only the owner), with the database size."""
    owner = amo.kv_get(con, "tg_owner")
    if not owner:
        return {"ok": False, "error": "no owner chosen"}
    blob, counts = make_backup(con)
    size = db_size_mb(con)
    pct = round(size / DB_LIMIT_MB * 100) if size is not None else None
    warn = f"\n⚠️ База {pct}% толды — маған хабарлаңыз" if pct is not None and pct >= 80 else ""
    caption = (f"EduApp · резервтік көшірме · {datetime.now(igdata.TZ):%d.%m.%Y}\n"
               f"База: {size if size is not None else '—'} МБ / {DB_LIMIT_MB} МБ" + (f" ({pct}%)" if pct is not None else "") + warn +
               f"\nЛидтер: {counts.get('leads')} · бот оқиғалары: {counts.get('events')} · қызметкерлер: {counts.get('staff')} · есептер: {counts.get('reports')}")
    ok, why = await tg.send_file(http, owner, f"eduapp-backup-{datetime.now(igdata.TZ):%Y-%m-%d}.json.gz", blob, caption)
    return {"ok": ok, "error": why, "bytes": len(blob)}


PUBLIC_URL = os.getenv("PUBLIC_URL", "https://dashboard.eduapp.example.com").rstrip("/")


async def motivation_for(con, login: str, day, seed: int) -> str | None:
    """A text this person has never had before; kept so «жіберу» sends exactly what the director saw."""
    person = staffauth.get_staff(con, login)
    if not person:
        return None
    m = await mkt.build(http, API, auth(), con, period="day", anchor=day, plans=person.get("plans") or {}, name=person["name"])
    used = amo.kv_get(con, f"motiv_used:{login}", []) or []
    text, key = motiv.compose(person["name"], m["crm"]["leads"] or 0, m["lead_day"], (m.get("streak") or {}).get("days", 0),
                              used, salt=f"{day:%Y%m%d}:{seed}")
    amo.kv_set(con, f"motiv_used:{login}", used + [key])
    amo.kv_set(con, f"mtxt:{login}:{day:%Y%m%d}:{seed}", text)
    return text


def staff_chats(con) -> dict:
    """{login: telegram chat id} for employees the admin linked on the Telegram page."""
    return amo.kv_get(con, "tg_staff", {}) or {}


@app.get("/bot")
async def bot_page(request: Request, p: str = "day", d: str | None = None, d1: str | None = None, d2: str | None = None):
    if not stats_auth_ok(request):  # every employee may see what the bot did
        return need_login(request)
    today = igdata.today()
    _, anchor, picked = picked_days("range" if p == "range" else "day", d, d1, d2, "day")
    with db() as con:
        rules = [dict(r) for r in _site_settings()["rules"]]
        thumbs = await post_thumbs()
        for r in rules:
            r["thumb"] = thumbs.get(r["media_id"])
        queue = amo.kv_get(con, "dm_queue", []) or []
        for r in rules:
            mid = r["media_id"]
            r["stats"] = {
                "replies": con.execute("select count(*) from events where event = 'comment_reply' and detail = ?", (mid,)).fetchone()[0],
                "sent": con.execute("select count(distinct igsid) from events where event = 'rule_dm' and detail = ?", (mid,)).fetchone()[0],
                "queued": sum(1 for q in queue if q.get("media") == mid)}
        page = botpage.render(con, texts(), bot_on(), "range" if picked else p if p in ("day", "7d", "30d") else "day", anchor, today, session(request),
                              rules=rules, note=request.query_params.get("ok", ""), control=control_state(con), picked=picked)
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


_thumbs = {"at": 0.0, "map": {}}


async def post_thumbs() -> dict:
    """{media id: picture url} of recent posts; Instagram's picture links expire, so they are re-read every 30 minutes."""
    if time.time() - _thumbs["at"] > 1800:
        try:
            r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,media_type,media_url,thumbnail_url", "limit": 50})
            _thumbs["map"] = {m["id"]: m.get("thumbnail_url") or m.get("media_url") for m in r.json().get("data", [])}
            _thumbs["at"] = time.time()
        except Exception:
            log.exception("post thumbs")
    return _thumbs["map"]


def control_state(con) -> dict:
    q = amo.kv_get(con, "dm_queue", []) or []
    names = {}
    if q:
        marks = ", ".join("?" * min(len(q), 30))
        names = dict(con.execute(f"select igsid, username from profiles where igsid in ({marks})", tuple(x["uid"] for x in q[:30])).fetchall())
    until = amo.kv_get(con, "pr_block_until", 0) or 0
    return {"on": bot_on(), "blocked_until": until if until > time.time() else 0, "queue": len(q),
            "queue_names": [names.get(x["uid"]) or "…" + x["uid"][-4:] for x in q[:30]],
            "see_phones": bool(amo.kv_get(con, "staff_see_phones", True)), "kw": bool(amo.kv_get(con, "kw_mode"))}


@app.post("/bot/control")
async def bot_control(request: Request):
    """Admin switches the bot, resumes or clears the queue, answers missed comments — from the Bot page."""
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    a = f.get("action")
    msg = "Сақталды"
    with db() as con:
        if a in ("on", "off"):
            amo.kv_set(con, "bot_enabled", a == "on")
            msg = "Бот қосылды" if a == "on" else "Бот өшірілді"
        elif a in ("kw_on", "kw_off"):
            amo.kv_set(con, "kw_mode", a == "kw_on")
            msg = "Кілт сөз режимі қосылды" if a == "kw_on" else "Кілт сөз режимі өшірілді"
        elif a == "queue_send":
            amo.kv_set(con, "pr_block_until", 0)
            amo.kv_set(con, "dm_queue_last", 0)
            msg = "Кезек жіберіле бастайды: әр 2 минутта бір хабарлама"
        elif a == "queue_clear":
            amo.kv_set(con, "dm_queue", [])
            msg = "Кезек тазаланды"
        elif a == "phones":
            amo.kv_set(con, "staff_see_phones", f.get("v") == "1")
            msg = "Сақталды"
    if a == "backlog_send":
        await ensure_ready()
        if not ME.get("id"):
            await whoami()
        todo = [c for c in await unanswered_comments() if wants_info(c["text"])]
        done = 0
        started = time.time()
        for c in todo:
            if time.time() - started > 200 or pr_blocked():
                break
            await on_comment(c, backlog=True)
            done += 1
            await asyncio.sleep(3)
        msg = f"{done} комментке жауап берілді" + (f", {len(todo) - done} қалды (қайта басыңыз)" if done < len(todo) else "")
    _tx_cache["at"] = 0
    return RedirectResponse("/bot?ok=" + quote(msg) + "#control", status_code=303)


@app.get("/bot/backlog")
async def bot_backlog(request: Request):
    """Preview of comments that ask for information and have no reply yet (last 7 days)."""
    _, deny = admin_only(request)
    if deny:
        return deny
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    todo = [c for c in await unanswered_comments() if wants_info(c["text"])]
    return JSONResponse([{"user": c["from"].get("username"), "text": c["text"][:80], "time": c["timestamp"]} for c in todo])


# ---------- watchdog: tells the owner in Telegram before customers notice ----------

async def watchdog(force: bool = False) -> list:
    """Checks the database size, Instagram's limit, amoCRM freshness, lead flow, and the keys (their end dates, whether
    Meta / Gemini / YouTube still answer, whether Trends refreshed); one message per problem per day."""
    if not tg.configured():
        return []
    problems = []
    with db() as con:
        owner = amo.kv_get(con, "tg_owner")
        if not owner:
            return []
        size = db_size_mb(con)
        if size is not None and size >= DB_LIMIT_MB * 0.8:
            problems.append(("db", f"База {size} МБ / {DB_LIMIT_MB} МБ — толуға жақын."))
        if (amo.kv_get(con, "pr_block_until", 0) or 0) > time.time():
            problems.append(("ig", "Instagram Direct-ке жауап беруді уақытша шектеді. Бот күтіп тұр, комменттерге «Direct-ке жазыңыз» деп жауап береді."))
        st = amo.kv_get(con, "amo_sync", {}) or {}
        if amo.configured() and st.get("at") and time.time() - st["at"] > 6 * 3600:
            problems.append(("amo", f"amoCRM {round((time.time() - st['at']) / 3600)} сағаттан бері жаңармаған." + (f" Қате: {st.get('error')}" if st.get("error") else "")))
        # keys and outside services (the «Жүйе» rows added in November): asked at most every 6 hours, the answer kept
        kc = amo.kv_get(con, "keys_check", {}) or {}
        if force or time.time() - (kc.get("at") or 0) > 6 * 3600:
            try:
                kc = {"at": int(time.time()), "bad": [[x["name"], x["state"], re.sub(r"<[^>]+>", "", x["text"])]
                                                      for x in await key_status(con) if x["state"] in ("bad", "warn")]}
                amo.kv_set(con, "keys_check", kc)
            except Exception:
                log.exception("key check")
        for name, state, text in kc.get("bad") or []:
            problems.append((f"key:{name}", f"{name} — {'АҚАУ' if state == 'bad' else 'назар аударыңыз'}: {text}"))
        now = datetime.now(igdata.TZ)
        if 13 <= now.hour <= 20:  # a working afternoon with no new marketing lead for 3 hours
            if amo.numbers(con, int(time.time()) - 3 * 3600, int(time.time()))["leads"] == 0:
                problems.append(("leads", "Соңғы 3 сағатта бірде-бір маркетинг лиді келмеді."))
        sent = amo.kv_get(con, "alerts_sent", {}) or {}
        today = igdata.key(igdata.today())
        new = [(k, t) for k, t in problems if force or sent.get(k) != today]
        for k, _ in new:
            sent[k] = today
        if new:
            amo.kv_set(con, "alerts_sent", sent)
    for _, t in new:
        await tg.send(http, owner, "⚠️ EduApp сторож: " + t, markdown=False)
    return [t for _, t in new]


async def watchdog_tick():
    """Runs the watchdog at most every 15 minutes, on Instagram events and page views."""
    try:
        with db() as con:
            last = amo.kv_get(con, "watchdog_at", 0) or 0
            if time.time() - last < 900:
                return
            amo.kv_set(con, "watchdog_at", int(time.time()))
            # keep amoCRM fresh even when nobody opens the site (weekends): Instagram events come all day
            if amo.configured():
                await amo.sync(http, con, budget=4)
        await watchdog()
        await slow_leads_alert()
    except Exception:
        log.exception("watchdog")


@app.exception_handler(Exception)
async def friendly_error(request: Request, exc: Exception):
    """A plain page instead of «Internal Server Error», and a note to the owner."""
    log.exception("unhandled: %s", request.url.path)
    db_down = "quota" in str(exc) or "connection" in str(exc).lower()
    text = ("База уақытша қолжетімсіз. Деректер жоғалған жоқ — әкімшіге хабар берілді." if db_down
            else "Бетте қате шықты. Бірнеше минуттан соң қайта ашып көріңіз.")
    return HTMLResponse(f"""<!doctype html><html lang="kk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EduApp Marketing</title></head><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f5fa;font-family:Golos Text,system-ui,sans-serif;color:#14112b">
<div style="max-width:420px;padding:32px;border-radius:24px;background:#fff;box-shadow:0 20px 50px -20px rgba(46,15,76,.3);text-align:center">
<h1 style="font-size:1.375rem;margin:10px 0">Сәл күте тұрыңыз</h1><p style="color:#625a7d;line-height:1.5">{text}</p>
<a href="/" style="display:inline-block;margin-top:12px;padding:12px 20px;border-radius:12px;background:linear-gradient(90deg,#7336F7,#9B6BFF);color:#fff;text-decoration:none;font-weight:700">Қайта ашу</a></div></body></html>""",
                        status_code=503 if db_down else 500)


# ---------- 2.3 search one person: Instagram, bot history, answers, amoCRM ----------

async def amo_deals_by_phone(phone: str) -> list:
    """Deals of the amoCRM contact with this phone (one API call, kept 10 minutes)."""
    digits = "".join(ch for ch in phone or "" if ch.isdigit())[-10:]
    if not amo.configured() or len(digits) < 10:
        return []
    hit = _phone_cache.get(digits)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    out = []
    try:
        r = await http.get(f"{amo.base()}/contacts", headers=amo.headers(), params={"query": digits, "with": "leads", "limit": 5}, timeout=20)
        ids = [l["id"] for c in ((r.json().get("_embedded") or {}).get("contacts") or []) if r.status_code == 200
               for l in ((c.get("_embedded") or {}).get("leads") or [])]
        if ids:
            with db() as con:
                marks = ", ".join("?" * len(ids))
                out = [{"id": i, "price": pr, "status": st, "created": cr, "closed": cl} for i, pr, st, cr, cl in
                       con.execute(f"select id, price, status, created, closed from amo_deals where id in ({marks})", tuple(ids)).fetchall()]
    except Exception:
        log.exception("amo phone lookup")
    _phone_cache[digits] = (time.time(), out)
    return out


_phone_cache: dict = {}
EV_LABEL = {"msg": "Direct-ке жазды", "welcome": "бот бірінші хабарламаны жіберді", "comment": "коммент жазды", "comment_reply": "комментіне жауап жазылды",
            "rule_dm": "пост бойынша арнайы мәтін жіберілді", "rule_dm_fail": "арнайы мәтін жіберілмеді (Instagram шектеуі)",
            "lead_answer": "сұрақтарға жауап берді", "lead_phone": "телефон қалдырды", "dm_fail": "Direct-ке жіберілмеді", "extra_sent": "вебинар сілтемесі жіберілді"}


@app.get("/person")
async def person_page(request: Request, q: str = ""):
    """Find a person by @username or phone: everything the bot knows, and their amoCRM deals."""
    user = session(request)
    if not user:
        return need_login(request)
    is_admin = user.get("r") == "admin"
    q = q.strip()
    body = ""
    if q:
        with db() as con:
            see = is_admin or bool(amo.kv_get(con, "staff_see_phones", True))
            digits = "".join(ch for ch in q if ch.isdigit())
            ids = []
            if len(digits) >= 7:
                ids = [r[0] for r in con.execute("select igsid from leads where replace(replace(replace(phone, ' ', ''), '+', ''), '-', '') like ?", (f"%{digits[-10:]}%",))]
            name = q.lstrip("@").lower()
            if not ids:
                ids = [r[0] for r in con.execute("select igsid from profiles where lower(username) = ?", (name,))]
            if not ids:
                ids = [r[0] for r in con.execute("select igsid from profiles where lower(username) like ? limit 5", (f"%{name}%",))]
            people = []
            for igsid in ids[:5]:
                un = (con.execute("select username from profiles where igsid = ?", (igsid,)).fetchone() or [None])[0]
                lead = leads.get_lead(con, igsid)
                evs = con.execute("select ts, event, detail from events where igsid = ? order by ts desc limit 40", (igsid,)).fetchall()
                queued = any(x["uid"] == igsid for x in (amo.kv_get(con, "dm_queue", []) or []))
                people.append((igsid, un, lead, evs, queued))
        cards = ""
        for igsid, un, lead, evs, queued in people:
            deals = await amo_deals_by_phone((lead or {}).get("phone"))
            won = [d for d in deals if d["status"] == amo.WON]
            ph = (lead or {}).get("phone")
            ph_txt = (ph if see else (ph[:-5] + " ** **" if ph else None)) or "—"
            timeline = "".join(f'<li><b>{datetime.fromtimestamp(ts, igdata.TZ):%d.%m %H:%M}</b> — {EV_LABEL.get(ev.split(":")[0], ev)}</li>' for ts, ev, _ in evs) or "<li>оқиға жоқ</li>"
            deal_txt = (f'{len(deals)} сделка · сатылым: {len(won)} · {sum(d["price"] or 0 for d in won):,} ₸'.replace(",", " ") if deals
                        else ("amoCRM-де бұл телефон табылмады" if ph else "телефон белгісіз — amoCRM-мен байланыстыру мүмкін емес"))
            cards += (f'<section class="card cardin" style="margin-top:16px"><div class="ch"><h2>{"@" + html.escape(un) if un else "…" + igsid[-4:]}</h2>'
                      + (f'<a class="btng" href="https://instagram.com/{html.escape(un)}" target="_blank" rel="noopener">Instagram ↗</a>' if un else "")
                      + f'</div><div class="pgrid"><div><small>Қала</small><b>{html.escape((lead or {}).get("city") or "—")}</b></div>'
                      f'<div><small>Сынып</small><b>{html.escape(str((lead or {}).get("grade") or "—"))}</b></div>'
                      f'<div><small>Телефон</small><b>{html.escape(ph_txt)}</b></div><div><small>amoCRM</small><b>{deal_txt}</b></div>'
                      f'<div><small>Кезекте ме</small><b>{"иә, хабарлама күтіп тұр" if queued else "жоқ"}</b></div></div>'
                      f'<h3 style="margin:16px 0 8px;font-size:0.9375rem">Тарих</h3><ul class="tl2">{timeline}</ul></section>')
        body = cards or '<section class="card" style="margin-top:16px"><p>Ешкім табылмады. @username немесе телефонды тексеріңіз.</p></section>'
    css = ("<style>.sf{display:flex;gap:10px}.sf input{flex:1;height:46px;padding:0 14px;border-radius:12px;border:1.5px solid var(--border);background:var(--surface2);color:var(--text);font:500 0.9375rem Golos Text,sans-serif}"
           ".pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}.pgrid div{padding:12px;border-radius:14px;background:var(--surface2)}"
           ".pgrid small{display:block;color:var(--faint);font-size:0.75rem}.pgrid b{font-weight:700}.tl2{margin:0;padding-left:18px;display:grid;gap:4px;color:var(--muted);font-size:0.875rem}.tl2 b{color:var(--text)}</style>")
    return HTMLResponse(admin.page("Адам іздеу · EduApp", f"""<main class="wrap narrow">{css}
<section class="ph cardin"><div><h1>Адам іздеу</h1><p>@username немесе телефон: бот не жіберді, ол не жауап берді, amoCRM-де сделкасы бар ма</p></div></section>
<form class="sf" method="get"><input name="q" value="{html.escape(q)}" placeholder="@username немесе 8 707 123 45 67" autofocus><button class="btnp" type="submit">Іздеу</button></form>
{body}</main>""", user, "bot"), headers={"Cache-Control": "no-store"})


# ---------- 2.4 how fast people get a human answer in Direct ----------

_speed = {"at": 0.0, "data": None}


@app.get("/bot/speed")
async def bot_speed(request: Request):
    """From Instagram's own chats (last 7 days): minutes to the first human answer, and who waits for more than an hour.
    Bot messages (welcome, post texts, thanks) are not counted as answers."""
    if not session(request):
        return JSONResponse({"error": "login"}, status_code=401)
    if _speed["data"] and time.time() - _speed["at"] < 900:
        return JSONResponse(_speed["data"])
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    t = texts()
    bot_starts = [x.strip()[:25] for x in (t.get("welcome_text"), t.get("lead_thanks"), t.get("comment_reply_blocked")) if x] + \
                 [(r.get("dm") or "").strip()[:25] for r in _site_settings()["rules"] if r.get("dm")] + ["Сәлеметсіз бе!\n\n🏆"]
    me_ids = {ME.get("id"), ME.get("username")}
    since = time.time() - 7 * 86400
    delays, waiting, after = [], [], None

    def ts(m):
        return datetime.strptime(m["created_time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    for _ in range(4):
        params = {"platform": "instagram", "limit": 50, "fields": "updated_time,messages.limit(30){from,created_time,message}"}
        if after:
            params["after"] = after
        r = await http.get(f"{API}/me/conversations", headers=auth(), params=params)
        if r.status_code != 200:
            break
        j = r.json()
        for conv in j.get("data", []):
            msgs = sorted((conv.get("messages") or {}).get("data", []), key=ts)
            msgs = [m for m in msgs if ts(m) >= since]
            if not msgs:
                continue
            pending = None
            for m in msgs:
                frm = m.get("from") or {}
                ours = frm.get("id") in me_ids or frm.get("username") in me_ids
                is_bot = ours and any((m.get("message") or "").startswith(b) for b in bot_starts if b)
                if not ours and pending is None:
                    pending = (ts(m), frm.get("username"))
                elif ours and not is_bot and pending is not None:
                    delays.append((ts(m) - pending[0]) / 60)
                    pending = None
            if pending is not None and time.time() - pending[0] > 3600:
                waiting.append({"user": pending[1], "hours": round((time.time() - pending[0]) / 3600, 1)})
        after = ((j.get("paging") or {}).get("cursors") or {}).get("after") if (j.get("paging") or {}).get("next") else None
        if not after:
            break
    delays.sort()
    data = {"answered": len(delays), "median_min": round(delays[len(delays) // 2]) if delays else None,
            "within_15": round(sum(1 for d in delays if d <= 15) / len(delays) * 100) if delays else None,
            "waiting": sorted(waiting, key=lambda x: -x["hours"])[:20], "waiting_count": len(waiting)}
    _speed.update(at=time.time(), data=data)
    return JSONResponse(data)


# ---------- system status, lead response speed, the report as a picture ----------

def _amo_domain() -> str:
    return os.getenv("AMO_DOMAIN", "").strip().removeprefix("https://").strip("/")


def _ago_text(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m} мин" if m < 60 else f"{m // 60} сағ {m % 60} мин" if m < 1440 else f"{m // 1440} күн"


async def system_status(con, deep: bool = True) -> list:
    """One row per part the report depends on. deep=False skips the calls to Instagram and Telegram (for the overview)."""
    items, now = [], time.time()
    today = igdata.today()
    yesterday = today - timedelta(days=1)
    t0 = time.perf_counter()
    try:
        con.execute("select 1").fetchone()
        ms = round((time.perf_counter() - t0) * 1000)
        size = db_size_mb(con)
        p = round(size / DB_LIMIT_MB * 100) if size is not None else None
        items.append({"name": "База", "state": "bad" if (p or 0) >= 95 else "warn" if (p or 0) >= 80 else "ok",
                      "text": f"Supabase · {size} МБ / {DB_LIMIT_MB} МБ ({p}%) · жауап {ms} мс"})
    except Exception as e:
        items.append({"name": "База", "state": "bad", "text": html.escape(str(e)[:160])})

    if not amo.configured():
        items.append({"name": "amoCRM", "state": "off", "text": "AMO_DOMAIN / AMO_TOKEN қойылмаған."})
    else:
        s = amo.kv_get(con, "amo_sync", {}) or {}
        n = amo.numbers(con, int(today.timestamp()), int(now))
        tail = f" · бүгін {n['leads']} маркетинг лиді, {n['sales']} сатылым"
        if s.get("error"):
            items.append({"name": "amoCRM", "state": "bad", "text": "Қате: " + html.escape(str(s["error"])[:160]) + tail})
        elif not s.get("at"):
            items.append({"name": "amoCRM", "state": "warn", "text": "Әлі бірде-бір рет жаңартылмаған." + tail})
        else:
            age = now - s["at"]
            when = datetime.fromtimestamp(s["at"], igdata.TZ).strftime("%d.%m %H:%M")
            items.append({"name": "amoCRM", "state": "ok" if age <= 7200 else "warn" if age <= 6 * 3600 else "bad",
                          "text": f"Соңғы жаңарту: {when} ({_ago_text(age)} бұрын)"
                                  + (" · сделкалар әлі жүктеліп жатыр" if s.get("behind") else "") + tail})

    snap = history.get(con, igdata.key(yesterday))
    if snap:
        when = datetime.fromtimestamp(snap["ts"], igdata.TZ).strftime("%d.%m %H:%M") if snap.get("ts") else ""
        items.append({"name": "Түнгі жұмыс (00:05)", "state": "ok",
                      "text": f"Кешегі ({yesterday:%d.%m}) Instagram снимогы сақталды {when}. amoCRM толық жаңартылды."})
    else:
        items.append({"name": "Түнгі жұмыс (00:05)", "state": "warn",
                      "text": f"Кешегі ({yesterday:%d.%m}) снимок жоқ — түнгі жұмыс өтпеген болуы мүмкін. "
                              '<a href="/api/igbot/archive">Тарих</a> бетінде «Бүгінгі снимокты сақтау».'})

    ig_state, ig_text = "ok", ""
    if not token():
        ig_state, ig_text = "bad", "Instagram токені жоқ (IG_TOKEN)."
    elif deep:
        try:
            r = await http.get(f"{API}/me", headers=auth(), params={"fields": "username,followers_count"})
            if r.status_code == 200:
                j = r.json()
                ig_text = f"@{j.get('username')} · {j.get('followers_count', '—')} жазылушы · токен жарамды"
            else:
                ig_state, ig_text = "bad", f"Instagram жауап бермеді ({r.status_code}): токенді тексеріңіз."
        except Exception as e:
            ig_state, ig_text = "bad", "Instagram-ға қосылу мүмкін болмады: " + html.escape(str(e)[:100])
    else:
        ig_text = "Токен бар"
    until = amo.kv_get(con, "pr_block_until", 0) or 0
    if until > now:
        ig_state = "warn" if ig_state == "ok" else ig_state
        ig_text += f" · Direct-ке жауапқа шектеу {datetime.fromtimestamp(until, igdata.TZ):%H:%M} дейін"
    items.append({"name": "Instagram", "state": ig_state, "text": ig_text})

    if not tg.configured():
        items.append({"name": "Telegram есеп", "state": "off", "text": "TELEGRAM_BOT_TOKEN қойылмаған."})
    else:
        rec = tg.recipients(con)
        sent = amo.kv_get(con, "tg_sent")
        clock = datetime.now(igdata.TZ)
        st = "ok"
        if sent == igdata.key(yesterday):
            rep = "бүгінгі 08:00 есебі жіберілді ✓"
        elif clock.hour * 60 + clock.minute >= 8 * 60 + 15:
            st, rep = "bad", 'бүгінгі 08:00 есебі жіберілмеді — <a href="/telegram">Telegram</a> бетінде «Кешегі есепті қазір жіберу»'
        else:
            rep = "есеп 08:00-де жіберіледі"
        if not rec:
            st, rep = "bad", "алушы жоқ — есеп ешкімге бармайды"
        names = html.escape(", ".join(c["name"] for c in rec)) or "—"
        text = f"Алушылар ({len(rec)}): {names} · {rep}"
        if deep:
            info = (await tg.call(http, "getWebhookInfo")).get("result") or {}
            if info.get("last_error_date") and now - info["last_error_date"] < 86400:
                st = "warn" if st == "ok" else st
                text += " · бот батырмаларында қате: " + html.escape(info.get("last_error_message") or "")
        items.append({"name": "Telegram есеп", "state": st, "text": text})

    q = amo.kv_get(con, "dm_queue", []) or []
    items.append({"name": "Instagram бот", "state": "ok",
                  "text": ("қосулы" if bot_on() else "өшірулі (тек санайды)")
                          + (" · кілт сөз режимі қосулы" if amo.kv_get(con, "kw_mode") else "")
                          + (f" · кезекте {len(q)} адам" if q else "") + ' · <a href="/bot">Бот</a>'})
    if deep:
        items += await key_status(con)
    return items


def _days_left(ts_end: float) -> int:
    return int((ts_end - time.time()) // 86400)


def _jwt_exp(tok: str):
    """The «exp» of a JWT (the amoCRM long-lived token is one), or None."""
    import base64
    try:
        part = tok.split(".")[1]
        return int(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("exp") or 0) or None
    except Exception:
        return None


async def key_status(con) -> list:
    """Keys and outside services the newer pages depend on: when a key ends, and whether each one still answers.
    Never shows a key itself."""
    out, now = [], time.time()

    # Instagram token: refreshed every 3 days (refresh_token), lives 60 days from the last refresh
    token()
    if _token.get("ts"):
        left = _days_left(_token["ts"] + 60 * 86400)
        out.append({"name": "Instagram кілті", "state": "ok" if left >= 14 else "warn" if left >= 3 else "bad",
                    "text": f"Соңғы жаңарту {datetime.fromtimestamp(_token['ts'], igdata.TZ):%d.%m} · {left} күн қалды "
                            "(өздігінен әр 3 күн сайын жаңарады; 14 күннен аз қалса — жаңарту істемей тұр)"})
    else:
        out.append({"name": "Instagram кілті", "state": "warn",
                    "text": "Кілт әлі бірде-бір рет өздігінен жаңармаған: мерзімі белгісіз. Бір-екі күнде жаңаруы керек."})

    # amoCRM long-lived token: has a fixed end date chosen when it was created
    if amo.configured():
        exp = _jwt_exp(os.getenv("AMO_TOKEN", "").strip())
        if exp:
            left = _days_left(exp)
            out.append({"name": "amoCRM кілті", "state": "ok" if left >= 30 else "warn" if left >= 7 else "bad",
                        "text": f"Мерзімі {datetime.fromtimestamp(exp, igdata.TZ):%d.%m.%Y} дейін · {left} күн қалды. "
                                "Біткенде amoCRM-де жаңа ұзақ мерзімді кілт жасап, Vercel-дегі AMO_TOKEN-ді ауыстыру керек."})
        else:
            out.append({"name": "amoCRM кілті", "state": "warn", "text": "Кілттің мерзімін оқу мүмкін болмады."})

    # Meta tokens (ads spend, competitors): valid? when do they end?
    base = f"https://graph.facebook.com/{os.getenv('META_GRAPH_API_VERSION', 'v25.0')}"
    for name, var, use in (("Meta кілті · Жарнама", "META_ADS_TOKEN", "жарнама шығыны"),
                           ("Meta кілті · Бәсекелестер", "META_IG_TOKEN", "бәсекелестер")):
        tok = os.getenv(var, "").strip()
        if not tok:
            out.append({"name": name, "state": "off", "text": f"{var} қойылмаған: {use} жаңармайды."})
            continue
        try:
            r = await http.get(f"{base}/debug_token", params={"input_token": tok}, headers={"Authorization": f"Bearer {tok}"}, timeout=10)
            d = (r.json() or {}).get("data") or {}
        except Exception as e:
            out.append({"name": name, "state": "warn", "text": "Meta жауап бермеді: " + html.escape(type(e).__name__)})
            continue
        if not d.get("is_valid"):
            out.append({"name": name, "state": "bad", "text": f"Кілт жарамсыз: {use} жаңармайды. Meta Business Settings-те жаңасын жасау керек."})
            continue
        end = d.get("expires_at") or 0
        if end:
            left = _days_left(end)
            out.append({"name": name, "state": "ok" if left >= 14 else "warn" if left >= 3 else "bad",
                        "text": f"Жарамды · мерзімі {datetime.fromtimestamp(end, igdata.TZ):%d.%m.%Y} дейін ({left} күн)"})
        else:
            out.append({"name": name, "state": "ok", "text": "Жарамды · мерзімсіз (жүйелік пайдаланушы кілті)"})
    st = amo.kv_get(con, "ad_meta_state", {}) or {}
    if st.get("error"):
        out.append({"name": "Жарнама шығыны (Meta)", "state": "bad", "text": "Соңғы жаңарту сәтсіз: " + html.escape(str(st["error"])[:160])})
    cs = amo.kv_get(con, "comp_state", {}) or {}
    if cs.get("error"):
        out.append({"name": "Бәсекелестер", "state": "bad", "text": "Meta деректері алынбады: " + html.escape(str(cs["error"])[:160])})

    # AI (Gemini): «Сұрақ қойыңыз» and the Trends page
    gkey = os.getenv("GEMINI_API_KEY", "").strip()
    if not gkey:
        out.append({"name": "AI (Gemini)", "state": "off", "text": "GEMINI_API_KEY қойылмаған: AI сұрақтары мен Трендтер идеялары жоқ."})
    else:
        try:
            r = await http.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 1},
                               headers={"x-goog-api-key": gkey}, timeout=10)
            ok = r.status_code == 200
        except Exception:
            ok = False
        tr = amo.kv_get(con, "trends", {}) or {}
        age = now - (tr.get("at") or 0)
        text = ("Кілт жарамды" if ok else "Кілт жауап бермеді — AI сұрақтары мен Трендтер тоқтайды") + " · Трендтер: "
        text += (f"жаңартылды {datetime.fromtimestamp(tr['at'], igdata.TZ):%d.%m %H:%M}" if tr.get("at") else "әлі жаңармаған")
        if tr.get("error"):
            text += " · соңғы жаңарту сәтсіз: " + html.escape(str(tr["error"])[:120])
        if tr.get("search_error"):
            text += " · Google іздеуі жоқ (тегін тариф)"
        state = "bad" if not ok else "warn" if tr.get("error") or age > 30 * 3600 else "ok"
        out.append({"name": "AI (Gemini) · Трендтер", "state": state, "text": text})

    yt = os.getenv("YOUTUBE_API_KEY", "").strip()
    yt_err = next((x for x in (amo.kv_get(con, "trends", {}) or {}).get("src_errors") or [] if x.startswith("YouTube")), "")
    out.append({"name": "YouTube", "state": "off" if not yt else "bad" if yt_err else "ok",
                "text": "YOUTUBE_API_KEY қойылмаған" if not yt else html.escape(yt_err) if yt_err else
                        "Кілт бар · Трендтердегі видео жолағы жұмыс істейді"})
    return out


@app.get("/api/igbot/system-check")
async def system_check(request: Request):
    """The «Жүйе» page as JSON (for a check without signing in): one row per part, its state and text."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    with db() as con:
        items = await system_status(con)
    return [{"name": x["name"], "state": x["state"], "text": re.sub(r"<[^>]+>", "", x["text"])} for x in items]


@app.get("/status")
async def status_page(request: Request):
    user, deny = admin_only(request)
    if deny:
        return deny
    await ensure_ready()
    with db() as con:
        if amo.configured():
            await amo.sync(http, con, budget=6)  # show the state after a fresh copy, not since the last page view
        items = await system_status(con)
    return HTMLResponse(extras.status_page(items, user), headers={"Cache-Control": "no-store"})


@app.get("/speed-card")
async def speed_card(request: Request, d: str | None = None):
    """Lead response speed for one day, loaded by the overview after the page is shown (amoCRM is slow)."""
    if not session(request):
        return PlainTextResponse("", status_code=401)
    today = igdata.today()
    try:
        day = min(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=igdata.TZ), today) if d else today
    except ValueError:
        day = today
    since = int(day.timestamp())
    try:
        with db() as con:
            s = await amo.lead_speed(http, con, since, since + 86400)
    except Exception:
        log.exception("lead speed")
        return HTMLResponse("")
    label = "бүгін" if day == today else f"{day:%d.%m.%Y}"
    return HTMLResponse(extras.speed_card(s, _amo_domain(), label), headers={"Cache-Control": "no-store"})


async def slow_leads_alert():
    """Tell the owner about new marketing deals nobody touched for 15+ minutes (09:00–21:00, once per deal).
    Switched on by kv `speed_alerts` after the touch events were checked on the real account."""
    now = datetime.now(igdata.TZ)
    if not (tg.configured() and amo.configured()) or not 9 <= now.hour < 21:
        return
    with db() as con:
        owner = amo.kv_get(con, "tg_owner")
        if not owner or not amo.kv_get(con, "speed_alerts"):
            return
        s = await amo.lead_speed(http, con, int(igdata.today().timestamp()))
        done = amo.kv_get(con, "slow_alerted", {}) or {}
        today_key = igdata.key(igdata.today())
        seen = set(done.get(today_key, []))
        if not s or s.get("partial"):
            return
        new = [w for w in s.get("waiting", []) if w["id"] not in seen]
        if not new:
            return
        amo.kv_set(con, "slow_alerted", {today_key: sorted(seen | {w["id"] for w in new})})
    dom = _amo_domain()
    lines = [f"• #{w['id']} — {w['who'] or 'жауапты жоқ'}, {w['min']} мин" + (f"\n  https://{dom}/leads/detail/{w['id']}" if dom else "")
             for w in new[:10]]
    await tg.send(http, owner, f"⏱ {len(new)} жаңа лидке {amo.SLOW_MIN} минуттан көп жауап жоқ:\n" + "\n".join(lines), markdown=False)


@app.get("/api/igbot/amo-events")
async def amo_events(request: Request, hours: int = 3, alerts: str | None = None, d: str | None = None):
    """Diagnostics: which events amoCRM keeps (counted, no names) and today's lead speed; ?alerts=1|0 turns the Telegram alert on/off."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    types = await amo.probe_events(http, int(time.time()) - max(1, min(hours, 48)) * 3600)
    with db() as con:
        if alerts in ("0", "1"):
            amo.kv_set(con, "speed_alerts", alerts == "1")
        day = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=igdata.TZ) if d else igdata.today()
        s = await amo.lead_speed(http, con, int(day.timestamp()), int(day.timestamp()) + 86400, ttl=0) or {}
        on = bool(amo.kv_get(con, "speed_alerts"))
    speed = {k: s.get(k) for k in ("total", "touched", "median", "within", "events")}
    speed.update(waiting=len(s.get("waiting", [])), slow=[x["min"] for x in s.get("slow", [])])
    speed["partial"] = s.get("partial")
    with db() as con:
        sync = amo.kv_get(con, "touch_sync")
    return {"types": types, "alerts": on, "speed": speed, "download": amo._LAST_EVENTS, "touch_sync": sync}


REPORT_TITLES = {"day": ("Күндік есеп", "кешемен салыстырғанда"), "week": ("Апталық есеп", "өткен аптамен"),
                 "month": ("Айлық есеп", "өткен аймен"), "range": ("Кезең есебі", "алдыңғы осындай кезеңмен")}


@app.get("/report-card")
async def report_card(request: Request, p: str = "day", d: str | None = None, who: str | None = None,
                      d1: str | None = None, d2: str | None = None):
    """The report as one picture for the director (download, copy, share, print to PDF)."""
    user = session(request)
    if not user:
        return need_login(request)
    today = igdata.today()
    period, anchor, picked = picked_days(p, d, d1, d2, "day")
    await ensure_ready()
    with db() as con:
        team = staffauth.staff(con)
        if user["r"] == "admin":
            person = next((x for x in team if x["login"] == who), team[0] if team else None)
        else:
            person = staffauth.get_staff(con, user["u"])
        plans = (person or {}).get("plans") or {}
        await amo.sync(http, con)
        m = await mkt.build(http, API, auth(), con, period=period, anchor=anchor, plans=plans, name=(person or {}).get("name") or "",
                            login=(person or {}).get("login") if user["r"] != "admin" or who else None, span_days=picked)
        igx = await report_igx(con, m, today, period)
        speed = None
        if period == "day":
            try:
                speed = await amo.lead_speed(http, con, int(anchor.timestamp()), int(anchor.timestamp()) + 86400)
            except Exception:
                log.exception("lead speed")
    first, last = m["first"], m["last"]
    span = f"{first:%d.%m.%Y}" if first == last else f"{first:%d.%m} – {last:%d.%m.%Y}"
    title, prev_label = REPORT_TITLES[period]
    svg = extras.report_svg(m, igx, speed, title, span, prev_label)
    q = f"&who={quote(who)}" if who else ""
    segs = '<nav class="segs">' + "".join(
        f'<a class="seg{" on" if k == period else ""}" href="?p={k}&d={igdata.key(anchor)}{q}">{t}</a>' for k, t in mkt.PERIODS) + "</nav>"
    return HTMLResponse(extras.card_page(svg, user, segs, f"eduapp-esep-{igdata.key(anchor)}-{period}",
                                        (f"/?p=range&d1={igdata.key(picked[0])}&d2={igdata.key(picked[1])}{q}" if picked else f"/?p={period}&d={igdata.key(anchor)}{q}")),
                        headers={"Cache-Control": "no-store"})


# ---------- 2.2 / 4.2 content → money: each post's path from views to tenge ----------

async def phone_sales(con, phones: list, budget: int = 4) -> dict:
    """{digits: (sales, tenge)} from amoCRM won deals of the contact with that phone; cached in kv for a day (read in one
    query), at most `budget` new amoCRM lookups per page so the page stays fast — the rest fill in on the next visits."""
    digits = list(dict.fromkeys(d for d in ("".join(ch for ch in ph if ch.isdigit())[-10:] for ph in phones) if len(d) == 10))
    out, new, now, hits = {}, 0, time.time(), {}
    for i in range(0, len(digits), 500):
        part = digits[i:i + 500]
        hits.update({k[3:]: json.loads(v) for k, v in con.execute(f"select k, v from kv where k in ({', '.join('?' * len(part))})",
                                                                   tuple(f"ps:{d}" for d in part)) if v})
    for d in digits:
        hit = hits.get(d)
        if hit and now - hit[2] < 86400:
            out[d] = (hit[0], hit[1])
            continue
        if new >= budget:
            continue
        if new:
            await asyncio.sleep(0.5)
        new += 1
        deals = await amo_deals_by_phone(d)
        won = [x for x in deals if x["status"] == amo.WON]
        val = (len(won), sum(x["price"] or 0 for x in won))
        amo.kv_set(con, f"ps:{d}", [val[0], val[1], int(time.time())])
        out[d] = val
    return out


@app.get("/content")
async def content_page(request: Request, days: int = 30, d1: str | None = None, d2: str | None = None):
    """Grid of posts like the Instagram profile, each with views → comments → bot keywords → Direct → leads → sales → ₸."""
    user = session(request)
    if not user:
        return need_login(request)
    await ensure_ready()
    today = igdata.today()
    first, last = today - timedelta(days=max(7, min(days, 90)) - 1), today
    if d1 and d2:  # picked days; the 7 / 30 / 90 buttons stay plain «last N days»
        _, one, span_days = picked_days("range", None, d1, d2, "")
        first, last = (max(span_days[0], span_days[1] - timedelta(days=91)), span_days[1]) if span_days else (one, one)
        days = 0
    n_days = (last - first).days + 1
    with db() as con:
        posts = await igdata.media(http, API, auth(), con, first, last)
        cards, total_rev, pending = [], 0, 0
        ids = [m["id"] for m in posts]
        commenters, dms, phone_of = {}, {}, {}
        if ids:
            marks = ", ".join("?" * len(ids))
            for igsid, mid in con.execute(f"select distinct igsid, detail from events where event = 'comment' and detail in ({marks})", tuple(ids)):
                commenters.setdefault(mid, set()).add(igsid)
            dms = dict(con.execute(f"select detail, count(distinct igsid) from events where event in ('rule_dm', 'text_dm')"
                                   f" and detail in ({marks}) group by detail", tuple(ids)).fetchall())
            who = list({x for v in commenters.values() for x in v})
            for i in range(0, len(who), 500):
                part = who[i:i + 500]
                phone_of.update(con.execute(f"select igsid, phone from leads where phone is not null and igsid in ({', '.join('?' * len(part))})",
                                            tuple(part)).fetchall())
        ps = await phone_sales(con, list(phone_of.values()))
        for m in posts:
            mid = m["id"]
            phones = [phone_of[x] for x in commenters.get(mid, ()) if x in phone_of]
            mine = {d: ps[d] for d in ("".join(ch for ch in ph if ch.isdigit())[-10:] for ph in phones) if d in ps}
            sales = sum(v[0] for v in mine.values())
            rev = sum(v[1] for v in mine.values())
            pending += max(0, len(phones) - len(mine))
            total_rev += rev
            cards.append({"m": m, "keywords": len(commenters.get(mid, ())), "dms": dms.get(mid, 0), "leads": len(phones), "sales": sales, "rev": rev})
    thumbs = await post_thumbs()
    best = max(cards, key=lambda c: (c["rev"], c["keywords"]), default=None)

    def n(v):
        return f"{v:,}".replace(",", " ") if isinstance(v, (int, float)) else "—"
    grid = ""
    for c in cards:
        m = c["m"]
        pic = thumbs.get(m["id"]) or m.get("thumbnail_url") or m.get("media_url")
        kind = {"REELS": "Рилс", "FEED": "Пост", "STORY": "Сторис"}.get(m.get("media_product_type"), "Пост")
        steps = [("қаралым", m.get("views") or m.get("reach")), ("коммент", m.get("comments_count")), ("кілт сөз", c["keywords"]),
                 ("Direct", c["dms"]), ("лид", c["leads"]), ("сатылым", c["sales"])]
        grid += (f'<a class="pc{" best" if best is c and c["rev"] else ""}" href="{html.escape(m.get("permalink") or "#")}" target="_blank" rel="noopener">'
                 f'<div class="pi">{f"<img src={chr(34)}{html.escape(pic)}{chr(34)} loading=lazy referrerpolicy=no-referrer alt={chr(34)}{chr(34)}>" if pic else ""}'
                 f'<span class="pk">{kind} · {m["timestamp"][8:10]}.{m["timestamp"][5:7]}</span>'
                 f'<span class="pr">{n(c["rev"]) + " ₸" if c["rev"] else "—"}</span></div>'
                 f'<div class="pf">{"".join(f"<span><b>{n(v)}</b>{t}</span>" for t, v in steps)}</div></a>')
    note = (f'<p class="note">{pending} лидтің amoCRM-дегі сатылымы әлі тексерілмеген — бетті қайта ашқанда толығады.</p>' if pending else "")
    best_txt = (f'Ең көп ақша әкелген: <b>{html.escape((best["m"].get("caption") or "пост")[:60])}</b> — {n(best["rev"])} ₸, {best["sales"]} сатылым'
                if best and best["rev"] else "Әзірге сатылымға жеткен пост табылмады")
    css = ("<style>.cg{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px;margin-top:16px}"
           ".pc{display:block;border-radius:18px;overflow:hidden;background:var(--surface);box-shadow:var(--shadow);color:var(--text);transition:transform .15s}.pc:hover{transform:translateY(-3px)}"
           ".pc.best{box-shadow:0 0 0 3px #fec200,var(--shadow)}.pi{position:relative;aspect-ratio:4/5;background:var(--surface2)}.pi img{width:100%;height:100%;object-fit:cover;display:block}"
           ".pk{position:absolute;left:8px;top:8px;padding:3px 8px;border-radius:8px;background:rgba(14,11,26,.6);color:#fff;font-size:0.6875rem;font-weight:700}"
           ".pr{position:absolute;right:8px;bottom:8px;padding:6px 10px;border-radius:10px;background:#fec200;color:#2F0E51;font-weight:900;font-size:0.9375rem}"
           ".pf{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:10px}.pf span{display:grid;font-size:0.6875rem;color:var(--faint);text-align:center}.pf b{font-size:0.875rem;color:var(--text)}</style>")
    segs = "".join(f'<a class="seg{" on" if d == days else ""}" href="?days={d}">{d} күн</a>' for d in (7, 30, 90))
    label = f"{days} күн" if days else ui.dr_label(first, last, today)
    content_bento = content_widgets(cards, best, total_rev, label)
    span_txt = f"соңғы {days} күн" if days else label
    prev_href = f"?d1={first - timedelta(days=n_days):%Y-%m-%d}&d2={first - timedelta(days=1):%Y-%m-%d}"
    next_href = f"?d1={last + timedelta(days=1):%Y-%m-%d}&d2={min(last + timedelta(days=n_days), today):%Y-%m-%d}" if last < today else None
    picker = ui.date_range(first, last, today, prev_href, next_href, "?d1=@&d2=@")
    return HTMLResponse(admin.page("Контент · EduApp", f"""<main class="wrap">{css}
<section class="ph cardin"><div><h1>Контент → ақша</h1><p>Әр пост: қаралым → коммент → кілт сөз → Direct → лид → сатылым → ₸ ({span_txt})</p>
<div class="stats"><span>{len(cards)} пост</span><span>сатылым: {n(total_rev)} ₸</span></div></div></section>
<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between"><nav class="segs" style="display:inline-flex">{segs}</nav>{picker}</div>{content_bento}<p class="note">{best_txt}. Сатылым посттың комментаторларының телефоны amoCRM-дегі сделкамен сәйкес келгенде есептеледі (шамамен).</p>{note}
<div class="cg">{grid or "<p>Бұл кезеңде пост жоқ</p>"}</div></main>""", user, "content"), headers={"Cache-Control": "no-store"})


def content_widgets(cards: list, best, total_rev: int, label: str) -> str:
    """Bento row for the content page: views per post (monolith columns), the whole funnel, reels vs posts, posts that brought leads."""
    if not cards:
        return ""
    import charts
    chron = sorted(cards, key=lambda c: c["m"].get("timestamp") or "")
    views = [(c["m"].get("views") or c["m"].get("reach") or 0) for c in chron]
    top = max(views + [1])
    cols = charts.cols([{"value": v, "plan": top * 1.05, "now": c is best and c["rev"] > 0,
                         "tip": f'<span>{(c["m"].get("timestamp") or "")[8:10]}.{(c["m"].get("timestamp") or "")[5:7]}</span>{charts.nf(v)} қаралым'}
                        for v, c in zip(views, chron)])
    c1 = charts.card("s5", f"Контент · {label}", charts.num(total_rev, "₸"), cols,
                     f"{len(cards)} пост · бағана — посттың қаралымы", dark=True, i=1)
    tot = lambda k: sum(c[k] for c in cards)
    steps = [("Қаралым", sum(views)), ("Коммент", sum(c["m"].get("comments_count") or 0 for c in cards)),
             ("Direct", tot("dms")), ("Лид", tot("leads")), ("Сатылым", tot("sales"))]
    c2 = charts.card("s7", "Барлық посттардың воронкасы", "", charts.funnel(steps, soft=True), "", i=2)
    reels = sum(v for v, c in zip(views, chron) if c["m"].get("media_product_type") == "REELS")
    c3 = charts.card("s6", "Қаралым: рилс пен пост", charts.num(round(reels / sum(views) * 100) if sum(views) else 0, "% рилс"),
                     charts.split(reels, sum(views) - reels, "Рилс", "Пост"), "", i=3)
    with_leads = sum(1 for c in cards if c["leads"])
    pct = round(with_leads / len(cards) * 100)
    c4 = charts.card("s6", "Лид әкелген посттар", "", charts.ring(pct, f'{with_leads}<span class="zc-unit">/ {len(cards)}</span>', "кемінде бір лид әкелген пост"), "", i=4)
    return (charts.CSS + "<style>.zb.cw .zbc.dark .zb-cols{max-height:200px;min-height:150px;flex:none;height:200px;margin-top:auto}"
            ".zb.cw .zf{gap:6px}.zb.cw .zf-h b{font-size:1.25rem}.zb.cw .zf-b{height:10px;margin-top:-2px}.zb.cw .zf-c{margin:0 0 0 10px;padding:2px 8px}</style>"
            + charts.bento([c1, c2, c3, c4]).replace('<section class="zb">', '<section class="zb cw">', 1) + charts.JS)


# ---------- 4.1 morning insights: three findings and one piece of advice ----------

def insights(con) -> str:
    """Plain-rule analysis of yesterday (no AI key needed): leads vs the week, posts, best post, sales, waiting chats."""
    today = igdata.today()
    y0, y1 = int((today - timedelta(days=1)).timestamp()), int(today.timestamp())
    week = amo.daily(con, int((today - timedelta(days=8)).timestamp()), 7)
    avg = sum(d["leads"] for d in week) / 7 if week else 0
    yd = amo.numbers(con, y0, y1)
    out = []
    if avg:
        ch = round((yd["leads"] - avg) / avg * 100)
        out.append(f"Кеше {yd['leads']} лид — апталық орташадан {'+' if ch >= 0 else ''}{ch}% ({round(avg)}).")
    best = con.execute("select detail, count(distinct igsid) n from events where event = 'comment' and ts >= ? and detail is not null"
                       " group by detail order by n desc limit 1", (int((today - timedelta(days=7)).timestamp()),)).fetchone()
    rules = {r["media_id"]: r for r in _site_settings()["rules"]}
    if best:
        cap = (rules.get(best[0]) or {}).get("caption") or "бір пост"
        out.append(f"Аптаның ең белсенді посты: «{cap[:50]}» — {best[1]} адам кілт сөз жазды.")
    out.append(f"Кеше {yd['sales']} сатылым, " + f"{yd['amount']:,} ₸.".replace(",", " "))
    advice = ("Бүгін кілт сөзі бар есеп-рилс жариялаңыз: мұндай посттар ең көп лид әкеледі." if avg and yd["leads"] < avg
              else "Қарқын жақсы — табысты посттың форматын қайталаңыз.")
    if _speed.get("data") and _speed["data"].get("waiting_count"):
        advice = f"Direct-те {_speed['data']['waiting_count']} адам 1 сағаттан көп жауап күтіп тұр — алдымен соларға жауап беріңіз. " + advice
    return "*Талдау:*\n" + "\n".join("• " + x for x in out[:3]) + "\n💡 " + advice


@app.post("/bot/texts")
async def bot_texts(request: Request):
    """Admin edits the bot's texts on the Bot page; the bot uses them within 20 seconds."""
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    base = _load("texts.yml", lambda p: yaml.safe_load(p.read_text(encoding="utf-8")))
    new = {}
    for k in EDITABLE:
        v = (f.get(k) or "").replace("\r\n", "\n").strip()
        if k == "welcome_text" and not v:
            continue  # the welcome text may not be emptied by accident
        if v != str(base.get(k) or "").strip():
            new[k] = v
    with db() as con:
        amo.kv_set(con, "texts", new)
    _tx_cache["at"] = 0
    return RedirectResponse("/bot?ok=" + quote("Мәтіндер сақталды") + "#texts", status_code=303)


@app.post("/bot/rules")
async def bot_rules(request: Request):
    """Admin adds or removes a post with its own texts (comment reply + Direct text)."""
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    with db() as con:
        rules = amo.kv_get(con, "post_rules", []) or []
        if f.get("action") == "delete":
            rules = [r for r in rules if r.get("media_id") != f.get("media_id")]
            msg = "Өшірілді"
        else:
            link = (f.get("link") or "").strip()
            code = next((x for x in link.split("/") if len(x) >= 8 and x not in ("www.instagram.com", "instagram.com")), "")
            r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink,caption", "limit": 50})
            media = next((m for m in r.json().get("data", []) if code and code in (m.get("permalink") or "")), None)
            if not media:
                return RedirectResponse("/bot?ok=" + quote("Пост табылмады: сілтемені тексеріңіз") + "#rules", status_code=303)
            rules = [x for x in rules if x.get("media_id") != media["id"]] + [{
                "media_id": media["id"], "link": media.get("permalink"), "caption": (media.get("caption") or "")[:80],
                "keyword": (f.get("keyword") or "").strip(),
                "reply": (f.get("reply") or "").replace("\r\n", "\n").strip(), "dm": (f.get("dm") or "").replace("\r\n", "\n").strip()}]
            msg = "Пост ережесі сақталды"
        amo.kv_set(con, "post_rules", rules)
    _tx_cache["at"] = 0
    return RedirectResponse("/bot?ok=" + quote(msg) + "#rules", status_code=303)


@app.get("/api/igbot/ig-probe")
async def ig_probe(request: Request, metric: str = "follows_and_unfollows", days_back: int = 3, breakdown: str = "follow_type"):
    """Diagnostics: ask Instagram for one account metric of one past day (to see what history it keeps)."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    day = igdata.today() - timedelta(days=days_back)
    params = {"metric": metric, "period": "day", "metric_type": "total_value",
              "since": int(day.timestamp()), "until": int((day + timedelta(days=1)).timestamp())}
    if breakdown:
        params["breakdown"] = breakdown
    r = await http.get(f"{API}/me/insights", headers=auth(), params=params)
    return {"day": igdata.key(day), "status": r.status_code, "body": r.json()}


@app.get("/api/igbot/media-comments")
async def media_comments(request: Request, code: str | None = None, limit: int = 12):
    """Diagnostics: recent posts (id, link, caption start, comment count); with ?code=<shortcode> also that post's
    comments with whether we already replied and whether the person already got the welcome text."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink,caption,comments_count,timestamp", "limit": limit})
    media = [{"id": m["id"], "link": m.get("permalink"), "caption": (m.get("caption") or "")[:70], "comments": m.get("comments_count"),
              "time": m.get("timestamp")} for m in r.json().get("data", [])]
    out = {"media": media}
    target = next((m for m in media if code and code in (m["link"] or "")), None)
    if target:
        items, after = [], None
        with db() as con:
            greeted = {x[0] for x in con.execute("select igsid from leads")}
        for _ in range(10):
            params = {"fields": "id,text,timestamp,from,username,replies", "limit": 50}
            if after:
                params["after"] = after
            c = await http.get(f"{API}/{target['id']}/comments", headers=auth(), params=params)
            j = c.json()
            for cm in j.get("data", []):
                who = cm.get("from") or {}
                items.append({"id": cm["id"], "user": who.get("username") or cm.get("username"), "uid": who.get("id"), "text": cm.get("text"),
                              "replied": bool((cm.get("replies") or {}).get("data")), "greeted": who.get("id") in greeted, "time": cm.get("timestamp")})
            after = ((j.get("paging") or {}).get("cursors") or {}).get("after") if (j.get("paging") or {}).get("next") else None
            if not after:
                break
        out["post"] = target
        out["comments"] = items
    return out


async def post_comments(media_id: str) -> list:
    out, after = [], None
    for _ in range(10):
        params = {"fields": "id,text,timestamp,from,username,replies", "limit": 50}
        if after:
            params["after"] = after
        j = (await http.get(f"{API}/{media_id}/comments", headers=auth(), params=params)).json()
        out += j.get("data", [])
        after = ((j.get("paging") or {}).get("cursors") or {}).get("after") if (j.get("paging") or {}).get("next") else None
        if not after:
            break
    return out


@app.get("/api/igbot/post-dm")
async def post_dm(request: Request, code: str, send: str | None = None):
    """Send a post's own Direct text (its rule) to every person who commented on it and has not had it yet,
    as a private reply to their latest comment (no new public reply). Dry run by default, ?send=1 sends."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink", "limit": 30})
    media = next((m for m in r.json().get("data", []) if code in (m.get("permalink") or "")), None)
    rule = post_rule(media["id"]) if media else None
    if not rule:
        return {"error": "post or its rule not found"}
    with db() as con:
        done = {x[0] for x in con.execute("select igsid from events where event = 'rule_dm' and detail = ?", (media["id"],))}
    latest = {}
    for c in await post_comments(media["id"]):
        who = c.get("from") or {}
        if not who.get("id") or who["id"] == ME.get("id") or c.get("username") == ME.get("username") or who["id"] in done:
            continue
        if not post_rule(media["id"], c.get("text") or ""):
            continue  # the rule has a keyword and this comment does not contain it
        if who["id"] not in latest or (c.get("timestamp") or "") > (latest[who["id"]].get("timestamp") or ""):
            latest[who["id"]] = c
    if not send:
        return {"people": len(latest), "already_sent": len(done)}
    if send == "queue":
        with db() as con:
            q = amo.kv_get(con, "dm_queue", []) or []
            have = {x["uid"] for x in q}
            q += [{"uid": uid, "cid": c["id"], "media": media["id"]} for uid, c in latest.items() if uid not in have]
            amo.kv_set(con, "dm_queue", q)
        return {"queued": len(q)}
    sent = failed = 0
    errors = []
    started = time.time()
    for uid, c in latest.items():
        if time.time() - started > 200 or (failed > 5 and not sent and send != "all"):
            break
        pr = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": {"comment_id": c["id"]}, "message": {"text": rule["dm"]}})
        if pr.status_code < 400:
            track(uid, "rule_dm", None, media["id"])
            sent += 1
        else:
            track(uid, "rule_dm_fail", None, media["id"])  # e.g. that comment already had its one private reply
            failed += 1
            errors.append(pr.text[:200])
        await asyncio.sleep(1.5)
    return {"sent": sent, "failed": failed, "left": len(latest) - sent - failed, "errors": sorted(set(errors))[:3]}


@app.get("/api/igbot/post-reply")
async def post_reply(request: Request, code: str, send: str | None = None, limit: int = 0):
    """Answer every comment on one post that nobody answered yet (any text, also quiz answers): the public reply
    and, for people who never got it, the welcome text in Direct. Skips our own comments and people a manager
    already answered by @mention."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink", "limit": 30})
    media = next((m for m in r.json().get("data", []) if code in (m.get("permalink") or "")), None)
    if not media:
        return {"error": "post not found"}
    allc = await post_comments(media["id"])
    mine = [c for c in allc if (c.get("from") or {}).get("id") == ME.get("id") or c.get("username") == ME.get("username")]
    mentioned = {w[1:].lower().rstrip(".,!") for c in mine for w in (c.get("text") or "").split() if w.startswith("@")}
    todo, seen = [], set()
    for c in allc:
        who = c.get("from") or {}
        name = (who.get("username") or c.get("username") or "").lower()
        if c in mine or not who.get("id") or (c.get("replies") or {}).get("data") or name in mentioned or who["id"] in seen:
            continue
        seen.add(who["id"])
        todo.append({"id": c["id"], "from": who, "media": {"id": media["id"]}, "text": c.get("text") or ""})
    if not send:
        return {"post": media.get("permalink"), "comments": len(allc), "to_answer": len(todo), "texts": [t["text"][:40] for t in todo]}
    done = 0
    for c in todo[:limit] if limit > 0 else todo:  # limit: answer a few per call, so a script can pace them
        if pr_blocked():
            return {"answered": done, "left": len(todo) - done, "blocked": True}
        await on_comment(c, backlog=True, force=True)
        done += 1
        await asyncio.sleep(2)
    return {"answered": done, "left": len(todo) - done}


@app.post("/api/igbot/post-text-reply")
async def post_text_reply(request: Request):
    """Public reply with one given text (no Direct) to every unanswered comment on one post, one per person
    (their latest comment). JSON: code, text, user (only this username), send (false = dry run)."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    body = await request.json()
    code, text, only = body.get("code") or "", (body.get("text") or "").strip(), (body.get("user") or "").lower().lstrip("@")
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink", "limit": 30})
    media = next((m for m in r.json().get("data", []) if code and code in (m.get("permalink") or "")), None)
    if not media or not text:
        return {"error": "post or text missing"}
    allc = await post_comments(media["id"])
    mine = [c for c in allc if (c.get("from") or {}).get("id") == ME.get("id") or c.get("username") == ME.get("username")]
    mentioned = {w[1:].lower().rstrip(".,!") for c in mine for w in (c.get("text") or "").split() if w.startswith("@")}
    answered = {(c.get("from") or {}).get("id") for c in allc if (c.get("replies") or {}).get("data")}
    latest = {}
    for c in allc:
        who = c.get("from") or {}
        name = (who.get("username") or c.get("username") or "").lower()
        if c in mine or not who.get("id") or who["id"] in answered or name in mentioned or (only and name != only):
            continue
        if who["id"] not in latest or (c.get("timestamp") or "") > (latest[who["id"]].get("timestamp") or ""):
            latest[who["id"]] = c
    if body.get("dm_only"):  # only people who got the text in Direct from post-text-dm
        with db() as con:
            got = {x[0] for x in con.execute("select igsid from events where event = 'text_dm' and detail = ?", (media["id"],))}
        latest = {u: c for u, c in latest.items() if u in got}
    todo = list(latest.values())
    if not body.get("send"):
        return {"post": media.get("permalink"), "comments": len(allc), "to_answer": len(todo),
                "users": [(c.get("from") or {}).get("username") or c.get("username") for c in todo]}
    sent, failed, errors, started = 0, 0, [], time.time()
    for c in todo:
        if time.time() - started > 240:
            break
        pr = await http.post(f"{API}/{c['id']}/replies", headers=auth(), params={"message": text})
        if pr.status_code < 400:
            track((c.get("from") or {})["id"], "text_reply", None, media["id"])
            sent += 1
        else:
            failed += 1
            errors.append(pr.text[:200])
            if failed >= 3 and not sent:
                break
        await asyncio.sleep(4)
    return {"sent": sent, "failed": failed, "left": len(todo) - sent - failed, "errors": sorted(set(errors))[:3]}


@app.post("/api/igbot/dm-audit")
async def dm_audit(request: Request):
    """Open the Direct chat of every commenter on one post and sort them: got the webinar link, got the
    «link in stories» text, or got nothing from us. Resumable (kv dmaudit:<media>); JSON: code, reset."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    body = await request.json()
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink", "limit": 30})
    media = next((m for m in r.json().get("data", []) if body.get("code") and body["code"] in (m.get("permalink") or "")), None)
    if not media:
        return {"error": "post not found"}
    people = {}
    for c in await post_comments(media["id"]):
        who = c.get("from") or {}
        if who.get("id") and who["id"] != ME.get("id") and c.get("username") != ME.get("username"):
            people[who["id"]] = who.get("username") or c.get("username") or ""
    key = f"dmaudit:{media['id']}"
    with db() as con:
        res = {} if body.get("reset") else (amo.kv_get(con, key, {}) or {})
    started = time.time()
    for uid in people:
        if uid in res and res[uid] != "error":
            continue
        if time.time() - started > 230:
            break
        cr = await http.get(f"{API}/me/conversations", headers=auth(),
                            params={"platform": "instagram", "user_id": uid, "fields": "messages.limit(100){from,message}"})
        if cr.status_code != 200:
            res[uid] = "error"
            continue
        ours = [m.get("message") or "" for cv in cr.json().get("data", []) for m in (cv.get("messages") or {}).get("data", [])
                if (m.get("from") or {}).get("id") == ME.get("id") or (m.get("from") or {}).get("username") == ME.get("username")]
        res[uid] = ("link" if any("webinar.eduapp.example.com" in t for t in ours) else
                    "story_text" if any("стористегі сілтеме" in t for t in ours) else
                    "other" if ours else "nothing")
        await asyncio.sleep(0.3)
    with db() as con:
        amo.kv_set(con, key, res)
    counts = {}
    for uid in people:
        k = res.get(uid, "unchecked")
        counts[k] = counts.get(k, 0) + 1
    return {"post": media.get("permalink"), "people": len(people), "counts": counts,
            "nothing": sorted(people[u] for u in people if res.get(u) == "nothing"),
            "other": sorted(people[u] for u in people if res.get(u) == "other")}


@app.post("/api/igbot/wa-link")
async def wa_link_set(request: Request):
    """Set the WhatsApp group invite link the second button opens (JSON: link; empty = send the webinar text instead)."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    link = ((await request.json()).get("link") or "").strip()
    if link and not link.startswith("https://"):
        return {"error": "link must start with https://"}
    await ensure_ready()
    with db() as con:
        amo.kv_set(con, "wa_link", link)
    return {"wa_link": link}


@app.post("/api/igbot/dm-webinar")
async def dm_webinar(request: Request):
    """People who wrote in Direct in the last 24 h ABOUT THE WEBINAR (сақа, вебинар, сілтеме…) and never got the link
    or the button. Dry run lists them with their words; send=N sends the button to N of them (one call, slow)."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    body = await request.json()
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    me_ids = {ME.get("id"), ME.get("username")}
    cutoff = time.time() - 23 * 3600  # a little inside Meta's 24 h window
    found, skipped, after = [], {"other_topic": 0, "has_link": 0, "old": 0}, None

    def ts(m):
        return datetime.strptime(m["created_time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    with db() as con:
        done = {r[0] for r in con.execute("select distinct igsid from events where event in ('kw_btn', 'link_sent')")}
    for _ in range(6):
        params = {"platform": "instagram", "limit": 50, "fields": "updated_time,participants,messages.limit(25){from,message,created_time}"}
        if after:
            params["after"] = after
        r = await http.get(f"{API}/me/conversations", headers=auth(), params=params)
        if r.status_code != 200:
            break
        j = r.json()
        stop = False
        for cv in j.get("data", []):
            msgs = (cv.get("messages") or {}).get("data", [])
            theirs = [m for m in msgs if (m.get("from") or {}).get("id") not in me_ids and (m.get("from") or {}).get("username") not in me_ids]
            ours = [m for m in msgs if m not in theirs]
            if not theirs:
                continue
            if max(ts(m) for m in theirs) < cutoff:
                skipped["old"] += 1
                if cv.get("updated_time") and datetime.strptime(cv["updated_time"][:19], "%Y-%m-%dT%H:%M:%S").replace(
                        tzinfo=timezone.utc).timestamp() < cutoff:
                    stop = True  # the list is newest first: older chats are outside the window
                continue
            who = theirs[0]["from"]
            if who.get("id") in done or any("webinar.eduapp.example.com" in (m.get("message") or "") or KW_BTN_TEXT[:20] in (m.get("message") or "")
                                            for m in ours):
                skipped["has_link"] += 1
                continue
            words = " / ".join((m.get("message") or "")[:60] for m in theirs[:3] if m.get("message"))
            if not about_webinar(" ".join(m.get("message") or "" for m in theirs)):
                skipped["other_topic"] += 1
                continue
            found.append({"uid": who["id"], "user": who.get("username"), "said": words})
        after = ((j.get("paging") or {}).get("cursors") or {}).get("after") if (j.get("paging") or {}).get("next") else None
        if stop or not after:
            break
    n = int(body.get("send") or 0)
    if not n:
        return {"to_send": len(found), "skipped": skipped, "people": [{"user": x["user"], "said": x["said"]} for x in found]}
    sent, failed = 0, 0
    for x in found[:n]:
        if pr_blocked():
            break
        res = await kw_send({"uid": x["uid"], "who": x["uid"]})
        sent += res == "ok"
        failed += res != "ok"
        if res == "limit":
            break
        await asyncio.sleep(KW_GAP)
    return {"sent": sent, "failed": failed, "left": len(found) - sent - failed, "blocked": pr_blocked()}


@app.get("/api/igbot/user-events")
async def user_events(request: Request, user: str):
    """Diagnostics: the last events of one @username, plus the button queue."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    with db() as con:
        row = con.execute("select igsid from profiles where lower(username) = ?", (user.lower().lstrip("@"),)).fetchone()
        ev = [(datetime.fromtimestamp(t, igdata.TZ).strftime("%d.%m %H:%M:%S"), e, d) for t, e, d in con.execute(
            "select ts, event, detail from events where igsid = ? order by ts desc limit 15", (row[0],))] if row else []
        return {"events": ev, "kw_queue": len(amo.kv_get(con, "kw_queue", []) or []), "blocked": pr_blocked(), "kw_mode": kw_on()}


@app.get("/api/igbot/ask-test")
async def ask_test(request: Request, q: str = "Өткен аптада қанша сатылым болды?"):
    """Diagnostics: one question to the AI analyst, to check that the key works."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    if request.query_params.get("models"):
        r = await http.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": ask.gemini_key()},
                           params={"pageSize": 100})
        return {"status": r.status_code, "models": [m["name"] for m in r.json().get("models", [])
                                                    if "generateContent" in (m.get("supportedGenerationMethods") or [])], "err": r.text[:200] if r.status_code != 200 else ""}
    await ensure_ready()
    with db() as con:
        ans = await ask.answer(http, API, auth(), con, q)
        return {"gemini": bool(ask.gemini_key()), "answer": ans, "info": ask.LAST_ERROR}


@app.get("/api/igbot/ping-db")
async def ping_db(request: Request):
    """Diagnostics: how long one database round trip takes from this function."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    out = []
    with db() as con:
        for _ in range(8):
            t = time.perf_counter()
            con.execute("select 1").fetchone()
            out.append(round((time.perf_counter() - t) * 1000, 1))
    return {"ms": out, "region": os.getenv("VERCEL_REGION")}


@app.post("/api/igbot/btn-test")
async def btn_test(request: Request):
    """Send the «Сілтемені алу» button to one person who wrote to us in Direct (JSON: user), or with
    cid as a private reply to their comment — to see that Instagram accepts it."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    body = await request.json()
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    if body.get("cid"):
        r = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": {"comment_id": body["cid"]}, "message": button_msg(bool(body.get("wa")))})
        return {"status": r.status_code, "body": r.text[:300]}
    name = (body.get("user") or "").lower().lstrip("@")
    with db() as con:
        row = con.execute("select igsid from profiles where lower(username) = ?", (name,)).fetchone()
    uid = row[0] if row else None
    if not uid:  # not in our profiles yet: look in the recent Direct chats
        r = await http.get(f"{API}/me/conversations", headers=auth(), params={"platform": "instagram", "limit": 25,
                                                                               "fields": "participants"})
        for cv in r.json().get("data", []):
            for p in (cv.get("participants") or {}).get("data", []):
                if (p.get("username") or "").lower() == name:
                    uid = p["id"]
    if not uid:
        return {"error": "user not found"}
    if body.get("forget"):  # let a tester get the button again from a new comment
        with db() as con:
            con.execute("delete from events where igsid = ? and event in ('kw_btn', 'link_sent')", (uid,))
        return {"forgot": uid[-4:]}
    r = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": {"id": uid}, "message": button_msg(bool(body.get("wa")))})
    return {"status": r.status_code, "body": r.text[:300], "uid_end": uid[-4:]}


@app.get("/api/igbot/kw")
async def kw_switch(request: Request, on: str | None = None):
    """Keyword mode switch (same as the button on the Bot page): ?on=1 / ?on=0, without it just the state."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    with db() as con:
        if on is not None:
            amo.kv_set(con, "kw_mode", on == "1")
        q = amo.kv_get(con, "dm_queue", []) or []
        by = {}
        for x in q:
            by[x.get("media")] = by.get(x.get("media"), 0) + 1
        return {"kw_mode": bool(amo.kv_get(con, "kw_mode")), "bot": bot_on(), "queue": len(q),
                "queue_by_post": {m: {"n": n, "keyword": (post_rule(m) or {}).get("keyword"), "dm": ((post_rule(m) or {}).get("dm") or "")[:120]}
                                  for m, n in by.items()}}


@app.post("/api/igbot/solo-rule")
async def solo_rule_set(request: Request):
    """One post answers comments by itself while the bot is off. JSON: find (caption text or link code) or media_id;
    reply, dm, keyword; only (usernames: test; [] = everyone); off=true removes the post's solo mark.
    Without find/media_id it only changes «only». check=true lists matching posts without saving."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    b = json.loads(await request.body() or b"{}")
    out = {}
    if b.get("find") or b.get("media_id"):
        r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink,caption,timestamp", "limit": 50})
        found = [m for m in r.json().get("data", []) if m.get("id") == b.get("media_id")
                 or (b.get("find") and (b["find"] in (m.get("caption") or "") or b["find"] in (m.get("permalink") or "")))]
        out["matches"] = [{"id": m["id"], "link": m.get("permalink"), "time": m.get("timestamp"), "caption": (m.get("caption") or "")[:80]} for m in found]
        if b.get("check"):
            return out
        if len(found) != 1:
            return JSONResponse({**out, "error": "need exactly one post"}, status_code=400)
        m = found[0]
        with db() as con:
            rules = [x for x in (amo.kv_get(con, "post_rules", []) or []) if x.get("media_id") != m["id"]]
            if not b.get("off"):
                rules.append({"media_id": m["id"], "link": m.get("permalink"), "caption": (m.get("caption") or "")[:80],
                              "keyword": (b.get("keyword") or "").strip(), "reply": (b.get("reply") or "").strip(),
                              "dm": (b.get("dm") or "").strip(), "solo": True})
            amo.kv_set(con, "post_rules", rules)
    with db() as con:
        if "only" in b:
            amo.kv_set(con, "solo_only", [u.strip().lstrip("@").lower() for u in b["only"] if u.strip()])
        out["rules"] = [{k: x.get(k) for k in ("media_id", "link", "keyword", "solo")} for x in amo.kv_get(con, "post_rules", []) or []]
        out["only"] = amo.kv_get(con, "solo_only", []) or []
        out["bot"], out["kw"] = bot_on(), kw_on()
        out["pr_blocked"] = (amo.kv_get(con, "pr_block_until", 0) or 0) > time.time()
    _tx_cache["at"] = 0
    return out


@app.post("/api/igbot/post-text-dm")
async def post_text_dm(request: Request):
    """Direct (private reply to their latest comment) with one given text to every commenter on one post who never
    got the post's link (no rule_dm) nor this text before. JSON: code, text, user (only this username), send."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    body = await request.json()
    code, text, only = body.get("code") or "", (body.get("text") or "").strip(), (body.get("user") or "").lower().lstrip("@")
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,permalink", "limit": 30})
    media = next((m for m in r.json().get("data", []) if code and code in (m.get("permalink") or "")), None)
    if not media or not text:
        return {"error": "post or text missing"}
    with db() as con:
        done = {x[0] for x in con.execute("select igsid from events where event in ('rule_dm', 'text_dm', 'text_reply') and detail = ?", (media["id"],))}
    latest = {}
    for c in await post_comments(media["id"]):
        who = c.get("from") or {}
        name = (who.get("username") or c.get("username") or "").lower()
        if not who.get("id") or who["id"] == ME.get("id") or c.get("username") == ME.get("username") or who["id"] in done:
            continue
        if only and name != only:
            continue
        if who["id"] not in latest or (c.get("timestamp") or "") > (latest[who["id"]].get("timestamp") or ""):
            latest[who["id"]] = c
    if body.get("queue_only"):  # only the people waiting in the Direct queue for this post
        with db() as con:
            qs = {x["uid"] for x in amo.kv_get(con, "dm_queue", []) or [] if x.get("media") == media["id"]}
        latest = {u: c for u, c in latest.items() if u in qs}
    if body.get("check"):
        # open each person's Direct chat and see whether the webinar link was ever sent there; results kept in kv
        key = f"linkcheck:{media['id']}"
        with db() as con:
            seen = amo.kv_get(con, key, {}) or {}
        started = time.time()
        for uid in latest:
            if uid in seen:
                continue
            if time.time() - started > 230:
                break
            cr = await http.get(f"{API}/me/conversations", headers=auth(),
                                params={"platform": "instagram", "user_id": uid, "fields": "messages.limit(100){from,message}"})
            if cr.status_code != 200:
                continue
            msgs = [m for cv in cr.json().get("data", []) for m in (cv.get("messages") or {}).get("data", [])]
            seen[uid] = any("webinar.eduapp.example.com" in (m.get("message") or "") for m in msgs)
            await asyncio.sleep(0.3)
        with db() as con:
            amo.kv_set(con, key, seen)
        return {"checked": len(seen), "have_link": sum(1 for v in seen.values() if v),
                "no_link": sum(1 for u in latest if seen.get(u) is False), "left_to_check": sum(1 for u in latest if u not in seen)}
    if body.get("only_checked"):
        with db() as con:
            seen = amo.kv_get(con, f"linkcheck:{media['id']}", {}) or {}
        latest = {u: c for u, c in latest.items() if seen.get(u) is False}
    if not body.get("send"):
        return {"people": len(latest), "already": len(done),
                "users": [(c.get("from") or {}).get("username") or c.get("username") for c in latest.values()][:60]}
    sent, failed, errors, started, ok = 0, 0, [], time.time(), []
    for uid, c in latest.items():
        if time.time() - started > 240:
            break
        pr = await http.post(f"{API}/me/messages", headers=auth(), json={"recipient": {"comment_id": c["id"]}, "message": {"text": text}})
        if pr.status_code < 400:
            track(uid, "text_dm", None, media["id"])
            ok.append(uid)
            sent += 1
        else:
            failed += 1
            errors.append(pr.text[:200])
            if "limit how often" in pr.text or (failed >= 3 and not sent):
                break
        await asyncio.sleep(5)
    if ok:
        with db() as con:
            q = amo.kv_get(con, "dm_queue", []) or []
            amo.kv_set(con, "dm_queue", [x for x in q if x.get("uid") not in set(ok)])
    return {"sent": sent, "failed": failed, "left": len(latest) - sent - failed, "errors": sorted(set(errors))[:3]}


@app.get("/api/igbot/emergency")
async def emergency(request: Request, d: str, pipes: str = ""):
    """Report numbers straight from amoCRM and Instagram, without the database (for when it is down)."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    day = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=igdata.TZ)
    a, b = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    m0 = int(day.replace(day=1).timestamp())
    st = {"source_field": "1000001", "sources": ["Таргетированная реклама в Инстаграм или Фейсбук", "Органика Instagram"],
          "pipelines": [int(x) for x in pipes.split(",") if x]}

    async def deals(kind, since, until):
        out = []
        for page in range(1, 60):
            r = await http.get(f"{amo.base()}/leads", headers=amo.headers(), timeout=30, params={
                f"filter[{kind}][from]": since, f"filter[{kind}][to]": until - 1, "limit": 250, "page": page})
            if r.status_code != 200:
                break
            got = (r.json().get("_embedded") or {}).get("leads", [])
            out += got
            if len(got) < 250:
                break
            await asyncio.sleep(0.6)
        return out

    def mkt(dl):
        cf = {str(f["field_id"]): [str(v.get("value")) for v in f.get("values") or []] for f in dl.get("custom_fields_values") or []}
        return amo._is_marketing(json.dumps(cf, ensure_ascii=False), dl.get("pipeline_id"), st)

    created = [x for x in await deals("created_at", a, b) if mkt(x)]
    closed_m = [x for x in await deals("closed_at", m0, b) if mkt(x) and x.get("status_id") == amo.WON]
    won_day = [x for x in closed_m if a <= (x.get("closed_at") or 0) < b]
    tok = {"Authorization": f"Bearer {IG_TOKEN}"}
    ins = await igdata._day_from_api(http, API, tok, day)
    prof = await igdata.profile(http, API, tok)
    fu = (await http.get(f"{API}/me/insights", headers=tok, params={
        "metric": "follows_and_unfollows", "period": "day", "metric_type": "total_value", "breakdown": "follow_type",
        "since": a, "until": b})).json()
    md = (await http.get(f"{API}/me/media", headers=tok, params={"fields": "timestamp", "limit": 25})).json().get("data", [])
    posts = sum(1 for x in md if a <= datetime.strptime(x["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() < b)
    return {"fu": fu.get("data"), "posts": posts, "day": d, "leads": len(created), "sales": len(won_day), "amount": sum(x.get("price") or 0 for x in won_day),
            "month_amount": sum(x.get("price") or 0 for x in closed_m), "month_sales": len(closed_m), "ig": ins,
            "followers": prof.get("followers_count"), "ig_ok": bool(prof)}


@app.get("/api/igbot/dm-backlog")
async def dm_backlog(request: Request, send: str | None = None):
    """Direct chats nobody answered (no message from us at all) whose last message is inside Meta's 24 h window:
    found from Instagram's own conversation list, since the database was down. Dry run by default, ?send=1 sends."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    me_ids = {ME.get("id"), ME.get("username")}
    todo, after, seen, recent, answered = [], None, 0, 0, 0
    for _ in range(6):
        params = {"platform": "instagram", "limit": 50, "fields": "participants,updated_time,messages.limit(25){from,created_time}"}
        if after:
            params["after"] = after
        r = await http.get(f"{API}/me/conversations", headers=auth(), params=params)
        if r.status_code != 200:
            return {"error": r.text[:300]}
        j = r.json()
        for conv in j.get("data", []):
            seen += 1
            msgs = (conv.get("messages") or {}).get("data", [])
            ours = [m for m in msgs if (m.get("from") or {}).get("id") in me_ids or (m.get("from") or {}).get("username") in me_ids]
            theirs = [m for m in msgs if m not in ours]
            if theirs:
                lt = max(datetime.strptime(m["created_time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() for m in theirs)
                if time.time() - lt < FOLLOWUP_WINDOW:
                    recent += 1
                    answered += bool(ours)
            if ours or not theirs:
                continue
            last = max(datetime.strptime(m["created_time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() for m in theirs)
            if time.time() - last < FOLLOWUP_WINDOW:
                who = theirs[0]["from"]
                todo.append({"id": who.get("id"), "user": who.get("username")})
        after = ((j.get("paging") or {}).get("cursors") or {}).get("after") if (j.get("paging") or {}).get("next") else None
        if not after:
            break
    if not send:
        return {"chats_checked": seen, "wrote_last_24h": recent, "of_them_answered": answered, "unanswered": len(todo),
                "users": [t["user"] for t in todo]}
    sent = failed = 0
    started = time.time()
    for t in todo:
        if time.time() - started > 200:
            break
        with db() as con:
            if leads.get_lead(con, t["id"]):
                continue
        ok = await send_welcome(t["id"], None)
        sent += ok
        failed += not ok
        if failed >= 3 and not sent:
            break
        await asyncio.sleep(2)
    return {"sent": sent, "failed": failed, "of": len(todo)}


@app.get("/api/igbot/old-db")
async def old_db(request: Request, copy: str | None = None):
    """The old Neon database (DATABASE_URL): can we reach it, how much is there, and ?copy=1 brings its history over
    (bot events, leads, profiles, staff, saved reports, Telegram settings) without overwriting newer rows."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    import psycopg
    import store
    url = store._clean(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "")
    try:
        old = psycopg.connect(url, autocommit=True, prepare_threshold=None, connect_timeout=10)
    except Exception as e:
        return {"reachable": False, "error": " | ".join(sorted({l.split("failed:")[-1].strip()[:120] for l in str(e).splitlines() if "failed:" in l}))}
    tables = {"events": "ts, igsid, event, topic, detail", "leads": "*", "profiles": "*", "staff": "*", "reports": "*", "users": "*"}
    out = {"reachable": True}
    with old:
        for t in tables:
            try:
                out[t] = old.execute(f"select count(*) from {t}").fetchone()[0]
            except Exception as e:
                out[t] = str(e)[:80]
        if not copy:
            return out
        copied = {}
        with db() as con:
            history.ensure_table(con)
            leads.ensure_table(con)
            staffauth.ensure_table(con)
            # events: only the ones from before the new database started (no duplicates with new rows)
            first_new = con.execute("select min(ts) from events").fetchone()[0] or int(time.time())
            rows = old.execute("select ts, igsid, event, topic, detail from events where ts < %s", (first_new,)).fetchall()
            if rows:
                con.executemany("insert into events values (?, ?, ?, ?, ?)", rows)
            copied["events"] = len(rows)
            for t, key in (("leads", "igsid"), ("profiles", "igsid"), ("staff", "login"), ("reports", "day"), ("users", "igsid")):
                try:
                    cur = old.execute(f"select * from {t}")
                    cols = [c.name for c in cur.description]
                    data = cur.fetchall()
                    if data:
                        marks = ", ".join("?" * len(cols))
                        con.executemany(f"insert into {t} ({', '.join(cols)}) values ({marks}) on conflict ({key}) do nothing", data)
                    copied[t] = len(data)
                except Exception as e:
                    copied[t] = str(e)[:120]
            for k in ("tg_chats", "tg_staff", "tg_seen", "motiv_used:aigerim", "motiv_used:dana"):
                row = old.execute("select v from kv where k = %s", (k,)).fetchone()
                if row and row[0] and not con.execute("select 1 from kv where k = ?", (k,)).fetchone():
                    con.execute("insert into kv values (?, ?, ?)", (k, row[0], int(time.time())))
                    copied[k] = "ok"
        out["copied"] = copied
    return out


@app.get("/api/igbot/db-info")
async def db_info(request: Request):
    """Diagnostics: which database is used, its marketing settings, and how many rows the main tables hold."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    import store
    out = {"db": "postgres:" + store.PG_URL.split("@")[-1].split("/")[0] if store.PG_URL else "sqlite"}
    with db() as con:
        amo.ensure_tables(con)
        out["mkt_settings"] = amo.settings(con)
        try:
            out["leads_total"], out["leads_synced"] = con.execute("select count(*), coalesce(sum(case when synced > 0 then 1 else 0 end), 0) from leads").fetchone()
            out["sheet_url_set"] = bool(SHEETS_WEBHOOK_URL)
        except Exception as e:
            out["leads_err"] = str(e)[:80]
        out["dm_queue"] = len(amo.kv_get(con, "dm_queue", []) or [])
        last = amo.kv_get(con, "dm_queue_last", 0) or 0
        out["dm_queue_last"] = datetime.fromtimestamp(last, igdata.TZ).strftime("%d.%m %H:%M:%S") if last else None
        out["rule_dm_sent"] = con.execute("select count(distinct igsid) from events where event = 'rule_dm'").fetchone()[0]
        out["rule_dm_failed"] = con.execute("select count(*) from events where event = 'rule_dm_fail'").fetchone()[0]
        for t in ("amo_deals", "events", "leads", "reports", "kv", "staff"):
            try:
                out[t] = con.execute(f"select count(*) from {t}").fetchone()[0]
            except Exception as e:
                out[t] = str(e)[:80]
    return out


@app.get("/api/igbot/tg-info")
async def tg_info(request: Request):
    """Diagnostics: is Telegram delivering button presses to us, and who is on the list."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    info = (await tg.call(http, "getWebhookInfo")).get("result") or {}
    with db() as con:
        rec, links, last = tg.recipients(con), staff_chats(con), amo.kv_get(con, "tg_sent")
    return {"last_report_day": last, "url": info.get("url"), "pending": info.get("pending_update_count"), "last_error": info.get("last_error_message"),
            "last_error_date": info.get("last_error_date"), "recipients": [c["name"] for c in rec], "linked": list(links)}


@app.get("/api/igbot/tg-test")
async def tg_test(request: Request, to: str):
    """Send yesterday's report (with the buttons) to one recipient only, by name."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    with db() as con:
        chat = next((c for c in tg.recipients(con) if c["name"] == to), None)
        if not chat:
            return {"ok": False, "error": "no such recipient"}
        text, buttons = await morning_payload(con, PUBLIC_URL, igdata.today() - timedelta(days=1))
    ok, why = await tg.send(http, chat["id"], text, buttons)
    return {"ok": ok, "error": why, "buttons": [b[0] for b in buttons]}


@app.post("/api/tg-webhook")
async def tg_webhook(request: Request):
    """Telegram: Start presses (candidates for the list) and the «мақтау / қолдау мәтіні» buttons."""
    if not tg.configured() or request.headers.get("x-telegram-bot-api-secret-token", "") != tg.secret():
        return PlainTextResponse("forbidden", status_code=403)
    upd = json.loads(await request.body() or b"{}")
    with db() as con:
        msg = upd.get("message") or {}
        if msg.get("text", "").startswith("/start"):
            tg.remember_start(con, msg.get("chat") or {})
            known = {c["id"] for c in tg.recipients(con)}
            if (msg.get("chat") or {}).get("id") not in known:
                await tg.send(http, msg["chat"]["id"], "Сәлеметсіз бе! Әкімші сізді тізімге қосқан соң, күн сайын таңғы 08:00-де есеп келеді.",
                              markdown=False)
            return {"ok": True}
        cb = upd.get("callback_query") or {}
        if not cb:
            return {"ok": True}
        chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
        await tg.call(http, "answerCallbackQuery", callback_query_id=cb.get("id"), text="Мәтін дайындалып жатыр…")
        if chat_id not in {c["id"] for c in tg.recipients(con)}:
            return {"ok": True}  # only people on the list may use the buttons
        parts = (cb.get("data") or "").split(":")
        if len(parts) != 4 or parts[0] not in ("m", "s"):
            return {"ok": True}
        kind, login, d, n = parts
        try:
            day = datetime.strptime(d, "%Y%m%d").replace(tzinfo=igdata.TZ)
            seed = int(n)
        except ValueError:
            return {"ok": True}
        person = staffauth.get_staff(con, login)
        first = (person or {}).get("name", login).split()[0]
        if kind == "s":  # send the text the director is looking at to the employee
            text = amo.kv_get(con, f"mtxt:{login}:{d}:{seed}")
            target = staff_chats(con).get(login)
            if not text:
                await tg.send(http, chat_id, "Мәтін табылмады, «Басқа нұсқа» басып, қайта жіберіңіз.", markdown=False)
            elif not target:
                await tg.send(http, chat_id, f"{first} ботқа әлі қосылмаған. Ол @{await tg.bot_name(http)} ботында Start басып, "
                                             f"әкімші сайттағы Telegram бетінде оны «{first}» деп белгілеуі керек.", markdown=False)
            elif amo.kv_get(con, f"msent:{login}:{d}:{seed}"):
                await tg.send(http, chat_id, f"Бұл мәтін {first}ға бұрын жіберілген.", markdown=False)
            else:
                ok, why = await tg.send(http, target, text, markdown=False)
                if ok:
                    amo.kv_set(con, f"msent:{login}:{d}:{seed}", int(time.time()))
                await tg.send(http, chat_id, f"{first}ға жіберілді ✓" if ok else f"Жіберілмеді: {why}", markdown=False)
            return {"ok": True}
        await ensure_ready()
        text = await motivation_for(con, login, day, seed)
    if text:
        await tg.send(http, chat_id, text, [(f"{first}ға жіберу", f"s:{login}:{d}:{seed}"),
                                            ("Басқа нұсқа", f"m:{login}:{d}:{seed + 1}")], markdown=False)
    return {"ok": True}


async def report_sample(con, tpl: str) -> str:
    """This month's report with `tpl`, from the department's numbers (what the editor previews)."""
    m = await mkt.build(http, API, auth(), con, period="month", anchor=igdata.today(), plans={}, name="")
    igx = await report_igx(con, m, igdata.today(), "month")
    return mkt.short_report(m, f"{PUBLIC_URL}/?p=month&d={igdata.key(igdata.today())}", igx, tpl)


@app.get("/report-text")
async def report_text_get(request: Request, ok: str | None = None):
    user, deny = admin_only(request)
    if deny:
        return deny
    await ensure_ready()
    with db() as con:
        tpl = mkt.report_tpl(con)
        try:
            sample = await report_sample(con, tpl)
        except Exception as e:
            sample = f"Үлгі жасалмады: {e}"
    return HTMLResponse(admin.report_text_page(tpl, mkt.REPORT_TPL, sample, mkt.REPORT_VARS, ok or "", tpl != mkt.REPORT_TPL, user),
                        headers={"Cache-Control": "no-store"})


@app.post("/report-text")
async def report_text_post(request: Request):
    """Only the owner changes the report text; «preview» shows it without saving."""
    user, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    tpl = (f.get("tpl") or "").replace(chr(13), "").strip(chr(10))[:4000]
    with db() as con:
        if f.get("do") == "reset":
            con.execute("delete from kv where k = 'report_tpl'")
            dept.log(con, user["u"], "report.reset", "есеп мәтіні")
            return RedirectResponse("/report-text?ok=" + quote("Бастапқы мәтін қайтарылды"), status_code=303)
        if f.get("do") == "save" and tpl:
            amo.kv_set(con, "report_tpl", tpl if tpl != mkt.REPORT_TPL else "")
            dept.log(con, user["u"], "report.save", "есеп мәтіні")
            return RedirectResponse("/report-text?ok=" + quote("Есеп мәтіні сақталды"), status_code=303)
        try:
            sample = await report_sample(con, tpl or mkt.REPORT_TPL)
        except Exception as e:
            sample = f"Үлгі жасалмады: {e}"
    return HTMLResponse(admin.report_text_page(tpl or mkt.REPORT_TPL, mkt.REPORT_TPL, sample, mkt.REPORT_VARS,
                                               "Бұл — алдын ала көру, әлі сақталмады", (tpl or mkt.REPORT_TPL) != mkt.REPORT_TPL, user),
                        headers={"Cache-Control": "no-store"})


@app.get("/telegram")
async def telegram_page(request: Request, ok: str | None = None, err: str | None = None):
    user, deny = admin_only(request)
    if deny:
        return deny
    await ensure_ready()
    with db() as con:
        chats = tg.recipients(con)
        try:
            sample = await morning_text(con, str(request.base_url), igdata.today() - timedelta(days=1))
        except Exception as e:
            sample = f"Үлгі жасалмады: {e}"
    cands, name = ([], "")
    if tg.configured():
        await tg.ensure_webhook(http, f"{PUBLIC_URL}/api/tg-webhook")
        with db() as con:
            cands, name = await asyncio.gather(tg.candidates(http, con), tg.bot_name(http))
    known = {c["id"] for c in chats}
    with db() as con:
        team, links = staffauth.staff(con), staff_chats(con)
        owner, db_mb = amo.kv_get(con, "tg_owner"), db_size_mb(con)
    return HTMLResponse(admin.telegram_page(tg.configured(), name, chats, [c for c in cands if c["id"] not in known],
                                            note=ok or "", err=err or "", user=session(request), sample=sample,
                                            team=team, links=links, seen=cands, owner=owner, db_mb=db_mb))


@app.post("/telegram")
async def telegram_save(request: Request):
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    action = f.get("action")
    with db() as con:
        chats = tg.recipients(con)
        if action == "add" and f.get("id"):
            cid = int(f["id"])
            if cid not in {c["id"] for c in chats}:
                chats.append({"id": cid, "name": (f.get("name") or str(cid))[:60]})
                tg.save_recipients(con, chats)
            return RedirectResponse("/telegram?ok=" + quote("Қосылды"), status_code=303)
        if action == "link" and f.get("login"):
            links = staff_chats(con)
            if f.get("id"):
                links[f["login"]] = int(f["id"])
            else:
                links.pop(f["login"], None)
            amo.kv_set(con, "tg_staff", links)
            return RedirectResponse("/telegram?ok=" + quote("Сақталды"), status_code=303)
        if action == "owner" and f.get("id"):
            amo.kv_set(con, "tg_owner", int(f["id"]))
            return RedirectResponse("/telegram?ok=" + quote("Резервтік көшірме енді осы адамға ғана келеді"), status_code=303)
        if action == "backup":
            res = await send_backup(con)
            return RedirectResponse("/telegram?" + ("ok=" + quote("Резервтік көшірме жіберілді") if res.get("ok")
                                                    else "err=" + quote("Жіберілмеді: " + str(res.get("error")))), status_code=303)
        if action == "remove" and f.get("id"):
            tg.save_recipients(con, [c for c in chats if str(c["id"]) != f["id"]])
            return RedirectResponse("/telegram?ok=" + quote("Өшірілді"), status_code=303)
        if action == "test":
            if not chats:
                return RedirectResponse("/telegram?err=" + quote("Алдымен алушы қосыңыз"), status_code=303)
            await ensure_ready()
            try:
                text, buttons = await morning_payload(con, PUBLIC_URL, igdata.today() - timedelta(days=1))
            except Exception as e:
                log.exception("morning_text")
                return RedirectResponse("/telegram?err=" + quote(f"Есеп жасалмады: {e}"[:200]), status_code=303)
            res = [await tg.send(http, c["id"], text, buttons) for c in chats]
            if all(r[0] for r in res):
                return RedirectResponse("/telegram?ok=" + quote("Кешегі есеп жіберілді"), status_code=303)
            return RedirectResponse("/telegram?err=" + quote("Жіберілмеді: " + "; ".join(r[1] for r in res if not r[0])[:200]), status_code=303)
    return RedirectResponse("/telegram", status_code=303)


@app.get("/favicon.svg")
@app.get("/favicon.ico")
async def favicon():
    return PlainTextResponse(ui_logo_svg(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/logo.png")
@app.get("/apple-touch-icon.png")
async def logo_png():
    from fastapi.responses import Response
    return Response(Path(__file__).with_name("logo.png").read_bytes(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


def ui_logo_svg() -> str:
    return Path(__file__).with_name("logo.svg").read_text(encoding="utf-8")


@app.post("/ask")
async def ask_route(request: Request):
    """Question about our numbers, answered by Claude (any logged-in member of the team)."""
    if not session(request):
        return JSONResponse({"answer": "Алдымен кіріңіз"}, status_code=401)
    body = await request.json()
    if body.get("preset"):
        await ensure_ready()
        with db() as con:
            return JSONResponse({"answer": ask.preset(con, body["preset"])})
    q = (body.get("q") or "").strip()
    if not q:
        return JSONResponse({"answer": "Алдымен сұрақ жазыңыз"})
    await ensure_ready()
    try:
        with db() as con:
            return JSONResponse({"answer": await ask.answer(http, API, auth(), con, q)})
    except Exception:
        log.exception("ask")
        return JSONResponse({"answer": "Қате болды, кейінірек қайталаңыз."})


def role_only(request: Request, perm: str):
    """(user, None) when the session may do `perm` (see dept.PERMS), else (None, a redirect)."""
    user = session(request)
    if not user:
        return None, need_login(request)
    if not dept.can(user, perm):
        return None, RedirectResponse("/", status_code=303)
    return user, None


@app.get("/dept")
async def dept_page(request: Request, m: str | None = None, ok: str | None = None):
    user, deny = role_only(request, "view")
    if deny:
        return deny
    await ensure_ready()
    today = igdata.today()
    month = m if m and len(m) == 7 and m[4] == "-" else dept.month_key(today)
    with db() as con:
        team = staffauth.staff(con)
        dept.seed_from_staff(con, team, today)
        return HTMLResponse(dept.page(con, user, team, today, month, ok or ""), headers={"Cache-Control": "no-store"})


@app.get("/competitors")
async def competitors_page(request: Request, ok: str | None = None):
    """Competitors' public Instagram numbers next to ours (everyone on the team sees it, lead and admin change the list)."""
    user, deny = role_only(request, "view")
    if deny:
        return deny
    await ensure_ready()
    with db() as con:
        await competitors.refresh(http, con, ig_id=ME.get("id"))
        return HTMLResponse(competitors.page(con, user, dept.can(user, "dept.edit"), ok or ""), headers={"Cache-Control": "no-store"})


@app.get("/api/igbot/competitors-check")
async def competitors_check(request: Request):
    """Diagnostics: forget the cached account, refresh the competitors now and show what Meta answered."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    with db() as con:
        amo.kv_set(con, "comp_me", None)
        await competitors.refresh(http, con, force=True, ig_id=ME.get("id"))
        users = competitors.names(con)
        rows = {}
        for u in [(amo.kv_get(con, "comp_me") or {}).get("username")] + users:
            en = amo.kv_get(con, f"comp:{u}", {}) or {}
            kinds = {}  # media type → [posts, with media_url, with thumbnail_url, with a card picture]
            for m in en.get("media") or []:
                k = kinds.setdefault(f'{m.get("media_type")}/{m.get("media_product_type")}', [0, 0, 0, 0])
                k[0] += 1
                k[1] += bool(m.get("media_url"))
                k[2] += bool(m.get("thumbnail_url"))
                k[3] += bool(competitors.picture(m))
            rows[u] = {"followers": (en.get("p") or {}).get("followers_count"), "error": en.get("error"), "media": kinds}
        me_ = amo.kv_get(con, "comp_me") or {}
        st_ = amo.kv_get(con, "comp_state")
    who = {}
    for t in competitors.TOKENS:  # who each token belongs to and what it may do (never the token itself)
        if t in competitors.bad_tokens():
            who[t] = {"me": "Vercel-дегі мәні кілт емес (басқа мәтін көшірілген)"}
        if not competitors.token(t):
            continue
        h = {"Authorization": f"Bearer {competitors.token(t)}"}
        base = f"https://graph.facebook.com/{os.getenv('META_GRAPH_API_VERSION', 'v25.0')}"
        a = (await http.get(f"{base}/me", headers=h, params={"fields": "id,name"})).json()
        p = (await http.get(f"{base}/me/permissions", headers=h)).json()
        b = (await http.get(f"{base}/me/businesses", headers=h, params={"fields": "id,name"})).json()
        who[t] = {"me": a.get("name") or (a.get("error") or {}).get("message", "")[:120], "id": a.get("id"),
                  "granted": [x["permission"] for x in p.get("data", []) if x.get("status") == "granted"],
                  "businesses": [x.get("name") for x in b.get("data", [])] or (b.get("error") or {}).get("message", "")[:120]}
    return {"state": st_, "me": {k: me_.get(k) for k in ("username", "tok")}, "rows": rows,
            "tokens": who}


@app.get("/trends")
async def trends_page(request: Request, ok: str | None = None):
    """Today's loud stories and the AI's ideas for EduApp posts, stories, reels (everyone on the team; lead and admin refresh)."""
    user, deny = role_only(request, "view")
    if deny:
        return deny
    with db() as con:
        return HTMLResponse(trends.page(con, user, dept.can(user, "dept.edit"), ok or ""), headers={"Cache-Control": "no-store"})


@app.post("/trends")
async def trends_refresh(request: Request):
    user, deny = role_only(request, "dept.edit")
    if deny:
        return deny
    f = form_data(await request.body())
    if f.get("action") == "about":  # what the AI should know about us (products, the Roblox game); used from the next refresh
        with db() as con:
            amo.kv_set(con, "trends_about", (f.get("about") or "").replace("\r\n", "\n").strip()[:2000] or None)
            dept.log(con, user["u"], "trends.about", "")
        return RedirectResponse("/trends?ok=" + quote("Сақталды. Келесі «Жаңарту» осыны ескереді"), status_code=303)
    with db() as con:
        st = await trends.refresh(http, con)
        dept.log(con, user["u"], "trends.refresh", st.get("model") or st.get("error") or "")
    note = "Трендтер жаңартылды" if not st.get("error") else "Жаңарту толық болмады, төменде себебі жазылған"
    return RedirectResponse("/trends?ok=" + quote(note), status_code=303)


@app.get("/api/igbot/trends-check")
async def trends_check(request: Request, refresh: str | None = None):
    """Diagnostics: refresh the trends now (?refresh=1) and show a short summary."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    with db() as con:
        st = await trends.refresh(http, con) if refresh else (amo.kv_get(con, "trends", {}) or {})
    groups = {}
    for r in st.get("sources") or []:
        groups[r["src"]] = groups.get(r["src"], 0) + 1
    pics = {}
    for r in st.get("sources") or []:
        pics[r["src"]] = pics.get(r["src"], 0) + bool(r.get("img"))
    return {"at": st.get("at"), "model": st.get("model"), "error": st.get("error"), "search_error": (st.get("search_error") or "")[:600],
            "src_errors": st.get("src_errors"), "sources": groups, "with_picture": pics, "web": len(st.get("web") or []),
            "tip_kk": st.get("tip_kk"), "items": [{"kind": t.get("kind"), "title_kk": t["title_kk"], "region": t["region"],
                                                   "category": t["category"], "heat": t["heat"], "refs": len(t["refs"]),
                                                   "img": bool(t.get("img")), "views": t.get("views"),
                                                   "ideas": [(i["format"], i["hook_kk"]) for i in t["ideas"]]} for t in st.get("items") or []]}


@app.post("/competitors")
async def competitors_save(request: Request):
    user, deny = role_only(request, "dept.edit")
    if deny:
        return deny
    f = form_data(await request.body())
    with db() as con:
        cur = competitors.names(con)
        if f.get("remove"):
            amo.kv_set(con, "comp_list", [u for u in cur if u != f["remove"]])
            dept.log(con, user["u"], "comp.remove", f["remove"])
            return RedirectResponse("/competitors?ok=" + quote(f"@{f['remove']} тізімнен алынды"), status_code=303)
        u = competitors.username_of(f.get("add") or "")
        if not u:
            return RedirectResponse("/competitors?ok=" + quote("Профиль сілтемесін не никті жазыңыз (пост сілтемесі аккаунтты көрсетпейді)"), status_code=303)
        if u not in cur:
            amo.kv_set(con, "comp_list", cur + [u])
            dept.log(con, user["u"], "comp.add", u)
        amo.kv_set(con, "comp_state", {**(amo.kv_get(con, "comp_state", {}) or {}), "at": 0})  # read the new account at once
    return RedirectResponse("/competitors?ok=" + quote(f"@{u} қосылды"), status_code=303)


@app.post("/dept/plan")
async def dept_plan_save(request: Request):
    user, deny = role_only(request, "dept.edit")
    if deny:
        return deny
    f = form_data(await request.body())
    month = f.get("month") or dept.month_key(igdata.today())
    with db() as con:
        dept.save_draft(con, month, f, user["u"])
        msg = "Жоба сақталды"
        if f.get("do") == "approve" and dept.can(user, "dept.approve"):
            dept.approve(con, month, user["u"])
            msg = "Жоспар бекітілді — Шолу мен есептер енді осы жоспар бойынша"
    return RedirectResponse(f"/dept?m={month}&ok=" + quote(msg), status_code=303)


@app.post("/dept/people")
async def dept_people_save(request: Request):
    """Lead / admin set each person's own monthly plan (draft, or saved and approved at once)."""
    user, deny = role_only(request, "dept.edit")
    if deny:
        return deny
    f = form_data(await request.body())
    month = f.get("month") or dept.month_key(igdata.today())
    with db() as con:
        people = {s["login"]: s["name"] for s in staffauth.staff(con)}
        ok = f.get("do") == "approve" and dept.can(user, "dept.approve")
        dept.save_people(con, month, f, people, user["u"], ok)
    msg = "Жеке жоспарлар бекітілді — Шолуда әркім өз жоспарын көреді" if ok else "Жеке жоспарлар жобасы сақталды"
    return RedirectResponse(f"/dept?m={month}&ok=" + quote(msg), status_code=303)


@app.post("/dept/task/add")
async def dept_task_add(request: Request):
    user, deny = role_only(request, "tasks.edit")
    if deny:
        return deny
    f = form_data(await request.body())
    if (f.get("title") or "").strip() and f.get("login"):
        with db() as con:
            tm = (f.get("due_time") or "").strip()[:5]
            due = (f.get("due") or "") + (f" {tm}" if f.get("due") and len(tm) == 5 and tm[2] == ":" else "")
            dept.add_task(con, f["login"], f["title"].strip(), due, user["u"])
    return RedirectResponse("/dept?ok=" + quote("Тапсырма берілді"), status_code=303)


@app.post("/dept/task")
async def dept_task_set(request: Request):
    # the undo toast sends X-Undo and needs a real answer; a plain form post keeps the redirect
    quiet = request.headers.get("x-undo") == "1"
    user, deny = role_only(request, "view")
    if deny:
        if quiet:
            logged_in = session(request) is not None
            return JSONResponse({"error": "бұл әрекетке рұқсат жоқ" if logged_in else "кіру мерзімі бітті, қайта кіріңіз"},
                                status_code=403 if logged_in else 401)
        return deny
    f = form_data(await request.body())
    own = None if dept.can(user, "tasks.edit") else user["u"]  # a marketer ticks only their own tasks
    if f.get("status") == "deleted" and own:
        if quiet:
            return JSONResponse({"error": "тапсырманы тек жетекші өше алады"}, status_code=403)
        return RedirectResponse("/dept", status_code=303)
    try:
        with db() as con:
            dept.set_task(con, f.get("id") or "", f.get("status") or "", user["u"], own)
    except Exception:
        if not quiet:
            raise
        log.exception("task update failed")
        return JSONResponse({"error": "дерекқор жауап бермеді, қайталап көріңіз"}, status_code=503)
    # an already-missing task is what the person wanted: it is gone
    back = f.get("back") or ""
    back = back if back.startswith("/") and not back.startswith("//") else "/dept"
    return Response(status_code=204) if quiet else RedirectResponse(back, status_code=303)


@app.get("/ads")
async def ads_page(request: Request, ok: str | None = None, d1: str | None = None, d2: str | None = None):
    user, deny = role_only(request, "ads")
    if deny:
        return deny
    await ensure_ready()
    with db() as con:
        await amo.sync(http, con)
        await ads.sync_meta(http, con)
        first = last = None
        if d1 and d2:
            _, one, span_days = picked_days("range", None, d1, d2, "")
            first, last = span_days or (one, one)
        return HTMLResponse(ads.page(con, user, ok or "", first, last), headers={"Cache-Control": "no-store"})


@app.post("/ads")
async def ads_save(request: Request):
    _, deny = role_only(request, "ads")
    if deny:
        return deny
    f = form_data(await request.body())
    try:
        day = datetime.strptime(f.get("day") or "", "%Y-%m-%d").strftime("%Y-%m-%d")
        amount = max(0, int(float(f.get("amount") or 0)))
    except ValueError:
        return RedirectResponse("/ads", status_code=303)
    with db() as con:
        ads.save_day(con, day, amount)
    return RedirectResponse("/ads?ok=" + quote(f"{day}: сақталды"), status_code=303)


@app.get("/settings")
async def settings_page(request: Request, ok: str | None = None):
    _, deny = admin_only(request)
    if deny:
        return deny
    with db() as con:
        st, state = amo.settings(con), amo.kv_get(con, "amo_sync", {}) or {}
    if state.get("at"):
        state["when"] = datetime.fromtimestamp(state["at"], igdata.TZ).strftime("%d.%m.%Y %H:%M")
    fields, pipes = await asyncio.gather(amo.fields(http), amo.pipelines(http))
    month_start = int(igdata.today().replace(day=1).timestamp())
    with db() as con:
        counts = amo.value_counts(con, st.get("source_field"), month_start) if st.get("source_field") else {}
        pcounts = amo.pipeline_counts(con, month_start)
    return HTMLResponse(admin.settings_page(amo.configured(), state, fields, pipes, st, "Сақталды" if ok else "",
                                            counts, pcounts, session(request)),
                        headers={"Cache-Control": "no-store"})


@app.post("/settings")
async def settings_save(request: Request):
    _, deny = admin_only(request)
    if deny:
        return deny
    f = form_data(await request.body())
    as_list = lambda v: v if isinstance(v, list) else ([v] if v else [])
    with db() as con:
        old = amo.settings(con)
        field = f.get("source_field") or ""
        new = {"source_field": field, "sources": as_list(f.get("sources")) if field == old.get("source_field") else [],
               "pipelines": [int(x) for x in as_list(f.get("pipelines")) if str(x).isdigit()]}
        amo.kv_set(con, "mkt_settings", new)
    return RedirectResponse("/settings?ok=1", status_code=303)


@app.get("/preview")
async def preview_page(request: Request, v: str = "a", who: str | None = None, shots: int = 0):
    """Three visual directions on real numbers (admin only)."""
    user, deny = admin_only(request)
    if deny:
        return deny
    await ensure_ready()
    today = igdata.today()
    with db() as con:
        team = staffauth.staff(con)
        person = next((x for x in team if x["login"] == who), team[0] if team else None)
        await amo.sync(http, con)
        plans = dict((person or {}).get("plans") or {})
        demo_plan = (plans.get("amount") or 0) < 1000
        if demo_plan:  # a preview needs a plan to show progress; it is labelled on the page
            plans.update(amount=2_000_000, bonus_pct=plans.get("bonus_pct") or 3)
        m = await mkt.build(http, API, auth(), con, period="month", anchor=today, plans=plans,
                            name=(person or {}).get("name") or user["n"])
        days = amo.daily(con, int((today - timedelta(days=13)).timestamp()), 14)
    spark14 = {"amount": [x["amount"] for x in days], "sales": [x["sales"] for x in days], "leads": [x["leads"] for x in days],
               "avg": [round(x["amount"] / x["sales"]) if x["sales"] else 0 for x in days],
               "conv": [round(x["sales"] / x["leads"] * 100, 1) if x["leads"] else 0 for x in days]}
    return HTMLResponse(preview.render(v, m, spark14, user, bool(shots), demo_plan), headers={"Cache-Control": "no-store"})


@app.get("/api/igbot/bot-stats")
async def bot_stats_page(request: Request):
    """The old Direct-bot funnel page — superseded by /bot (same funnel, feed and answers in the current design)."""
    if not stats_auth_ok(request):
        return need_login(request)
    return RedirectResponse("/bot", status_code=303)


@app.get("/api/igbot/report")
async def report_page(request: Request, d: str | None = None):
    """Daily Instagram report with a ready-to-paste text for WhatsApp/Telegram."""
    if not stats_auth_ok(request):
        return need_login(request)
    await ensure_ready()
    _, day, _ = parse_range(None, d or igdata.key(igdata.today()), None)
    me = await igdata.profile(http, API, auth())
    skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    with db() as con:
        if me.get("followers_count") is not None:
            igdata.snapshot(con, me["followers_count"], me.get("media_count"))
        rows = await igdata.days(http, API, auth(), con, day - timedelta(days=1), day)
        posts = await igdata.media(http, API, auth(), con, day, day)
        is_today = day == igdata.today()  # (report page: small, two calls)
        followers = me.get("followers_count") if is_today else igdata.followers_on(con, igdata.key(day))
        prev = igdata.followers_on(con, igdata.key(day - timedelta(days=1)))
        since, until = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
        direct = igdata.direct_messages(con, since, until, skip)
        # the same report as on the dashboard: plan lines, sales, Instagram (the viewer's own plan; the admin sees the first employee's)
        user = session(request) or {}
        person = staffauth.get_staff(con, user.get("u", "")) if user.get("r") != "admin" else None
        if not person:
            team = staffauth.staff(con)
            person = team[0] if team else {"name": user.get("n", ""), "plans": {}}
        if amo.configured():
            await amo.sync(http, con)
        m = await mkt.build(http, API, auth(), con, period="day", anchor=day, plans=person.get("plans") or {}, name=person["name"])
        igx = await report_igx(con, m, igdata.today(), "day")
        rtpl = mkt.report_tpl(con)
    ins = dict(rows.get(igdata.key(day)) or {})
    if is_today and ins.get("new_followers") is None and followers is not None and prev is not None:
        ins["net_followers"] = followers - prev
    text = mkt.short_report(m, f"{PUBLIC_URL}/?p=day&d={igdata.key(day)}", igx, rtpl)
    return HTMLResponse(report.render(day, text, followers, prev, ins, direct, session(request)), headers={"Cache-Control": "no-store"})


@app.get("/api/igbot/broadcast")
async def broadcast_run(request: Request, campaign: str, send: str | None = None):
    """Server-side broadcast (the database lives here): dry run by default, ?send=1 to send.
    Sends are spaced out and stop after a time budget; call again to continue."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    exclude = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    people = followup_recipients(campaign, exclude)
    if not send:
        return {"campaign": campaign, "recipients": len(people)}
    started, sent, failed = time.time(), 0, 0
    for igsid in people:
        if time.time() - started > 200:
            break
        if await send_followup(igsid, campaign):
            sent += 1
        else:
            failed += 1
            if failed >= 3 and sent == 0:
                break  # first sends all failed: stop to protect the account
        await asyncio.sleep(2)
    return {"campaign": campaign, "sent": sent, "failed": failed, "left": max(0, len(people) - sent - failed)}


async def unanswered_comments(days: int = 7) -> list:
    """Top-level comments of the last `days` days on recent posts that have no reply from us yet.
    (Instagram allows a private reply to a comment for 7 days.)"""
    since = time.time() - days * 86400
    r = await http.get(f"{API}/me/media", headers=auth(), params={"fields": "id,timestamp,comments_count", "limit": 30})
    out = []
    for m in (r.json().get("data") or []) if r.status_code == 200 else []:
        if not m.get("comments_count"):
            continue
        c = await http.get(f"{API}/{m['id']}/comments", headers=auth(),
                           params={"fields": "id,text,timestamp,from,username,replies", "limit": 50})
        for cm in (c.json().get("data") or []) if c.status_code == 200 else []:
            ts = datetime.strptime(cm["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").timestamp() if cm.get("timestamp") else 0
            who = cm.get("from") or {}
            # Instagram returns only the ids of replies here, not who wrote them: a comment that
            # already has a reply (ours or a manager's) counts as answered
            replied = bool((cm.get("replies") or {}).get("data"))
            if ts >= since and who.get("id") and who["id"] != ME.get("id") and not replied:
                out.append({"id": cm["id"], "from": who, "media": {"id": m["id"]},
                            "text": cm.get("text") or "", "timestamp": cm.get("timestamp")})
    return out


@app.get("/api/igbot/comments-backlog")
async def comments_backlog(request: Request, send: str | None = None):
    """Comments written before the auto-reply was on: dry run by default, ?send=1 to answer them."""
    if not CRON_SECRET or request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await ensure_ready()
    if not ME.get("id"):
        await whoami()
    todo = await unanswered_comments()
    todo = [c for c in todo if wants_info(c["text"])]
    if not send:
        out = {"comments": len(todo), "people": len({c["from"]["id"] for c in todo})}
        if request.query_params.get("list"):
            with db() as con:
                greeted = {r[0] for r in con.execute("select igsid from leads")}
            out["items"] = [{"id": c["id"], "user": c["from"].get("username"), "text": c["text"], "time": c["timestamp"],
                             "greeted": c["from"]["id"] in greeted} for c in todo]
        return out
    started, done = time.time(), 0
    for c in todo:
        if time.time() - started > 200:
            break
        await on_comment(c, backlog=True)
        done += 1
        await asyncio.sleep(2)
    return {"answered": done, "left": len(todo) - done}


@app.get("/api/igbot/health")
async def health():
    return {"enabled": bot_on(), "only": sorted(BOT_ONLY), "token": bool(token()), "account": ME.get("username"),
            "trainings": len(catalog()), "texts": len(texts())}


# ---------- identity, webhook subscription, token refresh ----------
# Serverless has no long-running loops: requests make sure the bot knows who it is and
# refresh the token when due; a daily cron does the same even on quiet days.

async def whoami(subscribe: bool = False):
    if not token():
        log.error("no Instagram token (IG_TOKEN) — bot cannot send messages")
        return
    r = await http.get(f"{API}/me", headers=auth(), params={"fields": "user_id,username"})
    if r.status_code != 200:
        log.error("token check failed %s: %s", r.status_code, r.text[:300])
        return
    j = r.json()
    ME.update(id=str(j.get("user_id") or j.get("id")), username=j.get("username"))
    log.info("connected as @%s (%s)", ME["username"], ME["id"])
    if subscribe:
        sub = await http.post(f"{API}/me/subscribed_apps", headers=auth(),
                              params={"subscribed_fields": "messages,messaging_postbacks,comments"})
        log.info("webhook subscription: %s %s", sub.status_code, sub.text[:200])


async def refresh_token():
    """Long-lived tokens live 60 days; refresh every few days and keep the new one in the database."""
    current = token()
    if not current or time.time() - (_token.get("ts") or 0) < TOKEN_REFRESH_AFTER:
        return
    r = await http.get("https://graph.instagram.com/refresh_access_token",
                       params={"grant_type": "ig_refresh_token", "access_token": current})
    now = int(time.time())
    if r.status_code == 200 and r.json().get("access_token"):
        with db() as con:
            con.execute("insert into kv values ('ig_token', ?, ?) on conflict (k) do update set v = excluded.v,"
                        " ts = excluded.ts", (r.json()["access_token"], now))
        _token.update(v=r.json()["access_token"], ts=now)
        log.info("token refreshed")
    else:
        # Do not hammer Meta on every request; try again at the next refresh interval.
        _token["ts"] = now - TOKEN_REFRESH_AFTER + 3600
        log.error("token refresh failed %s: %s", r.status_code, r.text[:200])


async def ensure_ready():
    try:
        await refresh_token()
        if not ME.get("id"):
            await whoami()
    except Exception:
        log.exception("ensure_ready")


@app.get("/api/igbot/cron")
async def cron(request: Request):
    """Daily (vercel.json): refresh the token, renew the webhook subscription, retry the sheet."""
    if CRON_SECRET and request.headers.get("authorization", "") != f"Bearer {CRON_SECRET}":
        return PlainTextResponse("forbidden", status_code=403)
    await refresh_token()
    await whoami(subscribe=True)
    await sync_sheet()
    me = await igdata.profile(http, API, auth())
    with db() as con:
        if me.get("followers_count") is not None:
            igdata.snapshot(con, me["followers_count"], me.get("media_count"))
        # Settle the last few days in the cache so the dashboard opens fast.
        rows = await igdata.days(http, API, auth(), con, igdata.today() - timedelta(days=7), igdata.today())
        # Runs at 00:05 Astana: yesterday has just ended, so today's follower count is its end-of-day total.
        yesterday = igdata.today() - timedelta(days=1)
        if me.get("followers_count") is not None:
            con.execute("insert into daily values (?, ?, ?, ?) on conflict (day) do update set followers = excluded.followers,"
                        " media = excluded.media, ts = excluded.ts",
                        (igdata.key(yesterday), me["followers_count"], me.get("media_count"), int(time.time())))
        skip = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
        data = await history.summary(http, API, auth(), con, yesterday, me.get("followers_count"), skip)
        history.save(con, igdata.key(yesterday), data, "auto")
        history.fill_late_followers(con, rows)
        await ads.sync_meta(http, con, force=True)
        await competitors.refresh(http, con, force=True, ig_id=ME.get("id"))
        if amo.configured():
            await amo.sync(http, con, force=True, budget=200)
            await amo.sync_touches(http, con, budget=60)
    return {"ok": True, "account": ME.get("username")}
