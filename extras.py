"""Pages for the director's daily work: system status, lead response speed, and the report as a picture.

status_page — one row per part (database, amoCRM, Instagram, Telegram, nightly jobs) in green / yellow / red.
speed_card  — how fast managers touch new marketing deals in amoCRM (from amo.lead_speed).
card_page   — the day / week / month report drawn as one 1080×1350 picture to send in WhatsApp or Telegram.
"""
import html
from datetime import datetime

import home
import igdata
from home import money, num, pct_text

STATE = {"ok": ("Жұмыс істейді", "var(--green)"), "warn": ("Назар аударыңыз", "var(--amber)"),
         "bad": ("Ақау", "var(--red)"), "off": ("Қосылмаған", "var(--faint)")}

CSS = """.stl{display:grid;gap:12px}.st{display:grid;grid-template-columns:14px 1fr auto;gap:4px 14px;align-items:start;padding:16px 18px;border-radius:18px;background:var(--surface);box-shadow:var(--shadow)}
.st>i{width:14px;height:14px;border-radius:50%;margin-top:4px;box-shadow:0 0 0 4px color-mix(in srgb,currentColor 18%,transparent)}
.st h3{margin:0;font-size:1rem}.st .s{font-size:0.8125rem;font-weight:700;white-space:nowrap}.st p{grid-column:2/-1;margin:0;color:var(--muted);font-size:0.875rem}
.st a{color:var(--accent);font-weight:600}
.sum{display:flex;align-items:center;gap:14px;padding:18px 20px;border-radius:20px;margin-bottom:16px;color:#fff;font-weight:700;font-size:1.125rem}
.spg{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.spg div{background:var(--surface2);border-radius:14px;padding:12px 14px}
.spg span{display:block;color:var(--muted);font-size:0.75rem;font-weight:600}.spg b{font-size:1.375rem;font-weight:800;font-variant-numeric:tabular-nums}
.spw{margin:14px 0 0;padding:0;list-style:none;display:grid;gap:6px}.spw li{display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:space-between;padding:9px 12px;border-radius:12px;background:color-mix(in srgb,var(--red) 8%,var(--surface))}
.spw b{color:var(--red)}.spw a{font-weight:600}
.spu{width:100%;border-collapse:collapse;font-size:0.875rem;margin-top:12px}.spu th,.spu td{padding:8px 6px;text-align:right;border-bottom:1px solid var(--border)}
.spu th:first-child,.spu td:first-child{text-align:left}.spu th{color:var(--muted);font-size:0.75rem;font-weight:600}
@media (max-width:720px){.spg{grid-template-columns:repeat(2,1fr)}}"""


def status_page(items: list, user: dict) -> str:
    worst = "bad" if any(x["state"] == "bad" for x in items) else "warn" if any(x["state"] == "warn" for x in items) else "ok"
    head = {"ok": "Барлығы жұмыс істейді — есепке сенуге болады",
            "warn": "Жұмыс істейді, бірақ назар аударатын жер бар",
            "bad": "Ақау бар — есепті жібермес бұрын тексеріңіз"}[worst]
    rows = "".join(
        f'<div class="st" style="color:{STATE[x["state"]][1]}"><i style="background:currentColor"></i><h3 style="color:var(--text)">{html.escape(x["name"])}</h3>'
        f'<span class="s">{STATE[x["state"]][0]}</span><p>{x["text"]}</p></div>' for x in items)
    body = (f'<main class="wrap narrow"><section class="ph cardin"><div><h1>Жүйе күйі</h1>'
            f'<p>Есеп деректері қайдан келеді және олар қаншалықты жаңа: база, amoCRM, Instagram, Telegram, түнгі жұмыстар. '
            f'Тексерілді: {datetime.now(igdata.TZ):%d.%m.%Y %H:%M}.</p></div></section>'
            f'<div class="sum" style="background:{STATE[worst][1]}">{head}</div><div class="stl">{rows}</div></main>')
    import admin
    return admin.page("Жүйе · EduApp", body, user, "status").replace("</style>", CSS + "</style>", 1)


def worst_state(items: list) -> str:
    return "bad" if any(x["state"] == "bad" for x in items) else "warn" if any(x["state"] == "warn" for x in items) else "ok"


def status_banner(items: list) -> str:
    """Strip on the overview when something is wrong (admin only)."""
    bad = [x for x in items if x["state"] in ("bad", "warn")]
    if not bad:
        return ""
    worst = worst_state(items)
    names = ", ".join(html.escape(x["name"]) for x in bad)
    return (f'<div class="banner warn" style="{"border-color:var(--red)" if worst == "bad" else ""}">Жүйе: {names} — '
            f'<a href="/status"><b>тексеру</b></a></div>')


def _ago(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} мин"
    h, m = divmod(minutes, 60)
    return f"{h} сағ {m} мин" if h < 24 and m else f"{h} сағ" if h < 24 else f"{h // 24} күн"


def speed_card(s: dict | None, domain: str, label: str) -> str:
    """Lead response speed card on the overview."""
    if s is None:
        return ""
    head = (f'<style>{CSS}</style><article class="card" style="margin-top:18px"><div class="ch"><h2>Лидке жауап жылдамдығы</h2>'
            f'<span class="meta">amoCRM · {label} · жаңа маркетинг лидтері</span></div>')
    if not s["total"]:
        return head + '<p class="note">Бұл кезеңде жаңа маркетинг лиді жоқ.</p></article>'
    if s.get("partial"):
        head += '<p class="note">amoCRM әрекеттері әлі жүктеліп жатыр — сандар толық емес, бірнеше минуттан соң жаңартыңыз.</p>'
    within = s["within"]
    tone = "var(--green)" if (within or 0) >= 80 else "var(--amber)" if (within or 0) >= 50 else "var(--red)"
    grid = (f'<div class="spg"><div><span>Жаңа лид</span><b>{s["total"]}</b></div>'
            f'<div><span>Орташа жауап (медиана)</span><b>{_ago(s["median"]) if s["median"] is not None else "—"}</b></div>'
            f'<div><span>{SLOW} минут ішінде</span><b style="color:{tone}">{pct_text(within)}</b></div>'
            f'<div><span>Әлі жауапсыз ({SLOW}+ мин)</span><b style="color:{"var(--red)" if s["waiting"] else "var(--green)"}">{len(s["waiting"])}</b></div></div>')
    link = (lambda i: f'https://{domain}/leads/detail/{i}') if domain else (lambda i: "#")
    wait = ""
    if s["waiting"]:
        wait = ('<ul class="spw">' + "".join(
            f'<li><a href="{link(w["id"])}" target="_blank" rel="noopener">Сделка #{w["id"]}</a><span>{html.escape(w["who"] or "жауапты жоқ")}</span>'
            f'<b>{_ago(w["min"]) + " күтіп тұр" if label == "бүгін" else "жауап табылмады"}</b></li>' for w in s["waiting"][:8]) + "</ul>")
    users = ""
    if s["by_user"]:
        rows = "".join(f'<tr><td>{html.escape(n)}</td><td>{u["n"]}</td><td>{_ago(round(u["sum"] / u["n"]))}</td>'
                       f'<td>{round(u["fast"] / u["n"] * 100)}%</td></tr>'
                       for n, u in sorted(s["by_user"].items(), key=lambda kv: -kv[1]["n"]))
        users = (f'<table class="spu"><tr><th>Менеджер</th><th>Лид</th><th>Орташа</th><th>{SLOW} мин ішінде</th></tr>{rows}</table>')
    return (head + grid + wait + users +
            f'<p class="note">Жауап = менеджердің сделкадағы не контакттағы алғашқы әрекеті (қоңырау, чат, жазба, этап ауыстыру). '
            f'{SLOW} минуттан көп жауапсыз тұрған лид туралы Telegram-ға хабар келеді.</p></article>')


SLOW = 15


# ---------- the report as a picture ----------

def _t(x, y, text, size=28, weight=600, fill="#14112b", anchor="start", opacity=1):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"'
            f'{f" opacity={chr(34)}{opacity}{chr(34)}" if opacity != 1 else ""}>{html.escape(str(text))}</text>')


def _delta(cur, prev):
    p = home.delta_pct(cur, prev)
    if p is None:
        return "", "#9b98b3"
    return (f"▲ {p}%" if p >= 0 else f"▼ {abs(p)}%"), ("var(--green)" if p >= 0 else "var(--red)")


def report_svg(m: dict, igx: dict, speed: dict | None, title: str, span: str, prev_label: str) -> str:
    """1080×1350 picture: sales, KPIs, month plan with forecast, Instagram, lead speed."""
    W, H = 1080, 1350
    crm, prev = m["crm"], m["prev"]
    f = m.get("forecast")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="Golos Text, Segoe UI, Roboto, Arial, sans-serif">',
         '<defs><linearGradient id="h" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2F0E51"/><stop offset=".45" stop-color="#7336F7"/>'
         '<stop offset="1" stop-color="#2A78D6"/></linearGradient><linearGradient id="gb" x1="0" x2="1"><stop offset="0" stop-color="#fec200"/>'
         '<stop offset="1" stop-color="#f35b2f"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="#f4f5fa"/>',
         # hero
         f'<rect x="40" y="40" width="{W - 80}" height="420" rx="40" fill="url(#h)"/>',
         _t(88, 112, "EduApp Marketing", 30, 800, "#fff"),
         _t(W - 88, 112, title, 30, 700, "#fff", "end", .85),
         _t(88, 160, span, 26, 500, "#fff", opacity=.75),
         _t(88, 228, "Сатылым сомасы · маркетинг", 26, 600, "#fff", opacity=.8),
         _t(88, 318, money(crm["amount"]), 92, 800, "#fff")]
    d, c = _delta(crm["amount"], prev["amount"])
    if d:
        s.append(f'<rect x="{W - 300}" y="196" width="212" height="48" rx="24" fill="#fff" opacity=".18"/>')
        s.append(_t(W - 194, 229, d, 26, 700, "#fff", "middle"))
        s.append(_t(W - 194, 274, prev_label, 20, 500, "#fff", "middle", .7))
    mpl = m["month_plan"]["amount"]
    upto = igdata.key(m["last"])
    month_amount = sum(c["amount"] for c in m["calendar"] if c["date"] <= upto)  # as the text report: up to the chosen day
    mp = round(month_amount / mpl * 100) if mpl else None
    if mpl:
        w = W - 176
        s.append(_t(88, 372, f"Айлық жоспар · {money(mpl, True)}", 24, 600, "#fff", opacity=.85))
        s.append(_t(W - 88, 372, pct_text(mp), 24, 800, "#fff", "end"))
        s.append(f'<rect x="88" y="390" width="{w}" height="18" rx="9" fill="#fff" opacity=".2"/>')
        if f and not f["final"] and f["pct"]:
            s.append(f'<rect x="88" y="390" width="{w * min(100, f["pct"]) / 100:.0f}" height="18" rx="9" fill="#fff" opacity=".35"/>')
        s.append(f'<rect x="88" y="390" width="{max(18, w * min(100, mp or 0) / 100):.0f}" height="18" rx="9" fill="url(#gb)"/>')
        s.append(_t(88, 440, f"{money(month_amount, True)} жиналды" + (f" ({m['last']:%d.%m} дейін)" if upto < igdata.key(igdata.today()) else ""),
                    22, 500, "#fff", opacity=.8))
        if f and not f["final"]:
            s.append(_t(W - 88, 440, f"ай соңына болжам: {money(f['amount'], True)} ({pct_text(f['pct'])})", 22, 600, "#fff", "end", .9))
    # KPI tiles
    tiles = [("Сатылым саны", num(crm["sales"]), crm["sales"], prev["sales"], ""),
             ("Орташа чек", money(crm["avg"]), crm["avg"], prev["avg"], ""),
             ("Лид", num(crm["leads"]), crm["leads"], prev["leads"], f'жоспар {num(m["plan"]["leads"])} · {pct_text(m["done"]["leads"])}'),
             ("Конверсия", f'{crm["conv"] if crm["conv"] is not None else "—"}%', crm["conv"], prev["conv"],
              f'қажетті {m["conv_plan"]}%' if m.get("conv_plan") is not None else "")]
    tw, th = (W - 80 - 24) / 2, 190
    for i, (label, val, cur, pv, sub) in enumerate(tiles):
        x, y = 40 + (i % 2) * (tw + 24), 490 + (i // 2) * (th + 24)
        s.append(f'<rect x="{x:.0f}" y="{y}" width="{tw:.0f}" height="{th}" rx="30" fill="#fff"/>')
        s.append(_t(x + 36, y + 54, label, 24, 600, "#6b6889"))
        dd, dc = _delta(cur, pv)
        if dd:
            s.append(_t(x + tw - 36, y + 54, dd, 22, 700, dc, "end"))
        s.append(_t(x + 36, y + 124, val, 56, 800))
        if sub:
            s.append(_t(x + 36, y + 164, sub, 21, 500, "#6b6889"))
    # Instagram strip
    y = 490 + 2 * (th + 24) + 6
    ig = m.get("ig") or {}
    growth = None
    if igx.get("followers") is not None and igx.get("prev") is not None:
        growth = igx["followers"] - igx["prev"]
    elif igx.get("growth") is not None:
        growth = igx["growth"]
    cells = [("Жазылушы", f'{num(igx.get("followers"))}' + (f" ({growth:+d})" if growth is not None else "")),
             ("Охват", num(ig.get("reach"))), ("Қаралым", num(ig.get("views"))),
             ("Лайк / коммент", f'{num(ig.get("likes"))} / {num(ig.get("comments"))}')]
    s.append(f'<rect x="40" y="{y}" width="{W - 80}" height="170" rx="30" fill="#fff"/>')
    s.append(_t(76, y + 46, "Instagram", 24, 700, "#7336F7"))
    cw = (W - 152) / 4
    for i, (label, val) in enumerate(cells):
        x = 76 + i * cw
        s.append(_t(x, y + 96, label, 21, 600, "#6b6889"))
        s.append(_t(x, y + 140, val, 30 if len(val) < 14 else 24, 800))
    # lead speed strip
    y += 194
    if speed and speed.get("total"):
        s.append(f'<rect x="40" y="{y}" width="{W - 80}" height="96" rx="30" fill="#fff"/>')
        s.append(_t(76, y + 58, "Лидке жауап", 24, 700, "#7336F7"))
        within = speed["within"]
        txt = (f'медиана {_ago(speed["median"]) if speed["median"] is not None else "—"} · '
               f'{SLOW} мин ішінде {pct_text(within)} · жауапсыз {len(speed["waiting"])}')
        s.append(_t(W - 76, y + 58, txt, 24, 700, "#14112b", "end"))
        y += 120
    s.append(_t(W / 2, min(H - 34, y + 40), "dashboard.eduapp.example.com", 20, 500, "#9b98b3", "middle"))
    s.append("</svg>")
    return "".join(s)


def card_page(svg: str, user: dict, segs: str, name: str, back: str) -> str:
    body = f"""<main class="wrap narrow"><section class="ph cardin"><div><h1>Директорға есеп</h1>
<p>Бір сурет: сатылым, лид, жоспар, ай соңына болжам, Instagram. «Бөлісу» — телефонда бірден WhatsApp не Telegram-ға жібереді.</p></div></section>
<div class="cbar">{segs}<span class="sp"></span><button class="btnp" id="share" type="button">Бөлісу</button>
<button class="btn" id="dl" type="button">PNG жүктеу</button><button class="btn" id="cp" type="button">Көшіру</button>
<button class="btn" type="button" onclick="print()">PDF</button><a class="btn" href="{html.escape(back)}">Артқа</a></div>
<p class="note" id="msg"></p>
<div class="cimg" id="card">{svg}</div></main>
<script>(function(){{var svg=document.querySelector('#card svg'),msg=document.getElementById('msg'),name={name!r};
function png(){{return new Promise(function(ok,no){{var x=new XMLSerializer().serializeToString(svg),img=new Image();
img.onload=function(){{var c=document.createElement('canvas');c.width=1080;c.height=1350;var g=c.getContext('2d');g.drawImage(img,0,0);c.toBlob(ok,'image/png')}};
img.onerror=no;img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(x)}})}}
function save(b){{var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name+'.png';a.click();setTimeout(function(){{URL.revokeObjectURL(a.href)}},2000)}}
document.getElementById('dl').onclick=function(){{png().then(save)}};
document.getElementById('cp').onclick=function(){{png().then(function(b){{return navigator.clipboard.write([new ClipboardItem({{'image/png':b}})])}})
.then(function(){{msg.textContent='Сурет көшірілді — Telegram не WhatsApp чатына Ctrl+V басыңыз.'}}).catch(function(){{msg.textContent='Көшіру бұл браузерде жұмыс істемейді — «PNG жүктеу» басыңыз.'}})}};
document.getElementById('share').onclick=function(){{png().then(function(b){{var f=new File([b],name+'.png',{{type:'image/png'}});
if(navigator.canShare&&navigator.canShare({{files:[f]}}))return navigator.share({{files:[f],title:'EduApp есеп'}});save(b);
msg.textContent='Бұл құрылғыда «Бөлісу» жоқ — сурет жүктелді.'}}).catch(function(){{}})}};}})();</script>"""
    import admin
    css = (CSS + """.cbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px}.cbar .sp{flex:1}
.cbar .segs{display:inline-flex}.cimg{background:var(--surface);border-radius:24px;padding:12px;box-shadow:var(--shadow)}
.cimg svg{display:block;width:100%;height:auto;border-radius:16px}
@media print{@page{size:A4;margin:10mm}.top,.ph,.cbar,#msg,.mnav{display:none!important}body{background:#fff}.cimg{box-shadow:none;padding:0}}""")
    return admin.page("Есеп суреті · EduApp", body, user, "home").replace("</style>", css + "</style>", 1)


# ---------- best time: weekday × hour ----------
WD = ["Дс", "Сс", "Ср", "Бс", "Жм", "Сб", "Жс"]
WD_FULL = ["дүйсенбі", "сейсенбі", "сәрсенбі", "бейсенбі", "жұма", "сенбі", "жексенбі"]


def _peaks(grid: list, n: int = 2) -> list:
    """Best 2-hour windows over the whole week: [(start hour, share %)]."""
    by_hour = [sum(grid[d][h] for d in range(7)) for h in range(24)]
    total = sum(by_hour) or 1
    wins = sorted(((by_hour[h] + by_hour[(h + 1) % 24], h) for h in range(24)), reverse=True)
    out = []
    for v, h in wins:
        if all(abs(h - x) >= 2 for x, _ in out):
            out.append((h, round(v / total * 100)))
        if len(out) == n:
            break
    return out


def best_time_card(m: dict, weeks: int) -> str:
    """«Ең жақсы уақыт» as pictures: leads (or sales) by hour of the day with the peak windows lit gold,
    by weekday with the best / weakest day, the week × hour heat grid, and four small answer tiles."""
    lg, sg = m["leads"], m["sales"]
    total = sum(map(sum, lg))
    if not total:
        return ""
    sales_total = sum(map(sum, sg))

    def pane(g, key, unit):
        tot = sum(map(sum, g)) or 1
        by_hour = [sum(g[d][h] for d in range(7)) for h in range(24)]
        pk = _peaks(g, 2) if tot >= 10 else []
        hot = {h for h0, _ in pk for h in (h0, (h0 + 1) % 24)}
        mxh = max(by_hour) or 1
        hours = "".join(
            f'<div class="{"hot" if h in hot else ""}" data-tip="<span>{h:02d}:00–{(h + 1) % 24:02d}:00</span>{round(by_hour[h] / weeks / 7, 1)} {unit} / күн">'
            f'<i style="--h:{max(4, by_hour[h] / mxh * 100):.0f}%"></i><span>{f"{h:02d}" if h % 3 == 0 else ""}</span></div>' for h in range(24))
        pk_lbl = "".join(f'<span class="bt-pk">{h:02d}:00–{(h + 2) % 24:02d}:00 · {v}%</span>' for h, v in pk)
        day_tot = [sum(r) for r in g]
        best, low = max(range(7), key=lambda d: day_tot[d]), min(range(7), key=lambda d: day_tot[d])
        mxd = max(day_tot) or 1
        days = "".join(
            f'<div class="{"best" if d == best else "low" if d == low else ""}"><span>{WD[d]}</span><i style="--w:{max(3, day_tot[d] / mxd * 100):.0f}%"></i>'
            f'<b>{round(day_tot[d] / weeks)}</b></div>' for d in range(7))
        mx = max(max(r) for r in g) or 1
        heat = ('<span></span>' + "".join(f'<b>{h:02d}</b>' if h % 6 == 0 else "<b></b>" for h in range(24))
                + "".join(f'<span>{WD[d]}</span>' + "".join(
                    f'<i style="--a:{g[d][h] / mx:.2f}" data-tip="<span>{WD_FULL[d]} {h:02d}:00</span>{g[d][h]} {unit}"></i>' for h in range(24)) for d in range(7)))
        return (f'<div class="bt-p" data-btp="{key}"{"" if key == "l" else " hidden"}>'
                f'<div class="bt-sec"><div class="bt-st"><div class="zc-lbl">Тәулік бойы · {unit}</div><div class="bt-pks">{pk_lbl}</div></div>'
                f'<div class="bt-hours">{hours}</div></div>'
                f'<div class="bt-two"><div class="bt-sec"><div class="zc-lbl">Апта күндері · орташа</div><div class="bt-days">{days}</div></div>'
                f'<div class="bt-sec"><div class="zc-lbl">Күн × сағат</div><div class="bt-heat">{heat}</div></div></div></div>')

    day_tot = [sum(r) for r in lg]
    best_day, low_day = max(range(7), key=lambda d: day_tot[d]), min(range(7), key=lambda d: day_tot[d])
    pk = _peaks(lg)
    spk = _peaks(sg, 1) if sales_total >= 10 else []
    win = lambda h: f"{h:02d}:00–{(h + 2) % 24:02d}:00"
    tiles = [("Лид шыңы", win(pk[0][0]) if pk else "—", f"лидтің {pk[0][1]}%-ы" if pk else ""),
             ("Ең белсенді күн", WD_FULL[best_day].capitalize(), f"орташа {round(day_tot[best_day] / weeks)} лид · әлсізі {WD_FULL[low_day]}"),
             ("Сатылым уақыты", win(spk[0][0]) if spk else "—", "менеджерлер бос болсын" if spk else "сатылым аз"),
             ("Жарнама / пост", f"{(pk[0][0] - 2) % 24:02d}:00–{pk[0][0]:02d}:00" if pk else "—", "лид шыңынан 1–2 сағат бұрын")]
    tl = "".join(f'<div class="bt-t{" gold" if i == 3 else ""}"><div class="zc-lbl">{a}</div><b>{v}</b><small>{c}</small></div>' for i, (a, v, c) in enumerate(tiles))
    import charts
    return (charts.CSS + f'<article class="card bt-card cardin" style="--i:12;margin-top:18px"><div class="bt-h"><div><div class="zc-lbl">Ең жақсы уақыт</div>'
            f'<div class="bt-m">соңғы {weeks} апта · Астана уақыты · маркетинг сделкалары</div></div>'
            f'<div class="zcv-tabs" role="tablist"><button type="button" class="on" data-bt="l">Лид · {total}</button>'
            f'<button type="button" data-bt="s">Сатылым · {sales_total}</button></div></div>'
            f'<div class="bt-tiles">{tl}</div>{pane(lg, "l", "лид")}{pane(sg, "s", "сатылым")}</article>'
            '<script>document.querySelectorAll("[data-bt]").forEach(function(b){b.onclick=function(){var k=b.dataset.bt;'
            'document.querySelectorAll("[data-bt]").forEach(function(x){x.classList.toggle("on",x===b)});'
            'document.querySelectorAll("[data-btp]").forEach(function(p){p.hidden=p.dataset.btp!==k})}})</script>' + charts.JS)


BEST_CSS = """.bt-card{display:flex;flex-direction:column;gap:18px;padding:22px;border-radius:var(--r)}
.bt-h{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}.bt-m{margin-top:4px;font-size:0.8125rem;font-weight:400;color:var(--faint)}
.bt-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.bt-t{padding:14px 16px;border-radius:10px;background:var(--surface2);display:flex;flex-direction:column;gap:4px}
.bt-t b{font-size:1.375rem;font-weight:600;letter-spacing:-.015em;font-variant-numeric:tabular-nums;margin-top:2px}.bt-t small{font-size:0.75rem;font-weight:400;color:var(--faint)}
.bt-t.gold{background:color-mix(in srgb,var(--gilt) 16%,var(--surface))}.bt-t.gold b{color:var(--gold)}
.bt-p{display:flex;flex-direction:column;gap:18px}.bt-p[hidden]{display:none}
.bt-sec{display:flex;flex-direction:column;gap:10px;min-width:0}.bt-st{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.bt-pks{display:flex;gap:6px;flex-wrap:wrap}.bt-pk{padding:4px 10px;border-radius:999px;font-size:0.75rem;font-weight:500;font-variant-numeric:tabular-nums;color:var(--gold);background:color-mix(in srgb,var(--gilt) 16%,transparent)}
.bt-hours{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:4px;height:130px;align-items:end}
.bt-hours div{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;height:100%}
.bt-hours i{width:100%;max-width:18px;height:var(--h);border-radius:999px;background:color-mix(in srgb,var(--accent) 22%,var(--surface2));transition:background .15s}
.bt-hours .hot i{background:var(--gilt)}.bt-hours div:hover i{background:var(--accent)}
.bt-hours span{font-size:0.75rem;font-weight:400;color:var(--faint);height:14px;font-variant-numeric:tabular-nums}
.bt-two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.5fr);gap:22px}
.bt-days{display:grid;gap:8px}.bt-days div{display:grid;grid-template-columns:28px 1fr 34px;align-items:center;gap:10px;font-size:0.8125rem;font-weight:500;color:var(--muted)}
.bt-days i{display:block;height:12px;border-radius:999px;width:var(--w);background:color-mix(in srgb,var(--accent) 45%,var(--surface2))}
.bt-days .best i{background:var(--gilt)}.bt-days .low i{background:color-mix(in srgb,var(--accent) 16%,var(--surface2))}
.bt-days b{text-align:right;font-weight:600;color:var(--text);font-variant-numeric:tabular-nums}
.bt-heat{display:grid;grid-template-columns:24px repeat(24,minmax(0,1fr));gap:3px;font-size:0.6875rem;color:var(--faint)}
.bt-heat b{font-weight:400;height:14px;font-size:0.75rem}.bt-heat span{font-weight:500;color:var(--muted);line-height:1.455;font-size:0.75rem}
.bt-heat i{height:16px;border-radius:5px;background:color-mix(in srgb,var(--accent) calc(var(--a) * 100%),var(--surface2))}
@media (max-width:1000px){.bt-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}.bt-two{grid-template-columns:1fr}}
@media (max-width:560px){.bt-hours{gap:2px;height:110px}.bt-heat{gap:2px;grid-template-columns:20px repeat(24,minmax(0,1fr))}.bt-heat i{height:12px}}"""
