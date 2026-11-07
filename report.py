"""Daily Instagram report for @eduapp_demo as a ready-to-paste WhatsApp/Telegram text."""
import html
from datetime import datetime, timedelta

import ui
from igdata import TZ

try:
    from zoneinfo import ZoneInfo
    META_TZ = ZoneInfo("America/Los_Angeles")  # Instagram counts its days in Pacific time
except Exception:
    META_TZ = None

KINDS = {"REELS": "Рилс", "FEED": "Пост", "STORY": "Сторис"}


def fmt(n):
    return "—" if n is None else f"{n:,}".replace(",", " ")


def diff(a, b):
    if a is None or b is None:
        return ""
    d = a - b
    return f" ({'+' if d >= 0 else '−'}{fmt(abs(d))})"


def meta_day_window(day: datetime) -> str:
    """Astana time span of Instagram's own day that the «new followers» number covers."""
    start = datetime(day.year, day.month, day.day, tzinfo=META_TZ) if META_TZ else None
    if start is None:
        return ""
    a, b = start.astimezone(TZ), (start + timedelta(days=1)).astimezone(TZ)
    return f"{a:%d.%m %H:%M} – {b:%d.%m %H:%M}"


def build_text(day: datetime, followers, prev_followers, ins: dict, posts: list, direct: int, url: str,
               now: datetime, tg: dict | None = None) -> str:
    """Compact Instagram report: about a third of the old one, every number still there."""
    tg = tg or {}
    is_today = day.date() == now.date()
    span = f"00:00–{now:%H:%M}" if is_today else "00:00–23:59"

    def v(metric, value):
        t = tg.get(metric)
        return f"*{fmt(value)}*" + (f"/{fmt(t['target'])}" if t else "")

    new = ins.get("new_followers")
    growth = (f"+{fmt(new)} жаңа жазылушы" if new is not None else
              f"{diff(ins['net_followers'], 0).strip(' ()')} таза өсім" if ins.get("net_followers") is not None
              else "жаңа жазылушыны Instagram есептеуде")
    lines = [
        f"*EduApp · Instagram · {day:%d.%m.%Y}* ({span} Астана)",
        f"Жазылушы: {fmt(followers)}{diff(followers, prev_followers)} · {growth}" if followers is not None else f"Жазылушы: — · {growth}",
        f"Лайк {v('likes', ins.get('likes'))} · коммент {v('comments', ins.get('comments'))} · қамту {v('reach', ins.get('reach'))} · қаралым {fmt(ins.get('views'))}",
        f"Профиль {fmt(ins.get('profile_views'))} · сақтау {fmt(ins.get('saves'))} · бөлісу {fmt(ins.get('shares'))} · Direct {v('leads', direct)}",
    ]
    if posts:
        best = max(posts, key=lambda p: p.get("like_count") or 0)
        lines.append(f"Жарияланым {len(posts)} · үздігі: лайк {fmt(best.get('like_count'))} · коммент {fmt(best.get('comments_count'))}"
                     f" · қамту {fmt(best.get('reach'))}")
    lines.append(url)
    return "\n".join(lines)


PAGE = """<!doctype html><html lang="kk"><head>__HEAD____FONT__<title>Есеп мәтіні · EduApp</title>__STYLE__<style>__KIT__
.repcard{padding:0;overflow:hidden}
.reptop{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--border)}
.reptop .dots{display:flex;gap:6px}.reptop .dots i{width:10px;height:10px;border-radius:50%}
.reptop span{font-size:0.75rem;color:var(--faint);font-weight:600}
.bubble{margin:18px;padding:16px 18px;border-radius:18px 18px 18px 6px;background:color-mix(in srgb,#048848 8%,var(--surface2))}
pre{margin:0;padding:0;background:none;border:0;font:500 0.9062rem/1.65 Golos Text,system-ui,sans-serif;white-space:pre-wrap;word-break:break-word;color:var(--text)}
.links{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.btny.done{background:linear-gradient(90deg,#048848,#22c55e);color:#fff}
</style></head><body>__TOPBAR__<main class="wrap narrow">
<section class="ph cardin"><div><h1>Instagram есебі</h1><p>WhatsApp / Telegram-ға жіберуге дайын мәтін</p></div>
<div class="act"><form class="date" method="get"><a class="step" href="?d=__PREV__" aria-label="Алдыңғы">__LEFT__</a>
<input type="date" name="d" value="__DAY__" max="__MAX__" onchange="this.form.submit()" aria-label="Күн"><a class="step" href="?d=__NEXT__" aria-label="Келесі">__RIGHT__</a></form>
<button class="btny" id="copy" type="button">__COPYI__<span>Көшіру</span></button></div></section>
<section class="card repcard cardin" style="--i:1"><div class="reptop"><div class="dots"><i style="background:#f35b2f"></i><i style="background:#fec200"></i><i style="background:#048848"></i></div><span>__DAY__ · @eduapp_demo</span></div>
<div class="bubble"><pre id="txt">__TEXT__</pre></div></section>
<div class="links cardin" style="--i:2"><a class="btng" href="stats?d=__DAY__">__CHARTI__Instagram дашборды</a><a class="btng" href="/">__FILEI__Маркетинг есебі · Шолу</a></div>
</main>__THEMEJS____KITJS__<script>
document.getElementById('copy').onclick=async function(){var b=this;try{await navigator.clipboard.writeText(document.getElementById('txt').innerText);b.classList.add('done');b.querySelector('span').textContent='Көшірілді';setTimeout(function(){b.classList.remove('done');b.querySelector('span').textContent='Көшіру'},2200)}catch(e){}};
</script></body></html>"""


def render(day: datetime, text: str, followers, prev, ins: dict, direct: int, user: dict | None = None) -> str:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    nxt = min((day + timedelta(days=1)).strftime("%Y-%m-%d"), today)
    return (PAGE.replace("__HEAD__", ui.HEAD).replace("__FONT__", ui.FONT).replace("__STYLE__", ui.STYLE)
            .replace("__KIT__", ui.KIT + ui.PAGES).replace("__KITJS__", ui.KIT_JS)
            .replace("__CHARTI__", ui.icon("chart")).replace("__FILEI__", ui.icon("file")).replace("__TOPBAR__", ui.topbar(user, "instagram"))
            .replace("__THEMEJS__", ui.THEME_JS).replace("__LEFT__", ui.icon("left")).replace("__RIGHT__", ui.icon("right"))
            .replace("__COPYI__", ui.icon("copy", "ti"))
            .replace("__DAY__", day.strftime("%Y-%m-%d")).replace("__MAX__", today)
            .replace("__PREV__", (day - timedelta(days=1)).strftime("%Y-%m-%d")).replace("__NEXT__", nxt)
            .replace("__TEXT__", html.escape(text)))
