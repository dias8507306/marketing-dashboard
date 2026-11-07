"""Instagram dashboard page for @eduapp_demo.

The server builds every number; the browser only animates: count-up figures, card tilt,
the sliding period switch, bar/area charts that draw themselves, the ER ring.
No build step and no framework, so the page stays one fast response from the bot.
"""
import html
import json
from datetime import datetime, timedelta

import ui
from igdata import TZ, key

KPIS = [  # (metric, title, hint)
    ("new_followers", "Жаңа жазылушы", "кезең ішінде жазылғандар"),
    ("reach", "Қамту", "контентті көрген адамдар"),
    ("views", "Қаралым", "барлық көрсетілім"),
    ("likes", "Лайк", "посттар мен рилстерге"),
    ("comments", "Коммент", "жазылған пікірлер"),
    ("saves", "Сақтады", "кейін қарау үшін"),
    ("shares", "Бөлісті", "достарына жіберді"),
    ("profile_views", "Профильді қарады", "профиль ашылды"),
    ("accounts_engaged", "Белсенді аккаунт", "лайк, коммент, сақтау т.б."),
]
ICONS = {
    "new_followers": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    "reach": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "views": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "likes": '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7Z"/>',
    "comments": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "saves": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
    "shares": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "profile_views": '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    "accounts_engaged": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "direct": '<path d="M4 4h16v12H5.2L4 17.2Z"/><path d="m4 4 8 7 8-7"/>',
}
METRIC_COLORS = {"new_followers": "#7336F7", "reach": "#7336F7", "views": "#2A78D6", "likes": "#f35b2f", "comments": "#d99a00",
                 "saves": "#048848", "shares": "#2A78D6", "profile_views": "#7648c3", "accounts_engaged": "#f35b2f"}
TONES = {  # icon chip colour per card
    "reach": "cyan", "views": "violet", "likes": "pink", "comments": "amber", "saves": "cyan",
    "shares": "violet", "profile_views": "pink", "accounts_engaged": "green", "direct": "amber",
}
PERIODS = [("today", "Бүгін"), ("yesterday", "Кеше"), ("7", "7 күн"), ("30", "30 күн")]
KINDS = {"REELS": "Рилс", "FEED": "Пост", "STORY": "Сторис"}
WEEKDAYS = ["дс", "сс", "ср", "бс", "жм", "сб", "жс"]
MONTHS = ["қаң", "ақп", "нау", "сәу", "мам", "мау", "шіл", "там", "қыр", "қаз", "қар", "жел"]
ER_SCALE = 10  # the ring is drawn on a 0–10 % scale


def fmt(n):
    if n is None:
        return "—"
    return f"{n:,}".replace(",", " ")


def day_label(d: datetime) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def period_title(period, first, last) -> str:
    names = dict(PERIODS)
    if first == last:
        return f"{names.get(period, '')} · {day_label(first)} ({WEEKDAYS[first.weekday()]})".lstrip(" ·")
    return f"{names.get(period, '')} · {day_label(first)} – {day_label(last)}".lstrip(" ·")


def svg(paths: str, cls: str = "ico") -> str:
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'


TREND_UP = '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>'
TREND_DOWN = '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>'


def delta_html(cur, prev, is_today):
    if is_today:
        return '<span class="delta flat">күн әлі біткен жоқ</span>'
    if cur is None or prev in (None, 0):
        return '<span class="delta flat">салыстыру жоқ</span>'
    p = (cur - prev) / prev * 100
    cls = "up" if p > 0.5 else "down" if p < -0.5 else "flat"
    icon = svg(TREND_UP if p >= 0 else TREND_DOWN, "tr")
    sign = "+" if p > 0 else "−" if p < 0 else ""
    return (f'<span class="delta {cls}">{icon}{sign}{abs(p):.1f}%</span>'
            f'<span class="was">алдыңғы: {fmt(prev)}</span>')


def number(val, cls="num") -> str:
    """Big figure that counts up from zero in the browser; plain text when there is no value."""
    if val is None:
        return f'<div class="{cls}">—</div>'
    return f'<div class="{cls}" data-to="{val}">{fmt(val)}</div>'


def saved_html(saved) -> str:
    """Strip on a single past day: the report frozen for that day and its change against the day before."""
    if not saved:
        return ""
    data, when = saved["data"], datetime.fromtimestamp(saved["ts"], TZ)
    title = {"auto": "Күн соңындағы снимок", "manual": "Қолмен сақталған снимок"}.get(saved["kind"], "Қалпына келтірілген есеп")
    parts = [f"<b>{title}</b> · {when:%d.%m %H:%M}"]
    fol, pf = data.get("followers"), (saved.get("prev") or {}).get("followers")
    if fol is not None:
        line = f"жазылушы <b>{fmt(fol)}</b>"
        if pf is not None:
            d = fol - pf
            cls = "up" if d > 0 else "down" if d < 0 else "flat"
            sign = "+" if d > 0 else "−" if d < 0 else ""
            line += f' <span class="delta {cls}">{sign}{fmt(abs(d))}</span> {html.escape(saved["prev_label"])}-мен салыстырғанда'
        parts.append(line)
    icon = ('<svg class="ico" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/>'
            '<circle cx="12" cy="13" r="3"/></svg>')
    return f'<div class="saved">{icon}{" · ".join(parts)}<a href="archive">Барлық есептер →</a></div>'


def ig_canvas(chart_days: dict, all_days: dict) -> str:
    """One canvas line with tabs (new followers / reach / views / likes / comments); the dotted line is the same
    number of days just before, when those days are known."""
    import charts
    keys = list(chart_days.keys())
    if not keys:
        return ""
    n = len(keys)
    labels = [day_label(datetime.strptime(k, "%Y-%m-%d")) for k in keys]

    def prev_key(k):
        return key(datetime.strptime(k, "%Y-%m-%d") - timedelta(days=n))

    series = []
    for m, tab, label in (("new_followers", "Жазылушы", "Жаңа жазылушы"), ("reach", "Қамту", "Қамту"), ("views", "Қаралым", "Қаралым"),
                          ("likes", "Лайк", "Лайк"), ("comments", "Коммент", "Коммент")):
        cur = [(chart_days.get(k) or {}).get(m) or 0 for k in keys]
        prev = [(all_days.get(prev_key(k)) or {}).get(m) for k in keys]
        full = all(v is not None for v in prev)
        series.append({"tab": tab, "label": f"{label} · {n} күн", "cur": cur, "prev": prev if full else None, "total": sum(cur),
                       "delta": charts.delta(sum(cur), sum(prev)) if full else None, "unit": "", "unitBig": ""})
    return charts.CSS + charts.canvas("Instagram динамикасы", series, labels, prev_label=f"алдыңғы {n} күнмен", last_label="соңғы") + charts.JS


def render(*, me: dict, period: str, first: datetime, last: datetime, cur: dict, prev: dict,
           chart_days: dict, posts: list, today_key: str, net_today, errors: list, updated: str, net_range=None,
           saved: dict | None = None, user: dict | None = None, all_days: dict | None = None) -> str:
    is_today = first == last and key(first) == today_key
    fol = me.get("followers_count")

    series_keys = list(chart_days.keys())[-14:]
    series = {m: [(chart_days.get(k) or {}).get(m) or 0 for k in series_keys] for m in METRIC_COLORS}

    def pct(val, pval):
        if is_today or val is None or not pval:
            return None
        q = round((val - pval) / pval * 100)
        return None if abs(q) > 300 else q

    cards = []
    for i, (metric, title, hint) in enumerate(KPIS):
        val, pval = cur.get(metric), prev.get(metric)
        sub = hint
        if metric == "new_followers" and is_today:
            val = net_today
            sub = "таза өсім · толық санды Instagram ертең береді" if net_today is not None else \
                "Instagram бүгінгі санды ертең береді"
        if metric == "new_followers" and not is_today and val is not None and net_range is not None and val - net_range >= 0:
            sub = f"жазылды +{fmt(val)} · бас тартты −{fmt(val - net_range)} · таза өсім {'+' if net_range >= 0 else '−'}{fmt(abs(net_range))}"
        if metric == "new_followers" and not is_today and any(
                v.get("new_followers") is None for k, v in chart_days.items() if key(first) <= k <= key(last)):
            if net_range is not None:  # Instagram has not counted these days yet: show the growth of the total instead
                val = net_range
                sub = "таза өсім (жалпы жазылушы санының айырмасы) · Instagram өз санын 1–2 күннен кейін береді"
            else:
                sub = "соңғы 1–2 күнді Instagram әлі есептеп жатыр"
        color = METRIC_COLORS.get(metric, "#7336F7")
        prevtxt = (f" · алдыңғы {fmt(pval)}" if pval is not None and not is_today else "")
        if metric == "new_followers":
            cards.append(
                f'<article class="hero ighero cardin" style="--i:{i}"><div class="hh"><span>{title} · Instagram</span>{ui.pill_pct(pct(val, pval), True)}</div>'
                f'{number(val, "hv")}<p class="hsub">{html.escape(sub)}{prevtxt}</p>'
                f'<div class="hsp">{ui.spark(series["new_followers"], "#ffffff", 600, 90, cls="spark big")}</div></article>')
        else:
            cards.append(
                f'<article class="k cardin" style="--i:{i};--c:{color}"><div class="kh"><span class="chip">{svg(ICONS[metric], "i")}</span>'
                f'<span class="kl">{title}</span>{ui.pill_pct(pct(val, pval))}</div>{number(val, "kv")}'
                f'<p class="ksub">{html.escape(hint)}{prevtxt}</p><div class="ks">{ui.spark(series.get(metric, []), color, 240, 40)}</div></article>')

    inter = cur.get("total_interactions")
    er = round(inter / cur["reach"] * 100, 1) if cur.get("reach") and inter is not None else None
    prev_er = round(prev["total_interactions"] / prev["reach"] * 100, 1) \
        if prev.get("reach") and prev.get("total_interactions") is not None else None

    rows = []
    for p in sorted(posts, key=lambda x: x["ts"], reverse=True):
        when = datetime.fromtimestamp(p["ts"], TZ)
        thumb = p.get("thumbnail_url") or (p.get("media_url") if p.get("media_type") != "VIDEO" else "")
        cap = (p.get("caption") or "").strip().split("\n")[0][:80]
        total = sum(p.get(k) or 0 for k in ("like_count", "comments_count", "saved", "shares"))
        per = round(total / p["reach"] * 100, 1) if p.get("reach") else None
        kind = KINDS.get(p.get("media_product_type"), "Пост")
        media = (f'<img src="{html.escape(thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer"'
                 f' onerror="this.remove()">' if thumb else "")
        rows.append(
            f'<tr data-ts="{int(p["ts"])}" data-likes="{p.get("like_count") or 0}" data-comments="{p.get("comments_count") or 0}"'
            f' data-saved="{p.get("saved") or 0}" data-shares="{p.get("shares") or 0}" data-reach="{p.get("reach") or 0}"'
            f' data-views="{p.get("views") or 0}" data-er="{per or 0}">'
            f'<td class="post"><a href="{html.escape(p.get("permalink") or "#")}" target="_blank" rel="noopener">'
            f'<span class="thumb {kind.lower()}">{media}<em>{kind}</em></span>'
            f'<span class="cap"><b>{html.escape(cap) or "Жазуы жоқ"}</b><small>{day_label(when)}, {when:%H:%M}</small></span></a></td>'
            f'<td><span class="m like">{fmt(p.get("like_count"))}</span></td>'
            f'<td><span class="m com">{fmt(p.get("comments_count"))}</span></td>'
            f'<td><span class="m">{fmt(p.get("saved"))}</span></td><td><span class="m">{fmt(p.get("shares"))}</span></td>'
            f'<td><span class="m">{fmt(p.get("reach"))}</span></td><td><span class="m">{fmt(p.get("views"))}</span></td>'
            f'<td><span class="pe{" hi" if (per or 0) >= 5 else ""}">{f"{per}%" if per is not None else "—"}</span></td></tr>')
    posts_html = (
        '<div class="table-wrap"><table id="posts"><thead><tr><th>Жарияланым</th>'
        '<th data-k="likes">Лайк</th><th data-k="comments">Коммент</th><th data-k="saved">Сақтау</th>'
        '<th data-k="shares">Бөлісу</th><th data-k="reach">Қамту</th><th data-k="views">Қаралым</th>'
        f'<th data-k="er">ER</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>') if rows else \
        '<div class="empty">Бұл кезеңде жаңа пост не рилс жарияланбаған.</div>'

    canvas_html = ig_canvas(chart_days, all_days or chart_days)
    chart = [{"label": day_label(datetime.strptime(k, "%Y-%m-%d")), **{m: v.get(m) for m in
              ("new_followers", "reach", "views", "likes", "comments")}} for k, v in chart_days.items()]

    pills = "".join(f'<a class="seg{" on" if period == p else ""}" href="?p={p}">{t}</a>' for p, t in PERIODS)
    step = (last - first).days + 1
    prev_link = f"?d={key(first - timedelta(days=1))}" if first == last else (
        f"?p=range&d1={key(first - timedelta(days=step))}&d2={key(first - timedelta(days=1))}" if period == "range" else f"?p={period}&end={key(first - timedelta(days=1))}")
    today = datetime.strptime(today_key, "%Y-%m-%d").replace(tzinfo=TZ)
    next_link = "" if key(last) >= today_key else (
        f"?d={key(last + timedelta(days=1))}" if first == last else
        f"?p=range&d1={key(last + timedelta(days=1))}&d2={key(min(last + timedelta(days=step), today))}" if period == "range" else
        f"?p={period}&end={key(min(last + timedelta(days=step), today))}")
    avatar = me.get("profile_picture_url")
    er_ring = min((er or 0) / ER_SCALE, 1)
    er_delta = delta_html(er, prev_er, is_today) if er is not None else ""
    return (PAGE.replace("__HEAD__", ui.HEAD).replace("__STYLE__", ui.STYLE + "<style>" + ui.KIT + "</style>" + DASH_CSS)
            .replace("__TOPBAR__", ui.topbar(user, "instagram")).replace("__THEMEJS__", ui.THEME_JS).replace("__KITJS__", ui.KIT_JS)
            .replace("__AVATAR__", (f'<img src="{html.escape(avatar)}" alt="" referrerpolicy="no-referrer"'
                                    f' onerror="this.remove()">') if avatar else "")
            .replace("__USER__", html.escape(me.get("username") or "eduapp_demo"))
            .replace("__NAME__", html.escape(me.get("name") or "EduApp"))
            .replace("__FOLLOWERS_NUM__", number(fol))
            .replace("__FOLLOWERS__", fmt(fol))
            .replace("__FOLLOWS__", fmt(me.get("follows_count")))
            .replace("__MEDIA__", fmt(me.get("media_count")))
            .replace("__UPDATED_TIME__", updated[-5:])
            .replace("__SAVED__", saved_html(saved))
            .replace("__UPDATED__", updated)
            .replace("__PILLS__", pills)
            .replace("__DATE__", ui.date_range(first, last, today, prev_link, next_link or None, "?d=@"))
            .replace("__PERIOD__", html.escape(period_title(period, first, last)))
            .replace("__SPAN__", f"{first:%d.%m.%Y} 00:00 – " + (f"{updated[-5:]} (күн әлі жалғасуда)" if key(last) == today_key
                                                                   else f"{last:%d.%m.%Y} 23:59"))
            .replace("__KPIS__", "".join(cards))
            .replace("__ER__", f"{er}" if er is not None else "—")
            .replace("__ER_RING__", f"{er_ring:.4f}")
            .replace("__ER_DELTA__", er_delta)
            .replace("__INTER__", number(inter))
            .replace("__POSTCOUNT__", number(len(posts)))
            .replace("__DIRECT__", number(cur.get("direct")))
            .replace("__POSTS__", posts_html)
            .replace("__REPORT__", f"report?d={key(last)}")
            .replace("__CHART__", json.dumps(chart, ensure_ascii=False)).replace("__CANVAS__", canvas_html)
            .replace("__NOTE__", " · ".join(html.escape(e) for e in errors)))


DASH_CSS = """<style>
.ig-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;margin:8px 0 16px}
.acct{display:flex;align-items:center;gap:12px;min-width:0}
.ava{width:44px;height:44px;border-radius:50%;overflow:hidden;background:var(--surface2);border:1px solid var(--border);flex:none}
.ava img{width:100%;height:100%;object-fit:cover;display:block}
.acct h1{margin:0;font-size:1.25rem;line-height:1.4;font-weight:600;letter-spacing:-.02em}
.acct p{margin:0;color:var(--muted);font-size:0.8125rem;display:flex;align-items:center;gap:6px}
.acct p i{width:6px;height:6px;border-radius:50%;background:var(--green)}
.stats{display:flex;border:1px solid var(--border);border-radius:10px;background:var(--surface);overflow:hidden}
.stat{padding:6px 16px;text-align:center}.stat+.stat{border-left:1px solid var(--border)}
.stat b,.stat .num{display:block;font-size:0.9375rem;font-weight:600;font-variant-numeric:tabular-nums;margin:0}.stat span{font-size:0.6875rem;color:var(--faint)}
.ig-ctrl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin-bottom:8px}
.ig-ctrl .grp{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.period{color:var(--muted);font-size:0.8125rem;margin:0 0 16px}.period b{color:var(--text);font-weight:500}
.saved{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:12px 16px;margin:0 0 16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface)}
.saved .ico{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.75;color:var(--accent)}.saved a{margin-left:auto;color:var(--accent);font-weight:500}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.ighero{grid-column:span 2;grid-row:span 2}.ighero .hsp{flex:0 0 140px;margin-top:auto}.frz .ring .val{transition:none}.hsub{margin:2px 0 0;opacity:.85;font-size:0.8125rem}
.kpi{padding:16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface)}
.kpi{border:0!important;box-shadow:var(--shadow);border-radius:22px}.kpi.hero{grid-column:span 2;background:var(--hero);color:#fff;box-shadow:var(--shadow-lg)}.kpi.hero .kpi-top,.kpi.hero small,.kpi.hero .was{color:rgba(255,255,255,.85)}.kpi.hero .chip{background:rgba(255,255,255,.18);color:#fff}.kpi.hero .delta{background:rgba(255,255,255,.2);color:#fff}.charts .card,.posts{border:0;box-shadow:var(--shadow);border-radius:22px}
.kpi-top{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:0.8125rem;font-weight:500;color:var(--muted)}
.chip{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:var(--surface2);color:var(--muted);flex:none}
.chip .ico{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.kpi.hero .chip{color:var(--accent)}
.num{display:block;font-size:1.5rem;line-height:1.333;font-weight:600;letter-spacing:-.02em;margin:8px 0 0;font-variant-numeric:tabular-nums}
.kpi.hero .num{font-size:2rem;line-height:1.25}
.kpi small{display:block;color:var(--faint);font-size:0.75rem;min-height:18px}
.foot{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}
.delta{display:inline-flex;align-items:center;gap:3px;font-size:0.75rem;font-weight:600;padding:1px 6px;border-radius:6px}
.delta .tr{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2.25}
.delta.up{color:var(--green);background:rgba(34,197,94,.1)}.delta.down{color:var(--red);background:rgba(248,113,113,.1)}.delta.flat{color:var(--faint);font-weight:500;padding:0}
.was{font-size:0.6875rem;color:var(--faint)}
.charts{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;margin-top:12px}
.charts .card h2,.posts h2{margin:0;font-size:1.0625rem;font-weight:600}.charts .card .sub,.posts .sub{color:var(--faint);font-size:0.75rem;margin:2px 0 12px}
.c-fol{grid-column:span 7}.c-reach{grid-column:span 5}.c-like{grid-column:span 7}.c-er{grid-column:span 4}
.c-canvas{grid-column:span 8;min-width:0}.c-canvas .zcv{margin-top:0;height:100%}
.chart{position:relative;height:220px}.chart svg{width:100%;height:100%;overflow:visible;display:block;touch-action:pan-y}
.legend{display:flex;gap:16px;font-size:0.75rem;color:var(--faint);margin-top:8px}.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
.bar{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .6s cubic-bezier(.2,.8,.2,1) forwards}
.chart:hover .bar{opacity:.55}.chart .bar.hot{opacity:1}@keyframes grow{to{transform:scaleY(1)}}
.line{stroke-dasharray:var(--len);stroke-dashoffset:var(--len);animation:draw 1s ease forwards}@keyframes draw{to{stroke-dashoffset:0}}
.area{opacity:0;animation:fadein .8s .3s forwards}@keyframes fadein{to{opacity:1}}
.dot{opacity:0}.dot.hot{opacity:1}.cursor{opacity:0}.cursor.on{opacity:1}
.tip{position:absolute;z-index:3;pointer-events:none;min-width:150px;padding:10px 12px;border-radius:14px;font-size:0.75rem;background:#1C1530;color:#fff;box-shadow:0 10px 26px rgba(28,21,48,.25);
opacity:0;transform:translate(-50%,calc(-100% - 10px));transition:opacity .12s}.tip.on{opacity:1}
.tip b{display:block;margin-bottom:2px}.tip div{display:flex;justify-content:space-between;gap:12px}.tip i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
.er{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.ring{position:relative;width:140px;height:140px;flex:none}.ring svg{width:100%;height:100%;transform:rotate(-90deg)}
.ring .track{stroke:var(--bar)}.ring .val{stroke:url(#erg);stroke-linecap:round;stroke-dasharray:452.4;stroke-dashoffset:452.4}
.ring .center{position:absolute;inset:0;display:grid;place-items:center;text-align:center}.ring .center b{display:block;font-size:1.625rem;font-weight:600}.ring .center span{font-size:0.6875rem;color:var(--faint)}
.minis{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:8px;min-width:200px}.minis .foot{grid-column:span 2;margin:0}
.mini{padding:10px 12px;border-radius:10px;background:var(--surface2)}.mini span{display:block;font-size:0.75rem;color:var(--faint)}.mini .num{font-size:1.125rem;line-height:1.333;margin:2px 0 0}
.formula{font-size:0.75rem;color:var(--faint);margin:12px 0 0}
.posts{margin-top:12px}.table-wrap{overflow-x:auto}
#posts{width:100%;border-collapse:collapse;min-width:780px}
#posts th{font-size:0.75rem;font-weight:500;color:var(--faint);padding:8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
#posts th:first-child{text-align:left;padding-left:0}#posts th[data-k]{cursor:pointer}#posts th.sorted{color:var(--text)}#posts th.sorted:after{content:" ↓"}
#posts td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
#posts td:first-child{padding-left:0}#posts tbody tr:hover td{background:var(--surface2)}
.post a{display:flex;gap:12px;align-items:center;text-align:left}
.thumb{position:relative;width:40px;height:50px;border-radius:6px;overflow:hidden;flex:none;background:var(--surface2)}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .3s}@media (hover:hover){#posts tr:hover .thumb img{transform:scale(1.08)}}
.thumb em{position:absolute;left:2px;bottom:2px;font-style:normal;font-size:0.5625rem;font-weight:600;padding:1px 4px;border-radius:4px;background:rgba(0,0,0,.6);color:#fff}
.cap b{display:block;font-weight:500;max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cap small{color:var(--faint);font-size:0.75rem}
.m{font-weight:500}.pe{font-weight:600}.pe.hi{color:var(--green)}
.empty{padding:24px;text-align:center;color:var(--faint);border:1px dashed var(--border);border-radius:10px}
.note{color:var(--faint);font-size:0.75rem;margin-top:12px}
@media (max-width:1100px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.kpi.hero{grid-column:span 1}.c-fol,.c-reach,.c-like,.c-er,.c-canvas{grid-column:span 12}}
@media (max-width:720px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi.hero{grid-column:span 2}.stats{width:100%}.stat{flex:1}.ig-ctrl,.ig-ctrl .grp{width:100%}
.segs{flex:1}.seg{flex:1;text-align:center}.chart{height:190px}}
</style>"""


PAGE = r"""<!doctype html><html lang="kk"><head>__HEAD__<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800;900&display=swap" rel="stylesheet"><title>Instagram · EduApp</title>__STYLE__</head><body>
__TOPBAR__
<main class="wrap">
<div class="ig-head"><div class="acct"><span class="ava">__AVATAR__</span><div><h1>@__USER__</h1><p><i></i>Instagram · жаңартылды __UPDATED_TIME__</p></div></div>
<div class="stats" role="list"><div class="stat" role="listitem">__FOLLOWERS_NUM__<span>жазылушы</span></div>
<div class="stat" role="listitem"><b>__FOLLOWS__</b><span>жазылым</span></div><div class="stat" role="listitem"><b>__MEDIA__</b><span>жарияланым</span></div></div></div>
<div class="ig-ctrl"><div class="grp"><nav class="segs" aria-label="Кезең">__PILLS__</nav>
__DATE__</div>
<div class="grp"><a class="btn" href="archive"><svg class="i" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>Тарих</a>
<a class="btn" href="__REPORT__"><svg class="i" viewBox="0 0 24 24"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>Есеп мәтіні</a></div></div>
<p class="period">Көрсетілген: <b>__PERIOD__</b> · деректер кезеңі: <b>__SPAN__</b> (Астана) · жаңартылды __UPDATED__</p>
__SAVED__
<section class="kpis">__KPIS__</section>
<section class="charts">
 <div class="c-canvas">__CANVAS__</div>
 <div class="card c-er" style="--i:9"><h2>Тартымдылық</h2><p class="sub">таңдалған кезең бойынша</p>
  <div class="er"><div class="ring"><svg viewBox="0 0 160 160"><defs></defs>
   <defs><linearGradient id="erg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7336F7"/><stop offset="1" stop-color="#9B6BFF"/></linearGradient></defs><circle class="track" cx="80" cy="80" r="72" fill="none" stroke-width="14"/><circle class="val" id="erv" data-p="__ER_RING__" cx="80" cy="80" r="72" fill="none" stroke-width="14"/></svg>
   <div class="center"><div><b>__ER__%</b><span>Engagement rate</span></div></div></div>
  <div class="minis"><div class="mini"><span>Барлық әрекет</span>__INTER__</div><div class="mini"><span>Жарияланым</span>__POSTCOUNT__</div><div class="mini"><span>Direct-ке жазғандар</span>__DIRECT__</div>
  <div class="foot">__ER_DELTA__</div></div></div>
  <p class="formula">ER = (лайк + коммент + сақтау + бөлісу) ÷ қамту · шеңбер 0–10% шкаласында</p></div>
</section>
<section class="card posts cardin" style="--i:10"><h2>Жарияланымдар</h2><p class="sub">баған атауын басып сұрыптауға болады</p>__POSTS__</section>
<p class="note">__NOTE__</p>
</main>__THEMEJS____KITJS__
<script>
(function(){
const D=__CHART__;const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const nf=n=>Math.round(n).toLocaleString('ru-RU').replace(/ /g,' ');
/* count-up */
const ease=t=>1-Math.pow(1-t,4);
function countUp(el){const to=+el.dataset.to;if(!isFinite(to))return;el.textContent=nf(to);return;
 const dur=1400,st=performance.now();(function f(now){const t=Math.min(1,(now-st)/dur);el.textContent=nf(to*ease(t));if(t<1)requestAnimationFrame(f)})(st)}
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){countUp(e.target);io.unobserve(e.target)}}),{threshold:.3});

document.addEventListener('themechange',()=>all());
/* ER ring — apple-design «Response»: filled to its value on the first frame, like every other number */
{const v=document.getElementById('erv');v.style.strokeDashoffset=452.4*(1-(+v.dataset.p||0))}
/* charts */
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let C={},LAV='#C9BEE8';function colors(){const dk=document.documentElement.dataset.theme==='dark'||(!document.documentElement.dataset.theme&&matchMedia('(prefers-color-scheme: dark)').matches);LAV=dk?'#4B3B78':'#C9BEE8';C={new_followers:'#7336F7',reach:'#7336F7',views:LAV,likes:'#7336F7',comments:LAV}}
const N={new_followers:'Жаңа жазылушы',reach:'Қамту',views:'Қаралым',likes:'Лайк',comments:'Коммент'};
const short=v=>v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e4?Math.round(v/1e3)+'k':v>=1e3?(v/1e3).toFixed(1)+'k':v;
function niceMax(m){if(m<=0)return 1;const p=Math.pow(10,Math.floor(Math.log10(m))),n=m/p;return (n<=1?1:n<=2?2:n<=5?5:10)*p}
function spline(pts){if(pts.length<2)return pts.length?`M${pts[0][0]},${pts[0][1]}`:'';let d=`M${pts[0][0]},${pts[0][1]}`;
 for(let i=0;i<pts.length-1;i++){const p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2;
  d+=` C${p1[0]+(p2[0]-p0[0])/6},${p1[1]+(p2[1]-p0[1])/6} ${p2[0]-(p3[0]-p1[0])/6},${p2[1]-(p3[1]-p1[1])/6} ${p2[0]},${p2[1]}`}return d}
function chart(id,keys,type){const el=document.getElementById(id);if(!el)return;const W=Math.max(el.clientWidth,280),H=el.clientHeight||230,P={l:40,r:10,t:14,b:26};
 const n=D.length,cw=(W-P.l-P.r)/Math.max(n,1),max=niceMax(Math.max(0,...D.flatMap(r=>keys.map(k=>r[k]||0))));
 const y=v=>H-P.b-(v/max)*(H-P.t-P.b),xc=i=>P.l+cw*i+cw/2;const g=getComputedStyle(document.documentElement).getPropertyValue('--border'),mu=getComputedStyle(document.documentElement).getPropertyValue('--faint');
 let s=`<defs>`;keys.forEach(k=>{s+=`<linearGradient id="${id}${k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C[k]}" stop-opacity="${type==='area'?.16:1}"/><stop offset="1" stop-color="${C[k]}" stop-opacity="${type==='area'?0:1}"/></linearGradient>`});s+=`</defs>`;
 for(let i=0;i<=4;i+=2){const v=max*i/4,yy=y(v);s+=`<line x1="${P.l}" x2="${W-P.r}" y1="${yy}" y2="${yy}" stroke="${g}" ${i?'stroke-dasharray="2 6"':''}/><text x="${P.l-8}" y="${yy+4}" font-size="10" font-weight="600" text-anchor="end" fill="${mu}">${short(v)}</text>`}
 const every=Math.ceil(n/(W<500?5:8));D.forEach((r,i)=>{if(i%every===0||i===n-1)s+=`<text x="${xc(i)}" y="${H-6}" font-size="10" font-weight="600" text-anchor="middle" fill="${mu}">${r.label}</text>`});
 s+=`<line class="cursor" x1="0" x2="0" y1="${P.t}" y2="${H-P.b}" stroke="#7336F7" stroke-opacity=".3"/>`;
 if(type==='bar'){const gap=keys.length>1?3:0,bw=Math.max(3,Math.min(26,(cw*.62-gap)/keys.length));
  D.forEach((r,i)=>keys.forEach((k,j)=>{const v=r[k]||0,x=xc(i)-(bw*keys.length+gap*(keys.length-1))/2+j*(bw+gap),h=Math.max(v?2:0,H-P.b-y(v)),rr=Math.min(7,bw/2);
   const fillc=keys.length===1?(i===n-1?'#7336F7':LAV):`url(#${id}${k})`;
   s+=`<path class="bar" data-i="${i}" style="animation-delay:${i*28+j*60}ms" fill="${fillc}" d="M${x},${H-P.b} v${-(h-rr)} q0,${-rr} ${rr},${-rr} h${bw-2*rr} q${rr},0 ${rr},${rr} v${h-rr} z"/>`}))}
 else{keys.forEach(k=>{const pts=D.map((r,i)=>[xc(i),y(r[k]||0)]);const d=spline(pts);
   const main=k===keys[0];if(main)s+=`<path class="area" fill="url(#${id}${k})" d="${d} L${xc(n-1)},${H-P.b} L${xc(0)},${H-P.b} Z"/>`;
   s+=`<path class="line" d="${d}" fill="none" stroke="${C[k]}" stroke-width="${main?2.5:2}" ${main?'':'stroke-dasharray="3 5"'} stroke-linecap="round" />`;
   if(main){const L=pts[n-1];s+=`<circle cx="${L[0]}" cy="${L[1]}" r="5" fill="var(--surface)" stroke="${C[k]}" stroke-width="2.5"/>`}
   pts.forEach((p,i)=>s+=`<circle class="dot" data-i="${i}" cx="${p[0]}" cy="${p[1]}" r="5" fill="${C[k]}" stroke="var(--surface)" stroke-width="2"/>`)})}
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${s}</svg><div class="tip"></div>`;
 el.querySelectorAll('.line').forEach(l=>{const len=l.getTotalLength();l.style.setProperty('--len',len)});
 const tip=el.querySelector('.tip'),cur=el.querySelector('.cursor'),svgEl=el.querySelector('svg');
 function show(i){const r=D[i];if(!r)return;tip.innerHTML=`<b>${r.label}</b>`+keys.map(k=>`<div><span><i style="background:${C[k]}"></i>${N[k]}</span><strong>${r[k]==null?'—':nf(r[k])}</strong></div>`).join('');
  const px=xc(i)/W*el.clientWidth;tip.style.left=Math.min(Math.max(px,80),el.clientWidth-80)+'px';tip.style.top=Math.min(...keys.map(k=>y(r[k]||0)))/H*el.clientHeight+'px';tip.classList.add('on');
  cur.setAttribute('x1',xc(i));cur.setAttribute('x2',xc(i));cur.classList.add('on');
  el.querySelectorAll('.bar,.dot').forEach(b=>b.classList.toggle('hot',+b.dataset.i===i))}
 function hide(){tip.classList.remove('on');cur.classList.remove('on');el.querySelectorAll('.hot').forEach(b=>b.classList.remove('hot'))}
 const pick=e=>{const r=svgEl.getBoundingClientRect(),x=(e.touches?e.touches[0].clientX:e.clientX)-r.left;return Math.max(0,Math.min(n-1,Math.floor((x/r.width*W-P.l)/cw)))};
 svgEl.addEventListener('mousemove',e=>show(pick(e)));svgEl.addEventListener('mouseleave',hide);svgEl.addEventListener('touchstart',e=>show(pick(e)),{passive:true});
 /* apple-design «Direct manipulation»: on a phone the tooltip follows the finger along the chart and goes away when it lifts */
 svgEl.addEventListener('touchmove',e=>show(pick(e)),{passive:true});['touchend','touchcancel'].forEach(t=>svgEl.addEventListener(t,hide,{passive:true}))}
function all(){colors();chart('c1',['new_followers'],'bar');chart('c2',['reach','views'],'area');chart('c3',['likes','comments'],'bar')}
all();let rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(all,200)});
/* theme */
/* sortable posts */
const tb=document.querySelector('#posts tbody');if(tb)document.querySelectorAll('#posts th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;
 [...tb.rows].sort((a,b)=>b.dataset[k]-a.dataset[k]).forEach((r,i)=>{r.style.animation='none';r.offsetWidth;r.style.animation=`rise .4s ${i*30}ms both`;tb.appendChild(r)});
 document.querySelectorAll('#posts th').forEach(x=>x.classList.remove('sorted'));th.classList.add('sorted')});
})();
</script></body></html>"""
