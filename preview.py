"""/preview — three visual directions for the marketing dashboard, on real numbers (admin only).

A «Apple Fitness / Bento»  — dark, bento tiles, concentric plan rings.
B «Premium Fintech»        — light, gradient hero card, sparklines, soft shadows.
C «Gamified»               — XP bar and levels, streak in the centre, a colour per metric.
Colours come from eduapp_demo: purple #7336F7/#7648c3, indigo #2A78D6, yellow #fec200,
orange #f35b2f, green #048848. Static on purpose (screenshots); motion comes in step 2.
"""
import html
import math

import ui
from datetime import datetime

from dashboard import MONTHS, WEEKDAYS

BRAND = {"purple": "#7336F7", "violet": "#7648c3", "deep": "#2F0E51", "indigo": "#2A78D6",
         "yellow": "#fec200", "orange": "#f35b2f", "green": "#048848"}


def money(n):
    return "—" if n is None else f"{round(n):,}".replace(",", " ") + " ₸"


def num(n):
    return "—" if n is None else f"{round(n):,}".replace(",", " ")


def short_money(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".") + " млн ₸"
    if n >= 1000:
        return f"{n / 1000:.0f} мың ₸"
    return money(n)


def delta(cur, prev):
    if cur is None or not prev:
        return None
    p = round((cur - prev) / prev * 100)
    return None if abs(p) > 300 else p  # «Қайдан келді» is filled only since 12.10: older months are not comparable


def pill(p, cls="pill"):
    if p is None:
        return f'<span class="{cls} flat">—</span>'
    return f'<span class="{cls} {"up" if p >= 0 else "down"}">{"▲" if p >= 0 else "▼"} {abs(p)}%</span>'


def spark(vals, w=120, h=36, color="#fff", fill=True, sw=2):
    vals = [v or 0 for v in vals] or [0]
    mx, mn = max(vals), min(vals)
    rng = (mx - mn) or 1
    step = w / max(1, len(vals) - 1)
    pts = [(i * step, h - 3 - (v - mn) / rng * (h - 6)) for i, v in enumerate(vals)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    gid = f"g{abs(hash((tuple(vals), color))) % 10**6}"
    area = (f'<path d="{d} L{w},{h} L0,{h} Z" fill="url(#{gid})"/>' if fill else "")
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".35"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>{area}'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{color}"/></svg>')


def ring(pcts, colors, size=180, width=16, gap=4, track="rgba(255,255,255,.08)"):
    """Concentric Apple-Watch style rings, outermost first."""
    c = size / 2
    out = [f'<svg class="rings" viewBox="0 0 {size} {size}" aria-hidden="true">']
    for i, (p, col) in enumerate(zip(pcts, colors)):
        r = c - width / 2 - i * (width + gap)
        L = 2 * math.pi * r
        v = max(0, min(1, (p or 0) / 100))
        out.append(f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="{track}" stroke-width="{width}"/>'
                   f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="{col}" stroke-width="{width}" stroke-linecap="round"'
                   f' stroke-dasharray="{L * v:.1f} {L:.1f}" transform="rotate(-90 {c} {c})"/>')
    out.append("</svg>")
    return "".join(out)


def heat(cal, plan, shades, fire=True, done_color=None):
    """Month heatmap: colour strength = leads; on days the lead plan was met."""
    mx = max([c["leads"] for c in cal] + [plan, 1])
    wd0 = datetime.strptime(cal[0]["date"], "%Y-%m-%d").weekday() if cal else 0
    cells = "".join(f'<span class="wd">{w}</span>' for w in WEEKDAYS) + '<span></span>' * wd0
    for c in cal:
        if c["future"]:
            cells += f'<span class="hd fut">{c["day"]}</span>'
            continue
        k = min(len(shades) - 1, int(c["leads"] / mx * (len(shades) - 1) + .5))
        style = f'background:{shades[k]};' + ("color:#fff;" if k >= len(shades) // 2 else "")
        mark = '<em></em>' if (fire and c["done"]) else ""
        cells += (f'<span class="hd{" now" if c["today"] else ""}" style="{style}" '
                  f'title="{c["day"]}: {c["leads"]} лид · {money(c["amount"])}">{c["day"]}{mark}</span>')
    return f'<div class="heat">{cells}</div>'


def data(m, spark14, user):
    crm, prev, b, st = m["crm"], m["prev"], m["bonus"], m["streak"]
    return {
        "name": m["first_name"] or (user.get("n") or "").split()[0],
        "amount": crm["amount"], "d_amount": delta(crm["amount"], prev["amount"]),
        "sales": crm["sales"], "d_sales": delta(crm["sales"], prev["sales"]),
        "avg": crm["avg"], "d_avg": delta(crm["avg"], prev["avg"]),
        "leads": crm["leads"], "d_leads": delta(crm["leads"], prev["leads"]),
        "conv": crm["conv"], "d_conv": delta(crm["conv"], prev["conv"]), "conv_plan": m["conv_plan"],
        "m_amount": m["month"]["amount"], "m_plan": m["month_plan"]["amount"], "m_pct": m["month_pct"]["amount"],
        "m_leads": m["month"]["leads"], "m_lplan": m["month_plan"]["leads"], "m_lpct": m["month_pct"]["leads"],
        "w_amount": m["week"]["amount"], "w_plan": m["week_plan"]["amount"], "w_pct": m["week_pct"]["amount"],
        "today_leads": m["today_leads"], "lead_day": m["lead_day"],
        "day_pct": round((m["today_leads"] or 0) / m["lead_day"] * 100) if m["lead_day"] else None,
        "bonus": b["earned"] if b["reached"] else b["potential"], "bonus_reached": b["reached"], "bonus_pct": b["pct"],
        "bonus_left": b["left"], "streak": st["days"], "streak_next": st["next"], "cal": m["calendar"],
        "elapsed": m["elapsed"], "dim": m["dim"], "pace": m["pace"],
        "sp": spark14, "conv_pct": round(crm["conv"] / m["conv_plan"] * 100) if crm["conv"] and m["conv_plan"] else None,
    }


def near(p):
    if p is None:
        return "Жоспар қойылмаған"
    if p >= 100:
        return "Жоспар орындалды "
    if p >= 80:
        return "Жақындап қалдық! "
    if p >= 50:
        return "Жартысынан өттік "
    return "Әр лид маңызды "


def bar(p, cls="bar"):
    w = max(0, min(100, p or 0))
    return (f'<div class="{cls}{" ok" if (p or 0) >= 100 else ""}"><i style="width:{w}%"></i>'
            '<b style="left:50%"></b><b style="left:75%"></b><b style="left:100%"></b></div>')


# ---------------------------------------------------------------- A: Apple Fitness / Bento
def variant_a(d):
    sp = d["sp"]
    rings = ring([d["m_pct"], d["m_lpct"], d["conv_pct"]], ["#ff3d7f", "#fec200", "#22d3ee"], size=200, width=18)
    return f"""
<div class="A">
<section class="hello"><div><p class="eyebrow">Бүгін · {datetime.now().day} {MONTHS[datetime.now().month - 1]}</p>
<h1>Сәлем, {html.escape(d['name'])}</h1><p class="sub">Тағы бір жоспарды жабамыз ба? </p></div>
<div class="streak"><span></span><b>{d['streak']}</b><small>күн қатарынан</small></div></section>
<div class="bento">
 <article class="t hero"><p class="lbl">Сатылым сомасы · ай</p><div class="big">{money(d['amount'])}</div>
  <div class="row">{pill(d['d_amount'])}<span class="mut">өткен аймен салыстырғанда</span></div>
  <div class="sparkw">{spark(sp['amount'], 600, 90, '#ff3d7f')}</div>
  <div class="hb"><div class="hb-top"><span>Айлық жоспар</span><b>{d['m_pct'] if d['m_pct'] is not None else '—'}%</b></div>{bar(d['m_pct'], 'bar a')}
  <div class="hb-top mut"><span>{short_money(d['m_amount'])} / {short_money(d['m_plan'])}</span><span>{near(d['m_pct'])}</span></div></div></article>
 <article class="t rings-t"><p class="lbl">Жоспар сақиналары</p>{rings}
  <ul class="legend"><li><i style="background:#ff3d7f"></i>Сатылым <b>{d['m_pct'] or 0}%</b></li><li><i style="background:#fec200"></i>Лид <b>{d['m_lpct'] or 0}%</b></li><li><i style="background:#22d3ee"></i>Конверсия <b>{d['conv_pct'] or 0}%</b></li></ul></article>
 <article class="t"><p class="lbl">Сатылым саны</p><div class="mid">{num(d['sales'])}</div>{pill(d['d_sales'])}<div class="sparkw sm">{spark(sp['sales'], 200, 40, '#a78bfa')}</div></article>
 <article class="t"><p class="lbl">Орташа чек</p><div class="mid">{money(d['avg'])}</div>{pill(d['d_avg'])}<div class="sparkw sm">{spark(sp['avg'], 200, 40, '#22d3ee')}</div></article>
 <article class="t"><p class="lbl">Лид</p><div class="mid">{num(d['leads'])}</div>{pill(d['d_leads'])}<div class="sparkw sm">{spark(sp['leads'], 200, 40, '#fec200')}</div></article>
 <article class="t"><p class="lbl">Конверсия</p><div class="mid">{d['conv'] if d['conv'] is not None else '—'}%</div><span class="mut">қажетті {d['conv_plan'] or '—'}%</span><div class="sparkw sm">{spark(sp['conv'], 200, 40, '#34d399')}</div></article>
 <article class="t bonus"><p class="lbl">Бонус</p><div class="mid gold">{money(d['bonus'])}</div><p class="mut">{'Айлық жоспар орындалды' if d['bonus_reached'] else 'жоспар жабылса · ' + money(d['bonus_left']) + ' қалды'}</p></article>
 <article class="t today"><p class="lbl">Бүгінгі лид</p><div class="mid">{num(d['today_leads'])}<small> / {d['lead_day']}</small></div>{bar(d['day_pct'], 'bar a y')}<p class="mut">{near(d['day_pct'])}</p></article>
 <article class="t cal"><p class="lbl">Лид heatmap · {d['elapsed']}/{d['dim']} күн</p>{heat(d['cal'], d['lead_day'], ['#1c1c22', '#2e1a4d', '#4a2585', '#6d35c4', '#9b5cff'])}</article>
</div></div>"""


CSS_A = """
.A{--bg:#000;--t:#111114;--t2:#1a1a1f;--tx:#f5f5f7;--mu:#8e8e93;background:var(--bg);color:var(--tx);min-height:100vh;padding:24px}
.A .hello{display:flex;justify-content:space-between;align-items:center;gap:16px;max-width:1200px;margin:0 auto 20px}
.A .eyebrow{margin:0;color:#ff3d7f;font-weight:600;font-size:0.8125rem;text-transform:uppercase;letter-spacing:.06em}
.A h1{margin:4px 0;font-size:2.125rem;font-weight:700;letter-spacing:-.03em}.A .sub{margin:0;color:var(--mu)}
.A .streak{display:flex;align-items:center;gap:8px;padding:12px 18px;border-radius:20px;background:linear-gradient(135deg,#3a1406,#1a0b05);border:1px solid #5a2410}
.A .streak span{font-size:1.625rem}.A .streak b{font-size:1.875rem;font-weight:700}.A .streak small{color:#ffb38a;width:56px;line-height:1.2}
.A .bento{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;max-width:1200px;margin:0 auto}
.A .t{background:var(--t);border-radius:24px;padding:20px;min-width:0;position:relative;overflow:hidden}
.A .lbl{margin:0 0 8px;color:var(--mu);font-weight:600;font-size:0.8125rem}
.A .hero{grid-column:span 2;grid-row:span 2;background:radial-gradient(120% 90% at 0% 0%,rgba(255,61,127,.22),transparent 55%),var(--t)}
.A .big{font-size:3.5rem;line-height:1.05;font-weight:800;letter-spacing:-.04em}
.A .mid{font-size:1.875rem;line-height:1.1;font-weight:700;letter-spacing:-.03em;margin-bottom:6px}.A .mid small{font-size:1rem;color:var(--mu)}
.A .gold{color:#fec200;text-shadow:0 0 24px rgba(254,194,0,.35)}
.A .row{display:flex;gap:10px;align-items:center;margin-top:10px}.A .mut{color:var(--mu);font-size:0.8125rem;margin:6px 0 0}
.A .sparkw{margin:16px -20px 0;height:90px}.A .sparkw.sm{height:40px;margin:12px 0 0}.A .spark{width:100%;height:100%;display:block}
.A .hb{margin-top:8px}.A .hb-top{display:flex;justify-content:space-between;margin-top:8px;font-weight:600}.A .hb-top.mut{font-weight:500}
.A .rings-t{grid-row:span 2;display:flex;flex-direction:column;align-items:center}.A .rings{width:200px;height:200px;margin:8px 0 12px;filter:drop-shadow(0 0 18px rgba(255,61,127,.25))}
.A .legend{list-style:none;padding:0;margin:0;width:100%;display:grid;gap:8px}.A .legend li{display:flex;align-items:center;gap:8px;color:var(--mu)}
.A .legend i{width:10px;height:10px;border-radius:50%}.A .legend b{margin-left:auto;color:var(--tx)}
.A .bonus{background:radial-gradient(120% 120% at 100% 0%,rgba(254,194,0,.18),transparent 60%),var(--t)}
.A .cal{grid-column:span 4}.A .cal .heat .hd{height:30px}
@media (max-width:760px){.A{padding:16px}.A .bento{grid-template-columns:1fr 1fr;gap:10px}.A .hero,.A .cal{grid-column:span 2}.A .rings-t{grid-column:span 2;grid-row:auto}
.A h1{font-size:1.625rem}.A .big{font-size:2.5rem}.A .mid{font-size:1.375rem}.A .t{padding:16px;border-radius:20px}.A .sparkw{margin:12px -16px 0;height:70px}}
"""


# ---------------------------------------------------------------- B: Premium Fintech
def variant_b(d):
    sp = d["sp"]

    def kpi(label, value, dl, series, color, icon):
        return (f'<article class="k"><div class="kh"><span class="chip" style="background:{color}1f;color:{color}">{icon}</span>'
                f'<span>{label}</span>{pill(dl)}</div><div class="kv">{value}</div>'
                f'<div class="ks">{spark(series, 220, 44, color)}</div></article>')
    return f"""
<div class="B">
<section class="hello"><div><h1>Қайырлы күн, {html.escape(d['name'])} </h1><p>Бүгін тағы бір рекорд жаңартамыз ба?</p></div>
<div class="hs"><span class="st"><b>{d['streak']}</b> күн қатарынан</span><span class="st y">Бүгін <b>{num(d['today_leads'])}/{d['lead_day']}</b> лид</span></div></section>
<div class="grid">
 <article class="hero"><div class="hh"><span>Сатылым сомасы · маркетинг</span>{pill(d['d_amount'], 'pill w')}</div>
  <div class="hv">{money(d['amount'])}</div><div class="hsp">{spark(sp['amount'], 600, 80, '#ffffff')}</div>
  <div class="hp"><div class="hpt"><span>Айлық жоспар · {short_money(d['m_plan'])}</span><b>{d['m_pct'] if d['m_pct'] is not None else '—'}%</b></div>{bar(d['m_pct'], 'bar w')}
  <div class="hpt s"><span>{short_money(d['m_amount'])} жиналды</span><span>{near(d['m_pct'])}</span></div></div></article>
 <div class="side">
 {kpi('Сатылым саны', num(d['sales']), d['d_sales'], sp['sales'], '#7336F7', ui.icon('receipt'))}
 {kpi('Орташа чек', money(d['avg']), d['d_avg'], sp['avg'], '#2A78D6', ui.icon('wallet'))}
 {kpi('Лид', num(d['leads']), d['d_leads'], sp['leads'], '#f35b2f', ui.icon('users'))}
 {kpi('Конверсия', f"{d['conv'] if d['conv'] is not None else '—'}%", d['d_conv'], sp['conv'], '#048848', ui.icon('percent'))}
 </div>
 <article class="card plans"><h2>Жоспар</h2>
  <div class="pl"><div class="plt"><span>Айлық сатылым</span><b>{d['m_pct'] or 0}%</b></div>{bar(d['m_pct'], 'bar p')}<p>{short_money(d['m_amount'])} / {short_money(d['m_plan'])}</p></div>
  <div class="pl"><div class="plt"><span>Апталық сатылым</span><b>{d['w_pct'] or 0}%</b></div>{bar(d['w_pct'], 'bar p')}<p>{short_money(d['w_amount'])} / {short_money(d['w_plan'])}</p></div>
  <div class="pl"><div class="plt"><span>Айлық лид</span><b>{d['m_lpct'] or 0}%</b></div>{bar(d['m_lpct'], 'bar o')}<p>{num(d['m_leads'])} / {num(d['m_lplan'])}</p></div></article>
 <article class="card bonus"><h2>Бонус </h2><div class="bv">{money(d['bonus'])}</div>
  <p>{'Айлық жоспар орындалды!' if d['bonus_reached'] else 'Айлық жоспар жабылса аласың · ' + money(d['bonus_left']) + ' қалды'}</p>{bar(d['m_pct'], 'bar g')}</article>
 <article class="card cal"><h2>Лид heatmap</h2>{heat(d['cal'], d['lead_day'], ['#f1eefa', '#ddd2f5', '#bba5ec', '#8f6ad9', '#7336F7'])}</article>
</div></div>"""


CSS_B = """
.B{background:#f4f5fa;color:#14112b;min-height:100vh;padding:28px}
.B .hello{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:16px;max-width:1200px;margin:0 auto 22px}
.B h1{margin:0;font-size:1.75rem;font-weight:700;letter-spacing:-.02em}.B .hello p{margin:4px 0 0;color:#6b6889}
.B .hs{display:flex;gap:10px;flex-wrap:wrap}.B .st{padding:10px 16px;border-radius:999px;background:#fff;box-shadow:0 4px 16px rgba(46,15,76,.08);font-weight:500}
.B .st b{font-weight:700}.B .st.y{background:#fff7d6}
.B .grid{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;max-width:1200px;margin:0 auto}
.B .hero{position:relative;overflow:hidden;border-radius:28px;padding:28px;color:#fff;background:linear-gradient(135deg,#2F0E51 0%,#7336F7 45%,#2A78D6 100%);box-shadow:0 24px 60px -24px rgba(87,46,162,.65)}
.B .hero:after{content:"";position:absolute;width:320px;height:320px;right:-80px;top:-120px;border-radius:50%;background:radial-gradient(circle,rgba(254,194,0,.45),transparent 70%)}
.B .hh{display:flex;justify-content:space-between;align-items:center;font-weight:500;opacity:.9}
.B .hv{font-size:3.375rem;line-height:1.05;font-weight:800;letter-spacing:-.035em;margin:14px 0 6px}
.B .hsp{height:80px;margin:0 -28px}.B .spark{width:100%;height:100%;display:block}
.B .hp{margin-top:8px}.B .hpt{display:flex;justify-content:space-between;font-weight:600}.B .hpt.s{font-weight:500;opacity:.85;margin-top:8px;font-size:0.8125rem}
.B .side{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.B .k,.B .card{background:#fff;border-radius:24px;padding:18px;box-shadow:0 6px 24px rgba(20,17,43,.06)}
.B .kh{display:flex;align-items:center;gap:8px;color:#6b6889;font-weight:500;font-size:0.8125rem}.B .kh .pill{margin-left:auto}
.B .chip{display:grid;place-items:center;width:32px;height:32px;border-radius:10px}
.B .kv{font-size:1.875rem;font-weight:700;letter-spacing:-.03em;margin:12px 0 4px}.B .ks{height:44px}
.B .card h2{margin:0 0 14px;font-size:1.0625rem;font-weight:700}
.B .pl+.pl{margin-top:16px}.B .plt{display:flex;justify-content:space-between;font-weight:600}.B .pl p{margin:6px 0 0;color:#6b6889;font-size:0.8125rem}
.B .bonus{background:linear-gradient(160deg,#fff8dc,#fff 60%)}.B .bv{font-size:2.375rem;font-weight:800;letter-spacing:-.03em;color:#b07b00}.B .bonus p{color:#6b6889;margin:6px 0 0}
.B .cal{grid-column:span 2}
.B .bar{background:#ece9f6}.B .bar b{background:rgba(20,17,43,.15)}
.B .bar.w{background:rgba(255,255,255,.22)}.B .bar.w i{background:linear-gradient(90deg,#fec200,#ffe27a)}.B .bar.w b{background:rgba(255,255,255,.5)}
.B .bar.p i{background:linear-gradient(90deg,#7336F7,#9B6BFF)}.B .bar.o i{background:linear-gradient(90deg,#f35b2f,#ff9466)}.B .bar.g i{background:linear-gradient(90deg,#fec200,#ffd84d)}
.B .bar.ok i{background:linear-gradient(90deg,#048848,#22c55e)}
.B .pill.up{color:#048848;background:#e2f6ec}.B .pill.down{color:#d63c1a;background:#fde7e1}.B .pill.w{color:#fff;background:rgba(255,255,255,.18)}
.B .heat .hd{color:#4b4670}.B .heat .hd.fut{color:#c9c6dc}.B .heat .hd.now{box-shadow:inset 0 0 0 2px #fec200}
@media (max-width:900px){.B .grid{grid-template-columns:1fr}.B .cal{grid-column:auto}}
@media (max-width:760px){.B{padding:16px}.B h1{font-size:1.375rem}.B .hv{font-size:2.375rem}.B .side{gap:10px}.B .grid{gap:12px}.B .k{padding:14px;border-radius:20px}.B .kv{font-size:1.375rem}
.B .hero{padding:20px;border-radius:24px}.B .hsp{margin:0 -20px;height:60px}}
"""


# ---------------------------------------------------------------- C: Gamified
def variant_c(d):
    sp = d["sp"]
    xp = d["m_amount"] or 0
    level_size = max(1, (d["m_plan"] or 1_000_000) / 5)  # five levels to the monthly goal
    level = int(xp // level_size) + 1
    into = (xp % level_size) / level_size * 100
    titles = ["Жаңадан бастаушы", "Лид аңшысы", "Контент шебері", "Сатылым ниндзясы", "Маркетинг бастығы", "Аңыз"]
    title = titles[min(level - 1, len(titles) - 1)]

    def quest(label, value, sub, pct, color, emoji):
        return (f'<article class="q" style="--c:{color}"><div class="qh"><span class="qe">{emoji}</span><span>{label}</span></div>'
                f'<div class="qv">{value}</div><p>{sub}</p><div class="seg">'
                + "".join(f'<i class="{"on" if (pct or 0) >= (n + 1) * 20 else ""}"></i>' for n in range(5))
                + f'</div><div class="qs">{spark(sp[{"Сатылым саны": "sales", "Орташа чек": "avg", "Лид": "leads", "Конверсия": "conv"}[label]], 200, 34, color, False, 2.5)}</div></article>')
    return f"""
<div class="C">
<section class="top"><div class="who"><div class="lv">{level}</div><div><h1>{html.escape(d['name'])}</h1><p>Деңгей {level} · {title}</p></div></div>
<div class="xp"><div class="xpt"><span>XP · айлық сатылым</span><b>{short_money(xp)} / {short_money(d['m_plan'])}</b></div>
<div class="xpb"><i style="width:{into:.0f}%"></i></div><p>Келесі деңгейге {short_money(level_size - xp % level_size)} қалды</p></div></section>
<div class="main">
 <article class="hero"><p class="lbl">Сатылым сомасы · ай</p><div class="hv">{money(d['amount'])}</div>{pill(d['d_amount'])}
  <div class="hs">{spark(sp['amount'], 600, 70, '#fec200')}</div>
  <div class="mp"><div class="mpt"><span>Айлық жоспар</span><b>{d['m_pct'] or 0}%</b></div>{bar(d['m_pct'], 'bar c')}<p>{near(d['m_pct'])}</p></div></article>
 <article class="flame"><div class="fl"></div><div class="fn">{d['streak']}</div><p>күн қатарынан жоспар жабылды</p>
  <div class="fd">{''.join(f'<i class="{"on" if c["done"] else ""}">{c["day"]}</i>' for c in [c for c in d['cal'] if not c['future']][-7:])}</div>
  <p class="nx">Келесі сыйлық: <b>{d['streak_next']} күн</b> </p></article>
 <div class="quests">
 {quest('Сатылым саны', num(d['sales']), 'жабылған сделка', d['m_pct'], '#7336F7', ui.icon('receipt'))}
 {quest('Орташа чек', money(d['avg']), 'сома ÷ саны', d['m_pct'], '#2A78D6', ui.icon('wallet'))}
 {quest('Лид', num(d['leads']), f"бүгін {num(d['today_leads'])} / {d['lead_day']}", d['day_pct'], '#f35b2f', ui.icon('users'))}
 {quest('Конверсия', f"{d['conv'] or '—'}%", f"қажетті {d['conv_plan'] or '—'}%", d['conv_pct'], '#048848', ui.icon('percent'))}
 </div>
 <article class="card bonus"><p class="lbl">Сыйлық банкі</p><div class="bv">{money(d['bonus'])} </div><p>{'Ашылды!' if d['bonus_reached'] else 'Айлық жоспар жабылса ашылады'}</p></article>
 <article class="card cal"><p class="lbl">Лид картасы</p>{heat(d['cal'], d['lead_day'], ['#f3f0fa', '#e4d9f7', '#c8b2f0', '#a07ae3', '#7648c3'])}</article>
</div></div>"""


CSS_C = """
.C{background:#faf8ff;color:#1b1433;min-height:100vh;padding:24px}
.C .top{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:center;max-width:1200px;margin:0 auto 20px;padding:20px;border-radius:24px;background:#fff;box-shadow:0 6px 24px rgba(87,46,162,.08)}
.C .who{display:flex;gap:14px;align-items:center}.C .lv{display:grid;place-items:center;width:58px;height:58px;border-radius:18px;background:linear-gradient(135deg,#fec200,#f35b2f);color:#fff;font-size:1.625rem;font-weight:800;box-shadow:0 8px 20px -6px rgba(243,91,47,.6)}
.C h1{margin:0;font-size:1.5rem;font-weight:800}.C .who p{margin:2px 0 0;color:#7a7396;font-weight:600}
.C .xpt{display:flex;justify-content:space-between;font-weight:700;font-size:0.875rem}.C .xp p{margin:6px 0 0;color:#7a7396;font-size:0.8125rem}
.C .xpb{height:16px;border-radius:999px;background:#efeaf9;margin-top:8px;overflow:hidden;box-shadow:inset 0 2px 4px rgba(0,0,0,.06)}
.C .xpb i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#7648c3,#2A78D6);box-shadow:inset 0 -3px 0 rgba(0,0,0,.15)}
.C .main{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;max-width:1200px;margin:0 auto}
.C .hero,.C .flame,.C .card,.C .q{background:#fff;border-radius:24px;padding:20px;box-shadow:0 6px 24px rgba(87,46,162,.08)}
.C .lbl{margin:0;color:#7a7396;font-weight:700;font-size:0.8125rem;text-transform:uppercase;letter-spacing:.04em}
.C .hero{border:3px solid #fec200}.C .hv{font-size:3.25rem;line-height:1.05;font-weight:800;letter-spacing:-.035em;margin:8px 0}.C .hs{height:70px;margin:10px 0}.C .spark{width:100%;height:100%;display:block}
.C .mpt{display:flex;justify-content:space-between;font-weight:700}.C .mp p{margin:6px 0 0;font-weight:700;color:#7336F7}
.C .flame{text-align:center;background:linear-gradient(180deg,#fff3e8,#fff);border:3px solid #f35b2f}
.C .fl{font-size:3.375rem;line-height:1}.C .fn{font-size:4rem;font-weight:900;color:#f35b2f;line-height:1}.C .flame p{margin:4px 0;color:#7a4a2c;font-weight:600}
.C .fd{display:flex;justify-content:center;gap:6px;margin:12px 0}.C .fd i{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#f1ece6;color:#b8a89a;font-style:normal;font-size:0.75rem;font-weight:700}
.C .fd i.on{background:#f35b2f;color:#fff;box-shadow:0 4px 10px -2px rgba(243,91,47,.6)}.C .nx b{color:#f35b2f}
.C .quests{grid-column:span 2;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.C .q{border-top:6px solid var(--c)}.C .qh{display:flex;align-items:center;gap:8px;font-weight:700;color:#4a4366}.C .qe{display:grid;place-items:center;width:34px;height:34px;border-radius:12px;color:var(--c);background:color-mix(in srgb,var(--c) 14%,#fff)}
.C .qv{font-size:1.75rem;font-weight:800;margin:10px 0 2px;color:var(--c)}.C .q p{margin:0;color:#7a7396;font-size:0.8125rem}
.C .seg{display:flex;gap:4px;margin:12px 0 6px}.C .seg i{flex:1;height:10px;border-radius:4px;background:#efeaf9}.C .seg i.on{background:var(--c)}.C .qs{height:34px}
.C .bonus{background:linear-gradient(135deg,#fff8d9,#fff);border:3px dashed #fec200}.C .bv{font-size:2.125rem;font-weight:900;color:#b07b00;margin:8px 0 4px}.C .bonus p{margin:0;color:#7a7396;font-weight:600}
.C .cal{grid-column:auto}
.C .bar{background:#efeaf9;height:14px}.C .bar i{background:linear-gradient(90deg,#fec200,#f35b2f)}.C .bar b{background:rgba(27,20,51,.15)}
.C .pill.up{color:#048848;background:#e2f6ec}.C .pill.down{color:#d63c1a;background:#fde7e1}
.C .heat .hd{color:#4a4366}.C .heat .hd.fut{color:#cfc8e3}.C .heat .hd.now{box-shadow:inset 0 0 0 2px #f35b2f}
@media (max-width:900px){.C .main{grid-template-columns:1fr}.C .quests{grid-column:auto;grid-template-columns:1fr 1fr}}
@media (max-width:760px){.C{padding:14px}.C .top{grid-template-columns:1fr;gap:14px;padding:16px}.C .hv{font-size:2.375rem}.C .quests{gap:10px}.C .q{padding:14px}.C .qv{font-size:1.3125rem}.C .fn{font-size:3rem}}
"""

BASE = """*{box-sizing:border-box}body{margin:0;font:15px/1.45 Golos Text,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.switch{position:sticky;top:0;z-index:5;display:flex;gap:6px;justify-content:center;padding:10px;background:rgba(20,17,43,.9);backdrop-filter:blur(8px)}
.switch a{padding:6px 14px;border-radius:999px;color:#c9c3e6;text-decoration:none;font:600 0.8125rem Golos Text,sans-serif}.switch a.on{background:#fec200;color:#1b1433}
.heat .hd{background:#eee}
.chip .i,.qe .i{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.bar{position:relative;height:12px;border-radius:999px;background:rgba(255,255,255,.08);margin-top:10px}
.bar i{position:absolute;inset:0 auto 0 0;border-radius:inherit;background:linear-gradient(90deg,#ff3d7f,#ff7aa8)}
.bar b{position:absolute;top:-3px;width:2px;height:18px;border-radius:2px;background:rgba(255,255,255,.25);transform:translateX(-1px)}
.bar.y i{background:linear-gradient(90deg,#fec200,#ffe27a)}.bar.ok i{background:linear-gradient(90deg,#16a34a,#4ade80)}
.pill{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:999px;font-size:0.75rem;font-weight:700}
.pill.up{color:#30d158;background:rgba(48,209,88,.14)}.pill.down{color:#ff453a;background:rgba(255,69,58,.14)}.pill.flat{color:#8e8e93;background:rgba(142,142,147,.14)}
.heat{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}.heat .wd{font-size:0.6875rem;text-align:center;color:#8e8e93;text-transform:uppercase}
.heat .hd{position:relative;display:grid;place-items:center;height:34px;border-radius:9px;font-size:0.75rem;font-weight:600;color:#c7c7cc}
.heat .hd.fut{background:transparent;color:#3a3a3c}.heat .hd.now{box-shadow:inset 0 0 0 2px #fec200}
.heat em{position:absolute;top:-6px;right:-3px;font-size:0.8125rem;font-style:normal}
.note-demo{max-width:1200px;margin:0 auto 12px;padding:10px 14px;border-radius:12px;background:#fff7d6;color:#7a5a00;font:500 0.8125rem Golos Text,sans-serif}"""


def render(variant: str, m: dict, spark14: dict, user: dict, shots: bool = False, demo_plan: bool = False) -> str:
    d = data(m, spark14, user)
    body, css = {"a": (variant_a, CSS_A), "b": (variant_b, CSS_B), "c": (variant_c, CSS_C)}.get(variant, (variant_a, CSS_A))
    names = {"a": "A · Apple Fitness / Bento", "b": "B · Premium Fintech", "c": "C · Gamified"}
    switch = "" if shots else '<nav class="switch">' + "".join(
        f'<a class="{"on" if k == variant else ""}" href="?v={k}">{t}</a>' for k, t in names.items()) + "</nav>"
    return (f'<!doctype html><html lang="kk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Preview {variant.upper()} · EduApp</title><link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'
            f'<style>{BASE}{css}</style></head><body>{switch}'
            + (f'<p class="note-demo" style="margin-top:12px">Сандар нақты (amoCRM, Instagram). Айлық сатылым жоспары әлі қойылмағандықтан, көрініс үшін мысал жоспар алынды: 2 млн ₸.</p>' if demo_plan else '')
            + f'{body(d)}</body></html>')
