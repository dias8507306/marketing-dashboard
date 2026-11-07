"""«Сақталған есептер»: a month calendar with saved days lit up and one KPI card per saved day."""
import calendar
import html
from datetime import datetime, timedelta

import dashboard
from dashboard import MONTHS, WEEKDAYS, fmt
from history import KIND_NAMES
from igdata import TZ

import ui

STYLE = ui.STYLE
MONTH_FULL = ["Қаңтар", "Ақпан", "Наурыз", "Сәуір", "Мамыр", "Маусым", "Шілде", "Тамыз", "Қыркүйек", "Қазан", "Қараша", "Желтоқсан"]
CARD_KPIS = [("new_followers", "Жаңа жазылушы"), ("reach", "Қамту"), ("views", "Қаралым"),
             ("likes", "Лайк"), ("comments", "Коммент"), ("er", "ER")]

COLORS = {"new_followers": "#7336F7", "reach": "#7648c3", "views": "#2A78D6", "likes": "#f35b2f", "comments": "#d99a00", "er": "#048848"}
KIND_TONE = {"auto": "#048848", "manual": "#7336F7", "restored": "#2A78D6"}

EXTRA = """<style>""" + ui.KIT + ui.PAGES + """
.layout{display:grid;grid-template-columns:320px minmax(0,1fr);gap:18px;align-items:start}
.calbox{position:sticky;top:76px}
.cal-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.cal-head b{font-weight:700;font-size:1rem}
.cal-head .step{width:34px;height:34px;border-radius:10px;background:var(--surface2)}
.heat a.hd{color:inherit}.heat em .fx{width:15px;height:19px}.note .fx.in{width:14px;height:17px;flex:none}.heat .l3,.heat .l4{color:#fff}.heat .hd.restored{box-shadow:inset 0 0 0 2px #2A78D6}
.reports{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.rep{display:flex;flex-direction:column;gap:14px;scroll-margin-top:76px}.rep:target{box-shadow:0 0 0 3px var(--accent),var(--shadow-lg)}
.rep-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.rep-head h2{margin:0;font-size:1.0625rem;font-weight:600}.rep-head small{display:block;color:var(--faint);font-size:0.75rem;margin-top:2px}
.fol{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.fol .kv{margin:0}.fol .lbl{color:var(--faint);font-size:0.75rem}
.fol .cmp{flex-basis:100%;font-size:0.75rem;color:var(--faint);margin-top:-6px}.fol .fu{font-size:0.8125rem;color:var(--muted)}
.fol .fu b{font-weight:700}.fol .fu .up{color:var(--green)}.fol .fu .down{color:var(--red)}
.vals{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.vals div{padding:10px 12px;border-radius:14px;background:color-mix(in srgb,var(--c) 8%,var(--surface2))}
.vals span{display:flex;align-items:center;gap:6px;font-size:0.6875rem;color:var(--muted);font-weight:500}.vals span:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--c);flex:none}
.vals b{display:block;margin-top:2px;font-weight:700;font-size:1rem;font-variant-numeric:tabular-nums}
.rep-foot{display:flex;gap:8px;margin-top:auto}.rep-foot a{flex:1}
.empty{padding:32px;text-align:center;color:var(--faint);border:2px dashed var(--border);border-radius:24px}
@media (max-width:900px){.layout{grid-template-columns:1fr}.calbox{position:static}}
</style>"""


def kpi_val(data, k):
    v = data.get(k)
    if k == "er":
        return f"{v}%" if v is not None else "—"
    return fmt(v)


def label(day_key: str) -> str:
    d = datetime.strptime(day_key, "%Y-%m-%d")
    return f"{d.day} {MONTHS[d.month - 1]}"


def month_canvas(ordered: list, est: dict, month_name: str) -> str:
    """Canvas line over the saved days of the month: followers (total), new followers, reach, views."""
    import charts
    days = [r for r in ordered]
    if len(days) < 2:
        return ""
    labels = [f'{int(r["day"][8:10])} {MONTHS[int(r["day"][5:7]) - 1]}' for r in days]

    def val(r, k):
        if k == "followers":
            v = r["data"].get("followers")
            return v if v is not None else est.get(r["day"])
        return r["data"].get(k)
    out = []
    for k, tab in (("followers", "Жазылушы саны"), ("new_followers", "Жаңа жазылушы"), ("reach", "Қамту"), ("views", "Қаралым")):
        vals = [val(r, k) for r in days]
        if sum(1 for v in vals if v is not None) < 2:
            continue
        last = next((v for v in reversed(vals) if v is not None), 0)
        first = next((v for v in vals if v is not None), 0)
        vals = [v if v is not None else 0 for v in vals]
        total = last if k == "followers" else sum(vals)
        out.append({"tab": tab, "label": f"{tab} · {month_name}", "cur": vals, "prev": None, "total": total,
                    "delta": charts.delta(last, first) if k == "followers" else None, "unit": "", "unitBig": "", "fromMin": k == "followers"})
    if not out:
        return ""
    return charts.CSS + charts.canvas("Ай бойынша", out, labels, prev_label="айдың бірінші күнімен", last_label="соңғы") + charts.JS


def render(reports: list, month: datetime, today_key: str, flash: str = "", user: dict | None = None, fu: dict | None = None) -> str:
    fu = fu or {}
    by_day = {r["day"]: r for r in reports}
    # calendar
    y, m = month.year, month.month
    cells = "".join(f'<span class="wd">{w}</span>' for w in WEEKDAYS)
    reach_max = max([(r["data"].get("reach") or 0) for r in reports] + [1])
    first_wd, n_days = calendar.monthrange(y, m)
    cells += '<span></span>' * first_wd
    for d in range(1, n_days + 1):
        k = f"{y:04d}-{m:02d}-{d:02d}"
        rep = by_day.get(k)
        today = " now" if k == today_key else ""
        if rep:
            reach = rep["data"].get("reach") or 0
            lvl = 1 + min(3, int(reach / reach_max * 3.999))
            fire = f"<em>{ui.flame()}</em>" if reach and reach >= reach_max * .8 else ""
            cells += (f'<a class="hd l{lvl} {rep["kind"]}{today}" href="#r{k}" '
                      f'title="{html.escape(KIND_NAMES[rep["kind"]])} · қамту {fmt(rep["data"].get("reach"))}">{d}{fire}</a>')
        else:
            cells += f'<span class="hd{" fut" if k > today_key else ""}{today}">{d}</span>'
    prev_m = (month.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    next_first = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    next_m = next_first.strftime("%Y-%m") if next_first.strftime("%Y-%m-%d") <= today_key else ""

    # Instagram keeps no past follower totals: walk back from the first known total, taking away each
    # later day's new followers (unfollows are not known, so this is an estimate, shown with «≈»)
    est = {}
    days_desc = sorted(by_day, reverse=True)
    for k in days_desc:
        if by_day[k]["data"].get("followers") is not None:
            continue
        nxt = (datetime.strptime(k, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        later = by_day.get(nxt)
        base = (later["data"].get("followers") if later else None)
        base = base if base is not None else est.get(nxt)
        if base is None or not later:
            continue
        if nxt in fu:  # follows − unfollows of the later day: Instagram's own numbers
            est[k] = base - (fu[nxt][0] - fu[nxt][1])
        elif later["data"].get("new_followers") is not None:  # older fallback: new follows only
            est[k] = base - later["data"]["new_followers"]

    # cards, newest first, each compared with the saved day before it
    cards = []
    ordered = sorted(reports, key=lambda r: r["day"])
    prev_by_day = {r["day"]: (ordered[i - 1] if i else None) for i, r in enumerate(ordered)}
    for i, r in enumerate(sorted(reports, key=lambda r: r["day"], reverse=True)):
        data, prev = r["data"], prev_by_day.get(r["day"])
        d = datetime.strptime(r["day"], "%Y-%m-%d")
        fol = data.get("followers")
        cmp = ""
        if fol is not None and prev and prev["data"].get("followers") is not None:
            diff = fol - prev["data"]["followers"]
            cls = "up" if diff > 0 else "down" if diff < 0 else "flat"
            sign = "▲ +" if diff > 0 else "▼ −" if diff < 0 else ""
            cmp = (f'<span class="pill {cls}">{sign}{fmt(abs(diff))}</span>'
                   f'<span class="cmp">{label(prev["day"])}-мен салыстырғанда</span>')
        elif fol is None and r["day"] in est:
            cmp = '<span class="cmp">шамамен: 15 қазаннан кері қарай Instagram-ның жазылды / бас тартты сандарымен есептелді</span>'
        elif fol is None:
            cmp = '<span class="cmp">жалпы сан сақталмаған: Instagram жаңа жазылушылар санын берген соң өздігінен есептеледі</span>'
        if r["day"] in fu:
            f_, u_ = fu[r["day"]]
            net = f_ - u_
            cmp += (f'<span class="cmp fu"><b class="up">жазылды +{fmt(f_)}</b> · <b class="down">бас тартты −{fmt(u_)}</b>'
                    f' · таза {"+" if net >= 0 else "−"}{fmt(abs(net))}</span>')
        elif r["day"] >= "2026-10-15":
            cmp += '<span class="cmp">жазылды / бас тартты: Instagram 1–2 күннен кейін береді</span>'
        saved_at = datetime.fromtimestamp(r["ts"], TZ)
        vals = "".join(f'<div style="--c:{COLORS[k]}"><span>{t}</span><b>{kpi_val(data, k)}</b></div>' for k, t in CARD_KPIS)
        shown = fmt(fol) if fol is not None or r["day"] not in est else f"≈ {fmt(est[r['day']])}"
        cards.append(
            f'<article class="rep card cardin" style="--i:{min(i, 12) + 2}" id="r{r["day"]}">'
            f'<div class="rep-head"><div><h2>{d.day} {MONTH_FULL[d.month - 1].lower()} {d.year}</h2>'
            f'<small>{WEEKDAYS[d.weekday()]} · сақталды {saved_at:%d.%m %H:%M}</small></div>'
            f'<span class="ptag" style="--c:{KIND_TONE.get(r["kind"], "#7336F7")}">{html.escape(KIND_NAMES[r["kind"]])}</span></div>'
            f'<div class="fol"><div class="kv">{shown}</div><span class="lbl">жазылушы</span>{cmp}</div>'
            f'<div class="vals">{vals}</div>'
            f'<div class="rep-foot"><a class="btng" href="report?d={r["day"]}">{ui.icon("file")}Есеп мәтіні</a>'
            f'<a class="btng" href="stats?d={r["day"]}">{ui.icon("chart")}Толық көру</a></div></article>')
    body = "".join(cards) or '<div class="empty">Әзірге сақталған есеп жоқ. «Снимок жасау» батырмасын басыңыз.</div>'
    canvas_html = month_canvas(ordered, est, MONTH_FULL[m - 1].lower())
    flash_html = f'<div class="msg ok">{html.escape(flash)}</div>' if flash else ""
    counts = {k: sum(1 for r in reports if r["kind"] == k) for k in KIND_NAMES}
    return f"""<!doctype html><html lang="kk"><head>{ui.HEAD}{ui.FONT}<title>Тарих · EduApp</title>
{STYLE}{EXTRA}</head><body>{ui.topbar(user, "archive")}<main class="wrap">
<section class="ph cardin"><div><h1>Сақталған есептер</h1><p>Instagram көрсеткіштерінің күнделікті снимоктары</p>
<div class="stats"><span>{len(reports)} күн</span><span>авто {counts['auto']}</span><span>қолмен {counts['manual']}</span><span>қалпына келтірілген {counts['restored']}</span></div></div>
<div class="act"><form method="post" action="snapshot"><button class="btny" type="submit">{ui.icon("calendar")}Бүгінгі снимокты сақтау</button></form></div></section>
{flash_html}
{canvas_html}
<div class="layout" style="margin-top:18px"><aside class="card calbox cardin" style="--i:1">
<div class="cal-head"><a class="step" href="?m={prev_m}" aria-label="Алдыңғы ай">{ui.icon("left")}</a><b>{MONTH_FULL[m - 1]} {y}</b>
{f'<a class="step" href="?m={next_m}" aria-label="Келесі ай">{ui.icon("right")}</a>' if next_m else f'<span class="step off">{ui.icon("right")}</span>'}</div>
<div class="heat">{cells}</div>
<div class="hl">аз <i class="l0"></i><i class="l1"></i><i class="l2"></i><i class="l3"></i><i class="l4"></i> көп қамту</div>
<p class="note">{ui.flame("fx in")} — айдың ең күшті күндері. Көк жиек — Instagram-нан қалпына келтірілген. Әр түн 00:05-те (Астана) өткен күннің есебі өздігінен сақталады.</p>
</aside><section class="reports">{body}</section></div></main>{ui.THEME_JS}{ui.KIT_JS}</body></html>"""
