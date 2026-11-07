"""Numbers for the marketing home page: sales, leads, plans, bonus, Instagram.

Results are shared by the whole team (one Instagram, one CRM); plans and the bonus are
personal. The main daily KPI is leads (default 100 a day). The sales plan is monthly and
spread evenly over the month's days for week/day views. The bonus is paid when the month's
sales plan is reached: sales amount × bonus %.

What 100 leads take on Instagram (likes, comments, reach, new followers) is worked out
from the last 14 finished days: metric per marketing lead × daily lead plan.
"""
import calendar
import re
import time
from datetime import datetime, timedelta

import amo
import igdata

TZ = igdata.TZ
PERIODS = [("day", "Күн"), ("week", "Апта"), ("month", "Ай")]
DEFAULT_LEADS_DAY = 100
LOOKBACK = 14
IG_KEYS = ("likes", "comments", "reach", "new_followers")


def bounds(period: str, anchor: datetime):
    """(first day, last day) of the period that contains anchor."""
    if period == "day":
        return anchor, anchor
    if period == "week":
        first = anchor - timedelta(days=anchor.weekday())
        return first, first + timedelta(days=6)
    first = anchor.replace(day=1)
    return first, first.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])


def month_days(d: datetime) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def pct(v, t):
    return round(v / t * 100) if t and v is not None else None


def leads_day_plan(plans: dict) -> int:
    return int(plans.get("leads_day") or DEFAULT_LEADS_DAY)


async def ig_targets(http, api, auth, con, lead_goal: int) -> dict:
    """Per-day Instagram targets that go with `lead_goal` leads, from the last 14 finished days."""
    last = igdata.today() - timedelta(days=1)
    first = last - timedelta(days=LOOKBACK - 1)
    leads = amo.daily(con, int(first.timestamp()), LOOKBACK)
    rows = await igdata.days(http, api, auth, con, first, last)
    out = {}
    for m in IG_KEYS:
        pairs = [(rows.get(igdata.key(first + timedelta(days=i)), {}).get(m), leads[i]["leads"]) for i in range(LOOKBACK)]
        pairs = [(v, n) for v, n in pairs if v is not None and n]
        total_leads = sum(n for _, n in pairs)
        if total_leads >= 20:
            out[m] = round(sum(v for v, _ in pairs) / total_leads * lead_goal)
    out["_days"] = LOOKBACK
    out["_leads"] = sum(d["leads"] for d in leads)
    return out


async def build(http, api, auth, con, *, period: str, anchor: datetime, plans: dict, name: str, login: str | None = None,
                span_days: tuple | None = None) -> dict:
    """`span_days` = (first, last) for period "range": any days the user picked; `anchor` is then the last of them."""
    import dept  # the department's approved plan for this month; a person's approved own plan replaces its targets
    dp = dept.plan_for(con, anchor)
    if dp:
        plans = {**(plans or {}), **{k: dp.get(k) for k in ("amount", "leads_day", "bonus_pct")}}
    pp = dept.person_plan_for(con, login, anchor) if login else None
    if pp:
        plans = {**plans, "amount": pp.get("amount"), "leads_day": pp.get("leads_day")}
    today = igdata.today()
    first, last = span_days if period == "range" and span_days else bounds(period, anchor)
    until_day = min(last, today)
    since, until = int(first.timestamp()), int((last + timedelta(days=1)).timestamp())
    span = (last - first).days + 1
    open_days = max(1, (until_day - first).days + 1) if first <= today else 0
    prev_first = first - timedelta(days=span) if period != "month" else (first - timedelta(days=1)).replace(day=1)

    who = None  # results are shared by the team (personal attribution was removed from the team page)
    crm = amo.numbers(con, since, until, who)
    # a period that is still running is compared with the same stretch of the previous one (today until now ↔
    # yesterday until this hour, this month so far ↔ the same days of last month), not with the whole of it
    now_ts = int(time.time())
    prev_until = int(first.timestamp())
    if since <= now_ts < until:
        prev_until = min(prev_until, int(prev_first.timestamp()) + (now_ts - since))
    crm_prev = amo.numbers(con, int(prev_first.timestamp()), prev_until, who)
    for c in (crm, crm_prev):
        c["avg"] = round(c["amount"] / c["sales"]) if c["sales"] else None
        c["conv"] = round(c["sales"] / c["leads"] * 100, 1) if c["leads"] else None

    dim = month_days(anchor)
    lead_day = leads_day_plan(plans)
    amount_month = plans.get("amount") or 0
    if amount_month < 1000:  # a typo like «10» is not a plan; show it as not set
        amount_month = 0
    k = {"day": 1, "week": 7, "month": dim}.get(period, span)
    plan = {"amount": round(amount_month * k / dim), "leads": lead_day * k}
    done = {"amount": pct(crm["amount"], plan["amount"]), "leads": pct(crm["leads"], plan["leads"])}

    # month and week progress (always around the anchor day)
    m_first, _ = bounds("month", anchor)
    m_days = amo.daily(con, int(m_first.timestamp()), dim, who)
    month = {"amount": sum(d["amount"] for d in m_days), "leads": sum(d["leads"] for d in m_days),
             "sales": sum(d["sales"] for d in m_days)}
    elapsed = max(1, min(dim, (today - m_first).days + 1)) if m_first <= today else 0
    w_first, w_last = bounds("week", anchor)
    week = amo.numbers(con, int(w_first.timestamp()), int((w_last + timedelta(days=1)).timestamp()), who)
    week_plan = {"amount": round(amount_month * 7 / dim), "leads": lead_day * 7}

    forecast = month_forecast(m_days, month, amount_month, lead_day * dim, m_first, today)

    cal = []
    day_amount_plan = amount_month / dim if amount_month else 0
    for i, d in enumerate(m_days):
        day = m_first + timedelta(days=i)
        future = day > today
        cal.append({"day": i + 1, "date": igdata.key(day), "future": future, "today": day == today,
                    "amount": d["amount"], "leads": d["leads"], "sales": d["sales"],
                    "done": not future and d["leads"] >= lead_day,
                    "sales_done": bool(day_amount_plan) and not future and d["amount"] >= day_amount_plan})

    bonus_pct = plans.get("bonus_pct") or 0
    reached = bool(amount_month) and month["amount"] >= amount_month
    bonus = {"pct": bonus_pct, "reached": reached,
             "earned": round(month["amount"] * bonus_pct / 100) if reached else 0,
             "potential": round(max(month["amount"], amount_month) * bonus_pct / 100),
             "left": max(0, amount_month - month["amount"])}

    ig_rows = await igdata.days(http, api, auth, con, first, until_day) if first <= today else {}
    ig = {m: igdata.total(ig_rows, m) for m in ("new_followers", "views", "reach", "total_interactions",
                                                  "likes", "comments", "saves", "shares", "profile_views")}
    per_day = await ig_targets(http, api, auth, con, lead_day)
    ig_plan = {m: per_day[m] * open_days for m in IG_KEYS if m in per_day}
    # conversion the sales plan needs, at the average check of the period
    avg = crm["avg"] or crm_prev["avg"]
    conv_plan = round((amount_month / dim / avg) / lead_day * 100, 1) if amount_month and avg and lead_day else None

    series_first = first if period in ("month", "range") else until_day - timedelta(days=13)
    series = amo.daily(con, int(series_first.timestamp()), (until_day - series_first).days + 1, who)
    today_leads = next((c["leads"] for c in cal if c["today"]), None)
    streak = lead_streak(con, lead_day, who)
    celebrate = (period == "day" and done["leads"] is not None and done["leads"] >= 100) or \
        (today_leads is not None and today_leads >= lead_day)
    first_name = (name or "").split()[0] if name else ""
    return {
        "period": period, "first": first, "last": last, "name": name, "first_name": first_name,
        "crm": crm, "prev": crm_prev, "plan": plan, "done": done, "lead_day": lead_day,
        "month": month, "month_plan": {"amount": amount_month, "leads": lead_day * dim},
        # a person on their own plan also sees the department's shared one
        "dept_month_plan": {"amount": dp.get("amount") or 0, "leads": (dp.get("leads_day") or 0) * dim} if pp and dp else None,
        "month_pct": {"amount": pct(month["amount"], amount_month), "leads": pct(month["leads"], lead_day * dim)},
        "week": week, "week_plan": week_plan,
        "week_pct": {"amount": pct(week["amount"], week_plan["amount"]), "leads": pct(week["leads"], week_plan["leads"])},
        "pace": pct(month["amount"], amount_month * elapsed / dim) if amount_month and elapsed else None,
        "elapsed": elapsed, "dim": dim, "calendar": cal, "bonus": bonus, "ig": ig, "ig_plan": ig_plan,
        "ig_basis": {"days": per_day["_days"], "leads": per_day["_leads"]}, "conv_plan": conv_plan,
        "series": [{"label": f"{(series_first + timedelta(days=i)).day}", **d} for i, d in enumerate(series)],
        "celebrate": celebrate, "today_leads": today_leads, "streak": streak, "personal": amo.active(who),
        "forecast": forecast,
    }


def month_forecast(m_days: list, month: dict, amount_plan: int, leads_plan: int, m_first: datetime, today: datetime) -> dict | None:
    """Where the month ends at the current pace, and what each remaining day needs to reach the plan.
    Pace = the mean of the last 7 finished days and of the whole month so far (one lucky day weighs less).
    Today is not finished, so it counts at the pace unless it already did better."""
    if m_first > today:
        return None
    dim = len(m_days)
    current = m_first.year == today.year and m_first.month == today.month
    if not current:  # a finished month: the result is the forecast
        return {"final": True, "amount": month["amount"], "leads": month["leads"], "pct": pct(month["amount"], amount_plan),
                "leads_pct": pct(month["leads"], leads_plan)}
    done = (today - m_first).days  # finished days before today
    past, now = m_days[:done], m_days[done]

    def pace(key):
        if not past:
            return now[key]
        last7 = past[-7:]
        return (sum(d[key] for d in last7) / len(last7) + sum(d[key] for d in past) / len(past)) / 2
    left = dim - done  # today included
    out = {"final": False, "left": left}
    for key, plan in (("amount", amount_plan), ("leads", leads_plan)):
        p = pace(key)
        out[key] = round(sum(d[key] for d in past) + max(now[key], p) + p * (left - 1))
        out[key + "_pace"] = round(p)
        out[key + "_need"] = round(max(0, plan - month[key]) / left) if plan else None
    out["pct"], out["leads_pct"] = pct(out["amount"], amount_plan), pct(out["leads"], leads_plan)
    avg = month["amount"] / month["sales"] if month["sales"] else None
    conv = month["sales"] / month["leads"] if month["leads"] else None
    out["sales_need"] = round(out["amount_need"] / avg, 1) if avg and out["amount_need"] else None
    out["leads_for_sales"] = round(out["amount_need"] / avg / conv) if avg and conv and out["amount_need"] else None
    out["gap"] = max(0, amount_plan - out["amount"]) if amount_plan else None
    return out


STREAK_GIFTS = {5: "Кофе", 10: "Промокод", 15: "Бонус"}


def lead_streak(con, lead_day: int, who=None) -> dict:
    """Days in a row the daily lead plan was met. Today counts once it is met; until then the
    streak runs up to yesterday, so an unfinished morning does not break it."""
    today = igdata.today()
    first = today - timedelta(days=89)
    days = amo.daily(con, int(first.timestamp()), 90, who)
    met = [d["leads"] >= lead_day for d in days]
    today_met = met[-1]
    n = 0
    for ok in reversed(met if today_met else met[:-1]):
        if not ok:
            break
        n += 1
    milestones = sorted(STREAK_GIFTS)
    reached = max((m for m in milestones if n >= m), default=0)
    if n > milestones[-1]:  # after 15: every 5 more days is another reward
        reached = n - (n % 5)
    nxt = next((m for m in milestones if m > n), n + 5 - (n % 5))
    gift = STREAK_GIFTS.get(reached) or (STREAK_GIFTS[milestones[-1]] if reached else None)
    return {"days": n, "today_met": today_met, "next": nxt, "reached": reached, "gift": gift,
            "unlocked": today_met and reached and n == reached,  # the milestone was hit today
            "history": met[-15:]}


# The report text is a template the owner changes on the Telegram page: {name} is replaced by a number,
# a line whose {name} is empty is left out, and [ ... ] is left out when a {name} inside it is empty.
REPORT_TPL = """*Маркетинг · есеп · {кезең}*

*Жоспар орындалуы:*
Лид: {лид}[ (жоспар: {лид_жоспар}) — {лид_пайыз}]
Лайк: {лайк}[ (жоспар: {лайк_жоспар}) — {лайк_пайыз}]
Коммент: {коммент}[ (жоспар: {коммент_жоспар}) — {коммент_пайыз}]
Охват: {охват}[ (жоспар: {охват_жоспар}) — {охват_пайыз}]

*Сатылым (маркетинг):*
{сатылым_сома} · {сатылым_саны} сатылым · орташа чек {орташа_чек}[ · конверсия {конверсия}]
Айдың басынан: {ай_сатылым}[ (жоспар: {ай_жоспар}) — {ай_пайыз}]

*Instagram:*
Жазылушы: {жазылушы}[ ({жазылушы_өсім})]
Жаңа жазылушы: {жаңа_жазылушы}
Қаралым {қаралым} · профиль {профиль} · сақтау {сақтау} · бөлісу {бөлісу}
Direct-ке жазғандар: {direct}
{жарияланым}

{сілтеме}"""
REPORT_VARS = (("кезең", "есептің күні не кезеңі"), ("лид", "лид саны"), ("лид_жоспар", "лид жоспары"), ("лид_пайыз", "лид жоспарының орындалуы"),
               ("лайк", "лайк"), ("лайк_жоспар", "лайк жоспары"), ("лайк_пайыз", "лайк орындалуы"),
               ("коммент", "коммент"), ("коммент_жоспар", "коммент жоспары"), ("коммент_пайыз", "коммент орындалуы"),
               ("охват", "охват"), ("охват_жоспар", "охват жоспары"), ("охват_пайыз", "охват орындалуы"),
               ("сатылым_сома", "сатылым сомасы"), ("сатылым_саны", "сатылым саны"), ("орташа_чек", "орташа чек"), ("конверсия", "конверсия"),
               ("ай_сатылым", "айдың басынан сатылым"), ("ай_жоспар", "айлық сатылым жоспары"), ("ай_пайыз", "айлық жоспардың орындалуы"),
               ("жазылушы", "жазылушы саны"), ("жазылушы_өсім", "жазылушы өсімі"), ("жаңа_жазылушы", "жазылушы саны белгісіз күні — тек өсімі"), ("қаралым", "қаралым"), ("профиль", "профильге кіру"),
               ("сақтау", "сақтау"), ("бөлісу", "бөлісу"), ("direct", "Direct-ке жазғандар"), ("жарияланым", "жарияланым туралы жол"),
               ("сілтеме", "дашбордқа сілтеме"))
_VAR = re.compile(r"\{([^{}\s]+)\}")


def report_tpl(con) -> str:
    return amo.kv_get(con, "report_tpl") or REPORT_TPL


def fill_template(tpl: str, vals: dict) -> str:
    """{name} → value; [ … ] disappears when a {name} in it is empty; a line disappears when a {name} outside [ ] is empty."""
    def empty(text):
        return any(x in vals and not vals[x] for x in _VAR.findall(text))
    out = []
    for line in tpl.replace("\r\n", "\n").split("\n"):
        line = re.sub(r"\[([^\[\]]*)\]", lambda x: "" if empty(x.group(1)) else x.group(1), line)
        if not empty(line):
            out.append(_VAR.sub(lambda x: vals.get(x.group(1), x.group(0)), line))
    return "\n".join(out).strip("\n")


def short_report(m: dict, url: str, igx: dict | None = None, tpl: str | None = None) -> str:
    """Report for WhatsApp / Telegram from the owner's template: plan lines («орындалды ✓» once a plan is met), sales, Instagram."""
    igx = igx or {}

    def n(v):
        return "" if v is None else f"{round(v):,}".replace(",", " ")

    def money(v):
        return "" if v is None else n(v) + " ₸"

    def pct_of(value, target):
        if not target:
            return ""
        p = round((value or 0) / target * 100)
        return "орындалды ✓" if p >= 100 else f"{p}%"

    crm, ig, ip = m["crm"], m["ig"], m["ig_plan"]
    first, last = m["first"], m["last"]
    plan_amt = m["month_plan"]["amount"]
    mtd = sum(c["amount"] for c in m["calendar"] if c["date"] <= f"{last:%Y-%m-%d}")
    fol, prev = igx.get("followers"), igx.get("prev")
    growth = fol - prev if fol is not None and prev is not None else igx.get("growth", ig.get("new_followers"))
    vals = {"кезең": f"{first:%d.%m.%Y}" if first == last else f"{first:%d.%m}–{last:%d.%m.%Y}",
            "лид": n(crm["leads"]) or "—", "лид_жоспар": n(m["plan"]["leads"]) if m["plan"]["leads"] else "",
            "лид_пайыз": pct_of(crm["leads"], m["plan"]["leads"]),
            "сатылым_сома": money(crm["amount"]) or "—", "сатылым_саны": n(crm["sales"]) or "—", "орташа_чек": money(crm["avg"]) or "—",
            "конверсия": f"{crm['conv']}%" if crm["conv"] is not None else "",
            "ай_сатылым": money(mtd), "ай_жоспар": money(plan_amt) if plan_amt else "", "ай_пайыз": pct_of(mtd, plan_amt),
            "жазылушы": n(fol), "жазылушы_өсім": "" if growth is None else ("+" if growth >= 0 else "−") + n(abs(growth)),
            "жаңа_жазылушы": "" if fol is not None or growth is None else ("+" if growth >= 0 else "−") + n(abs(growth)),
            "қаралым": n(ig.get("views")) or "—", "профиль": n(ig.get("profile_views")) or "—", "сақтау": n(ig.get("saves")) or "—",
            "бөлісу": n(ig.get("shares")) or "—", "direct": n(igx.get("direct")),
            "жарияланым": (f"{'Бүгін ' if igx.get('is_today') else ''}{igx['posts']} жарияланым" if igx.get("posts")
                           else "Жарияланым болған жоқ" if igx.get("posts") == 0 else ""),
            "сілтеме": url}
    for key, kk in (("likes", "лайк"), ("comments", "коммент"), ("reach", "охват")):
        vals[kk] = n(ig.get(key)) or "—"
        vals[kk + "_жоспар"] = n(ip.get(key)) if ip.get(key) else ""
        vals[kk + "_пайыз"] = pct_of(ig.get(key), ip.get(key))
    return fill_template(tpl or REPORT_TPL, vals)
