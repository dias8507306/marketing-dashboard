"""Competitors: the public Instagram numbers of other accounts next to ours, through Meta's Business Discovery.

Needs META_IG_TOKEN, a Facebook-login token of a system user that sees the EduApp page and its Instagram
account (instagram_basic, pages_show_list, pages_read_engagement, business_management). Only what anyone sees on
a profile is available: followers, posts, likes, comments. Reach and views of other accounts Meta never gives.

kv `comp_list` = [usernames]; kv `comp:<username>` = {"p": profile, "media": [...], "days": {"YYYY-MM-DD": followers}, "at", "error"};
kv `comp_me` = {"id", "username"}, our Instagram business account as Meta's Graph API knows it.
"""
import asyncio
import html
import logging
import os
import re
import time
from datetime import datetime, timedelta

import amo
import igdata

log = logging.getLogger("competitors")
DEFAULT = ["demo_school_kz", "sample.academy", "example_online_kz", "tutor_demo.kz"]
EVERY = 3600  # seconds between refreshes when the page is opened; the night job refreshes every day
FULL = "username,name,profile_picture_url,followers_count,follows_count,media_count,media.limit(30){{id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp,media_url,thumbnail_url}}"
LEAN = "username,name,profile_picture_url,followers_count,follows_count,media_count,media.limit(30){{id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp}}"


TOKENS = ("META_IG_TOKEN", "META_ADS_TOKEN")  # tried in this order; the one that works is kept in comp_me["tok"]
_tok = {"name": "META_IG_TOKEN"}


def token(name: str) -> str:
    """The token in this variable, or "" when it is empty or not a token at all (other text pasted by mistake)."""
    v = (os.getenv(name) or "").strip()
    return v if v.isascii() and " " not in v else ""


def bad_tokens() -> list:
    return [t for t in TOKENS if os.getenv(t, "").strip() and not token(t)]


def configured() -> bool:
    return any(token(t) for t in TOKENS)


def names(con) -> list:
    v = amo.kv_get(con, "comp_list")
    return DEFAULT if v is None else v


def username_of(text: str) -> str | None:
    """`@competitor.kz`, `competitor.kz` or a profile link → `competitor.kz`; a post or reel link → None (it does not name the account)."""
    t = (text or "").strip()
    m = re.search(r"instagram\.com/([^/?#]+)", t)
    if m:
        t = m.group(1)
        if t in ("p", "reel", "reels", "tv", "stories", "explore"):
            return None
    t = t.lstrip("@").strip().lower()
    return t if re.fullmatch(r"[a-z0-9._]{1,30}", t) else None


def _api():
    return f"https://graph.facebook.com/{os.getenv('META_GRAPH_API_VERSION', 'v25.0')}", {"Authorization": f"Bearer {token(_tok['name'])}"}


async def _get(http, path: str, params: dict) -> dict:
    base, head = _api()
    r = await http.get(f"{base}/{path}", headers=head, params=params, timeout=15)
    body = r.json()
    if r.status_code != 200:
        raise RuntimeError(((body.get("error") or {}).get("message") or f"HTTP {r.status_code}")[:200])
    return body


async def me(http, con, ig_id: str | None = None) -> dict:
    """Our Instagram business account id and a token that can read it. Each Meta token is tried: the Instagram account
    of a page it sees (eduapp_demo first), else our account by id (META_IG_USER_ID or the bot's own ig_id) directly."""
    known = amo.kv_get(con, "comp_me")
    if known and known.get("id") and token(known.get("tok") or "META_IG_TOKEN"):
        _tok["name"] = known.get("tok") or "META_IG_TOKEN"
        return known
    ids = [x for x in (os.getenv("META_IG_USER_ID", "").strip(), ig_id) if x]
    why = [f"{t}: Vercel-дегі мәні кілт емес (басқа мәтін көшірілген)" for t in bad_tokens()]
    for name in TOKENS:
        if not token(name):
            continue
        _tok["name"] = name
        pick = None
        try:
            body = await _get(http, "me/accounts", {"fields": "name,instagram_business_account{id,username}", "limit": 50})
            accs = [p["instagram_business_account"] for p in body.get("data", []) if p.get("instagram_business_account")]
            pick = next((a for a in accs if a.get("username") == "eduapp_demo"), accs[0] if accs else None)
            if not pick:
                why.append(f"{name}: Facebook беттері көрінбейді")
        except RuntimeError as e:
            why.append(f"{name}: {e}")
        for i in ids if not pick else []:
            try:
                body = await _get(http, i, {"fields": "id,username"})
                if body.get("id"):
                    pick = {"id": body["id"], "username": body.get("username")}
                    break
            except RuntimeError as e:
                why.append(f"{name} → {i}: {e}")
        if pick:
            pick = {**pick, "tok": name}
            amo.kv_set(con, "comp_me", pick)
            return pick
    raise RuntimeError(("Meta кілті EduApp бетін де, eduapp_demo аккаунтын да көрмейді. Business Settings → System users → "
                        "активтерге EduApp бетін және eduapp_demo Instagram аккаунтын қосыңыз. ") + " | ".join(why)[:500])


async def _one(http, con, my_id: str, user: str):
    entry = amo.kv_get(con, f"comp:{user}", {}) or {}
    try:
        try:
            body = await _get(http, my_id, {"fields": f"business_discovery.username({user}){{{FULL.format()}}}"})
        except RuntimeError:  # some media fields are not allowed for every account: ask again without the pictures
            body = await _get(http, my_id, {"fields": f"business_discovery.username({user}){{{LEAN.format()}}}"})
        bd = body.get("business_discovery") or {}
        media = [{k: m.get(k) for k in ("id", "like_count", "comments_count", "media_type", "media_product_type", "permalink", "timestamp",
                                        "media_url", "thumbnail_url")} | {"caption": (m.get("caption") or "")[:140]}
                 for m in (bd.get("media") or {}).get("data", [])]
        days = entry.get("days") or {}
        if bd.get("followers_count") is not None:
            days[igdata.key(igdata.today())] = bd["followers_count"]
        entry = {"p": {k: bd.get(k) for k in ("username", "name", "profile_picture_url", "followers_count", "follows_count", "media_count")},
                 "media": media, "days": dict(sorted(days.items())[-400:]), "at": int(time.time()), "error": None}
    except Exception as e:
        log.warning("competitor %s: %s", user, type(e).__name__)
        entry = {**entry, "error": (str(e) if isinstance(e, RuntimeError) else type(e).__name__)[:200], "tried": int(time.time())}
    amo.kv_set(con, f"comp:{user}", entry)


async def refresh(http, con, force: bool = False, ig_id: str | None = None):
    """Every account in the list and ours, at most once an hour (or now with `force`); a failure keeps the old numbers.
    ig_id: our Instagram account id as the bot knows it, used when the Meta token sees no Facebook page."""
    if not configured():
        return
    st = amo.kv_get(con, "comp_state", {}) or {}
    if not force and time.time() - (st.get("at") or 0) < (60 if st.get("error") else EVERY):
        return
    st["at"] = int(time.time())
    try:
        my = await me(http, con, ig_id)
        st["error"] = None
    except Exception as e:
        st["error"] = (str(e) if isinstance(e, RuntimeError) else type(e).__name__)[:700]
        amo.kv_set(con, "comp_state", st)
        return
    amo.kv_set(con, "comp_state", st)
    users = [my["username"]] + [u for u in names(con) if u != my["username"]]
    sem = asyncio.Semaphore(4)

    async def run(u):
        async with sem:
            await _one(http, con, my["id"], u)
    await asyncio.gather(*(run(u) for u in users))


def stats(entry: dict, today) -> dict:
    """Numbers for one row: followers and their change, posts a week, average likes / comments, ER, share of reels."""
    p, media = entry.get("p") or {}, entry.get("media") or []
    fol = p.get("followers_count")
    month_ago = today - timedelta(days=30)

    def when(m):
        try:
            return datetime.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError, KeyError):
            return None
    recent = [m for m in media if when(m) and when(m).date() >= month_ago.date()]
    dated = [when(m) for m in media if when(m)]
    # Meta gives at most 30 posts: when all 30 fit in the month, the account posts more often than 30 a month, so the
    # rate is counted over the days those 30 posts really cover, not over 30 days (that would cap everyone at 7 a week)
    span = 30
    if len(media) >= 30 and dated and min(dated).date() >= month_ago.date():
        span = max(1, (today.date() - min(dated).date()).days + 1)
    covered_from = min(dated).date() if len(media) >= 30 and dated else None  # older weeks are unknown, not empty
    last = media[:12]
    likes = [m["like_count"] for m in last if m.get("like_count") is not None]
    comments = [m["comments_count"] for m in last if m.get("comments_count") is not None]
    avg_l = sum(likes) / len(likes) if likes else None
    avg_c = sum(comments) / len(comments) if comments else None
    days = entry.get("days") or {}
    first_key = next(iter(days), None)
    since = None
    if fol is not None and first_key and first_key < igdata.key(today):
        base_key = max([k for k in days if k <= igdata.key(month_ago)] or [first_key])
        since = {"from": base_key, "delta": fol - days[base_key]}
    mix = {"reels": 0, "carousel": 0, "image": 0}
    for m in media:
        if m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO":
            mix["reels"] += 1
        elif m.get("media_type") == "CAROUSEL_ALBUM":
            mix["carousel"] += 1
        else:
            mix["image"] += 1
    week0 = today.date() - timedelta(days=today.weekday())  # Monday of this week
    weeks = []
    for i in range(7, -1, -1):
        start = week0 - timedelta(weeks=i)
        n = sum(1 for d in dated if start <= d.date() < start + timedelta(days=7))
        weeks.append({"start": start, "n": None if covered_from and start + timedelta(days=7) <= covered_from else n})
    return {"followers": fol, "posts_week": round(len(recent) / span * 7, 1) if media else None, "avg_likes": avg_l, "avg_comments": avg_c,
            "er": round(((avg_l or 0) + (avg_c or 0)) / fol * 100, 2) if fol and (likes or comments) else None,
            "reels": round(sum(1 for m in last if m.get("media_product_type") == "REELS") / len(last) * 100) if last else None,
            "growth": round(since["delta"] / (fol - since["delta"]) * 100, 2) if since and fol and fol - since["delta"] else None,
            "likes_hidden": bool(last) and not likes, "since": since, "recent": recent, "mix": mix, "n_media": len(media), "weeks": weeks}


def picture(m: dict) -> str | None:
    """A still picture for a post card: a video's or reel's cover, else the photo — for a carousel Meta gives its first
    item as media_url (a video there is an .mp4, not a picture; the <img> then removes itself and the label shows)."""
    if m.get("thumbnail_url"):
        return m["thumbnail_url"]
    if m.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM") and m.get("media_url"):
        return m["media_url"]
    return None


def _num(v):
    return "—" if v is None else f"{round(v):,}".replace(",", " ")


def _dec(v, n=1):
    return f"{v:.{n}f}".replace(".", ",")


def rank_panel(title: str, note: str, data: list, key: str, fmt, my_user: str) -> str:
    """One measure across all accounts as ranked bars: ours in the brand violet, the rest neutral, the value at the tip.
    Negative values (growth) grow left from a centre baseline."""
    e = html.escape
    rows = sorted([(u, s.get(key)) for u, _, s in data], key=lambda x: (x[1] is None, -(x[1] or 0)))
    vals = [v for _, v in rows if v is not None]
    hi = max([abs(v) for v in vals] or [0]) or 1
    neg = any(v < 0 for v in vals)
    out = []
    for u, v in rows:
        if v is None:
            mark = ""
        else:
            w = abs(v) / hi * (50 if neg else 100)
            w = max(w, 0.8) if v else 0
            left = (50 - w if v < 0 else 50) if neg else 0
            mark = (f'<i class="{"l" if v < 0 else "r"}" style="left:{left:.1f}%;width:{w:.1f}%" '
                    f'data-tip="@{e(u)} · {e(title)}: {e(fmt(v))}"></i>')
        out.append(f'<div class="cpk{" us" if u == my_user else ""}"><span title="@{e(u)}">@{e(u)}</span>'
                   f'<div class="cpk-t{" mid" if neg else ""}">{mark}</div><b>{e(fmt(v)) if v is not None else "—"}</b></div>')
    return f'<section class="cpb cpq"><h2>{e(title)}</h2><p>{e(note)}</p>{"".join(out)}</section>'


MIX = (("reels", "Рилс"), ("carousel", "Карусель"), ("image", "Сурет"))


def mix_panel(data: list, my_user: str) -> str:
    """What each account posts: one tall segmented bar per account (reels / carousels / photos of its latest posts)."""
    e = html.escape
    rows = []
    for u, _, s in data:
        tot = sum(s["mix"].values())
        if not tot:
            rows.append(f'<div class="cps"><span>@{e(u)}</span><div class="cps-none">Деректер жоқ</div></div>')
            continue
        segs, parts = "", []
        for i, (k, lab) in enumerate(MIX, 1):
            n = s["mix"][k]
            if not n:
                continue
            pct = round(n / tot * 100)
            parts.append(f"{lab} {pct}%")
            segs += (f'<i class="k{i}" style="flex:{n} 1 0" data-tip="@{e(u)} · {lab}: {n} ({pct}%)">'
                     f'{f"{pct}%" if n / tot >= .18 else ""}</i>')
        rows.append(f'<div class="cps{" us" if u == my_user else ""}"><span>@{e(u)}<small>соңғы {tot}</small></span>'
                    f'<div class="cps-b" role="img" aria-label="@{e(u)}: {e(", ".join(parts))}">{segs}</div></div>')
    legend = "".join(f'<span><i class="k{i}"></i>{lab}</span>' for i, (_, lab) in enumerate(MIX, 1))
    return (f'<section class="cpb"><h2>Контент түрі</h2><p>Соңғы жарияланымдардың қаншасы рилс, карусель, сурет</p>'
            f'<div class="cpl2">{legend}</div>{"".join(rows)}</section>')


def activity_panel(data: list, my_user: str) -> str:
    """Posts per week, last 8 weeks: accounts × weeks, darker = more posts. Weeks older than the 30 posts Meta gives
    are «белгісіз», not zero."""
    e = html.escape
    weeks = data[0][2]["weeks"] if data else []
    mx = max([w["n"] or 0 for _, _, s in data for w in s["weeks"]] or [0]) or 1
    head = "".join(f'<span>{w["start"]:%d.%m}</span>' for w in weeks)
    rows = []
    for u, _, s in data:
        cells = ""
        for w in s["weeks"]:
            when_ = f'{w["start"]:%d.%m} аптасы'
            if w["n"] is None:
                cells += f'<i class="na" data-tip="@{e(u)} · {when_}: белгісіз (Meta тек соңғы 30 жарияланымды береді)">·</i>'
                continue
            p = 14 + 86 * w["n"] / mx if w["n"] else 0
            style = f'background:color-mix(in srgb,var(--accent) {p:.0f}%,var(--surface2));' if w["n"] else ""
            if p >= 55:
                style += "color:var(--on-accent,#fff);"
            cells += f'<i style="{style}" data-tip="@{e(u)} · {when_}: {w["n"]} жарияланым">{w["n"]}</i>'
        rows.append(f'<div class="cph2{" us" if u == my_user else ""}"><span>@{e(u)}</span>{cells}</div>')
    return (f'<section class="cpb"><h2>Жариялау жиілігі · 8 апта</h2><p>Әр аптада неше жарияланым шықты. Қою түс — көп</p>'
            f'<div class="cphw"><div class="cph2 hd"><span></span>{head}</div>{"".join(rows)}</div></section>')


CSS = """.cph{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px;margin:0 0 16px}.cph h1{margin:0;font-size:1.375rem;font-weight:600;letter-spacing:-.02em}.cph p{margin:4px 0 0;max-width:64ch;font-size:.8125rem;color:var(--muted)}
.cpw{overflow-x:auto;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.cpt{width:100%;border-collapse:collapse;font-size:.875rem;font-variant-numeric:tabular-nums}.cpt th,.cpt td{padding:12px 16px;text-align:right;white-space:nowrap;border-top:1px solid var(--border)}.cpt thead th{border-top:0;font-size:.75rem;font-weight:500;color:var(--faint)}
.cpt th:first-child,.cpt td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}.cpt tr.us td{background:var(--surface2)}.cpt td.cpx{font-weight:600}.cpt td small{display:block;font-size:.75rem;color:var(--faint)}
.cpa{display:flex;align-items:center;gap:10px}.cpa img,.cpa i{width:32px;height:32px;border-radius:50%;flex:none;background:var(--surface2);object-fit:cover}.cpa b{font-weight:600}.cpa em{font-style:normal;margin-left:6px;padding:1px 6px;border-radius:4px;font-size:.6875rem;font-weight:600;color:#fff;background:#7336F7}.cpa small{color:var(--faint)}
.cpe{color:var(--red)!important;white-space:normal!important}
.cpg{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:16px;margin-top:16px;align-items:start}.cpb{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px}.cpb h2{margin:0 0 4px}.cpb>p{margin:0 0 16px;font-size:.75rem;color:var(--faint)}
.cpr{display:grid;grid-template-columns:120px minmax(0,1fr) 56px;align-items:center;gap:12px;padding:6px 0;font-size:.8125rem}.cpr span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cpr i{display:block;height:10px;border-radius:3px;background:color-mix(in srgb,var(--accent) 12%,color-mix(in srgb,var(--text) 12%,var(--surface)))}.cpr.us i{background:#7336F7}.cpr b{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
.cpp{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.cpp a{display:block;color:var(--text);border:1px solid var(--border);border-radius:12px;overflow:hidden}.cpp a:hover{border-color:var(--accent)}
.cpp .ph{position:relative;overflow:hidden;aspect-ratio:4/5;background:var(--surface2);display:grid;place-items:center;color:var(--faint);font-size:.75rem}
.cpp .ph img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.cpp .tx{padding:8px 10px;font-size:.75rem;line-height:1.4}.cpp .tx b{display:block;font-size:.8125rem;font-weight:600}.cpp .tx span{color:var(--faint)}
.cpm{margin-top:16px}.cpm form{display:flex;flex-wrap:wrap;gap:8px;align-items:end}.cpm .btnp{width:auto;min-height:44px;padding:0 20px}.cpm label{flex:1;min-width:220px}.cpl{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.cpl form{display:inline-flex}.cpl button{display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font:500 .8125rem 'Golos Text',sans-serif;cursor:pointer}.cpl button:hover{border-color:var(--red);color:var(--red)}
.cpn{margin:12px 0 0;font-size:.75rem;line-height:1.5;color:var(--faint)}
.cpa small{max-width:260px;overflow:hidden;text-overflow:ellipsis}
.cps2{margin:28px 0 12px}.cps2 h2{margin:0;font-size:1.0625rem;font-weight:600}.cps2 p{margin:4px 0 0;font-size:.8125rem;color:var(--muted)}
.cpqg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.cpk{display:grid;grid-template-columns:118px minmax(0,1fr) 72px;align-items:center;gap:10px;min-height:30px;font-size:.8125rem}
.cpk span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.cpk.us span{color:var(--text);font-weight:600}
.cpk b{text-align:right;font-weight:500;font-variant-numeric:tabular-nums}.cpk.us b{font-weight:700}
.cpk-t{position:relative;height:24px}.cpk-t.mid::before{content:"";position:absolute;left:50%;top:2px;bottom:2px;width:1px;background:var(--border)}
.cpk-t i{position:absolute;top:7px;height:10px;background:color-mix(in srgb,var(--text) 26%,var(--surface));border-radius:0 4px 4px 0;cursor:default}
.cpk-t i.l{border-radius:4px 0 0 4px}.cpk.us .cpk-t i{background:var(--accent)}
.cpk-t i::after{content:"";position:absolute;inset:-7px 0}
.cpg2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;margin-top:16px;align-items:start}
.cpz{--k1:#2a78d6;--k2:#eb6834;--k3:#1baf7a}
:root[data-theme=dark] .cpz{--k1:#3987e5;--k2:#d95926;--k3:#199e70}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .cpz{--k1:#3987e5;--k2:#d95926;--k3:#199e70}}
.cpl2{display:flex;flex-wrap:wrap;gap:6px 16px;margin:0 0 12px;font-size:.75rem;color:var(--muted)}.cpl2 span{display:inline-flex;align-items:center;gap:6px}
.cpl2 i{width:10px;height:10px;border-radius:3px}.cpl2 i.k1,.cps-b i.k1{background:var(--k1)}.cpl2 i.k2,.cps-b i.k2{background:var(--k2)}.cpl2 i.k3,.cps-b i.k3{background:var(--k3)}
.cps{display:grid;grid-template-columns:118px minmax(0,1fr);align-items:center;gap:10px;padding:5px 0;font-size:.8125rem}
.cps>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.cps.us>span{color:var(--text);font-weight:600}.cps>span small{display:block;font-size:.6875rem;color:var(--faint);font-weight:400}
.cps-b{display:flex;gap:2px;height:28px}.cps-b i{display:flex;align-items:center;min-width:0;padding:0 8px;border-radius:4px;color:#fff;font-style:normal;font-size:.75rem;font-weight:600;font-variant-numeric:tabular-nums;cursor:default}
.cps-none{font-size:.75rem;color:var(--faint)}
.cphw{overflow-x:auto}.cph2{display:grid;grid-template-columns:118px repeat(8,minmax(34px,1fr));gap:3px;align-items:center;font-size:.8125rem;margin-bottom:3px}
.cph2>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.cph2.us>span{color:var(--text);font-weight:600}
.cph2.hd>span{font-size:.6875rem;color:var(--faint);text-align:center;font-variant-numeric:tabular-nums}.cph2.hd>span:first-child{text-align:left}
.cph2 i{display:grid;place-items:center;height:30px;border-radius:4px;background:var(--surface2);font-style:normal;font-size:.75rem;font-weight:600;font-variant-numeric:tabular-nums;color:var(--text);cursor:default}
.cph2 i.na{background:none;color:var(--faint);font-weight:400}
@media (max-width:1100px){.cpqg{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cpqg>*,.cpg2>*{min-width:0}
@media (max-width:900px){.cpg,.cpg2{grid-template-columns:minmax(0,1fr)}.cpr{grid-template-columns:96px minmax(0,1fr) 48px}}
@media (max-width:640px){.cpqg{grid-template-columns:minmax(0,1fr)}.cpk,.cps{grid-template-columns:96px minmax(0,1fr) 64px}.cps{grid-template-columns:96px minmax(0,1fr)}.cph2{grid-template-columns:76px repeat(8,minmax(22px,1fr));gap:2px}.cph2.hd>span{font-size:.625rem}}"""


def page(con, user: dict, editor: bool, note: str = "") -> str:
    import admin
    import home
    e = html.escape
    today = igdata.today()
    if not configured():
        body = ('<main class="wrap"><div class="cph"><div><h1>Бәсекелестер</h1></div></div><section class="cpb"><p style="font-size:.875rem;color:var(--muted)">'
                'Бұл бөлімге Meta-дан жеке кілт керек: Vercel → <project> → Environment Variables → <b>META_IG_TOKEN</b>.</p></section></main>')
        return admin.page("Бәсекелестер · EduApp", body, user, "competitors").replace("</style>", CSS + "</style>", 1)
    my = amo.kv_get(con, "comp_me") or {}
    st = amo.kv_get(con, "comp_state", {}) or {}
    order = ([my["username"]] if my.get("username") else []) + [u for u in names(con) if u != my.get("username")]
    rows = [(u, amo.kv_get(con, f"comp:{u}", {}) or {}) for u in order]
    data = [(u, en, stats(en, today)) for u, en in rows]

    def top(key):
        vals = [s[key] for _, _, s in data if s.get(key) is not None]
        return max(vals) if vals else None
    tops = {k: top(k) for k in ("followers", "posts_week", "avg_likes", "avg_comments", "er")}

    def cell(s, key, fmt):
        v = s.get(key)
        return f'<td{" class=cpx" if v is not None and v == tops.get(key) else ""}>{fmt(v) if v is not None else "—"}</td>'
    n0 = lambda v: home.num(v)
    dec = lambda v: f"{v:.1f}".replace(".", ",")
    trs = []
    for u, en, s in data:
        p = en.get("p") or {}
        us = u == my.get("username")
        pic = p.get("profile_picture_url")
        who = (f'<div class="cpa">{f"<img src={chr(34)}{e(pic)}{chr(34)} alt={chr(34)}{chr(34)} loading=lazy referrerpolicy=no-referrer>" if pic else "<i></i>"}'
               f'<div><a href="https://www.instagram.com/{e(u)}/" target="_blank" rel="noopener"><b>@{e(u)}</b></a>{"<em>біз</em>" if us else ""}'
               f'<small style="display:block">{e((p.get("name") or "")[:40])}</small></div></div>')
        if en.get("error") and not p:
            trs.append(f'<tr{" class=us" if us else ""}><td>{who}</td><td colspan="7" class="cpe">Деректер алынбады: {e(en["error"])}</td></tr>')
            continue
        since = s["since"]
        growth = (f'{"+" if since["delta"] >= 0 else "−"}{home.num(abs(since["delta"]))}<small>{since["from"][8:10]}.{since["from"][5:7]} бастап</small>'
                  if since else '—<small>бақылау басталды</small>')
        trs.append(f'<tr{" class=us" if us else ""}><td>{who}</td>' + cell(s, "followers", n0) + f'<td>{growth}</td>'
                   + cell(s, "posts_week", dec) + cell(s, "avg_likes", n0) + cell(s, "avg_comments", n0)
                   + cell(s, "er", lambda v: dec(v) + "%") + f'<td>{str(s["reels"]) + "%" if s["reels"] is not None else "—"}</td></tr>')
    table = ('<div class="cpw"><table class="cpt"><thead><tr><th>Аккаунт</th><th>Жазылушы</th><th>Өсім</th><th>Жарияланым / апта</th>'
             '<th>Орташа лайк</th><th>Орташа коммент</th><th>ER</th><th>Рилс үлесі</th></tr></thead><tbody>' + "".join(trs) + '</tbody></table></div>')

    me_u = my.get("username") or ""
    signed = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + _dec(abs(v), 2) + "%"
    has_growth = any(s.get("growth") is not None for _, _, s in data)
    panels = "".join([
        rank_panel("Жазылушы", "Қазіргі саны", data, "followers", _num, me_u),
        rank_panel("Жазылушы өсімі", "Бақылау басталған күннен бері, %" if has_growth else "Жазылушы саны күн сайын жазылады: өсім ертеңнен шығады",
                   data, "growth", signed, me_u),
        rank_panel("Жарияланым / апта", "Соңғы 30 күн", data, "posts_week", lambda v: _dec(v), me_u),
        rank_panel("Орташа лайк", "Соңғы 12 жарияланым", data, "avg_likes", _num, me_u),
        rank_panel("Орташа коммент", "Соңғы 12 жарияланым", data, "avg_comments", _num, me_u),
        rank_panel("Белсенділік · ER", "(Лайк + коммент) ÷ жазылушы. Аккаунт көлеміне тәуелді емес", data, "er", lambda v: _dec(v, 2) + "%", me_u),
    ])
    compare = (f'<div class="cps2"><h2>Салыстыру</h2><p>Әр көрсеткіш бойынша кім алда. Біздің аккаунт күлгін түспен</p></div>'
               f'<div class="cpqg">{panels}</div><div class="cpg2 cpz">{mix_panel(data, me_u)}{activity_panel(data, me_u)}</div>')

    posts = []
    for u, en, s in data:
        fol = s["followers"] or 0
        for m in s["recent"]:
            score = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
            posts.append((score / fol if fol else 0, score, u, m))
    posts.sort(key=lambda x: (-x[0], -x[1]))
    kind = {"REELS": "Рилс", "FEED": "Пост", "STORY": "Сторис"}
    label = lambda m: "Карусель" if m.get("media_type") == "CAROUSEL_ALBUM" else kind.get(m.get("media_product_type"), "Пост")
    cards = "".join(
        f'<a href="{e(m.get("permalink") or "#")}" target="_blank" rel="noopener"><div class="ph">{label(m)}'
        + (f'<img src="{e(picture(m))}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">' if picture(m) else "")
        + '</div>'
        f'<div class="tx"><b>@{e(u)}</b><span>{label(m)} ·{(m.get("timestamp") or "")[8:10]}.{(m.get("timestamp") or "")[5:7]}</span><br>'
        f'{home.num(m.get("like_count")) if m.get("like_count") is not None else "—"} лайк · {home.num(m.get("comments_count"))} коммент</div></a>'
        for _, _, u, m in posts[:8]) or '<p class="cpn">Соңғы 30 күнде жарияланым табылмады.</p>'
    top_box = (f'<section class="cpb"><h2>Ең белсенді жарияланымдар · 30 күн</h2><p>Барлық аккаунттан, жазылушы санына шаққандағы лайк пен коммент бойынша</p>'
               f'<div class="cpp">{cards}</div></section>')

    manage = ""
    if editor:
        chips = "".join(f'<form method="post" action="/competitors"><input type="hidden" name="remove" value="{e(u)}">'
                        f'<button type="submit" aria-label="@{e(u)} тізімнен алу">@{e(u)} <span aria-hidden="true">×</span></button></form>' for u in names(con))
        manage = (f'<section class="cpb cpm"><h2>Тізім</h2><p>Профиль сілтемесін не никті жазыңыз. Аккаунт бизнес не автор аккаунты болуы керек</p>'
                  f'<form class="f" method="post" action="/competitors"><label>Instagram аккаунты<input name="add" placeholder="competitor.kz немесе instagram.com/competitor.kz" required></label>'
                  f'<button class="btnp" type="submit">Қосу</button></form><div class="cpl">{chips}</div></section>')

    upd = max([en.get("at") or 0 for _, en in rows] or [0])
    when = f'жаңартылды {datetime.fromtimestamp(upd, igdata.TZ):%d.%m %H:%M}' if upd else "әлі жаңартылмады"
    err = f'<div class="msg err">Meta-дан деректер алынбады: {e(st["error"])}</div>' if st.get("error") else ""
    body = (f'<main class="wrap"><div class="cph"><div><h1>Бәсекелестер</h1><p>Instagram-дағы ашық деректер · {when}. '
            f'Қамту мен қаралымды Meta тек өз аккаунтыңа береді, сондықтан салыстыру жазылушы, жарияланым және белсенділік бойынша.</p></div></div>'
            f'{admin.msg(note) if note else ""}{err}{table}{compare}<div style="margin-top:16px">{top_box}</div>{manage}'
            f'<p class="cpn">Ең жоғары мән қалың әріппен. Өсім — бақылау басталған күннен бері, 30 күннен кейін соңғы 30 күндікі. '
            f'Лайкты жасырған аккаунттың орташа лайгы мен ER-і шықпайды.</p></main>')
    import charts  # the shared hover/touch tooltip for every [data-tip] mark
    body = body.replace("</main>", charts.CSS + charts.JS + "</main>", 1)
    return admin.page("Бәсекелестер · EduApp", body, user, "competitors").replace("</style>", CSS + "</style>", 1)
