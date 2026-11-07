"""Trends: what people talk about today and what everyone watches this week, and how EduApp can use it in posts,
stories, reels.

Sources: Google Trends (most searched today, KZ and US), news feeds (Tengrinews ru/kz, BBC sport/science/technology/world), Wikipedia (most read
pages of the last 7 days, ru and kk), YouTube (most popular videos in Kazakhstan, needs YOUTUBE_API_KEY), and Gemini
with Google Search when the key's plan allows it. Gemini (GEMINI_API_KEY, already used by «Сұрақ қойыңыз») picks what
fits a brand for school children and parents: 6 «hot» topics (videos, songs, series, games, memes everyone knows now)
and 8 news stories of the day, with ideas in Kazakh and Russian. Every item keeps a picture when its source has one.

kv `trends` = {"at", "items": [...], "tip_kk", "tip_ru", "sources": [{"n", "src", "title", "url", "img", "views"}],
"web": [{"title", "url"}], "model", "error", "search_error", "src_errors"}. Refreshed every morning and by the button.
"""
import asyncio
import html
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus

import amo
import igdata

log = logging.getLogger("trends")
GT = "{https://trends.google.com/trending/rss}"
MRSS = "{http://search.yahoo.com/mrss/}"
UA = {"User-Agent": "EduAppMarketing/1.0 (https://dashboard.eduapp.example.com; trends)"}
WIKI = (("ru", "Wikipedia · орысша", 16), ("kk", "Wikipedia · қазақша", 8))  # most read pages of the last 7 days
# pages that are always on top and say nothing about this week, or that the brand must never touch
WIKI_SKIP = re.compile(r"(?i)^(заглавная_страница|басты_бет|main_page|список_умерших|умершие_в|imgsrc|xxx|порн|секс|-$)")
FEEDS = (  # key, name shown on the page, url, how many items go to the AI
    ("gt_kz", "Google Trends · Қазақстан", "https://trends.google.com/trending/rss?geo=KZ", 10),
    ("gt_world", "Google Trends · әлем (АҚШ)", "https://trends.google.com/trending/rss?geo=US", 10),
    ("gt_gb", "Google Trends · Ұлыбритания", "https://trends.google.com/trending/rss?geo=GB", 8),
    # the world: BBC (English; the AI writes about it in Kazakh and Russian), topics children and parents care about
    ("bbc_sport", "BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", 15),
    ("bbc_science", "BBC · ғылым", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", 12),
    ("bbc_tech", "BBC · технология", "https://feeds.bbci.co.uk/news/technology/rss.xml", 12),
    ("bbc_world", "BBC · әлем", "https://feeds.bbci.co.uk/news/world/rss.xml", 12),
    ("tengri_ru", "Tengrinews", "https://tengrinews.kz/news.rss", 20),
    ("tengri_kz", "Tengrinews · қазақша", "https://kaz.tengrinews.kz/news.rss", 15),
)
MODELS = [m for m in dict.fromkeys([os.getenv("TRENDS_MODEL", "gemini-3.5-flash"), "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                                     "gemini-flash-latest"]) if m]
FORMATS = ("Рилс", "Сторис", "Пост", "Карусель")


def configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


async def _feed(http, key: str, name: str, url: str, limit: int) -> list:
    try:
        r = await http.get(url, headers={"User-Agent": "Mozilla/5.0 (EduAppMarketing trends)"}, timeout=25, follow_redirects=True)
        root = ET.fromstring(r.content)
    except Exception as e:
        log.warning("feed %s: %s", key, type(e).__name__)
        return []
    out = []
    ch = root.find("channel")
    for it in (ch if ch is not None else root).findall("item")[:limit]:
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        row = {"src": name, "title": title[:200], "url": (it.findtext("link") or "").strip(), "img": _picture(it)}
        if key.startswith("gt_"):  # a search term: its traffic and the first news story about it
            row["traffic"] = (it.findtext(GT + "approx_traffic") or "").strip()
            row["img"] = (it.findtext(GT + "picture") or "").strip()
            news = it.find(GT + "news_item")
            if news is not None:
                row["news"] = (news.findtext(GT + "news_item_title") or "").strip()[:200]
                row["url"] = (news.findtext(GT + "news_item_url") or "").strip()
            else:
                row["url"] = "https://www.google.com/search?q=" + quote_plus(title)
        out.append(row)
    return out


def _picture(it) -> str:
    """The item's picture: media:content / media:thumbnail / an image enclosure / the first <img> in its text."""
    for tag in (MRSS + "content", MRSS + "thumbnail"):
        el = it.find(tag)
        if el is not None and el.get("url") and "image" in (el.get("type") or "image") and el.get("medium") != "video":
            return re.sub(r"(ichef\.bbci\.co\.uk/ace/standard/)\d+/", r"\g<1>800/", el.get("url"))  # BBC sends 240px, 800px exists
    enc = it.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image") and enc.get("url"):
        return enc.get("url")
    text = (it.findtext("description") or "") + (it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or "")
    m = re.search(r'<img[^>]+src="(https?://[^"]+)"', text)
    return m.group(1) if m else ""


async def _wiki(http, lang: str, name: str, limit: int) -> list:
    """The pages read most in the last 7 days and in the last 30 days (daily tops summed), with their short description
    and picture: the week shows what is loud now, the month — the biggest stories of the month."""
    today = igdata.today()
    days = [today - timedelta(days=d) for d in range(1, 31)]

    async def top(d):
        try:
            r = await http.get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{d:%Y/%m/%d}",
                               headers=UA, timeout=15)
            return r.json()["items"][0]["articles"] if r.status_code == 200 else []
        except Exception:
            return []
    week, month = {}, {}
    for i, arts in enumerate(await asyncio.gather(*(top(d) for d in days))):
        for a in arts:
            t = a.get("article") or ""
            if ":" in t or WIKI_SKIP.match(t):
                continue
            month[t] = month.get(t, 0) + (a.get("views") or 0)
            if i < 7:
                week[t] = week.get(t, 0) + (a.get("views") or 0)
    best = [t for t, _ in sorted(week.items(), key=lambda x: -x[1])[:limit]]
    best += [t for t, _ in sorted(month.items(), key=lambda x: -x[1])[:limit] if t not in best]

    async def summary(t):
        row = {"src": name, "title": t.replace("_", " ")[:200], "url": f"https://{lang}.wikipedia.org/wiki/{quote(t)}",
               "views": week.get(t, 0), "views_month": month.get(t, 0), "img": ""}
        try:
            r = await http.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(t, safe='')}", headers=UA, timeout=15)
            if r.status_code == 200:
                j = r.json()
                row.update(title=(j.get("title") or row["title"])[:200], news=(j.get("description") or "")[:160],
                           img=((j.get("thumbnail") or {}).get("source") or ""))
        except Exception:
            pass
        return row
    return list(await asyncio.gather(*(summary(t) for t in best)))


async def _youtube(http) -> tuple[list, str]:
    """The most popular videos in Kazakhstan right now (YouTube's own chart), with views and covers."""
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        return [], ""
    try:
        r = await http.get("https://www.googleapis.com/youtube/v3/videos", timeout=15, params={
            "part": "snippet,statistics", "chart": "mostPopular", "regionCode": "KZ", "maxResults": 25, "key": key})
        if r.status_code != 200:
            return [], f"YouTube: {r.status_code} {((r.json().get('error') or {}).get('message') or '')[:120]}"
    except Exception as e:
        return [], f"YouTube: {type(e).__name__}"
    out = []
    for v in r.json().get("items") or []:
        sn, stat = v.get("snippet") or {}, v.get("statistics") or {}
        th = sn.get("thumbnails") or {}
        out.append({"src": "YouTube · Қазақстан", "title": (sn.get("title") or "")[:200], "news": (sn.get("channelTitle") or "")[:80],
                    "url": f"https://www.youtube.com/watch?v={v.get('id')}", "views": int(stat.get("viewCount") or 0),
                    "img": (th.get("high") or th.get("medium") or th.get("default") or {}).get("url", "")})
    return out, ""


async def sources(http) -> tuple[list, list]:
    """All sources at once, numbered so the AI can point at what it used; plus what could not be read."""
    feeds, wikis, (yt, yt_err) = await asyncio.gather(asyncio.gather(*(_feed(http, *f) for f in FEEDS)),
                                                      asyncio.gather(*(_wiki(http, *w) for w in WIKI)), _youtube(http))
    rows = yt + [r for g in wikis for r in g] + [r for g in feeds for r in g]
    for i, r in enumerate(rows, 1):
        r["n"] = i
    errors = [yt_err] if yt_err else []
    errors += [f"{name}: оқылмады" for (key, name, *_), g in zip(FEEDS, feeds) if not g]
    return rows, errors


SYSTEM = (
    "You are the trend scout and creative director of EduApp (eduapp_demo on Instagram): an online learning platform for "
    "school children in Kazakhstan, grades 1-11 — mathematics, preparation for the «Алтын сақа» olympiad (the district stage is "
    "now), English. The audience is Kazakh-speaking parents and their children. Our posts: math problems «write the answer», "
    "carousels with olympiad tasks, reels with a teacher, English vocabulary.\n"
    "Your job is newsjacking: take what people talk about right now and turn it into EduApp content that is clever, positive "
    "and useful — a math problem, a fact, a quiz, an English phrase or a learning lesson built around the story, with a hook in "
    "the first second.\n"
    "Never use (skip the story entirely): deaths, tragedies, accidents, disasters, violence, crime with victims, war, politics, "
    "elections, religion, 18+, alcohol, betting and bookmakers, gambling, scandals about private people. Politics means also "
    "governments, ministers, appointments, diplomacy, international security and negotiations, sanctions, protests; crime means "
    "also any incident with police, a court or the law, even about school children. Sport, technology, "
    "culture, films, music, games, science, viral internet moments, records, business news and finance curiosities are welcome "
    "(for money or crypto stories: no investment advice, only the math or the lesson in it).\n"
    "Answer with JSON only, no other text.")

SEARCH_ON = ("Also use Google Search to find what is loudest right now on TikTok, Instagram, YouTube and in the news, "
             "in Kazakhstan and in the world.")
SEARCH_OFF = "Google Search is not available today: use only the items below and what you know."

PROMPT = """Today is {today} (Astana). Below are numbered items: the most read Wikipedia pages (views of the last 7 and 30 days),
today's Google searches (Kazakhstan, USA, UK) and today's headlines — Kazakh sites and BBC (sport, science, technology, world;
in English: write about them in Kazakh and Russian).
{search}

ABOUT US (from the marketing team):
{about}
Our own Roblox game is for Roblox and gaming news only: when a story is about Roblox or games kids play, one of its ideas may
invite to our game. Never bring the game into other topics.

We work with NEWS — real events that people discuss — not with entertainment content: never make a topic out of a YouTube
video, a blogger, a music clip, a song, a game trailer or animation, a TV show episode or a meme page.
Only stories WE CAN REALLY USE in a post for school children and parents: sport wins and records (a famous footballer's
hat-trick, a Kazakh athlete's gold), science and space, technology and AI, big tech events (a hack, a launch, a record sale)
told through numbers, school life, exams and olympiads, holidays, nature and weather records, world records.
Do not take a story only because it is loud: economy, exchange rates, adult celebrities and gossip, conflicts at school,
anything sad or negative is not for us — skip it unless the link to children and learning is obvious and positive.

WORLD FIRST: most topics must come from other countries — at least 6 of the 8 news and at least half of each other group
(sport records, science and space discoveries, technology, world records from the BBC and the searches); Kazakhstan only for
the really big Kazakh stories.

Make three groups, skipping everything forbidden; a story goes into one group only:
1. kind "news" — up to 8 positive stories of today, at least 6 of them from the world.
2. kind "hot" — up to 6 BIG NEWS of the last 7 days that almost everyone in Kazakhstan has heard of, parents and children alike
   (a historic match, a record, a famous launch or hack, a national success); use the Wikipedia 7-day views and today's searches
   to judge how big a story is.
3. kind "month" — up to 6 of the MOST POPULAR stories of the last 30 days (the biggest events of the month that everyone still
   remembers); use the Wikipedia 30-day views. Only real events of this month, never invent one.
For each give 2 content ideas in different formats (Рилс, Сторис, Пост or Карусель). Be honest in the scores: a weak link to us
gets a low score.

JSON shape:
{{"tip_kk": "one sentence: today's main advice", "tip_ru": "the same in Russian",
 "trends": [{{"kind": "news" or "hot" or "month", "title_kk": "short title", "title_ru": "...", "what_kk": "what it is / what happened, 1-2 sentences",
   "what_ru": "...", "why_kk": "why everyone talks about it, 1 sentence", "why_ru": "...", "region": "kz" or "world",
   "category": "спорт|технология|мәдениет|ғылым|вирус|білім|музыка|ойын|фильм", "heat": 1-3 (3 = everyone talks about it),
   "fit": 1-10 (how well EduApp can use it in a post for kids and parents; 8+ = a ready strong post),
   "refs": [numbers of the items below about it — always give at least one when an item fits, its picture is shown],
   "ideas": [{{"format": "Рилс|Сторис|Пост|Карусель", "score": 1-10 (how strong: hook, link to learning, comments it will bring),
     "roblox": true if the idea uses our Roblox game, "hook_kk": "first line / first second", "hook_ru": "...",
     "idea_kk": "what exactly to show and how it ties to math, the olympiad, English or our game, 2-3 sentences", "idea_ru": "...",
     "caption_kk": "ready caption with a call to action (write the answer in the comments / + in the comments)",
     "caption_ru": "..."}}]}}]}}

Kazakh must be natural literary Kazakh (Cyrillic), Russian natural Russian. No emoji except at most one in a caption.

ITEMS
{items}"""


ABOUT_DEFAULT = ("EduApp — 1–11 сынып оқушыларына арналған онлайн платформа: математика, «Алтын сақа» олимпиадасына дайындық, "
                 "ағылшын тілі. Instagram: @eduapp_demo.\n"
                 "Бізде Roblox-та өз ойынымыз бар.")
STRONG = 7  # trends and ideas scored below this are hidden behind «show the weaker ones»


def about(con) -> str:
    return (amo.kv_get(con, "trends_about") or ABOUT_DEFAULT).strip()


def _items_text(rows: list) -> str:
    out = []
    for r in rows:
        if r["src"].startswith("YouTube"):  # videos are shown in their own strip only; the ideas are about news
            continue
        extra = f" (searches today: {r['traffic']})" if r.get("traffic") else ""
        if r.get("views_month"):
            extra += f" (views 7 days: {r.get('views') or 0:,}; 30 days: {r['views_month']:,})".replace(",", " ")
        elif r.get("views"):
            extra += f" (views: {r['views']:,})".replace(",", " ")
        news = f" — {r['news']}" if r.get("news") else ""
        out.append(f"{r['n']}. [{r['src']}] {r['title']}{extra}{news}")
    return "\n".join(out)


def views_text(n) -> str:
    """1 234 567 → «1,2 млн», 45 600 → «46 мың»."""
    if not n:
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " млн"
    if n >= 1_000:
        return f"{round(n / 1000)} мың"
    return str(n)


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON")
    return json.loads(m.group(0))


# A second guard after the AI (a weaker model sometimes lets them through): stems in Russian, Kazakh and English.
BANNED = re.compile(
    r"(?i)(\bвыбор(ы|ов|ах|ам)?\b|сайлау|\belection|президент|president|парламент|депутат|министр|правительств|үкімет|дипломат|"
    r"келіссөз|переговор|negotiat|санкци|sanction|\bвойн|соғыс|военн|әскер|\bармия|\barmy\b|\bнато\b|\bnato\b|террор|terror|"
    r"митинг|протест|полици|police|\bсуд(а|е|ом|ы)?\b|\bсот(қа|та|ы)?\b|\bзаң\b|преступ|қылмыс|\bcrime|убий|өлтір|\bkill|погиб|"
    r"\bқаза\b|қаза бол|қайтыс бол|\bөлім|смерт|\bdeath|авари|\bапат(қа|та|тан|ы|тар)?\b|\bcrash|пожар|\bөрт\b|өртен|катастроф|землетряс|жер сілкін|"
    r"наводнен|наркот|есірткі|алкогол|\bставк|казино|casino|букмекер|betting|\bсекс|\bsex\b|порн|религи|діни|\bдін\b|мешіт|"
    r"церк|самоубий|суицид|ұрлық|\bкраж|избиен|насили|зорлық|"
    # world conflicts and politicians (BBC World brings them in every day)
    r"украин|израил|\bгаз[аы]\b|палестин|\bиран|\bтрамп|\bпутин|\bзеленск|\bwar\b|missile|airstrike|\bbomb|shooting|murder|\bcourt\b)")


def _banned(t: dict) -> bool:
    """Forbidden subject, or a topic built only on YouTube videos (those stay in the video strip, ideas are about news)."""
    refs = t.get("refs") or []
    if refs and all(isinstance(r, dict) and str(r.get("src", "")).startswith("YouTube") for r in refs):
        return True
    return bool(BANNED.search(" ".join(str(t.get(k) or "") for k in ("title_kk", "title_ru", "what_kk", "what_ru", "category"))))


def _clean(data: dict, rows: list) -> dict:
    """Keep only well-formed, allowed trends and ideas; refs become links to the numbered items."""
    by_n = {r["n"]: r for r in rows}
    trends = []
    for t in (data.get("trends") or [])[:22]:
        if not isinstance(t, dict) or not (t.get("title_kk") or t.get("title_ru")) or _banned(t):
            continue
        ideas = [i for i in (t.get("ideas") or []) if isinstance(i, dict) and (i.get("idea_kk") or i.get("idea_ru"))][:3]
        refs = []
        for n in t.get("refs") or []:
            try:
                r = by_n.get(int(n))
            except (TypeError, ValueError):
                r = None
            if r and r.get("url") and not r["src"].startswith("YouTube") and r["url"] not in {x["url"] for x in refs}:
                refs.append({"src": r["src"], "title": r["title"], "url": r["url"], "img": r.get("img") or "", "views": r.get("views") or 0,
                             "views_month": r.get("views_month") or 0})
        kind = t.get("kind") if t.get("kind") in ("hot", "month") else "news"
        idea_rows = sorted([{**{k: str(i.get(k) or "")[:1200] for k in ("hook_kk", "hook_ru", "idea_kk", "idea_ru", "caption_kk", "caption_ru")},
                             "format": i.get("format") if i.get("format") in FORMATS else "Пост", "score": _num(i.get("score"), 1, 10, 6),
                             "roblox": bool(i.get("roblox"))} for i in ideas], key=lambda i: -i["score"])
        trends.append({**{k: str(t.get(k) or "")[:600] for k in ("title_kk", "title_ru", "what_kk", "what_ru", "why_kk", "why_ru", "category")},
                       "region": "kz" if t.get("region") == "kz" else "world", "heat": _num(t.get("heat"), 1, 3, 2), "refs": refs[:3],
                       "kind": kind, "fit": _num(t.get("fit"), 1, 10, 6),
                       "img": next((r["img"] for r in sorted(refs, key=lambda r: "gstatic.com" in r["img"]) if r["img"]), ""),  # big photos first
                       "views": max([r["views_month" if kind == "month" else "views"] for r in refs] or [0]),
                       "ideas": idea_rows})
    trends.sort(key=lambda t: (-t["fit"], -max([i["score"] for i in t["ideas"]] or [0])))  # the strongest first
    return {"items": trends, "tip_kk": str(data.get("tip_kk") or "")[:400], "tip_ru": str(data.get("tip_ru") or "")[:400]}


def _num(v, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return default


def strong(t: dict) -> bool:
    """A topic worth showing at once: it fits us and has at least one strong idea."""
    return t.get("fit", STRONG) >= STRONG and any(i.get("score", STRONG) >= STRONG for i in t.get("ideas") or [])


async def _ask(http, rows: list, about_us: str = ABOUT_DEFAULT) -> tuple[dict, list, str]:
    """Gemini with Google Search: the stories and ideas, the web pages it read, the model that answered."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 24000}}

    def ask(search: str) -> list:
        return [{"role": "user", "parts": [{"text": PROMPT.format(today=igdata.key(igdata.today()), search=search, about=about_us[:2000],
                                                                  items=_items_text(rows))}]}]
    with_search = json.dumps({**body, "contents": ask(SEARCH_ON), "tools": [{"google_search": {}}]})
    lists_only = json.dumps({**body, "contents": ask(SEARCH_OFF)})
    # every model with Google Search first; if none of them can search (no quota, not allowed), the lists alone
    tries = [(m, with_search) for m in MODELS] + [(m, lists_only) for m in MODELS]
    errors, started = [], time.time()
    no_search = False
    for model, payload in tries:
        if time.time() - started > 150:  # the serverless function must finish: do not start another long try
            break
        if payload is with_search and no_search:  # the key's plan has no Google Search at all: do not ask every model
            continue
        tag = model + ("" if payload is with_search else " (іздеусіз)")
        try:
            r = await http.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", timeout=110,
                                headers={"x-goog-api-key": key, "content-type": "application/json"}, content=payload)
            if r.status_code == 503 and model == MODELS[0] and time.time() - started < 90:
                # the best model is only busy for a moment: wait and ask it once more before taking a weaker one
                errors.append(f"{tag}: 503 бос емес, 15 с күтіп қайталадық")
                await asyncio.sleep(15)
                r = await http.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", timeout=110,
                                    headers={"x-goog-api-key": key, "content-type": "application/json"}, content=payload)
        except Exception as e:
            errors.append(f"{tag}: {type(e).__name__}")
            continue
        if r.status_code != 200:
            try:
                why = (r.json().get("error") or {}).get("message") or r.text
            except Exception:
                why = r.text
            errors.append(f"{tag}: {r.status_code} {why[:120]}")
            no_search = no_search or (payload is with_search and r.status_code == 429 and "quota" in why.lower())
            continue
        cand = (r.json().get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or [] if not p.get("thought"))
        try:
            data = _parse(text)
        except Exception:
            errors.append(f"{tag}: жауап JSON емес ({cand.get('finishReason') or ''})")
            continue
        web, seen = [], set()
        for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks") or []:
            w = ch.get("web") or {}
            if w.get("uri") and w.get("title") and w["title"] not in seen:
                seen.add(w["title"])
                web.append({"title": w["title"][:120], "url": w["uri"]})
        _ask.errors = errors  # why the earlier tries failed (e.g. Google Search not allowed), kept for the page
        return data, web[:12], tag
    raise RuntimeError(" | ".join(errors) or "AI жауап бермеді")


_ask.errors = []


async def refresh(http, con, max_age: int = 0) -> dict:
    """Fetch the sources and ask the AI; a failure keeps the previous ideas and records the error."""
    cur = amo.kv_get(con, "trends", {}) or {}
    if max_age and time.time() - (cur.get("at") or 0) < max_age and cur.get("items"):
        return cur
    rows, src_errors = await sources(http)
    new = {**cur, "sources": rows, "src_errors": src_errors, "tried": int(time.time())}
    if not configured():
        new["error"] = "GEMINI_API_KEY қосылмаған"
    else:
        try:
            data, web, model = await _ask(http, rows, about(con))
            new.update(_clean(data, rows), web=web, model=model, at=int(time.time()), error=None,
                       search_error=" | ".join(_ask.errors)[:900] if "іздеусіз" in model else None)
            if not new["items"]:
                new["error"] = "AI бірде-бір тақырып ұсынбады"
        except Exception as e:
            log.warning("trends AI: %s", e)
            new["error"] = str(e)[:900]
    if not new.get("at") and rows:
        new["at"] = int(time.time())
    amo.kv_set(con, "trends", new)
    return new


CSS = """.trh{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px;margin:0 0 16px}.trh h1{margin:0;font-size:1.375rem;font-weight:600;letter-spacing:-.02em}
.trh p{margin:4px 0 0;max-width:70ch;font-size:.8125rem;color:var(--muted)}.trh form{display:flex}.trh .btnp{width:auto;min-height:44px;padding:0 20px}
.trlang{display:inline-flex;padding:3px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.trlang button{min-height:36px;padding:0 14px;border:0;border-radius:7px;background:none;color:var(--muted);font:500 .8125rem 'Golos Text',sans-serif;cursor:pointer}
.trlang button[aria-pressed=true]{background:var(--board);color:var(--bink)}
.trtools{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.trtip{margin:0 0 16px;padding:14px 18px;border-radius:var(--r);background:var(--board);color:var(--bink);font-size:.875rem;line-height:1.5}.trtip b{color:var(--gilt)}
.trg{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.trg>*{min-width:0}
.trc{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px}
.trc-m{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px;font-size:.6875rem;font-weight:600;color:var(--muted)}
.trc-m span{padding:3px 8px;border-radius:6px;background:var(--surface2)}.trc-m .heat{display:inline-flex;gap:3px;background:none;padding:0}
.trc-m .heat i{width:8px;height:8px;border-radius:2px;background:var(--bar)}.trc-m .heat i.on{background:var(--orange)}
.trc h2{margin:0 0 6px;font-size:1.0625rem;font-weight:600;line-height:1.3}.trc>p{margin:0 0 4px;font-size:.8125rem;line-height:1.5;color:var(--text)}
.trc>p.why{color:var(--muted)}
.trrefs{display:flex;flex-wrap:wrap;gap:6px 12px;margin:8px 0 0;font-size:.75rem}.trrefs a{color:var(--accent)}
.tri{margin-top:14px;padding-top:14px;border-top:1px solid var(--border)}
.tri-f{display:inline-block;margin-bottom:6px;padding:2px 8px;border-radius:6px;font-size:.6875rem;font-weight:700;color:var(--on-accent,#fff);background:var(--accent)}
.tri b{display:block;font-size:.875rem;line-height:1.4;margin-bottom:4px}.tri p{margin:0 0 8px;font-size:.8125rem;line-height:1.5;color:var(--muted)}
.trcap{position:relative;padding:10px 12px;border-radius:8px;background:var(--surface2);font-size:.8125rem;line-height:1.5;white-space:pre-wrap}
.trcopy{margin-top:6px;min-height:32px;padding:0 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font:500 .75rem 'Golos Text',sans-serif;cursor:pointer}
.trcopy:hover{border-color:var(--accent);color:var(--accent)}
.trsrc{margin-top:16px}.trsrc details{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px 18px;margin-bottom:10px}
.trsrc summary{cursor:pointer;font-weight:600;font-size:.875rem}.trsrc ol{margin:10px 0 0;padding-left:20px;font-size:.8125rem;line-height:1.6}.trsrc small{color:var(--faint)}
.trempty{padding:20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:.875rem;color:var(--muted)}
.trc{overflow:hidden}.trimg{margin:-20px -20px 14px;height:180px;overflow:hidden;background:var(--surface2)}
.trimg img{display:block;width:100%;height:100%;object-fit:cover}
.trimg.sm{flex:none;width:64px;height:64px;margin:0;aspect-ratio:auto;border-radius:10px}
.trban{position:relative;margin:-20px -20px 14px;height:180px;overflow:hidden;background:color-mix(in srgb,var(--accent) 8%,var(--surface2))}
.trban img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.trban.sm .bg{filter:blur(20px) saturate(1.3);transform:scale(1.25);opacity:.75}.trban.sm .fg{object-fit:contain}
.trban span{display:none}.trban.none img{display:none}
.trban.none span{position:absolute;inset:0;display:grid;place-items:center;font-size:1.25rem;font-weight:700;color:var(--faint);text-transform:capitalize}
.trsec{margin:0 0 28px}.trsec>h2{margin:0;font-size:1.125rem;font-weight:600}.trsec>p{margin:4px 0 12px;font-size:.8125rem;color:var(--muted)}
.trstrip{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(180px,200px);gap:12px;overflow-x:auto;padding:0 0 10px;margin:0 0 16px;scroll-snap-type:x mandatory}
.trstrip a{display:block;scroll-snap-align:start;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.trstrip a:hover{border-color:var(--accent)}.trstrip .trph{aspect-ratio:16/9;background:var(--surface2)}
.trstrip .trimg{margin:0;height:100%}.trstrip b{display:block;padding:8px 10px 2px;font-size:.8125rem;font-weight:600;line-height:1.35;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.trstrip small{display:block;padding:0 10px 10px;font-size:.6875rem;color:var(--faint)}
[data-lang=ru] .kk,[data-lang=kk] .ru{display:none}
.trfilt{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 16px}.trfilt span{font-size:.75rem;color:var(--faint)}
.trfilt button{min-height:36px;padding:0 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text);font:500 .8125rem 'Golos Text',sans-serif;cursor:pointer}
.trfilt button[aria-pressed=true]{background:var(--board);color:var(--bink);border-color:var(--board)}
main:not([data-all]) .weak{display:none}main[data-rbx] .trc:not(.has-rbx),main[data-rbx] .tri:not(.rbx){display:none}
.trc.weak{opacity:.75}.trnone{padding:14px 18px;border:1px dashed var(--border);border-radius:var(--r);font-size:.8125rem;color:var(--muted)}
main[data-all] .weak-only{display:none}.tri.weak .tri-s{color:var(--faint)}
.tri-r,.tri-s,.trc-m .fit{display:inline-block;margin:0 0 6px 6px;padding:2px 8px;border-radius:6px;font-size:.6875rem;font-weight:700}
.tri-r{color:#fff;background:#E2231A}.tri-s{color:var(--muted);background:var(--surface2)}
.trc-m .fit{margin:0;color:var(--gink);background:var(--gilt)}
.trabout p{margin:10px 0 8px;font-size:.8125rem;color:var(--muted)}.trabout textarea{width:100%;box-sizing:border-box;padding:10px 12px;border:1.5px solid var(--border);
border-radius:8px;background:var(--surface2);color:var(--text);font:400 .875rem/1.5 'Golos Text',sans-serif;resize:vertical}.trabout .btnp{width:auto;margin-top:8px;padding:0 20px;min-height:44px}
@media (max-width:900px){.trg{grid-template-columns:minmax(0,1fr)}}"""

JS = """<script>(function(){var root=document.querySelector('[data-lang]');if(!root)return;
function set(l){root.dataset.lang=l;document.querySelectorAll('.trlang button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.l===l)});try{localStorage.setItem('tr-lang',l)}catch(e){}}
try{var s=localStorage.getItem('tr-lang');if(s)set(s)}catch(e){}
document.querySelectorAll('.trlang button').forEach(function(b){b.onclick=function(){set(b.dataset.l)}});
document.querySelectorAll('.trcopy').forEach(function(b){b.onclick=function(){var t=b.previousElementSibling.innerText;
 (navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(function(){b.textContent=b.dataset.ok;setTimeout(function(){b.textContent=b.dataset.t},1600)},function(){})}});
document.querySelectorAll('.trfilt button').forEach(function(b){b.onclick=function(){var on=b.getAttribute('aria-pressed')!=='true';
 b.setAttribute('aria-pressed',on);if(on)root.setAttribute('data-'+b.dataset.f,'');else root.removeAttribute('data-'+b.dataset.f)}});
var f=document.querySelector('.trh form');if(f)f.addEventListener('submit',function(){var b=f.querySelector('button');b.disabled=true;b.textContent=b.dataset.busy;document.documentElement.classList.add('zbusy')});
})();</script>"""


def error_text(err: str, has_old: bool) -> str:
    """A failed refresh in plain words; the technical text stays under «Толығырақ». The Google Search «429» is left
    out: it is the free plan and happens every time, the ideas are made without it."""
    tries = [x for x in err.split(" | ") if "(іздеусіз)" in x] or err.split(" | ")
    keep = " Алдыңғы идеялар көрсетіліп тұр." if has_old else ""
    if tries and all("503" in x for x in tries):
        why = "Google-дың AI сервері қазір шамадан тыс жүктелген (уақытша)."
        todo = " Бір-екі сағаттан кейін «Жаңарту» басыңыз, болмаса ертең таңертең өзі жаңарады."
    elif any("429" in x for x in tries):
        why = "Gemini кілтінің тегін лимиті бүгінге бітті."
        todo = " Ертең таңертең өзі жаңарады."
    elif "GEMINI_API_KEY" in err:
        why, todo = "Gemini кілті қосылмаған.", " Vercel-ге GEMINI_API_KEY қосу керек."
    else:
        why = "Соңғы жаңарту өтпеді."
        todo = " Бір сағаттан кейін қайта көріңіз; қайталанса, «Толығырақ» мәтінін әкімшіге жіберіңіз."
    return why + keep + todo


def page(con, user: dict, editor: bool, note: str = "") -> str:
    import admin
    e = html.escape
    st = amo.kv_get(con, "trends", {}) or {}
    when = datetime.fromtimestamp(st["at"], igdata.TZ).strftime("%d.%m %H:%M") if st.get("at") else "әлі жаңартылмады"

    def two(kk, ru, tag="span", cls=""):
        return f'<{tag} class="kk {cls}">{e(kk or ru)}</{tag}><{tag} class="ru {cls}">{e(ru or kk)}</{tag}>'
    button = ('<form method="post" action="/trends"><button class="btnp" type="submit" data-busy="Іздеп жатыр… (1 минуттай)">Жаңарту</button></form>'
              if editor else "")
    head = (f'<div class="trh"><div><h1>Трендтер</h1><p>Бүгін не туралы айтып жатыр және оны EduApp постына, сторисіне, рилсіне қалай айналдыруға болады. '
            f'BBC, YouTube, Wikipedia, Google Trends, Tengrinews · жаңартылды {when}. Күн сайын таңертең өзі жаңарады.</p></div>'
            f'<div class="trtools"><div class="trlang" role="group" aria-label="Тіл"><button type="button" data-l="kk" aria-pressed="true">Қазақша</button>'
            f'<button type="button" data-l="ru" aria-pressed="false">Русский</button></div>{button}</div></div>')
    err = ""
    if st.get("error"):
        err = (f'<div class="msg err">{e(error_text(st["error"], bool(st.get("items"))))}'
               f'<details style="margin-top:6px;font-size:.75rem"><summary>Толығырақ</summary>{e(st["error"])}</details></div>')
    notes = []
    if st.get("search_error") and not st.get("error"):
        notes.append("Google іздеуі қосылмаған (Gemini кілтінің тегін тарифі), идеялар тек төмендегі тізімдерден жасалды")
    if not os.getenv("YOUTUBE_API_KEY", "").strip():
        notes.append("YouTube қосылмаған: Vercel-ге YOUTUBE_API_KEY қосылса, Қазақстандағы ең көп қаралған видеолар да шығады")
    notes += st.get("src_errors") or []
    if notes and editor:
        err += f'<p style="margin:0 0 12px;font-size:.75rem;color:var(--faint)">{e(". ".join(notes))}.</p>'
    tip = (f'<div class="trtip"><b class="kk">Бүгінгі кеңес. </b><b class="ru">Совет дня. </b>{two(st.get("tip_kk"), st.get("tip_ru"))}</div>'
           if st.get("tip_kk") or st.get("tip_ru") else "")
    def banner(url: str, label: str) -> str:
        """The same 180px picture area on every card: a big photo fills it; a small one (Google Trends) sits in the middle
        on its own blurred copy; no picture, or one that does not load, leaves the category word on a quiet tint."""
        if url and "upload.wikimedia.org" in url:
            url = re.sub(r"/(\d{2,3})px-", "/640px-", url)
        none = f'<span>{e(label)}</span>'
        if not url:
            return f'<div class="trban none">{none}</div>'
        img = lambda c: (f'<img class="{c}" src="{e(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                         f'onerror="this.parentNode.className=\'trban none\'">')
        if "gstatic.com" in url:
            return f'<div class="trban sm">{img("bg")}{img("fg")}{none}</div>'
        return f'<div class="trban">{img("fg")}{none}</div>'

    def pic(url: str, big: bool) -> str:
        """A picture that removes itself when it does not load; Wikipedia thumbnails are asked for at 640px."""
        if not url:
            return ""
        url = re.sub(r"/(\d{2,3})px-", "/640px-", url) if "upload.wikimedia.org" in url and big else url
        return (f'<div class="{"trimg" if big else "trimg sm"}"><img src="{e(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                f'onerror="this.parentNode.remove()"></div>')

    def card(t: dict) -> str:
        heat = "".join(f'<i class="{"on" if k < t["heat"] else ""}"></i>' for k in range(3))
        refs = "".join(f'<a href="{e(r["url"])}" target="_blank" rel="noopener" title="{e(r["src"])}">'
                       f'{e(r["title"][:48] + ("…" if len(r["title"]) > 48 else ""))} ↗</a>' for r in t.get("refs") or [])
        q = quote_plus(t.get("title_ru") or t.get("title_kk") or "")
        refs += f'<a href="https://www.google.com/search?q={q}&tbm=nws" target="_blank" rel="noopener">Google жаңалықтары ↗</a>'
        ideas = "".join(
            f'<div class="tri{" weak" if i.get("score", STRONG) < STRONG else ""}{" rbx" if i.get("roblox") else ""}">'
            f'<span class="tri-f">{e(i["format"])}</span>{"<span class=tri-r>Roblox</span>" if i.get("roblox") else ""}'
            f'{f"<span class=tri-s title=Күші>{i["score"]}/10</span>" if i.get("score") else ""}{two(i["hook_kk"], i["hook_ru"], "b")}'
            f'{two(i["idea_kk"], i["idea_ru"], "p")}'
            + (f'<div class="kk"><div class="trcap">{e(i["caption_kk"] or i["caption_ru"])}</div>'
               f'<button type="button" class="trcopy" data-t="Мәтінді көшіру" data-ok="Көшірілді">Мәтінді көшіру</button></div>'
               f'<div class="ru"><div class="trcap">{e(i["caption_ru"] or i["caption_kk"])}</div>'
               f'<button type="button" class="trcopy" data-t="Скопировать текст" data-ok="Скопировано">Скопировать текст</button></div>'
               if i.get("caption_kk") or i.get("caption_ru") else "") + '</div>'
            for i in t.get("ideas") or [])
        region = "Қазақстан" if t["region"] == "kz" else "Әлем"
        img = t.get("img") or ""
        views = f'<span>{views_text(t["views"])} қаралым</span>' if t.get("views") else ""
        title = two(t["title_kk"], t["title_ru"], "h2")
        cls = "trc" + ("" if strong(t) else " weak") + (" has-rbx" if any(i.get("roblox") for i in t.get("ideas") or []) else "")
        fit = f'<span class="fit" title="Бізге қаншалық жарайды">{t["fit"]}/10</span>' if t.get("fit") else ""
        return (f'<article class="{cls}">{banner(img, t.get("category") or "")}<div class="trc-m">{fit}<span>{region}</span>'
                f'{f"<span>{e(t["category"])}</span>" if t.get("category") else ""}{views}'
                f'<span class="heat" title="Қаншалық шулы: {t["heat"]} / 3" aria-label="Қаншалық шулы: {t["heat"]} / 3">{heat}</span></div>'
                f'{title}{two(t["what_kk"], t["what_ru"], "p")}{two(t["why_kk"], t["why_ru"], "p", "why")}'
                f'<div class="trrefs">{refs}</div>{ideas}</article>')

    items = [t for t in st.get("items") or [] if not _banned(t)]  # also hides what older answers let through
    weak_n = sum(1 for t in items if not strong(t))
    filt = ""
    if items:
        filt = ('<div class="trfilt">'
                + (f'<button type="button" data-f="all" aria-pressed="false">Әлсіздерін де көрсету ({weak_n})</button>' if weak_n else "")
                + f'<span>Тақырып пен идеяның бағасы — бізге қаншалық жарайтыны (10 = дайын мықты пост). '
                  f'{STRONG}-ден төмендері жасырулы.</span></div>')
    hot = [t for t in items if t.get("kind") == "hot"]
    news = [t for t in items if t.get("kind") not in ("hot", "month")]
    month = [t for t in items if t.get("kind") == "month"]
    rows_all = st.get("sources") or []
    # the week's chart: YouTube's most watched in Kazakhstan (Wikipedia's top is mostly Russian celebrities: it only feeds the AI)
    chart = [r for r in rows_all if r["src"].startswith("YouTube")][:12]
    strip = ""
    if chart:
        strip = ('<div class="trstrip">' + "".join(
            f'<a href="{e(r["url"])}" target="_blank" rel="noopener"><div class="trph">{pic(r.get("img"), True)}</div>'
            f'<b>{e(r["title"][:70])}</b><small>{e(r["src"].split(" · ")[0])} · {views_text(r.get("views"))} қаралым</small></a>'
            for r in chart) + '</div>')

    def section(kk, ru, sub_kk, sub_ru, cards, extra=""):
        none_strong = ('<p class="trnone weak-only">Бүгін бұл топта бізге жарайтын мықты тақырып жоқ. '
                       'Қалғандарын «Әлсіздерін де көрсету» арқылы көруге болады.</p>' if cards and not any(strong(t) for t in cards) else "")
        return (f'<section class="trsec"><h2>{two(kk, ru)}</h2><p>{two(sub_kk, sub_ru)}</p>{extra}{none_strong}'
                + (f'<div class="trg">{"".join(card(t) for t in cards)}</div>' if cards else "") + '</section>')
    if items:
        body_cards = (section("Бүгінгі жаңалықтар", "Новости дня", "Бүгін не туралы айтып жатыр", "О чём говорят сегодня", news)
                      + section("Аптаның басты жаңалықтары", "Главные новости недели",
                                "Соңғы 7 күнде бүкіл Қазақстан естіген оқиғалар — оны балалар да, ата-аналар да біледі",
                                "События последних 7 дней, о которых слышали все — и дети, и родители", hot)
                      + (section("Айдың ең танымал жаңалықтары", "Самые популярные новости месяца",
                                 "Соңғы 30 күннің ең үлкен оқиғалары — әлі де бәрінің есінде", "Главные события последних 30 дней — их всё ещё помнят все",
                                 month) if month else "")
                      + (section("YouTube-та қазір көп қаралатындар", "Что сейчас смотрят на YouTube",
                                 "Қазақстандағы ең көп қаралған видеолар — тек анықтама үшін", "Самые просматриваемые видео в Казахстане — для справки",
                                 [], strip) if strip else ""))
    elif not configured():
        body_cards = section("Трендтер", "Тренды", "AI идеялары үшін Vercel-ге GEMINI_API_KEY қосу керек",
                             "Для идей нужен GEMINI_API_KEY в Vercel", [], strip)
    else:
        body_cards = (f'<div class="trempty">Идеялар әлі жоқ. {"«Жаңарту» батырмасын басыңыз." if editor else "Ертең таңертең пайда болады."}</div>'
                      + (section("YouTube-та қазір көп қаралатындар", "Что сейчас смотрят на YouTube", "Тек анықтама үшін", "Для справки", [], strip) if strip else ""))
    groups = {}
    for r in rows_all:
        groups.setdefault(r["src"], []).append(r)
    src = "".join(
        f'<details><summary>{e(name)} · {len(rows)}</summary><ol>'
        + "".join(f'<li><a href="{e(r["url"])}" target="_blank" rel="noopener">{e(r["title"])}</a>'
                  f'{f" <small>{e(r["traffic"])} іздеу</small>" if r.get("traffic") else ""}'
                  f'{f" <small>{views_text(r["views"])} қаралым</small>" if r.get("views") else ""}</li>' for r in rows) + '</ol></details>'
        for name, rows in groups.items())
    if st.get("web"):
        src += ('<details><summary>AI оқыған беттер (Google іздеу) · ' + str(len(st["web"])) + '</summary><ol>'
                + "".join(f'<li><a href="{e(w["url"])}" target="_blank" rel="noopener">{e(w["title"])}</a></li>' for w in st["web"]) + '</ol></details>')
    src_box = f'<section class="trsrc"><h2 style="margin:24px 0 10px;font-size:1.0625rem">Бүгінгі тізімдер</h2>{src}</section>' if src else ""
    if editor:
        src_box += (f'<section class="trsrc"><details><summary>AI-ға біз туралы</summary>'
                    f'<form method="post" action="/trends" class="trabout"><input type="hidden" name="action" value="about">'
                    f'<p>AI бізді осы мәтін бойынша біледі. Roblox ойынымызды тек Roblox пен ойын тақырыбындағы трендтерде ғана еске алады. '
                    f'Келесі жаңартудан бастап ескеріледі.</p>'
                    f'<textarea name="about" rows="7" maxlength="2000">{e(about(con))}</textarea>'
                    f'<button class="btnp" type="submit">Сақтау</button></form></details></section>')
    body = (f'<main class="wrap" data-lang="kk">{head}{admin.msg(note) if note else ""}{err}{tip}{filt}{body_cards}{src_box}'
            f'<p class="cpn" style="margin-top:12px;font-size:.75rem;color:var(--faint)">Идеяларды AI жазады: жарияламас бұрын фактілерді сілтеме арқылы тексеріңіз. '
            f'Қайғылы оқиға, саясат, дін, 18+, ставкалар әдейі алынып тасталады.</p></main>{JS}')
    return admin.page("Трендтер · EduApp", body, user, "trends").replace("</style>", CSS + "</style>", 1)
