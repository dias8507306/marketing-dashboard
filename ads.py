"""Ad spend typed in by the admin (per day) and what it bought: cost per lead (CPL) and return (ROMI).

Spend typed by hand is kept in kv `ad_spend` as {"YYYY-MM-DD": tenge}; when META_ADS_TOKEN and META_AD_ACCOUNT are set,
what Meta reports per day is kept in kv `ad_spend_meta` and wins for those days. Leads and sales are the amoCRM deals whose
source is targeted ads (values of the marketing source field that mention «таргет»); when no such value
is chosen in the settings, all marketing deals are used.
ROMI = (sales amount − spend) ÷ spend × 100%.
"""
import asyncio
import html
import logging
import os
import re
import time
from datetime import timedelta

import amo
import home
import igdata
import ui


log = logging.getLogger("ads")
META_EVERY = 3600  # seconds between refreshes of the spend from Meta
META_BACK = 35  # days re-read each time (Meta still corrects recent days); the first run reads 13 months


def meta_on() -> bool:
    return bool(os.getenv("META_ADS_TOKEN") and os.getenv("META_AD_ACCOUNT"))


async def _rates(http, con, cur: str, days: list) -> tuple:
    """({day: tenge for 1 unit of `cur`}, all fetched?) from the National Bank: each recent day, one day a week for older
    ones; kept in kv. A page view waits at most 6 s: what is missing arrives on the next refresh."""
    known = amo.kv_get(con, f"fx:{cur}", {}) or {}
    recent = igdata.key(igdata.today() - timedelta(days=META_BACK))

    def key_of(k):
        if k >= recent:
            return k
        d = igdata.datetime.strptime(k, "%Y-%m-%d")
        return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
    wanted = sorted({key_of(k) for k in days}, reverse=True)
    today_key = igdata.key(igdata.today())
    missing = [k for k in wanted if k not in known or k == today_key]
    sem = asyncio.Semaphore(8)

    async def one(k):
        async with sem:
            r = await http.get("https://nationalbank.kz/rss/get_rates.cfm", params={"fdate": f"{k[8:10]}.{k[5:7]}.{k[:4]}"}, timeout=6)
        m = re.search(rf"<title>{cur}</title>\s*<description>([\d.]+)</description>\s*<quant>(\d+)", r.text)
        if m:
            known[k] = float(m.group(1)) / int(m.group(2))
    tasks = [asyncio.create_task(one(k)) for k in missing]
    if tasks:
        await asyncio.wait(tasks, timeout=6)
        for t in tasks:
            if not t.done():
                t.cancel()
            elif t.exception():
                log.warning("nationalbank rate: %s", type(t.exception()).__name__)
        amo.kv_set(con, f"fx:{cur}", known)

    def rate(k):
        if key_of(k) in known:
            return known[key_of(k)]
        return known[min(known, key=lambda x: abs(igdata.datetime.strptime(x, "%Y-%m-%d") - igdata.datetime.strptime(k, "%Y-%m-%d")))]
    return ({k: rate(k) for k in days} if known else {}), all(k in known for k in wanted)


async def sync_meta(http, con, force: bool = False):
    """Daily spend from the Meta ad account, in tenge, into kv; at most once an hour, and a failure only leaves the old numbers."""
    if not meta_on():
        return
    st = amo.kv_get(con, "ad_meta_state", {}) or {}
    if not force and time.time() - (st.get("tried") or 0) < (60 if st.get("error") or not st.get("fx") else META_EVERY):
        return
    st["tried"] = int(time.time())
    today = igdata.today()
    first = today - timedelta(days=META_BACK if st.get("fx") else 396)  # «fx»: every day so far is stored in tenge
    ver = os.getenv("META_GRAPH_API_VERSION", "v25.0")
    url = f"https://graph.facebook.com/{ver}/{os.environ['META_AD_ACCOUNT'].strip()}/insights"
    params = {"fields": "spend", "level": "account", "time_increment": 1, "limit": 500,
              "time_range": f'{{"since":"{igdata.key(first)}","until":"{igdata.key(today)}"}}'}
    head = {"Authorization": f"Bearer {os.environ['META_ADS_TOKEN'].strip()}"}
    got = {}
    try:
        r = await http.get(url.rsplit("/", 1)[0], headers=head, params={"fields": "currency"}, timeout=15)
        if r.status_code == 200:
            st["currency"] = r.json().get("currency")
        cur = st.get("currency")
        if not cur:
            raise RuntimeError("Рекламалық аккаунттың валютасы анықталмады")
        for _ in range(10):
            r = await http.get(url, headers=head, params=params, timeout=15)
            body = r.json()
            if r.status_code != 200:
                raise RuntimeError(((body.get("error") or {}).get("message") or f"HTTP {r.status_code}")[:200])
            for row in body.get("data", []):
                got[row["date_start"]] = float(row.get("spend") or 0)
            after = (body.get("paging") or {}).get("cursors", {}).get("after")
            if not after or not (body.get("paging") or {}).get("next"):
                break
            params["after"] = after
        got = {k: v for k, v in got.items() if v > 0}
        done = True
        if cur != "KZT" and got:
            rates, done = await _rates(http, con, cur, list(got))
            if not rates:
                raise RuntimeError(f"{cur} бағамы Ұлттық банктен алынбады")
            st["rate"] = rates[max(got)]
            got = {k: v * rates[k] for k, v in got.items()}
    except Exception as e:
        log.warning("meta spend: %s", type(e).__name__)
        st["error"] = str(e)[:200] if isinstance(e, RuntimeError) else type(e).__name__
        if not st.get("fx"):  # what is stored may still be in the account's currency: better no number than a wrong one
            amo.kv_set(con, "ad_spend_meta", {})
        amo.kv_set(con, "ad_meta_state", st)
        return
    keep = {k: v for k, v in (amo.kv_get(con, "ad_spend_meta", {}) or {}).items() if k < igdata.key(first)}
    amo.kv_set(con, "ad_spend_meta", {**keep, **{k: round(v) for k, v in got.items()}})
    st["at"], st["error"], st["fx"] = int(time.time()), None, bool(done)
    amo.kv_set(con, "ad_meta_state", st)


def manual(con) -> dict:
    return amo.kv_get(con, "ad_spend", {}) or {}


def load(con) -> dict:
    return {**manual(con), **(amo.kv_get(con, "ad_spend_meta", {}) or {})}


def meta_note(con) -> str:
    """One line for the ads page: where the spend comes from and whether the last refresh worked."""
    if not meta_on():
        return ""
    st = amo.kv_get(con, "ad_meta_state", {}) or {}
    if st.get("error"):
        return f'<div class="msg err">Meta-дан шығын алынбады: {html.escape(st["error"])}. Соңғы сақталған сандар көрсетіліп тұр.</div>'
    if st.get("at"):
        from datetime import datetime
        fx = (f' · {html.escape(st["currency"])} → ₸ Ұлттық банк бағамымен, соңғы бағам 1 {html.escape(st["currency"])} = {st["rate"]:.2f} ₸'
              if st.get("currency") != "KZT" and st.get("rate") else "")
        return f'<p class="note">Шығын Meta-дан автоматты түрде келеді · жаңартылды {datetime.fromtimestamp(st["at"], igdata.TZ):%d.%m %H:%M}{fx}</p>'
    return ""


def save_day(con, day: str, amount: int):
    spend = manual(con)
    if amount > 0:
        spend[day] = amount
    else:
        spend.pop(day, None)
    amo.kv_set(con, "ad_spend", spend)


def target_filter(con):
    """Deals that came from ads: the source values mentioning «таргет», or None (all marketing deals)."""
    st = amo.settings(con)
    vals = [v for v in st.get("sources") or [] if "таргет" in v.lower() or "реклам" in v.lower()]
    return {"field": st.get("source_field"), "values": vals} if st.get("source_field") and vals else None


def summary(con, first, last) -> dict | None:
    """Spend, leads, CPL, sales, ROMI for the days first..last; None when nothing was spent."""
    spend_map = load(con)
    spend = sum(v for k, v in spend_map.items() if igdata.key(first) <= k <= igdata.key(last))
    if not spend:
        return None
    who = target_filter(con)
    n = amo.numbers(con, int(first.timestamp()), int((last + timedelta(days=1)).timestamp()), who)
    return {"spend": spend, "leads": n["leads"], "sales": n["sales"], "amount": n["amount"],
            "cpl": round(spend / n["leads"]) if n["leads"] else None,
            "romi": round((n["amount"] - spend) / spend * 100) if spend else None, "target_only": bool(who)}


def card(s: dict | None) -> str:
    """Strip under the KPIs on the overview (admin only)."""
    if not s:
        return ('<article class="card cardin adsc" style="--i:5;margin-top:18px"><div class="ch"><h2>Жарнама</h2>'
                '<a class="meta" href="/ads">шығынды енгізу</a></div><p class="note">Бұл кезеңге жарнама шығыны енгізілмеген. '
                '<a href="/ads">Жарнама</a> бетінде күн сайынғы бюджетті жазсаңыз, бір лидтің бағасы мен ROI осында шығады.</p></article>')
    romi = s["romi"]
    tone = "var(--green)" if romi is not None and romi >= 0 else "var(--red)"
    return f"""<article class="card cardin adsc" style="--i:5;margin-top:18px"><div class="ch"><h2>Жарнама</h2><a class="meta" href="/ads">толығырақ</a></div>
<div class="adsg"><div><span>Шығын</span><b>{home.money(s["spend"])}</b></div>
<div><span>Лид{" (таргет)" if s["target_only"] else ""}</span><b>{home.num(s["leads"])}</b></div>
<div><span>Бір лид (CPL)</span><b>{home.money(s["cpl"]) if s["cpl"] else "—"}</b></div>
<div><span>Сатылым</span><b>{home.money(s["amount"])}</b></div>
<div><span>ROI</span><b style="color:{tone}">{f"{romi:+d}%" if romi is not None else "—"}</b></div></div></article>"""


CSS = """.adsg{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.adsg{gap:0!important}.adsg div{padding:2px 16px;border-left:1px solid var(--border)}.adsg div:first-child{border-left:0;padding-left:0}
.adsg span{display:block;color:var(--muted);font-size:0.75rem;font-weight:600}.adsg b{font-size:1.25rem;font-weight:600;font-variant-numeric:tabular-nums}
@media (max-width:720px){.adsg{grid-template-columns:1fr}.adsg div,.adsg div:first-child{display:flex;justify-content:space-between;align-items:baseline;padding:10px 0;border-left:0;border-top:1px solid var(--border)}.adsg span{font-size:0.875rem}}
"""


AD_CSS = """.ah{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin:0 0 16px}.ah h1{margin:0;font-size:1.375rem;font-weight:600;letter-spacing:-.02em}.ah p{margin:2px 0 0;color:var(--muted);font-size:.8125rem}
.ab{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:32px;padding:24px;border-radius:var(--r);background:var(--board);color:var(--bink)}.ab-l{font-size:.8125rem;color:var(--bmuted)}
.ab-v{margin:6px 0 8px;font-size:clamp(2.5rem,1.6rem + 2.4vw,3.5rem);line-height:1.05;font-weight:700;letter-spacing:-.035em;font-variant-numeric:tabular-nums}.ab-v.up{color:var(--yellow)}
.ab-s{margin:0;font-size:.9375rem;line-height:1.45;color:var(--bink)}.ab-bars{display:grid;align-content:center;gap:16px}.ab-t{display:flex;justify-content:space-between;gap:12px;margin-bottom:6px;font-size:.8125rem;color:var(--bmuted)}.ab-t b{color:var(--bink);font-size:1rem;font-weight:600;font-variant-numeric:tabular-nums}
.ab-r{height:10px;border-radius:3px;background:var(--bline);overflow:hidden}.ab-r i{display:block;height:100%;background:var(--bink)}.ab-r.sa i{background:var(--yellow)}
.ar{display:grid;grid-template-columns:repeat(4,1fr);margin-top:12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}.ar>div{padding:16px 18px;border-left:1px solid var(--border)}.ar>div:first-child{border-left:0}
.ar-t{display:flex;justify-content:space-between;gap:8px;font-size:.8125rem;font-weight:500;color:var(--muted)}.ar-t em{font-style:normal;font-weight:600;font-variant-numeric:tabular-nums}.ar-t em.g{color:var(--green)}.ar-t em.b{color:var(--red)}.ar b{display:block;margin:6px 0 2px;font-size:1.625rem;line-height:1.2;font-weight:700;letter-spacing:-.025em;font-variant-numeric:tabular-nums}.ar small{font-size:.75rem;color:var(--faint)}
.adb{margin-top:18px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:18px}.adb h2{margin:0 0 10px}.adscr{max-height:440px;overflow:auto;margin:0 -18px -18px;padding:0 18px}
.adt{width:100%;border-collapse:collapse;font-size:.875rem;font-variant-numeric:tabular-nums}.adt th,.adt td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}.adt tr:last-child td{border-bottom:0}.adt th:first-child,.adt td:first-child{text-align:left;padding-left:0}.adt th:last-child,.adt td:last-child{padding-right:0}.adt thead th{position:sticky;top:0;background:var(--surface)}.adt .z{color:var(--faint)}.adt .g{color:var(--green)}.adt .b{color:var(--red)}
.adh{margin-top:18px}.adh summary{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:10px;background:var(--surface2);font-weight:600;font-size:.8125rem;cursor:pointer;list-style:none}.adh summary::-webkit-details-marker{display:none}.adh form{margin-top:12px;padding:18px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.adn{margin:14px 0 0;font-size:.75rem;line-height:1.5;color:var(--faint)}
@media (max-width:860px){.ab{grid-template-columns:1fr;gap:20px;padding:20px}.ar{grid-template-columns:1fr 1fr}.ar>div:nth-child(3){border-left:0}.ar>div:nth-child(n+3){border-top:1px solid var(--border)}}"""


def _period(con, who, spend_map, a, b) -> dict:
    """The numbers of the days a..b (shown, or the same number of days before them for the comparison)."""
    n = amo.numbers(con, int(a.timestamp()), int((b + timedelta(days=1)).timestamp()), who)
    spend = sum(v for k, v in spend_map.items() if igdata.key(a) <= k <= igdata.key(b))
    return {**n, "spend": spend, "cpl": round(spend / n["leads"]) if spend and n["leads"] else None,
            "romi": round((n["amount"] - spend) / spend * 100) if spend else None}


def _delta(cur, prev, lower_is_better=False) -> str:
    if not cur or not prev:
        return ""
    p = round((cur - prev) / prev * 100)
    good = p <= 0 if lower_is_better else p >= 0
    return f'<em class="{"g" if good else "b"}" title="алдыңғы осындай кезеңмен">{p:+d}%</em>'


def page(con, user, note: str = "", first=None, last=None) -> str:
    """Does advertising pay off: the answer first, then what it is made of, then day by day; typing spend by hand is last."""
    today = igdata.today()
    last = min(last or today, today)
    first = first or today.replace(day=1)
    n_days = (last - first).days + 1
    spend = load(con)
    who = target_filter(con)
    cur = _period(con, who, spend, first, last)
    prv = _period(con, who, spend, first - timedelta(days=n_days), first - timedelta(days=1))
    days = amo.daily(con, int(first.timestamp()), n_days, who)
    dates = [first + timedelta(days=i) for i in range(n_days)]

    if cur["spend"]:
        romi, per = cur["romi"], cur["amount"] / cur["spend"]
        top = max(cur["amount"], cur["spend"])
        said = (f"Жарнамаға жұмсалған әр 1 ₸ {per:.1f} ₸ сатылым әкелді".replace(".", ",") + (". Жарнама өзін ақтап тұр." if romi >= 0 else ". Жарнама әзірге өзін ақтаған жоқ."))
        board = (f'<section class="ab cardin"><div><div class="ab-l">Жарнама табысы · ROI</div><div class="ab-v{" up" if romi >= 0 else ""}">{romi:+d}%</div><p class="ab-s">{said}</p></div>'
                 f'<div class="ab-bars"><div><div class="ab-t"><span>Сатылым</span><b>{home.money(cur["amount"])}</b></div><div class="ab-r sa"><i style="width:{cur["amount"] / top * 100:.1f}%"></i></div></div>'
                 f'<div><div class="ab-t"><span>Шығын</span><b>{home.money(cur["spend"])}</b></div><div class="ab-r"><i style="width:{cur["spend"] / top * 100:.1f}%"></i></div></div></div></section>')
    else:
        board = ('<section class="ab cardin" style="grid-template-columns:1fr"><div><div class="ab-l">Жарнама табысы · ROI</div><div class="ab-v">—</div>'
                 f'<p class="ab-s">Бұл күндерде жарнама шығыны жоқ. {"Басқа күндерді таңдап көріңіз." if meta_on() else "Шығынды төменде енгізіңіз."}</p></div></section>')
    tag = " (таргет)" if who else ""
    rows_top = (f'<section class="ar" aria-label="Көрсеткіштер"><div><div class="ar-t"><span>Шығын</span>{_delta(cur["spend"], prv["spend"], True)}</div><b>{home.money(cur["spend"]) if cur["spend"] else "—"}</b><small>жарнамаға жұмсалды</small></div>'
                f'<div><div class="ar-t"><span>Лид{tag}</span>{_delta(cur["leads"], prv["leads"])}</div><b>{home.num(cur["leads"])}</b><small>{"таргеттен келген" if who else "барлық маркетинг"}</small></div>'
                f'<div><div class="ar-t"><span>Бір лид</span>{_delta(cur["cpl"], prv["cpl"], True)}</div><b>{home.money(cur["cpl"]) if cur["cpl"] else "—"}</b><small>шығын ÷ лид</small></div>'
                f'<div><div class="ar-t"><span>Сатылым саны</span>{_delta(cur["sales"], prv["sales"])}</div><b>{home.num(cur["sales"])}</b><small>{home.money(cur["amount"]) if cur["amount"] else "0 ₸"}</small></div></section>')

    canvas_html = ""
    if n_days >= 2 and cur["spend"]:
        import charts
        sp = [spend.get(igdata.key(d)) or 0 for d in dates]
        ld = [x["leads"] for x in days]
        cpl = [round(a / b) if a and b else 0 for a, b in zip(sp, ld)]
        labels = [f"{d.day}.{d.month:02d}" for d in dates]
        canvas_html = charts.CSS + '<div style="margin-top:18px">' + charts.canvas("Күн сайын", [
            {"tab": "Шығын", "label": "Жарнама шығыны", "cur": sp, "prev": None, "total": sum(sp), "delta": None, "unit": " ₸", "unitBig": "₸"},
            {"tab": "Лид", "label": "Лид (таргет)" if who else "Лид", "cur": ld, "prev": None, "total": sum(ld), "delta": None, "unit": "", "unitBig": ""},
            {"tab": "Бір лид", "label": "Бір лидтің бағасы · орташа", "cur": cpl, "prev": None,
             "total": round(sum(sp) / sum(ld)) if sum(ld) else 0, "delta": None, "unit": " ₸", "unitBig": "₸"}],
            labels, prev_label="", last_label="соңғы") + "</div>" + charts.JS

    rows = []
    for d, x in reversed(list(zip(dates, days))):
        sp = spend.get(igdata.key(d)) or 0
        if not (sp or x["leads"] or x["amount"]):
            continue
        r = round((x["amount"] - sp) / sp * 100) if sp else None
        rows.append(f'<tr><td>{d:%d.%m}</td><td{"" if sp else " class=z"}>{home.money(sp) if sp else "—"}</td><td>{x["leads"]}</td>'
                    f'<td{"" if sp and x["leads"] else " class=z"}>{home.money(round(sp / x["leads"])) if sp and x["leads"] else "—"}</td>'
                    f'<td{"" if x["amount"] else " class=z"}>{home.money(x["amount"]) if x["amount"] else "—"}</td>'
                    f'<td class="{"z" if r is None else "g" if r >= 0 else "b"}">{"—" if r is None else f"{r:+d}%"}</td></tr>')
    table = (f'<section class="adb cardin"><h2>Күндер бойынша</h2><div class="adscr"><table class="adt"><thead><tr><th>Күн</th><th>Шығын</th><th>Лид</th><th>Бір лид</th><th>Сатылым</th><th>ROI</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div></section>') if rows else ""

    prev_href = f"?d1={first - timedelta(days=n_days):%Y-%m-%d}&d2={first - timedelta(days=1):%Y-%m-%d}"
    next_href = f"?d1={last + timedelta(days=1):%Y-%m-%d}&d2={min(last + timedelta(days=n_days), today):%Y-%m-%d}" if last < today else None
    src = "Лид пен сатылым — таргет көзінен келген сделкалар." if who else "Лид пен сатылым — барлық маркетинг сделкалары: Баптауда таргет көзі таңдалмаған, сондықтан ROI шынайыдан жоғары көрінуі мүмкін."
    hand = (f'<details class="adh"{"" if meta_on() else " open"}><summary>Шығынды қолмен енгізу</summary><form class="f" method="post" action="/ads"><div class="row2">'
            f'<label>Күн<input type="date" name="day" value="{igdata.key(today)}" max="{igdata.key(today)}" required></label>'
            f'<label>Сома, ₸<input type="number" name="amount" min="0" step="1" inputmode="numeric" placeholder="мысалы 25000" required><small>0 жазсаңыз — сол күннің шығыны өшеді{". Meta-да шығыны бар күнде Meta-ның саны қолданылады" if meta_on() else ""}</small></label></div>'
            '<button class="btnp" type="submit">Сақтау</button></form></details>')
    body = f"""<main class="wrap"><div class="ah"><div><h1>Жарнама</h1><p>{ui.dr_label(first, last, today)} · {n_days} күн</p></div>{ui.date_range(first, last, today, prev_href, next_href, "?d1=@&d2=@")}</div>
{f'<div class="msg ok">{html.escape(note)}</div>' if note else ''}{meta_note(con)}
{board}{rows_top}{canvas_html}{table}{hand}
<p class="adn">ROI = (сатылым − шығын) ÷ шығын. {src} Сатылым сделка жабылған күнге жазылады, сондықтан бір күннің ROI-і шамамен, ұзағырақ кезеңдікі дәлірек.</p></main>"""
    import admin
    return admin.page("Жарнама · EduApp", body, user, "ads").replace("</style>", CSS + AD_CSS + "</style>", 1)
