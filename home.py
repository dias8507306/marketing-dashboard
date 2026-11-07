"""Marketing home page (the default page), direction «Құрмет тақтасы» (the school honour board): the month's
sales sit on a deep purple board with a plan line and a gilt «should be today» pin; under it every day of the
month is a plaque that turns gilt when the day's lead plan was met (tap one to read that day). Four figures
follow as ruled rows. Order: period → board → rows → greeting → trend → plans + streak + bonus → Instagram →
report. The celebration overlay lives in celebrate.py."""
import html
import json
from datetime import datetime, timedelta

import celebrate
import charts
import ui
from dashboard import MONTHS, WEEKDAYS
from mkt import PERIODS
from ui import EGGS, ICON, KIT, PRAISE, STREAK_LINES, STYLE, THEME_JS, icon, praise_of_day, topbar  # noqa: F401

MONTH_FULL = ["Қаңтар", "Ақпан", "Наурыз", "Сәуір", "Мамыр", "Маусым", "Шілде", "Тамыз", "Қыркүйек", "Қазан", "Қараша", "Желтоқсан"]


def money(n, short=False):
    if n is None:
        return "—"
    if short and abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".") + " млн ₸"
    if short and abs(n) >= 10_000:
        return f"{n / 1000:.0f} мың ₸"
    return f"{round(n):,}".replace(",", " ") + " ₸"


def num(n):
    return "—" if n is None else f"{round(n):,}".replace(",", " ")


def figure(val, suffix="", cls="fig"):
    if val is None:
        return f'<div class="{cls}">—</div>'
    return f'<div class="{cls}" data-to="{round(val)}" data-suffix="{html.escape(suffix)}">{num(val)}{suffix}</div>'


def delta_pct(cur, prev):
    if cur is None or not prev:
        return None
    p = round((cur - prev) / prev * 100)
    return None if abs(p) > 300 else p  # «Қайдан келді» is filled only since 12.10.2026


def pill(cur, prev, light=False):
    p = delta_pct(cur, prev)
    if p is None:
        return f'<span class="pill flat{" w" if light else ""}">—</span>'
    return f'<span class="pill {"up" if p >= 0 else "down"}{" w" if light else ""}">{"▲" if p >= 0 else "▼"} {abs(p)}%</span>'


def chg(cur, prev, cls="rc"):
    p = delta_pct(cur, prev)
    if p is None:
        return f'<em class="{cls} fl" title="өткен кезеңмен салыстыру жоқ">—</em>'
    return f'<em class="{cls} {"up" if p >= 0 else "dn"}" title="өткен кезеңмен">{"+" if p >= 0 else "−"}{abs(p)}%</em>'


def plaques(m: dict, q: str, anchor_key: str) -> str:
    """The honour board's strip: one plaque per day of the month, gilt when the day's lead plan was met,
    dashed for today, an empty frame for days still to come. A plaque opens that day."""
    lead_day = m["lead_day"] or 100
    mon = MONTHS[m["last"].month - 1]
    pick = m["period"] in ("day", "range")
    lo, hi = f'{m["first"]:%Y-%m-%d}', f'{m["last"]:%Y-%m-%d}'
    out = []
    for c in m["calendar"]:
        if c["future"]:
            out.append(f'<span class="pq f" aria-hidden="true"><span>{c["day"]}</span><b></b></span>')
            continue
        cls = "pq" + (" g" if c["done"] else "") + (" t" if c["today"] else "") + (" sel" if pick and lo <= c["date"] <= hi else "")
        lab = f'{c["day"]} {mon}: {c["leads"]} лид' + (", жоспар орындалды" if c["done"] else "")
        out.append(f'<a class="{cls}" href="?p=day&d={c["date"]}{q}" aria-label="{html.escape(lab)}"'
                   f'{" aria-current=date" if pick and c["date"] == anchor_key else ""}><span>{c["day"]}</span><b>{c["leads"]}</b></a>')
    done = sum(1 for c in m["calendar"] if c["done"])
    return (f'<div class="bd-days{" pick" if pick else ""}" id="pqs">{"".join(out)}</div>'
            f'<div class="bd-lg"><span><i></i>күндік лид жоспары ({num(lead_day)}+) орындалды</span><span>{done} күн</span></div>')


def tasks_block(tasks: list, today_key: str, names: dict, show_who: bool, back: str) -> str:
    """Open tasks due today or earlier (and undated ones), ticked off right here; the full list lives on /dept."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    open_ = [t for t in tasks if t["status"] != "done" and (not t.get("due") or t["due"][:10] <= today_key)]
    done = sum(1 for t in tasks if t["status"] == "done" and (t.get("due") or "")[:10] == today_key)
    rows = ""
    for t in open_[:6]:
        due = t.get("due") or ""
        hhmm = due[11:16] if len(due) >= 16 else ""
        late = due and (due[:16] if hhmm else due[:10] + " 23:59") < now
        when = ("мерзімі өтті" if late else hhmm) if due else ""
        who = f'<small>{html.escape(names.get(t["login"], t["login"]))}</small>' if show_who else ""
        rows += (f'<div class="tq"><form method="post" action="/dept/task"><input type="hidden" name="id" value="{html.escape(t["id"])}">'
                 f'<input type="hidden" name="status" value="done"><input type="hidden" name="back" value="{html.escape(back)}">'
                 f'<button class="cbx" type="submit" aria-label="Орындалды: {html.escape(t["title"])}"></button></form>'
                 f'<span class="tqt">{html.escape(t["title"])}{who}</span><time class="{"late" if late else ""}">{when}</time></div>')
    if not rows:
        rows = f'<p class="tqe">{"Бүгінгі тапсырмалар орындалды." if done else "Бүгінге тапсырма жоқ."}</p>'
    more = len(open_) - 6
    return (f'<section class="tqs" aria-label="Бүгінгі тапсырмалар"><div class="ch"><h2>Бүгінгі тапсырмалар</h2>'
            f'<span class="meta">{done} / {done + len(open_)}</span><a class="more" href="/dept">Барлығы{f" · тағы {more}" if more > 0 else ""}</a></div>{rows}</section>')


def spark(vals, color, w=240, h=46, fill=True, sw=2.2, cls="spark"):
    return ui.spark(vals, color, w, h, fill, sw, cls)

def near(p):
    if p is None:
        return "Жоспар қойылмаған"
    if p >= 100:
        return "Жоспар орындалды"
    if p >= 80:
        return "Жақындап қалдық!"
    if p >= 50:
        return "Жартысынан өттік"
    return "Әр лид маңызды"


def bar(p, tone, label):
    w = max(0, min(100, p or 0))
    ok = (p or 0) >= 100
    return (f'<div class="pbar {tone}{" ok" if ok else ""}" role="progressbar" aria-label="{html.escape(label)}" aria-valuenow="{p or 0}" '
            f'aria-valuemin="0" aria-valuemax="100"><i style="--w:{w}%"></i><b style="left:50%"></b><b style="left:75%"></b><b style="left:100%"></b>'
            + ('<span class="okc"><svg viewBox="0 0 24 24"><path d="M5 12.5 10 17l9-10"/></svg></span>' if ok else "") + "</div>")


def wk_first_key(m: dict) -> str:
    return m["first"].strftime("%Y-%m-%d") if m["period"] == "week" else (m["last"] - timedelta(days=m["last"].weekday())).strftime("%Y-%m-%d")


def wk_last_key(m: dict) -> str:
    return (datetime.strptime(wk_first_key(m), "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")


def pct_text(p):
    return "—" if p is None else f"{p}%"


def forecast_card(m: dict, plan_amount: int) -> str:
    """V1 «trajectory»: the month's sales added up day by day (solid), the forecast to the month end (dotted),
    the plan pace (dashed gold); on the right what each remaining day needs against today's pace."""
    f = m.get("forecast")
    if not f or not plan_amount:
        return ""
    cal = m["calendar"]
    dim = len(cal) or 30
    past = [c for c in cal if not c["future"]]
    cum, run = [], 0
    for c in past:
        run += c["amount"] or 0
        cum.append(run)
    n = len(cum)
    W, H, pt, pb = 600, 220, 14, 10
    top = max(plan_amount, f["amount"] or 0, run) * 1.06 or 1
    x = lambda i: i / max(1, dim) * W           # i = days passed (0 … dim)
    y = lambda v: pt + (1 - v / top) * (H - pt - pb)
    pts = [(x(0), y(0))] + [(x(i + 1), y(v)) for i, v in enumerate(cum)]
    line = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    area = line + f" L{pts[-1][0]:.1f},{H} L0,{H} Z"
    ex, ey = pts[-1]
    fx, fy = x(dim), y(f["amount"] or 0)
    ns = 'vector-effect="non-scaling-stroke"'
    proj = "" if f["final"] else (f'<path d="M{ex:.1f},{ey:.1f} L{fx:.1f},{fy:.1f}" fill="none" stroke="var(--accent)" stroke-width="3" '
                                  f'stroke-dasharray="2 7" stroke-linecap="round" {ns}/><path d="M{fx:.1f},{fy:.1f}h0" stroke="var(--accent)" stroke-width="10" stroke-linecap="round" {ns}/>')
    svg = (f'<svg class="fct-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="fcA" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="#7336F7" stop-opacity=".32"/><stop offset="1" stop-color="#7336F7" stop-opacity="0"/></linearGradient></defs>'
           f'<path d="M0,{y(0):.1f} L{x(dim):.1f},{y(plan_amount):.1f}" stroke="var(--plan)" stroke-width="2" stroke-dasharray="4 6" fill="none" {ns}/>'
           f'<path d="M{x(dim):.1f},{y(plan_amount):.1f}h0" stroke="var(--plan)" stroke-width="10" stroke-linecap="round" {ns}/>'
           f'<path d="{area}" fill="url(#fcA)"/><path d="{line}" fill="none" stroke="var(--accent)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" {ns}/>'
           f'{proj}<path d="M{ex:.1f},{ey:.1f}h0" stroke="var(--accent)" stroke-width="13" stroke-linecap="round" {ns}/>'
           f'<path d="M{ex:.1f},{ey:.1f}h0" stroke="var(--surface)" stroke-width="6" stroke-linecap="round" {ns}/></svg>')
    mon = MONTHS[m["last"].month - 1]
    ok = (f["pct"] or 0) >= 100
    chip = ("" if f["final"] and ok else
            f'<span class="fc-chip {"ok" if ok else "bad"}">{"▲ жоспар орындалады" if ok else "▼ " + money(f["gap"], True) + " жетпейді"}</span>')
    head = (f'<div class="fc-h"><div><div class="zc-lbl">{"Ай қорытындысы" if f["final"] else "Ай соңына болжам"}</div>'
            f'<div class="zc-num fc-v">{money(f["amount"], True).replace(" ₸", "")}<span class="zc-unit">₸</span></div>'
            f'<div class="zc-cap">жоспардың {pct_text(f["pct"])} · {"ай аяқталды" if f["final"] else "қазіргі қарқын бойынша"}</div></div>{chip}</div>')
    axis = (f'<div class="fc-x"><span>1 {mon}</span><span class="now">{"" if f["final"] else "бүгін · "}{money(run, True)}</span><span>{dim} {mon}</span></div>'
            f'<div class="fc-leg"><span><em class="a"></em>нақты</span>' + ("" if f["final"] else f'<span class="p"><em class="d"></em>болжам {money(f["amount"], True)}</span>')
            + f'<span class="g"><em class="g"></em>жоспар {money(plan_amount, True)}</span></div>')

    need = ""
    if not f["final"]:
        elapsed = max(1, len(past))
        sales_pace = (m["month"]["sales"] or 0) / elapsed

        def tile(label, need_v, now_v, fmt):
            if not need_v:
                return ""
            w = max(3, min(100, (now_v or 0) / need_v * 100))
            return (f'<div class="fc-t"><div class="fc-th"><span>{label}</span><b>{fmt(need_v)}</b></div>'
                    f'<div class="fc-c"><div><span>керек</span><i class="nd" style="width:100%"></i><em>{fmt(need_v)}</em></div>'
                    f'<div><span>қазір</span><i class="nw" style="width:{w:.0f}%"></i><em>{fmt(now_v)}</em></div></div></div>')
        tiles = (tile("Сатылым сомасы", f.get("amount_need"), f.get("amount_pace"), lambda v: money(v, True))
                 + tile("Сатылым саны", f.get("sales_need"), round(sales_pace, 1), lambda v: f"≈ {num(round(v))}")
                 + tile("Лид", f.get("leads_for_sales"), f.get("leads_pace"), lambda v: f"≈ {num(round(v))}"))
        if ok:
            tiles = '<div class="fc-t"><div class="fc-th"><span>Жақсы қарқын</span></div><p class="zc-cap">Қазіргі қарқынды сақтасаңыз, ай жоспары орындалады.</p></div>'
        need = f'<div class="fc-need"><div class="zc-lbl">Жоспарға жету үшін күн сайын · {f["left"]} күн</div>{tiles}</div>'
    return (f'<article class="card fcc2 cardin" style="--i:5;margin-top:18px"><div class="fc-main">{head}{svg}{axis}</div>{need}</article>')


FORECAST_CSS_NEW = """
.fcc2{--plan:#F2AE00;display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:26px;padding:24px;border-radius:26px}
.fcc2:has(.fc-main:only-child){grid-template-columns:1fr}
.fc-h{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.fc-v{font-size:3.25rem;margin:8px 0 8px}
.fc-chip{display:inline-flex;align-items:center;padding:6px 12px;border-radius:999px;font-size:0.75rem;font-weight:800;white-space:nowrap}
.fc-chip.bad{color:var(--red);background:color-mix(in srgb,var(--red) 12%,transparent)}.fc-chip.ok{color:var(--green);background:color-mix(in srgb,var(--green) 12%,transparent)}
.fct-svg{display:block;width:100%;height:200px;margin-top:14px;overflow:visible}
.fc-x{display:flex;justify-content:space-between;font-size:0.6875rem;font-weight:800;color:var(--faint);margin-top:8px}.fc-x .now{color:var(--accent)}
.fc-leg{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px;font-size:0.75rem;font-weight:700;color:var(--muted)}
.fc-leg span{display:inline-flex;align-items:center;gap:6px}.fc-leg .p{color:var(--accent)}.fc-leg .g{color:var(--plan)}
.fc-leg em{display:inline-block;width:16px;height:0;border-top:3px solid var(--accent);border-radius:2px}
.fc-leg em.d{border-top-style:dotted}.fc-leg em.g{border-top:2px dashed var(--plan)}
.fc-need{display:flex;flex-direction:column;gap:12px}
.fc-t{padding:14px 16px;border-radius:18px;background:var(--surface2)}
.fc-th{display:flex;justify-content:space-between;align-items:baseline;gap:10px}.fc-th span{font-size:0.8125rem;font-weight:700;color:var(--muted)}
.fc-th b{font-size:1.375rem;font-weight:900;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.fc-c{display:grid;gap:6px;margin-top:10px}.fc-c div{display:grid;grid-template-columns:44px 1fr 70px;align-items:center;gap:8px;font-size:0.6875rem;font-weight:700;color:var(--faint)}
.fc-c i{display:block;height:8px;border-radius:9px}.fc-c i.nd{background:var(--plan)}.fc-c i.nw{background:var(--accent)}
.fc-c em{font-style:normal;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
@media (max-width:900px){.fcc2{grid-template-columns:1fr}.fc-v{font-size:2.625rem}.fct-svg{height:170px}}
"""
FORECAST_CSS_NEW += ":root[data-theme=dark] .fcc2{--plan:#FEC200}@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .fcc2{--plan:#FEC200}}"



FORECAST_CSS = """
.rcb{display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 18px;border-radius:10px;font-weight:600;color:var(--on-accent);background:var(--accent)}.rcb .i{width:18px;height:18px}
@media (max-width:720px){.rcb{flex:1;justify-content:center}}
.fcc{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;align-items:start}
.fcv{font-size:2.5rem;line-height:1.2;font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.fcs{margin:4px 0 14px;color:var(--muted)}
.fcb{position:relative;height:14px;border-radius:999px;background:var(--bar);overflow:hidden}
.fcb i{position:absolute;left:0;top:0;bottom:0;border-radius:999px}.fcb i.a{background:linear-gradient(90deg,var(--accent),var(--accent2))}
.fcb i.g{background:color-mix(in srgb,var(--accent) 35%,transparent)}
.fcl{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px;font-size:0.8125rem;color:var(--muted)}
.fcl i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.fcl i.a{background:var(--accent)}.fcl i.g{background:color-mix(in srgb,var(--accent) 35%,transparent)}
.fcn{background:var(--surface2);border-radius:16px;padding:14px 16px}.fcn h3{margin:0 0 8px;font-size:0.875rem}
.fcr{display:grid;grid-template-columns:1fr auto;gap:0 12px;padding:8px 0;border-top:1px solid var(--border)}.fcr:first-of-type{border-top:0}
.fcr span{font-weight:600}.fcr b{font-size:1.125rem;font-variant-numeric:tabular-nums}.fcr small{grid-column:1/-1;color:var(--muted);font-size:0.75rem}
.fcn .note{margin:8px 0 0}
@media (max-width:900px){.fcc{grid-template-columns:1fr}.fcv{font-size:2rem;line-height:1.25}}
"""


def hero_cols(m: dict) -> str:
    day_plan = (m["month_plan"]["amount"] or 0) / (m["dim"] or 30)
    days = [{"value": c["amount"], "plan": day_plan or None, "future": c["future"], "now": c["today"],
             "tip": f'<span>{c["day"]} {MONTHS[m["last"].month - 1]}</span>{money(c["amount"])}' + (f' / {money(day_plan, True)}' if day_plan else "")}
            for c in m["calendar"]]
    return charts.cols(days)


def trend_block(m: dict, t: dict) -> str:
    """The canvas line (leads / sales ₸ / sales count, this month against the previous one) and the bento row."""
    cal = [c for c in m["calendar"] if not c["future"] and not c["today"]] or [c for c in m["calendar"] if not c["future"]]
    if not cal:
        return ""
    mon = MONTHS[m["last"].month - 1]
    labels = [f'{c["day"]} {mon}' for c in cal]
    pd = t.get("prev_days") or []
    picked = m["period"] == "range"
    line = cal
    if picked:  # the line shows exactly the picked days, against the same number of days before them
        line = m["series"]
        labels = [f'{d.day} {MONTHS[d.month - 1]}' for d in (m["first"] + timedelta(days=i) for i in range(len(line)))]
        pd = t.get("range_prev") or []

    def prev(k):
        return [pd[i][k] if i < len(pd) else None for i in range(len(line))]

    def ser(tab, label, k, unit="", unit_big=""):
        cur = [c[k] for c in line]
        pv = prev(k)
        ps = sum(v for v in pv if v is not None)
        return {"tab": tab, "label": label, "cur": cur, "prev": pv, "total": sum(cur), "delta": charts.delta(sum(cur), ps), "unit": unit, "unitBig": unit_big}
    canvas = charts.canvas("Таңдалған күндер" if picked else "Ай динамикасы", [ser("Лид", f"Лид · {ui.dr_label(m['first'], m['last'], m['last'])}" if picked else f"Лид · {MONTH_FULL[m['last'].month - 1].lower()}", "leads"),
                                            ser("Сатылым ₸", "Сатылым сомасы", "amount", " ₸", "₸"),
                                            ser("Сатылым саны", "Сатылым саны", "sales")],
                           labels, prev_label="алдыңғы осындай кезеңмен" if picked else "өткен айдың осы күндерімен", last_label="соңғы күн" if picked else "кеше" if len(cal) < len([c for c in m["calendar"] if not c["future"]]) else "бүгін")

    lead_day = m["lead_day"] or 100
    def lvl(v):
        p = (v or 0) / lead_day
        return 0 if p < .25 else 1 if p < .5 else 2 if p < .8 else 3 if p < 1 else 4
    cal_all = m["calendar"]
    dots = charts.dots([{"level": lvl(c["leads"]), "future": c["future"], "now": c["today"],
                         "tip": f'<span>{c["day"]} {mon}</span>{c["leads"]} лид'} for c in cal_all], 16)
    met = sum(1 for c in cal if c["leads"] >= lead_day)
    today_c = next((c for c in cal_all if c["today"]), cal[-1])
    c1 = charts.card("s7", "Лид күнтізбесі", charts.num(today_c["leads"], f"/ {lead_day}"), dots,
                     f"жоспар орындалған күн: {met} / {len(cal)} · түс неғұрлым қою — лид соғұрлым көп", i=6)

    wd = t.get("week_days") or []
    wf = t.get("week_first")
    tk = today_key_of(m)
    names = ["Дс", "Сс", "Ср", "Бс", "Жм", "Сб", "Жс"]
    wdays = []
    for i, d in enumerate(wd):
        key = (wf + timedelta(days=i)).strftime("%Y-%m-%d") if wf else ""
        wdays.append({"label": names[i], "value": d["leads"], "now": key == tk, "future": bool(key) and key > tk,
                      "tip": f'<span>{names[i]}</span>{d["leads"]} лид'})
    wsum = sum(d["leads"] for d in wd)
    src = t.get("sources") or []
    c2 = charts.card("s6" if len(src) >= 2 else "s12", "Осы апта · лид", charts.num(wsum, f"/ {lead_day * 7}"), charts.week(wdays),
                     f'апталық жоспардың {round(wsum / (lead_day * 7) * 100) if lead_day else 0}%', i=7)

    if len(src) >= 2:
        a_name, a = src[0]
        b_val = sum(v for _, v in src[1:])
        short = "Таргет" if "таргет" in a_name.lower() else a_name[:18]
        c3 = charts.card("s6", "Лид көзі", charts.num(round(a / (a + b_val) * 100) if (a + b_val) else 0, f"% {short.lower()}"),
                         charts.split(a, b_val, short, "Органика" if len(src) == 2 else "Басқа"), "таңдалған кезең бойынша", i=8)
    else:
        c3 = ""
    mp = m["month_pct"]["amount"]
    mpl = m["month_plan"]["amount"]
    c4 = charts.card("s6" if c3 else "s12", "Ай жоспары · сатылым", "", charts.ring(mp, f'{mp or 0}<span class="zc-unit">%</span>',
                     f'{money(m["month"]["amount"], True)} / {money(mpl, True) if mpl else "—"}'), "", i=9)
    return charts.CSS + canvas + charts.bento([c2, c3] if c3 else [c2]) + charts.JS


def today_key_of(m: dict) -> str:
    return next((c["date"] for c in m["calendar"] if c["today"]), "9999-99-99")


def render(m: dict, *, trend: dict | None = None, ads_html: str = "", user: dict, staff: list, who: str | None, anchor_key: str, today_key: str,
           amo_state: dict, report_text: str, spark14: dict | None = None, demo_ok: bool = False, planok: bool = False,
           top_html: str = "", best_html: str = "", tasks: list | None = None) -> str:
    sp = spark14 or {k: [] for k in ("amount", "sales", "leads", "avg", "conv")}
    crm, prev, plan, done = m["crm"], m["prev"], m["plan"], m["done"]
    first, last = m["first"], m["last"]
    period_label = dict(PERIODS).get(m["period"], "таңдалған күндер").lower()
    span = (f"{first.day} {MONTHS[first.month - 1]} {first.year}" if first == last else
            f"{first.day} {MONTHS[first.month - 1]} {first.year} – {last.day} {MONTHS[last.month - 1]} {last.year}" if first.year != last.year else
            f"{first.day} {MONTHS[first.month - 1]} – {last.day} {MONTHS[last.month - 1]} {last.year}")
    q = f"&who={html.escape(who)}" if who else ""
    is_admin = user["r"] == "admin"
    b, st = m["bonus"], m["streak"]
    first_name = m["first_name"] or (user.get("n") or "").split()[0]

    segs = "".join(f'<a class="seg{" on" if m["period"] == p else ""}" href="?p={p}&d={anchor_key}{q}">{t}</a>' for p, t in PERIODS)
    prev_d = (first - timedelta(days=1)).strftime("%Y-%m-%d")
    next_d = (last + timedelta(days=1)).strftime("%Y-%m-%d")
    picked = m["period"] == "range"
    n_days = (last - first).days + 1
    # the page's own address, and the two arrows: the same number of days before / after the picked ones
    here = f'p=range&d1={first:%Y-%m-%d}&d2={last:%Y-%m-%d}' if picked else f'p={m["period"]}&d={anchor_key}'
    prev_href = (f'?p=range&d1={first - timedelta(days=n_days):%Y-%m-%d}&d2={first - timedelta(days=1):%Y-%m-%d}{q}' if picked else f'?p={m["period"]}&d={prev_d}{q}')
    next_href = (f'?p=range&d1={next_d}&d2={last + timedelta(days=n_days):%Y-%m-%d}{q}' if picked else f'?p={m["period"]}&d={next_d}{q}')
    who_sel = ""
    if is_admin and staff:
        opts = "".join(f'<option value="{html.escape(s["login"])}"{" selected" if s["login"] == who else ""}>{html.escape(s["name"])}</option>' for s in staff)
        who_sel = (f'<form method="get" class="who">{"".join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in (x.split("=") for x in here.split("&")))}'
                   f'<label class="sr" for="who">Қызметкер</label><select id="who" name="who" onchange="this.form.submit()">{opts}</select></form>')

    # ---- hero: sales amount
    mp, mpl = m["month_pct"], m["month_plan"]
    due_pct = m["elapsed"] / m["dim"] * 100 if m["dim"] else 100
    if m["period"] == "day":
        ld = m["lead_day"] or 100
        dp = round((crm["leads"] or 0) / ld * 100) if ld else 0
        rail = (f'<div class="bd-plan"><div class="bd-rail{" ok" if dp >= 100 else ""}" role="progressbar" aria-label="Күндік лид жоспары" '
                f'aria-valuenow="{dp}" aria-valuemin="0" aria-valuemax="100"><i style="--w:{min(dp, 100)}%"></i></div>'
                f'<div class="bd-rl"><span>Лид <b>{num(crm["leads"])}</b> / {num(ld)} · {dp}%</span>'
                f'<em>{"күндік жоспар орындалды" if dp >= 100 else "күндік жоспарға " + num(ld - (crm["leads"] or 0)) + " лид жетпеді"}</em></div></div>')
    elif mpl["amount"]:
        w = max(0, min(100, mp["amount"] or 0))
        due_amt = mpl["amount"] * min(due_pct, 100) / 100
        ahead = m["month"]["amount"] >= due_amt
        rail = (f'<div class="bd-plan"><div class="bd-rail{" ok" if (mp["amount"] or 0) >= 100 else ""}" role="progressbar" aria-label="Айлық сатылым жоспары" '
                f'aria-valuenow="{mp["amount"] or 0}" aria-valuemin="0" aria-valuemax="100"><i style="--w:{w}%"></i>'
                + (f'<u style="left:{due_pct:.1f}%" title="бүгінге дейін болуы керек"></u>' if due_pct < 100 else "") + '</div>'
                f'<div class="bd-rl"><span><b>{money(m["month"]["amount"], True)}</b> / {money(mpl["amount"], True)} · {pct_text(mp["amount"])}</span>'
                f'<em>{"жоспар орындалды" if (mp["amount"] or 0) >= 100 else ("бүгінгі деңгейден озып тұр" if ahead else "бүгінге дейін " + money(due_amt, True) + " болуы керек")}</em></div></div>')
    else:
        rail = '<div class="bd-plan"><div class="bd-rl"><span>Айлық жоспар қойылмаған</span></div></div>'
    hero = (f'<section class="board" aria-label="Сатылым">'
            f'<div class="bd-main"><div class="bd-h"><span>Сатылым · {"жеке нәтиже" if m.get("personal") else "маркетинг"} · {period_label}</span>{chg(crm["amount"], prev["amount"], "bc")}</div>'
            f'{figure(crm["amount"], " ₸", "bd-v")}{rail}</div>'
            f'{plaques(m, q, anchor_key)}</section>')

    def row(label, value, cur, prv, sub):
        return (f'<div class="rw"><span class="rl">{label}</span>{chg(cur, prv)}<b class="rv">{value}</b><small class="rs">{sub}</small></div>')
    kpis = ('<section class="rows" aria-label="Көрсеткіштер">'
            + row("Лид", num(crm["leads"]), crm["leads"], prev["leads"], f'жоспар {num(plan["leads"])} · {pct_text(done["leads"])}')
            + row("Сатылым саны", num(crm["sales"]), crm["sales"], prev["sales"], "жабылған сделка")
            + row("Орташа чек", money(crm["avg"]), crm["avg"], prev["avg"], "сома ÷ сатылым саны")
            + row("Конверсия", f'{crm["conv"] if crm["conv"] is not None else "—"}%', crm["conv"], prev["conv"],
                  f'қажетті {m["conv_plan"] if m["conv_plan"] is not None else "—"}%')
            + '</section>')

    trend_html = trend_block(m, trend or {})
    names = {x["login"]: x["name"] for x in staff}
    tasks_html = tasks_block(tasks or [], today_key, names, user.get("r") in ("admin", "lead"), f'/?p={m["period"]}&d={anchor_key}')

    # ---- plans
    wk, wpl, wp = m["week"], m["week_plan"], m["week_pct"]
    left_days = max(0, m["dim"] - m["elapsed"])
    left_amount = max(0, (mpl["amount"] or 0) - m["month"]["amount"])

    def prow(title, p, tone, a, b_, note):
        return (f'<div class="pl"><div class="plt"><span>{title}</span><b>{pct_text(p)}</b></div>{bar(p, tone, title)}'
                f'<div class="pls"><span>{a} / {b_}</span><span class="{"okt" if (p or 0) >= 100 else ""}">{note}</span></div></div>')
    editing = is_admin and who
    me_s = next((s for s in staff if s["login"] == who), None) if editing else None
    pe = (me_s or {}).get("plans") or {}
    edit_btn = (f'<a class="btn sm pedit" href="/dept">{icon("edit")}Жоспарды өзгерту</a>' if user.get("r") in ("admin", "lead") else "")
    me_s = None  # the plan is the department's now: it is edited on /dept, not in a dialog per person
    plan_dlg = "" if not me_s else f"""<dialog class="pdlg" id="pdlg"><form class="f" method="post" action="/plan-quick">
<input type="hidden" name="login" value="{html.escape(me_s['login'])}"><input type="hidden" name="back" value="?p={m['period']}&d={anchor_key}&who={html.escape(me_s['login'])}">
<div class="pdh"><div><h2>{html.escape(me_s['name'])} · жоспар</h2><p>Өзгеріс бірден дашбордқа түседі</p></div><button class="pdx" type="button" data-pclose aria-label="Жабу">{icon("x")}</button></div>
<label>Айлық сатылым жоспары, ₸<input name="amount" id="pamt" inputmode="numeric" autocomplete="off" placeholder="мысалы 10 000 000" value="{f"{pe['amount']:,}".replace(",", " ") if pe.get("amount") else ""}">
<small id="pamtx">Толық сомасын жазыңыз</small></label>
<div class="qa">{"".join(f'<button type="button" data-a="{v}">{t}</button>' for v, t in ((1000000, "1 млн"), (3000000, "3 млн"), (5000000, "5 млн"), (10000000, "10 млн"), (20000000, "20 млн")))}</div>
<div class="row2"><label>Күндік лид жоспары<input name="leads_day" type="number" min="1" inputmode="numeric" value="{pe.get('leads_day') or 100}"></label>
<label>Бонус, % сатылымнан<input name="bonus_pct" type="number" min="0" max="100" step="0.1" inputmode="decimal" value="{pe.get('bonus_pct') or ''}"></label></div>
<small>Апталық және күндік сатылым жоспары айлықтан өздігінен есептеледі. Бонус айлық жоспар орындалғанда төленеді.</small>
<button class="btnp" type="submit">Сақтау</button></form></dialog>"""
    # where the bars should be by today: share of the month / week already gone
    try:
        _td = datetime.strptime(today_key, "%Y-%m-%d")
        week_due = (_td.weekday() + 1) / 7 * 100 if wk_first_key(m) <= today_key <= wk_last_key(m) else 100
    except ValueError:
        week_due = 100
    month_due = m["elapsed"] / m["dim"] * 100 if m["dim"] else 100

    def prow2(title, p, tone, a, b_, note, due):
        w = max(0, min(100, p or 0))
        ok = (p or 0) >= 100
        behind = not ok and p is not None and p < due - 3
        return (f'<div class="pr"><div class="pr-t"><span>{title}</span><b class="{"ok" if ok else ""}">{"—" if p is None else p}<small>%</small></b></div>'
                f'<div class="pr-b {tone}{" ok" if ok else ""}" role="progressbar" aria-label="{html.escape(title)}" aria-valuenow="{p or 0}" aria-valuemin="0" aria-valuemax="100">'
                f'<i style="--w:{w}%"></i>' + (f'<u style="left:{min(due, 100):.0f}%" title="бүгінге дейін болуы керек: {due:.0f}%"></u>' if due < 100 else "") + '</div>'
                f'<div class="pr-s"><span><b>{a}</b> / {b_}</span><span class="{"okt" if ok else "late" if behind else ""}">{note}</span></div></div>')
    dmp = m.get("dept_month_plan")
    dept_rows = ""
    if dmp:
        dpa = round(m["month"]["amount"] / dmp["amount"] * 100) if dmp["amount"] else None
        dpl = round(m["month"]["leads"] / dmp["leads"] * 100) if dmp["leads"] else None
        dept_rows = ('<h3 class="pl2-d">Бөлімнің ортақ жоспары</h3>'
                     + prow2("Бөлім · айлық сатылым", dpa, "s", money(m["month"]["amount"], True), money(dmp["amount"], True) if dmp["amount"] else "—",
                             near(dpa) if dmp["amount"] else "жоспар қойылмаған", month_due)
                     + prow2("Бөлім · айлық лид", dpl, "l", num(m["month"]["leads"]), num(dmp["leads"]), near(dpl), month_due))
    plans = (f'<article class="card pl2 cardin" style="--i:5"><div class="pl2-h"><div><h2 class="pl2-n">{"Жеке жоспар" if dmp else "Жоспар"} · {MONTH_FULL[last.month - 1].lower()}</h2>'
             f'<div class="pl2-m">{m["elapsed"]}/{m["dim"]} күн · қарқын {pct_text(m["pace"])}</div></div>{edit_btn}</div>'
             + prow2("Айлық сатылым", mp["amount"], "s", money(m["month"]["amount"], True), money(mpl["amount"], True) if mpl["amount"] else "—",
                     (near(mp["amount"]) + (f" · күніне {money(left_amount / left_days, True)}" if left_days and left_amount and (mp["amount"] or 0) < 100 else "")) if mpl["amount"] else "жоспар қойылмаған", month_due)
             + prow2("Апталық сатылым", wp["amount"], "s", money(wk["amount"], True), money(wpl["amount"], True) if wpl["amount"] else "—", near(wp["amount"]) if wpl["amount"] else "", week_due)
             + prow2("Айлық лид", mp["leads"], "l", num(m["month"]["leads"]), num(mpl["leads"]), near(mp["leads"]), month_due)
             + prow2("Апталық лид", wp["leads"], "l", num(wk["leads"]), num(wpl["leads"]), near(wp["leads"]), week_due)
             + dept_rows
             + '<div class="pl2-k"><u></u>бүгінге дейін болуы керек деңгей</div></article>'
             + """<style>.pl2{display:flex;flex-direction:column;gap:18px;padding:22px}
.pl2-d{margin:4px 0 -6px;padding-top:16px;border-top:1px solid var(--border);font-size:.8125rem;font-weight:600;color:var(--muted)}.pl2-h{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}.pl2-n{margin:0;font-size:1.0625rem;font-weight:600}.pl2-m{margin-top:4px;font-size:0.8125rem;color:var(--muted)}
.pl2 .pedit{border-radius:8px;font-weight:500}
.pr-t{display:flex;justify-content:space-between;align-items:baseline}.pr-t span{font-size:0.875rem;font-weight:600}
.pr-t b{font-size:1.5rem;font-weight:700;letter-spacing:-.025em;font-variant-numeric:tabular-nums}.pr-t b small{font-size:0.8125rem;color:var(--faint);margin-left:1px}.pr-t b.ok{color:var(--green)}
.pr-b{position:relative;height:8px;border-radius:2px;background:var(--bar);margin-top:10px}
.pr-b i{position:absolute;inset:0 auto 0 0;width:0;border-radius:inherit;transition:width 1.2s cubic-bezier(.2,.8,.2,1)}.go .pr-b i,.frz .pr-b i{width:var(--w)}
.pr-b.s i{background:var(--accent)}.pr-b.l i{background:var(--orange)}.pr-b.ok i{background:var(--green)}
.pr-b u{position:absolute;top:-5px;width:2px;height:18px;margin-left:-1px;background:var(--gold)}
.pr-s{display:flex;justify-content:space-between;gap:10px;margin-top:8px;font-size:0.75rem;color:var(--faint);flex-wrap:wrap}.pr-s b{color:var(--text);font-weight:600}
.pr-s .okt{color:var(--green);font-weight:600}.pr-s .late{color:var(--amber);font-weight:600}
.pl2-k{display:flex;align-items:center;gap:8px;font-size:0.75rem;color:var(--faint)}.pl2-k u{display:inline-block;width:2px;height:14px;background:var(--gold)}</style>""")

    # ---- streak card (from direction C)
    recent = [c for c in m["calendar"] if not c["future"]][-7:]
    days_html = "".join(f'<div class="{"on" if c["done"] else ""}{" now" if c["today"] else ""}"><i></i><span>{c["day"]}</span></div>' for c in recent)
    to_next = max(0, st["next"] - st["days"])
    streak_card = (f'<article class="card sk"><div class="ch"><h2>Қатарынан</h2><span class="meta">күндік лид жоспары</span></div>'
                   f'<div class="sk-m"><b class="sk-n">{st["days"]}</b><span>күн қатарынан жоспар орындалды</span></div>'
                   f'<div class="sk-g"><div class="sk-gt"><span>{icon("gift")}Келесі сыйлық · {st["next"]} күн</span><b>қалды {to_next}</b></div>'
                   f'<div class="sk-b"><i style="width:{min(100, st["days"] / st["next"] * 100) if st["next"] else 0:.0f}%"></i></div></div></article>'
                   """<style>.sk{display:flex;flex-direction:column;gap:14px;padding:20px}
.sk-m{display:flex;align-items:baseline;gap:10px}.sk-n{font-size:3rem;line-height:1;font-weight:700;letter-spacing:-.035em;font-variant-numeric:tabular-nums}.sk-m span{color:var(--muted)}
.sk-d{display:flex;gap:4px}.sk-d div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;height:40px;border:1px solid var(--border);border-radius:3px;font-size:0.75rem;color:var(--faint);font-variant-numeric:tabular-nums}
.sk-d i{display:none}.sk-d .on{background:var(--gilt);border-color:var(--gilt);color:var(--gink);font-weight:600}.sk-d .now{border:1px dashed var(--gold)}
.sk-g{margin-top:auto;padding:12px 14px;border-radius:8px;background:var(--surface2)}.sk-gt{display:flex;justify-content:space-between;gap:8px;font-size:0.8125rem;color:var(--muted)}
.sk-gt .i{width:14px;height:14px;vertical-align:-2px;margin-right:6px;color:var(--gold)}.sk-gt b{color:var(--gold);font-weight:600}
.sk-b{height:6px;border-radius:2px;background:var(--surface);margin-top:8px;overflow:hidden}.sk-b i{display:block;height:100%;background:var(--gilt)}</style>""")

    # ---- bonus
    if not mpl["amount"]:
        bonus_body = ('<p class="bsub">Айлық сатылым жоспары қойылмаған — бонус жоспар бойынша есептеледі.</p>'
                      + (f'<button class="btnp bset" type="button" data-plan>{icon("edit")}Жоспар қою</button>' if me_s else ""))
    elif not b["pct"]:
        bonus_body = '<p class="bsub">Бонус пайызы әлі қойылмаған.</p>'
    elif b["reached"]:
        bonus_body = f'{figure(b["earned"], " ₸", "bv")}<p class="bsub">Айлық жоспар орындалды · сатылымның {b["pct"]}%</p>'
    else:
        bonus_body = (f'{figure(b["potential"], " ₸", "bv")}<p class="bsub">Айлық жоспар жабылса аласың · {money(b["left"])} қалды</p>'
                      f'{bar(mp["amount"], "gold", "Бонусқа дейін")}')
    bonus = f'<article class="card bonus"><div class="ch"><h2>Бонус</h2></div>{bonus_body}</article>'

    # ---- heatmap
    cal = m["calendar"]
    mx = max([c["leads"] for c in cal] + [m["lead_day"], 1])
    wd0 = datetime.strptime(cal[0]["date"], "%Y-%m-%d").weekday() if cal else 0
    cells = "".join(f'<span class="wd">{w}</span>' for w in WEEKDAYS) + "<span></span>" * wd0
    for c in cal:
        if c["future"]:
            cells += f'<span class="hd fut">{c["day"]}</span>'
            continue
        lvl = min(4, int(c["leads"] / mx * 4 + .5))
        tip = f'{c["day"]}: {c["leads"]} лид · {c["sales"]} сатылым · {money(c["amount"])}'
        cells += (f'<a class="hd l{lvl}{" now" if c["today"] else ""}" href="?p=day&d={c["date"]}{q}" title="{html.escape(tip)}">{c["day"]}'
                  + (f'<em>{ui.flame()}</em>' if c["done"] else "") + "</a>")
    done_days = sum(1 for c in cal if c["done"])
    heat = ""
    _unused_heat = (f'<article class="card"><div class="ch"><h2>Лид heatmap</h2><span class="meta">{done_days} күн жоспар жабылды · {ui.flame("fx in")} = {num(m["lead_day"])}+ лид</span></div>'
            f'<div class="heat">{cells}</div><div class="hl"><span>аз</span><i class="l0"></i><i class="l1"></i><i class="l2"></i><i class="l3"></i><i class="l4"></i><span>көп</span></div></article>')

    chart = (f'<article class="card chartc cardin" style="--i:9"><div class="ch"><h2>Сатылым мен лид</h2><span class="meta"><i class="sw a"></i>сатылым <i class="sw b"></i>лид</span></div>'
             f'<div class="chart" id="cs" role="img" aria-label="Күн сайынғы сатылым мен лид"></div></article>')
    ig, ip = m["ig"], m["ig_plan"]
    rows = ""
    for key, label in (("new_followers", "Жаңа жазылушы"), ("likes", "Лайк"), ("comments", "Коммент"), ("reach", "Охват"),
                       ("views", "Қаралым"), ("total_interactions", "Өзара әрекет")):
        v, t = ig.get(key), ip.get(key)
        p = round(v / t * 100) if t and v is not None else None
        rows += (f'<tr><th scope="row">{label}</th><td>{num(v)}</td><td>{num(t) if t else "—"}</td>'
                 f'<td class="pc">{bar(p, "purple sm", label) if t else ""}<span>{pct_text(p) if t else ""}</span></td></tr>')
    igc = (f'<article class="card cardin" style="--i:10"><div class="ch"><h2>Instagram: жоспар / нәтиже</h2><a class="more" href="/api/igbot/stats">Толық {icon("right", "ti")}</a></div>'
           f'<div class="tw"><table><thead><tr><th>Көрсеткіш</th><th>Нәтиже</th><th>Жоспар</th><th>Орындалуы</th></tr></thead><tbody>{rows}</tbody></table></div>'
           f'<p class="note">Жоспар — күніне {num(m["lead_day"])} лидке қажетті мөлшер, соңғы {m["ig_basis"]["days"]} күндегі {num(m["ig_basis"]["leads"])} маркетинг лиді бойынша.</p></article>')
    card_url = f'/report-card?{here}{q}'
    rt_edit = '<a class="btn sm" href="/report-text">Мәтінді өзгерту</a>' if is_admin else ""
    report = (f'<article class="card cardin" style="--i:11"><div class="ch"><h2>Есеп мәтіні</h2>{rt_edit}<a class="btn sm" href="{card_url}">Сурет</a><button class="btn sm" id="copy" type="button">{icon("copy", "ti")}<span>Көшіру</span></button></div>'
              f'<pre id="rep">{html.escape(report_text)}</pre></article>')

    warn = ""
    if amo_state.get("behind"):
        warn = '<div class="banner warn">amoCRM сделкалары жүктеліп жатыр — сандар толық емес. Бір минуттан соң жаңартыңыз.</div>'
    elif not amo_state.get("ok"):
        warn = (f'<div class="banner warn">amoCRM деректері алынбады: {html.escape(amo_state.get("error") or "")}'
                + (' · <a href="/settings">Баптау</a>' if is_admin else "") + "</div>")
    dots = "".join(f'<i class="{"on" if ok else ""}"></i>' for ok in st["history"][-10:])
    streak_pill = (f'<button class="streak{" hot" if st["days"] else ""}" id="streak" type="button" aria-label="Қатарынан {st["days"]} күн жоспар орындалды">'
                   f'<span class="sq" aria-hidden="true"></span><b>{st["days"]}</b><small>күн қатарынан</small></button>')

    cfg = {
        "name": first_name or "Команда", "full_name": m["name"] or user.get("n") or "",
        "praise": PRAISE, "eggs": EGGS, "streak": st["days"], "streak_left": max(0, st["next"] - st["days"]),
        "streak_reached": bool(st["reached"]), "streak_unlocked": bool(st["unlocked"]), "gift": st["gift"],
        "streak_line": STREAK_LINES[st["days"] % len(STREAK_LINES)] if st["days"] else STREAK_LINES[0],
        "daily_line": "{name}, күндік жоспар 100% орындалды. Керемет жұмыс!",
        "month_line": "{name}, айлық жоспар орындалды! Бұл — бір айлық еңбектің үлкен нәтижесі.",
        "today_leads": m["today_leads"] if m["today_leads"] is not None else 0, "lead_day": m["lead_day"],
        "month_pct": mp["amount"], "bonus": (b["earned"] if b["reached"] else b["potential"]) if b["pct"] and mpl["amount"] else 0,
        "bonus_reached": b["reached"],
        "bonus_label": "Түскен бонус" if b["reached"] else "Айлық жоспар жабылса — бонус" if b["pct"] else "Бонус % әлі қойылмаған",
        "ring_from": .86, "count_from": round(m["lead_day"] * .86), "count_to": max(m["lead_day"], m["today_leads"] or 0),
        "daily_hit": bool(m["celebrate"]), "month_hit": bool(b["reached"]), "today": today_key, "demo_ok": demo_ok,
    }
    cel_css, cel_html, cel_js = celebrate.block(cfg)

    return (PAGE.replace("__STYLE__", STYLE).replace("__HOME_CSS__", KIT + ui.PAGES + HOME_CSS + PLAN_CSS + FORECAST_CSS + FORECAST_CSS_NEW + cel_css)
            .replace("__TOPBAR__", topbar(user, "home")).replace("__THEMEJS__", THEME_JS)
            .replace("__HELLO__", f"Қайырлы күн, {html.escape(first_name)}" if first_name else "Қайырлы күн")
            .replace("__PRAISE_DAY__", html.escape(praise_of_day(first_name or "Команда")))
            .replace("__STREAK_PILL__", streak_pill + plan_dlg + (PLAN_JS if me_s else "") + (PLAN_OK if planok else ""))
            .replace("__SEGS__", segs).replace("__DR__", ui.date_range(first, last, datetime.strptime(today_key, "%Y-%m-%d").replace(tzinfo=first.tzinfo), prev_href,
                                              next_href if next_d <= today_key else None, "?p=day&d=@", q, "?p=month&d=@"))
            
            
            .replace("__SPAN__", span).replace("__WARN__", warn + top_html)
            .replace("__ADS__", trend_html + ads_html).replace("__HERO__", hero).replace("__KPIS__", kpis).replace("__PLANS__", plans).replace("__STREAKC__", streak_card)
            .replace("__HEAT__", heat).replace("__BONUS__", bonus).replace("__CHART__", chart).replace("__IG__", igc)
            .replace("__BEST__", best_html).replace("__REPORT__", report).replace("__CEL_HTML__", cel_html).replace("__CEL_JS__", cel_js)
            .replace("__SERIES__", json.dumps(m["series"])))


HOME_CSS = """
.wrap{max-width:1240px}
.board{background:var(--board);color:var(--bink);border-radius:var(--r);overflow:hidden}
.bd-main{padding:22px 24px 20px}
.bd-h{display:flex;justify-content:space-between;gap:12px;align-items:baseline;font-size:0.8125rem;color:var(--bmuted)}
.bc{font-style:normal;font-weight:600;font-size:0.8125rem;font-variant-numeric:tabular-nums}.bc.up,.bc.dn,.bc.fl{color:var(--bink)}
.bd-v{font-size:clamp(2.5rem,1.6rem + 2.4vw,3.5rem);line-height:1.05;font-weight:700;letter-spacing:-.035em;margin:10px 0 0;font-variant-numeric:tabular-nums;white-space:nowrap}
.bd-plan{margin-top:22px}
.bd-rail{position:relative;height:6px;background:var(--bline)}
.bd-rail i{position:absolute;inset:0 auto 0 0;width:var(--w);background:var(--bink)}.bd-rail.ok i{background:var(--gilt)}
.bd-rail u{position:absolute;top:-7px;width:2px;height:20px;margin-left:-1px;background:var(--gilt)}
.bd-rail u:after{content:"";position:absolute;left:-4px;top:-6px;width:10px;height:10px;background:var(--gilt);transform:rotate(45deg)}
.bd-rl{display:flex;justify-content:space-between;gap:4px 16px;flex-wrap:wrap;margin-top:12px;font-size:0.8125rem;color:var(--bmuted);font-variant-numeric:tabular-nums}
.bd-rl b{color:var(--bink);font-weight:600}.bd-rl em{font-style:normal;color:var(--gilt)}
.bd-days{display:flex;gap:4px;padding:14px 24px 10px;background:var(--board2);overflow-x:auto;scrollbar-width:none;scroll-snap-type:x proximity;overscroll-behavior-x:contain}
.bd-days::-webkit-scrollbar{display:none}
.pq{flex:1 0 32px;min-width:32px;height:50px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border:1px solid var(--bline);border-radius:3px;
color:var(--bmuted);font-size:0.75rem;line-height:1.1;scroll-snap-align:end;font-variant-numeric:tabular-nums;transition:opacity .2s ease-out,transform .1s ease-out}
.pq b{font-size:0.8125rem;font-weight:600;color:var(--bink)}
.pq.g{background:var(--gilt);border-color:var(--gilt);color:#5C4500}.pq.g b{color:var(--gink)}
.pq.t{border:1px dashed var(--gilt)}.pq.f{opacity:.6}
a.pq:active{transform:scale(.94)}
.pick .pq:not(.sel):not(.g) b{color:var(--bmuted);font-weight:500}
.pq.sel{outline:2px solid var(--bink);outline-offset:2px;transform:translateY(-3px)}
@media (hover:hover){a.pq:hover{border-color:var(--bmuted)}}
.bd-lg{display:flex;justify-content:space-between;gap:12px;padding:4px 24px 14px;background:var(--board2);font-size:0.75rem;color:var(--bmuted)}
.bd-lg i{display:inline-block;width:9px;height:11px;margin-right:6px;border-radius:1px;background:var(--gilt);vertical-align:-1px}
.rows{display:grid;grid-template-columns:repeat(4,1fr);margin-top:16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.rw{display:grid;grid-template-columns:1fr auto;grid-template-areas:"l c" "v v" "s s";column-gap:8px;padding:16px 18px;min-width:0}
.rw+.rw{border-left:1px solid var(--border)}
.rl{grid-area:l;font-size:0.8125rem;color:var(--muted)}.rc{grid-area:c;font-style:normal;font-size:0.8125rem;font-weight:600;font-variant-numeric:tabular-nums;text-align:right}
.rc.up{color:var(--green)}.rc.dn{color:var(--red)}.rc.fl{color:var(--faint)}
.rv{grid-area:v;margin-top:6px;font-size:1.625rem;line-height:1.2;font-weight:600;letter-spacing:-.025em;font-variant-numeric:tabular-nums;white-space:nowrap}
.rs{grid-area:s;margin-top:2px;font-size:0.75rem;color:var(--faint)}
.ph1{margin:0 0 14px}
@media (max-width:1100px){.rows{grid-template-columns:1fr 1fr}.rw:nth-child(3){border-left:0}.rw:nth-child(n+3){border-top:1px solid var(--border)}}
@media (max-width:720px){.bd-main{padding:18px 16px 18px}.bd-days{padding:12px 16px 8px}.bd-lg{padding:0 16px 12px}
 .board{border-radius:0;margin:0 -16px}
 .rows{grid-template-columns:1fr;margin-top:12px}.rw,.rw:nth-child(n){grid-template-areas:"l v" "s c";align-items:baseline;padding:12px 16px;border-left:0}
 .rw+.rw{border-top:1px solid var(--border)}.rv{margin:0;text-align:right;font-size:1.25rem}.rl{font-size:0.875rem;color:var(--text)}
 .hello{margin:22px 0 14px}.hello h1{font-size:1.1875rem}.hello .act .streak{flex:none}.motiv{white-space:nowrap}
 .ph1{gap:8px;margin-bottom:12px}.ph1 .ctrl{flex-wrap:nowrap;gap:8px}.ph1 .date{flex:none}.ph1 .date input{width:108px}.ph1 .seg{padding:0 6px}}
.stk{display:grid;gap:18px;grid-template-rows:1fr 1fr}
.tqs{margin-top:16px;padding:16px 18px 6px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}.tqs .ch{margin-bottom:4px}.tqs .ch .more{margin-left:12px}
.tq{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;min-height:48px;border-top:1px solid var(--border)}
.tq .cbx{width:22px;height:22px;border-radius:4px;border:1.5px solid var(--accent);background:transparent;cursor:pointer;padding:0}
.tqt{min-width:0;overflow-wrap:anywhere}.tqt small{display:block;font-size:0.75rem;color:var(--faint)}
.tq time{font-size:0.8125rem;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}.tq time.late{color:var(--red)}
.tqe{margin:0;padding:12px 0;border-top:1px solid var(--border);color:var(--muted)}
.adsc .ch a.meta{color:var(--accent)}
@media (max-width:700px){.zct{display:none!important}}
@media (max-width:720px){.stk{gap:12px;grid-template-rows:none}}

.hello{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;margin:28px 0 18px}
.hello h1{margin:0;font-size:1.375rem;line-height:1.3;font-weight:600;letter-spacing:-.02em}.hello p{margin:4px 0 0;color:var(--muted)}
.hello .act{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.streak{display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 14px;border-radius:10px;border:1px solid var(--border);background:var(--surface);cursor:pointer;color:var(--text);font:inherit}
.streak .sq{width:14px;height:18px;border-radius:2px;background:var(--gilt)}.streak b{font-size:1.0625rem;font-weight:600;font-variant-numeric:tabular-nums}.streak small{color:var(--muted)}
.sdots{display:flex;gap:3px;margin-left:4px}.sdots i{width:5px;height:16px;border-radius:1px;background:var(--bar)}.sdots i.on{background:var(--gilt)}
.motiv{display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 16px;border-radius:10px;border:1px solid var(--border);cursor:pointer;font:500 0.875rem Golos Text,sans-serif;color:var(--text);
background:var(--surface);transition:transform .1s ease-out}.motiv .i{color:var(--accent)}
.motiv:active{transform:scale(.97)}.motiv .i{width:18px;height:18px}
.ph1{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin:0 0 16px}
.ph1 p{margin:0;color:var(--muted)}
.top-grid{display:grid;grid-template-columns:1.25fr 1fr;gap:18px}
.kgrid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.mid-grid{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;margin-top:18px}
.pl+.pl{margin-top:16px}.plt{display:flex;justify-content:space-between;font-weight:600}.plt b{font-variant-numeric:tabular-nums}
.pls{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-top:8px;font-size:0.8125rem;color:var(--muted)}.pls .okt{color:var(--green);font-weight:600}
transform:scale(0);animation:okpop .5s 1.3s cubic-bezier(.2,1.6,.4,1) forwards}
.streakc{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:linear-gradient(180deg,color-mix(in srgb,var(--orange) 10%,var(--surface)),var(--surface));box-shadow:var(--shadow),inset 0 0 0 2px color-mix(in srgb,var(--orange) 70%,transparent)}
.streakc .fl{color:var(--orange);line-height:1;margin-top:6px;display:inline-block}
.streakc .fn{font-size:4rem;line-height:1;font-weight:900;color:var(--orange);margin-top:4px}
.streakc p{margin:6px 0;color:var(--muted);font-weight:600}
.fd{display:flex;justify-content:center;gap:6px;margin:12px 0}.fd i{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:var(--surface2);color:var(--faint);font-style:normal;font-size:0.75rem;font-weight:700}
.fd i.on{background:var(--orange);color:#fff;box-shadow:0 4px 12px -2px color-mix(in srgb,var(--orange) 70%,transparent)}.fd i.now{box-shadow:0 0 0 2px var(--orange) inset}.fd i.on.now{box-shadow:0 0 0 3px color-mix(in srgb,var(--orange) 35%,transparent)}
.nx b{color:var(--orange)}.nx .i{vertical-align:-3px;margin-right:6px;color:var(--orange)}.streakc .fl .fx{width:56px;height:56px;filter:drop-shadow(0 6px 14px rgba(243,91,47,.35))}.heat em .fx{width:15px;height:19px}.meta .fx.in{width:13px;height:16px;vertical-align:-3px}
.low-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;margin-top:18px}
.bonus{display:flex;flex-direction:column}.bonus .ch{margin-bottom:auto;padding-bottom:14px}.bonus .pbar{margin-bottom:auto}
.bv{font-size:2.25rem;line-height:1.2;font-weight:700;letter-spacing:-.03em;color:var(--gold);font-variant-numeric:tabular-nums}.bsub{margin:6px 0 0;color:var(--muted)}
.chartc{display:flex;flex-direction:column}.chart{flex:1;min-height:240px}.chart svg{width:100%;height:100%;display:block}
.sw{display:inline-block;width:8px;height:8px;border-radius:2px;margin:0 4px 0 8px}.sw.a{background:var(--accent)}.sw.b{background:var(--orange);border-radius:50%}
@media (max-width:1100px){.top-grid,.mid-grid,.low-grid{grid-template-columns:1fr}}
@media (max-width:720px){.hello{margin:4px 0 14px}.hello h1{font-size:1.375rem;line-height:1.273}.hello .act{width:100%}.streak{flex:1;justify-content:center}.motiv{flex:1;justify-content:center}
.ph1 .ctrl{width:100%}.top-grid,.mid-grid,.low-grid{gap:12px}.mid-grid,.low-grid{margin-top:12px}.kgrid{gap:12px}
.kh .kl{display:none}.card{padding:16px;border-radius:var(--r)}.heat{gap:4px}.heat .hd{height:34px}.streakc .fn{font-size:3.25rem}.bv{font-size:2rem}}
@media (prefers-reduced-motion:reduce){.cardin{opacity:1;transform:none;animation:none}.spark .ln{stroke-dashoffset:0;animation:none}.pbar i{transition:none}}
"""

PLAN_CSS = """
.ch .pedit{margin-left:auto}.ch .pedit+.meta{margin-left:12px}.pedit .i{width:14px;height:14px}
.bset{margin-top:14px;height:40px}.bset .i{width:16px;height:16px}
.pdlg{border:0;padding:0;border-radius:24px;width:min(520px,calc(100vw - 32px));background:var(--surface);color:var(--text);box-shadow:var(--shadow-lg)}
.pdlg::backdrop{background:rgba(20,10,40,.55)}.pdlg form{padding:24px}
.pdh{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.pdh h2{margin:0;font-size:1.25rem;font-weight:800}.pdh p{margin:4px 0 0;color:var(--faint);font-size:0.8125rem}
.pdx{display:grid;place-items:center;width:36px;height:36px;border-radius:12px;border:0;background:var(--surface2);color:var(--muted);cursor:pointer}
.qa{display:flex;gap:8px;flex-wrap:wrap;margin-top:-6px}.qa button{height:32px;padding:0 12px;border-radius:999px;border:1.5px solid var(--border);background:var(--surface);color:var(--text);font:600 0.8125rem Golos Text,sans-serif;cursor:pointer}
.qa button:hover{border-color:var(--accent);color:var(--accent)}#pamtx.bad{color:var(--red)}#pamtx.good{color:var(--green)}
"""
PLAN_JS = """<script>(function(){var d=document.getElementById('pdlg');if(!d)return;var a=document.getElementById('pamt'),x=document.getElementById('pamtx');
function nf(n){return n.toLocaleString('ru-RU').replace(/\\u00a0/g,' ')}
function chk(){var v=+(a.value||'').replace(/\\D/g,'');if(!v){x.textContent='Толық сомасын жазыңыз';x.className='';return}
if(v<1000){x.textContent='Тым аз: '+nf(v)+' ₸. Толық соманы жазыңыз, мысалы 10 000 000';x.className='bad'}else{x.textContent='= '+nf(v)+' ₸ айына';x.className='good'}}
a.addEventListener('input',function(){var v=(a.value||'').replace(/\\D/g,'');a.value=v?nf(+v):'';chk()});chk();
document.querySelectorAll('.qa button').forEach(function(b){b.onclick=function(){a.value=nf(+b.dataset.a);chk()}});
/* the plan dialog opens from its button and closes back into it (shared helpers from ui.CONFIRM_JS) */
function shut(){window.zDlgClose?zDlgClose(d):d.close()}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-plan]');if(b){window.zDlgOpen?zDlgOpen(d,b):d.showModal();a.focus()}});
d.querySelector('[data-pclose]').onclick=shut;d.addEventListener('click',function(e){if(e.target===d)shut()});d.addEventListener('cancel',function(e){e.preventDefault();shut()});
d.querySelector('form').addEventListener('submit',function(e){var v=+(a.value||'').replace(/\\D/g,'');if(v&&v<1000){e.preventDefault();chk();a.focus()}})})();</script>"""
# the shared toast (ui .ztoast): sits above the phone's bottom bar, arrives and leaves the same way, can be closed
PLAN_OK = ('<div class="ztoast out" id="planok" role="status"><span class="badge-ok"><svg class="ck" viewBox="0 0 24 24" aria-hidden="true">'
           '<path d="M20 6 9 17l-5-5"/></svg></span><span>Жоспар сақталды</span><button type="button" class="x" aria-label="Жабу">&times;</button></div>'
           "<script>(function(){var t=document.getElementById('planok');if(!t)return;document.body.appendChild(t);void t.offsetWidth;t.classList.remove('out');"
           "function hide(){clearTimeout(tm);t.classList.add('out');setTimeout(function(){t.remove()},260)}"
           "var tm=setTimeout(hide,4000);t.querySelector('.x').onclick=hide})();</script>")

PAGE = r"""<!doctype html><html lang="kk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>EduApp Marketing</title><link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="apple-touch-icon" href="/logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script>try{var P=new URLSearchParams(location.search),q=P.get('theme'),t=q||localStorage.getItem('mk-theme');if(t)document.documentElement.dataset.theme=t;if(P.get('freeze')!==null)document.documentElement.classList.add('frz')}catch(e){}</script>
__STYLE__<style>__HOME_CSS__</style></head><body>
__TOPBAR__
<main class="wrap">
__WARN__
<div class="ph1"><p>__SPAN__ · Астана уақыты</p>
<div class="ctrl"><nav class="segs" aria-label="Кезең">__SEGS__</nav>
__DR__</div></div>
__HERO____KPIS__
<section class="hello"><div><h1>__HELLO__</h1><p>__PRAISE_DAY__</p></div>
<div class="act">__STREAK_PILL__<button class="motiv" id="motiv" type="button"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.94 14.06 4 20"/><path d="m14 4 1.2 2.8L18 8l-2.8 1.2L14 12l-1.2-2.8L10 8l2.8-1.2Z"/></svg>Күндік мотивация</button></div></section>
__ADS__
<section class="mid-grid">__PLANS__<div class="stk">__STREAKC____BONUS__</div></section>__HEAT__
<section class="ig-row" style="margin-top:18px">__IG__</section>
__BEST__
<section style="margin-top:18px">__REPORT__</section>
</main>
__CEL_HTML__
__THEMEJS__
<script>
(function(){
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches,root=document.documentElement;
const nf=n=>Math.round(n).toLocaleString('ru-RU').replace(/ /g,' ');
/* apple-design «Response»: the numbers stay as the server sent them — final on the first frame */
document.body.classList.add('go');
const pq=document.getElementById('pqs');if(pq){const t=pq.querySelector('.sel,.t');if(t)pq.scrollLeft=t.offsetLeft-pq.clientWidth+t.offsetWidth+40}
const cp=document.getElementById('copy');if(cp)cp.onclick=async()=>{try{await navigator.clipboard.writeText(document.getElementById('rep').innerText);cp.querySelector('span').textContent='Көшірілді'}catch(e){}};
const S=__SERIES__;
function draw(){const el=document.getElementById('cs');if(!el||!S.length)return;const cs=getComputedStyle(root);
 const W=Math.max(el.clientWidth,260),H=el.clientHeight||240,P={l:4,r:4,t:14,b:22},n=S.length,cw=(W-P.l-P.r)/n;
 const ma=Math.max(1,...S.map(r=>r.amount)),ml=Math.max(1,...S.map(r=>r.leads));
 const ya=v=>H-P.b-(v/ma)*(H-P.t-P.b),yl=v=>H-P.b-(v/ml)*(H-P.t-P.b);
 const acc=cs.getPropertyValue('--accent').trim(),or=cs.getPropertyValue('--orange').trim(),faint=cs.getPropertyValue('--faint'),bord=cs.getPropertyValue('--border');
 let s=`<line x1="${P.l}" x2="${W-P.r}" y1="${H-P.b}" y2="${H-P.b}" stroke="${bord}"/>`;
 const every=Math.ceil(n/(W<480?6:12));
 S.forEach((r,i)=>{const bw=Math.max(3,cw*.58),x=P.l+cw*i+(cw-bw)/2,h=Math.max(r.amount?2:0,H-P.b-ya(r.amount));
  s+=`<rect x="${x}" y="${H-P.b-h}" width="${bw}" height="${h}" rx="${Math.min(2,bw/2)}" fill="${acc}"><title>${r.label}: ${nf(r.amount)} ₸ · ${r.sales} сатылым · ${r.leads} лид</title></rect>`;
  if(i%every===0||i===n-1)s+=`<text x="${P.l+cw*i+cw/2}" y="${H-6}" font-size="10" text-anchor="middle" fill="${faint}">${r.label}</text>`});
 s+=`<polyline points="${S.map((r,i)=>`${P.l+cw*i+cw/2},${yl(r.leads)}`).join(' ')}" fill="none" stroke="${or}" stroke-width="2.2" stroke-linejoin="round"/>`;
 S.forEach((r,i)=>s+=`<circle cx="${P.l+cw*i+cw/2}" cy="${yl(r.leads)}" r="2.6" fill="${or}"/>`);
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${s}</svg>`}
draw();let rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(draw,150)});document.addEventListener('themechange',draw);
})();
</script>
__CEL_JS__
</body></html>"""
