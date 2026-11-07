"""Daily Instagram plan: 100 leads a day, and how much of each metric that takes.

A lead is a person who wrote to @eduapp_demo in Direct that day. Targets for likes,
comments, reach… are either set by hand on the plan page, or worked out from the
last 14 finished days: (metric per lead) × lead target. Until enough leads have been
counted (MIN_LEADS), a metric without a hand-set target has no target.
"""
import json
import time
from datetime import timedelta

import igdata
import ui

METRICS = [("leads", "Лид (Direct-ке жазғандар)"), ("new_followers", "Жаңа жазылушы"), ("reach", "Қамту"),
           ("profile_views", "Профильді қарады"), ("likes", "Лайк"), ("comments", "Коммент")]
DEFAULT = {"leads": 100}
LOOKBACK = 14
MIN_LEADS = 20


def load(con) -> dict:
    row = con.execute("select v from kv where k = 'plan'").fetchone()
    return {**DEFAULT, **(json.loads(row[0]) if row and row[0] else {})}


def save(con, plan: dict):
    con.execute("insert into kv values ('plan', ?, ?) on conflict (k) do update set v = excluded.v, ts = excluded.ts",
                (json.dumps(plan), int(time.time())))


def leads_by_day(con, first, last, skip=()) -> dict:
    out = {}
    d = first
    while d <= last:
        out[igdata.key(d)] = igdata.direct_messages(con, int(d.timestamp()), int((d + timedelta(days=1)).timestamp()), skip)
        d += timedelta(days=1)
    return out


async def targets(http, api, auth, con, skip=()) -> dict:
    """{metric: {"target": n, "auto": bool}} for every metric that has a target."""
    plan = load(con)
    lead_goal = plan.get("leads") or 0
    out = {"leads": {"target": lead_goal, "auto": False}} if lead_goal else {}
    last = igdata.today() - timedelta(days=1)
    first = last - timedelta(days=LOOKBACK - 1)
    leads = leads_by_day(con, first, last, skip)
    days_with = {k for k, v in leads.items() if v}
    total_leads = sum(leads.values())
    rows = await igdata.days(http, api, auth, con, first, last) if total_leads >= MIN_LEADS else {}
    for m, _ in METRICS[1:]:
        if plan.get(m):
            out[m] = {"target": plan[m], "auto": False}
        elif lead_goal and total_leads >= MIN_LEADS:
            vals = [rows[k].get(m) for k in days_with if rows.get(k, {}).get(m) is not None]
            if vals:
                per_lead = sum(vals) / sum(leads[k] for k in days_with if rows.get(k, {}).get(m) is not None)
                out[m] = {"target": max(1, round(per_lead * lead_goal)), "auto": True}
    out["_basis"] = {"leads": total_leads, "days": len(days_with)}
    return out


def progress(value, target):
    if value is None or not target:
        return None
    return round(value / target * 100)


PAGE = """<!doctype html><html lang="kk"><head>__HEAD____FONT__<title>Күндік план · EduApp</title>__STYLE__<style>__KIT__
.f .row{display:flex;gap:10px}.f .row>*{flex:1}
</style></head><body>__TOPBAR__<main class="wrap narrow">
<section class="ph cardin"><div><h1>Instagram күндік планы</h1><p>Лид — сол күні Direct-ке жазған адамдар. Басқа көрсеткіштерді бос қалдырсаңыз, олар 100 лидке қанша керек екені бойынша соңғы 14 күннен өздігінен есептеледі.</p></div></section>
__OK__<section class="card cardin" style="--i:1"><form class="f" method="post"><div class="row2">__FIELDS__</div>
<div class="row"><a class="btng" href="report" style="height:44px">← Есеп</a><button class="btnp" type="submit">Сақтау</button></div></form></section></main>__THEMEJS____KITJS__</body></html>"""


def render(current: dict, tg: dict, saved: bool, user: dict | None = None) -> str:
    fields = []
    for m, name in METRICS:
        val = current.get(m) or ""
        auto = tg.get(m) if not current.get(m) else None
        hint = (f"қазір өздігінен: {auto['target']}" if auto and auto.get("auto") else
                "бос қалса — өздігінен есептеледі" if m != "leads" else "күніне неше лид керек")
        fields.append(f'<label>{name}<input type="number" min="0" name="{m}" value="{val}" inputmode="numeric">'
                      f'<small>{hint}</small></label>')
    return (PAGE.replace("__HEAD__", ui.HEAD).replace("__FONT__", ui.FONT).replace("__STYLE__", ui.STYLE)
            .replace("__KIT__", ui.KIT + ui.PAGES).replace("__TOPBAR__", ui.topbar(user, "instagram"))
            .replace("__THEMEJS__", ui.THEME_JS).replace("__KITJS__", ui.KIT_JS)
            .replace("__FIELDS__", "".join(fields))
            .replace("__OK__", '<div class="msg ok">План сақталды</div>' if saved else ""))
