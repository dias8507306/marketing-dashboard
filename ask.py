"""«Ask anything»: a question about our numbers, answered by an AI model from a compact table of the last 60 days,
plus ready-made questions (buttons) that are computed here without any AI.

The AI part needs one Vercel variable: GEMINI_API_KEY (Google, free tier) or ANTHROPIC_API_KEY (Claude, paid);
Gemini is used when both are set. The model gets only aggregated numbers (per day: leads, sales, amount, ad spend,
Instagram metrics; posts with their stats) — no names or phone numbers.
"""
import json
import os
from datetime import timedelta

import ads
import amo
import igdata

MODEL = os.getenv("ASK_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_MODELS = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-2.5-flash-lite"]
DAYS = 60
LAST_ERROR: dict = {}


def gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def configured() -> bool:
    return bool(gemini_key() or os.getenv("ANTHROPIC_API_KEY", "").strip())


async def context(http, api, auth, con) -> str:
    today = igdata.today()
    first = today - timedelta(days=DAYS - 1)
    mk = amo.daily(con, int(first.timestamp()), DAYS)
    tf = ads.target_filter(con)
    tg = amo.daily(con, int(first.timestamp()), DAYS, tf) if tf else None
    spend = ads.load(con)
    ig = await igdata.days(http, api, auth, con, first, today)
    lines = ["date|weekday|leads|sales|amount_kzt|target_leads|target_sales|target_amount|ad_spend|ig_views|ig_reach|ig_new_followers|ig_likes|ig_comments|direct_writers"]
    for i in range(DAYS):
        d = first + timedelta(days=i)
        k = igdata.key(d)
        r = ig.get(k, {})
        t = tg[i] if tg else {}
        dm = igdata.direct_messages(con, int(d.timestamp()), int((d + timedelta(days=1)).timestamp()))
        lines.append("|".join(str(x if x is not None else "") for x in (
            k, d.strftime("%a"), mk[i]["leads"], mk[i]["sales"], mk[i]["amount"], t.get("leads"), t.get("sales"), t.get("amount"), spend.get(k),
            r.get("views"), r.get("reach"), r.get("new_followers"), r.get("likes"), r.get("comments"), dm or None)))
    posts = await igdata.media(http, api, auth, con, today - timedelta(days=29), today)
    plines = ["published|type|caption|views|reach|likes|comments|saves|shares"]
    for m in posts:
        plines.append("|".join(str(x if x is not None else "") for x in (
            (m.get("timestamp") or "")[:10], m.get("media_product_type") or m.get("media_type"),
            (m.get("caption") or "").replace("\n", " ").replace("|", "/")[:80], m.get("views"), m.get("reach"),
            m.get("like_count") or m.get("likes"), m.get("comments_count"), m.get("saved") or m.get("saves"), m.get("shares"))))
    hours = amo.hour_counts(con, int((today - timedelta(days=1)).timestamp()), int(today.timestamp()))
    usual = amo.hour_counts(con, int((today - timedelta(days=29)).timestamp()), int((today - timedelta(days=1)).timestamp()))
    hlines = ["hour|leads_yesterday|avg_leads_per_day_last_28_days"] + [
        f"{h:02d}|{hours[h]}|{round(usual[h] / 28, 1)}" for h in range(24)]
    st = amo.settings(con)
    mon = today - timedelta(days=today.weekday())
    weeks = (f"Weekday today: {['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][today.weekday()]}. "
             f"«This week» = {igdata.key(mon)}..{igdata.key(today)}; «last week» = {igdata.key(mon - timedelta(days=7))}..{igdata.key(mon - timedelta(days=1))} "
             f"(Monday to Sunday); «this month» = {igdata.key(today.replace(day=1))}..{igdata.key(today)}. ")
    return (weeks + f"Today: {igdata.key(today)} (Astana time). Marketing deals = amoCRM deals with source in {st.get('sources') or 'any'}. "
            f"Target = deals from targeted ads{'' if tf else ' (not configured: target columns empty)'}. "
            "A lead = a deal created that day; a sale = a deal won that day, amount in tenge.\n\n"
            "DAILY\n" + "\n".join(lines) + "\n\nPOSTS (last 30 days)\n" + "\n".join(plines)
            + "\n\nLEADS BY HOUR (Astana)\n" + "\n".join(hlines))


SYSTEM = ("You are the marketing assistant of EduApp (online olympiad preparation for school children in Kazakhstan). "
          "Questions about our numbers (sales, leads, Instagram, ads, posts, plans) you answer only from the data given, never invent numbers. "
          "Any other question — ideas for posts and reels, captions, scripts, slogans, poems, Kazakh literature, marketing advice, "
          "general knowledge — you answer fully from your own knowledge, like a helpful creative colleague; never refuse it because "
          "it is not in the data. Always answer in the same language as the question (Russian question → Russian answer, Kazakh → Kazakh), "
          "for number questions short and plain: the number first, then one or two sentences of explanation. Format numbers with spaces "
          "(142 400 ₸). If a question about our numbers cannot be answered from the data, say what is missing. No emoji. "
          "For «why» questions (why few leads, why sales fell): compare the day with the average of the same weekday in the previous "
          "4 weeks and with the last 7 days; look at Instagram reach and views, the number and kind of posts that day and the day before, "
          "ad spend, and the hours when leads came; give at most three likely reasons, each with its number, then one concrete thing "
          "to do today. Write for a director, not an analyst: simple words, no column names.")


async def answer(http, api, auth, con, question: str) -> str:
    if not configured():
        return "AI сұрақтары әлі қосылмаған: Vercel-ге GEMINI_API_KEY қосу керек. Әзірге дайын сұрақ батырмаларын қолданыңыз."
    ctx = await context(http, api, auth, con)
    kazakh = any(ch in question.lower() for ch in "әғқңөұүһі")
    question = question[:500] + (" (Answer in Kazakh.)" if kazakh else " (Answer in Russian.)")
    if gemini_key():
        payload = json.dumps({"systemInstruction": {"parts": [{"text": SYSTEM}]},
                              "contents": [{"role": "user", "parts": [{"text": f"<data>\n{ctx}\n</data>\n\nQuestion: {question}"}]}],
                              "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.2}})
        code = None
        for model in GEMINI_MODELS:  # a busy or missing model: try the next one
            try:
                r = await http.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", timeout=25,
                                    headers={"x-goog-api-key": gemini_key(), "content-type": "application/json"}, content=payload)
            except Exception as e:
                LAST_ERROR[model] = type(e).__name__
                continue
            code = r.status_code
            if r.status_code == 200:
                parts = ((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                text = "".join(x.get("text", "") for x in parts if not x.get("thought")).strip()
                if text:
                    LAST_ERROR["model"] = model
                    return text
            LAST_ERROR[model] = r.text[:160]
        return f"Қазір жауап алу мүмкін болмады ({code or 'timeout'}). Бір минуттан кейін қайталаңыз."
    r = await http.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
        "x-api-key": os.getenv("ANTHROPIC_API_KEY", "").strip(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
        content=json.dumps({"model": MODEL, "max_tokens": 1500, "system": SYSTEM,
                            "messages": [{"role": "user", "content": f"<data>\n{ctx}\n</data>\n\nQuestion: {question}"}]}))
    if r.status_code != 200:
        return f"Жауап алу мүмкін болмады ({r.status_code}). Кейінірек қайталаңыз."
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip() or "Жауап бос келді."


def _money(n) -> str:
    return f"{round(n or 0):,}".replace(",", " ") + " ₸"


def _pct(a, b) -> str:
    if not b:
        return ""
    d = round((a - b) / b * 100)
    return f" ({'+' if d >= 0 else '−'}{abs(d)}% алдыңғымен салыстырғанда)"


PRESETS = [("week", "Өткен апта"), ("best_day", "Айдың ең жақсы күні"), ("sources", "Таргет пен органика"),
           ("forecast", "Ай соңына болжам")]


def preset(con, key: str) -> str:
    """Answers to the ready-made questions, computed straight from the deals (no AI, always free)."""
    today = igdata.today()
    if key == "week":
        mon = today - timedelta(days=today.weekday() + 7)
        a, b = int(mon.timestamp()), int((mon + timedelta(days=7)).timestamp())
        cur, prev = amo.numbers(con, a, b), amo.numbers(con, a - 7 * 86400, a)
        return (f"Өткен апта ({mon:%d.%m}–{mon + timedelta(days=6):%d.%m}):\n"
                f"Сатылым: {_money(cur['amount'])}{_pct(cur['amount'], prev['amount'])}\n"
                f"Сатылым саны: {cur['sales']} · Лид: {cur['leads']}{_pct(cur['leads'], prev['leads'])}\n"
                f"Конверсия: {round(cur['sales'] / cur['leads'] * 100, 1) if cur['leads'] else 0}%")
    if key == "best_day":
        first = today.replace(day=1)
        days = amo.daily(con, int(first.timestamp()), today.day)
        i = max(range(len(days)), key=lambda k: days[k]["amount"])
        j = max(range(len(days)), key=lambda k: days[k]["leads"])
        return (f"Сатылым бойынша: {(first + timedelta(days=i)):%d.%m} — {_money(days[i]['amount'])} ({days[i]['sales']} сатылым)\n"
                f"Лид бойынша: {(first + timedelta(days=j)):%d.%m} — {days[j]['leads']} лид")
    if key == "sources":
        st = amo.settings(con)
        field, values = st.get("source_field"), st.get("sources") or []
        if not field or not values:
            return "Баптауда «Қайдан келді» өрісі мен мәндері таңдалмаған."
        a, b = int(today.replace(day=1).timestamp()), int((today + timedelta(days=1)).timestamp())
        lines = [f"Осы ай ({today:%m.%Y}):"]
        for v in values:
            n = amo.numbers(con, a, b, {"field": field, "values": [v]})
            conv = round(n["sales"] / n["leads"] * 100, 1) if n["leads"] else 0
            lines.append(f"{v}: {n['leads']} лид · {n['sales']} сатылым · {_money(n['amount'])} · конверсия {conv}%")
        return "\n".join(lines)
    if key == "forecast":
        first = today.replace(day=1)
        import calendar
        dim = calendar.monthrange(today.year, today.month)[1]
        n = amo.numbers(con, int(first.timestamp()), int((today + timedelta(days=1)).timestamp()))
        per_day = n["amount"] / today.day
        return (f"{today.day} күнде: {_money(n['amount'])}. Орташа күніне {_money(per_day)}.\n"
                f"Осы қарқынмен ай соңында ≈ {_money(per_day * dim)} болады.")
    return "Белгісіз сұрақ."


CARD = """<article class="card cardin askc" style="--i:6;margin-top:18px">
<div class="askh"><span class="aski"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9Z"/><path d="M19 15l.8 1.9 1.9.8-1.9.8L19 20.5l-.8-1.9-1.9-.8 1.9-.8Z"/></svg></span>
<div><h2>Сұрақ қойыңыз</h2><p class="asks">AI-талдаушы · соңғы 60 күн</p></div></div>
<div class="askp">__PRESETS__</div>
__FORM__<div id="aska" class="aska" hidden><div class="askq" id="askqv"></div><div class="askt" id="askt"></div></div></article>
<style>
.askc{padding:22px}.askh{display:flex;gap:14px;align-items:center;margin-bottom:18px}.askh h2{margin:0;font-size:1.25rem;font-weight:600;letter-spacing:-.02em}.asks{margin:2px 0 0;font-size:0.8125rem;color:var(--muted)}
.aski{width:48px;height:48px;flex:none;border-radius:10px;display:grid;place-items:center;color:var(--gilt);background:var(--board)}
.aski svg{width:20px;height:20px}
.askp{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
.askp button{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:0 16px;border-radius:999px;border:0;background:var(--surface2);
color:var(--text);font:inherit;font-size:0.8125rem;font-weight:600;cursor:pointer;transition:border-color .15s,background .15s}
.askp button:hover{background:color-mix(in srgb,#7336F7 14%,var(--surface2))}.askp svg{width:15px;height:15px;color:#7336F7}
.askf{display:flex;align-items:center;gap:6px;padding:6px 6px 6px 16px;border-radius:10px;border:1px solid var(--border);background:var(--surface2);transition:border-color .15s,box-shadow .15s}
.askf:focus-within{border-color:#7336F7;box-shadow:0 0 0 4px color-mix(in srgb,#7336F7 15%,transparent)}
.askf input{flex:1;min-width:0;border:0 !important;outline:0 !important;background:transparent !important;box-shadow:none !important;height:46px;padding:0 !important;font:inherit;font-size:1rem;font-weight:600;color:var(--text)}
.askf button{height:46px;padding:0 20px;border:0;border-radius:8px;color:var(--on-accent);font:inherit;font-weight:600;cursor:pointer;background:var(--accent);display:inline-flex;align-items:center;gap:6px}
.askf button svg{width:16px;height:16px}
.aska{margin-top:14px;border-radius:10px;background:color-mix(in srgb,#7336F7 7%,var(--surface));border:1px solid color-mix(in srgb,#7336F7 18%,transparent);padding:14px 16px}
.askq{font-size:0.8125rem;font-weight:600;color:var(--accent);margin-bottom:8px}
.askt{white-space:pre-wrap;line-height:1.7;font-size:0.9375rem;font-weight:600}
.askt.load{color:var(--muted)}.askt.load:after{content:"";display:inline-block;width:14px;animation:dots 1.2s steps(4) infinite;overflow:hidden;vertical-align:bottom}
@keyframes dots{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}
@media (prefers-reduced-motion:reduce){.askt.load:after{animation:none;content:"..."}}
@media (max-width:560px){.askf button span{display:none}.askp button{flex:1 1 calc(50% - 8px);justify-content:center}}
</style>
<script>async function askGo(body,label){var box=document.getElementById('aska'),t=document.getElementById('askt');box.hidden=false;
document.getElementById('askqv').textContent=label;t.className='askt load';t.textContent='Есептеп жатыр';
try{var r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});var d=await r.json();t.className='askt';t.textContent=d.answer||'Қате'}
catch(err){t.className='askt';t.textContent='Қате, қайта көріңіз'}}
document.querySelectorAll('[data-preset]').forEach(function(b){b.onclick=function(){askGo({preset:b.dataset.preset},b.textContent.trim())}});
var f=document.getElementById('askf');if(f)f.onsubmit=function(e){e.preventDefault();var q=document.getElementById('askq').value.trim();
if(!q){document.getElementById('askq').focus();return}askGo({q:q},q)}</script>"""


ICONS = {
    "week": '<path d="M8 2v4M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/>',
    "best_day": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "sources": '<path d="M21.2 15.9A10 10 0 1 1 8 2.8"/><path d="M22 12A10 10 0 0 0 12 2v10Z"/>',
    "forecast": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
}

FORM = """<form id="askf" class="askf"><input id="askq" maxlength="500" placeholder="Өз сұрағыңыз: қай күні лид ең көп болды?" autocomplete="off">
<button type="submit"><span>Сұрау</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form>"""


def card() -> str:
    btns = "".join(f'<button type="button" data-preset="{k}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                   f'stroke-linecap="round" stroke-linejoin="round">{ICONS.get(k, "")}</svg>{t}</button>' for k, t in PRESETS)
    return CARD.replace("__PRESETS__", btns).replace("__FORM__", FORM if configured() else
                                                    '<p class="note">Өз сұрағыңызды жазу үшін Vercel-ге GEMINI_API_KEY қосу керек (тегін).</p>')


CARD_OFF = """<article class="card cardin askc" style="--i:6;margin-top:18px"><div class="ch"><h2>Сұрақ қойыңыз</h2><span class="meta">AI-талдаушы</span></div>
<p class="note">«Кез келген сұрақ» мүмкіндігі дайын, бірақ әлі қосылмаған: Vercel → Environment Variables бөліміне ANTHROPIC_API_KEY (Anthropic кілті) қосу керек.
Кілт қосылғанда мұнда сұрақ жолы шығады: «өткен аптада таргеттен қанша сатылым болды?» деген сияқты.</p></article>"""
