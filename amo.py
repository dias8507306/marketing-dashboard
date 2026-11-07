"""amoCRM deals for the marketing dashboard.

Deals are copied into the database (amo_deals) and kept fresh by asking amoCRM only for
deals changed since the last copy. A lead = a deal created in the period; a sale = a deal
moved to «Успешно реализовано» (status 142) in the period, its budget is the sale amount.
«Marketing» deals are chosen on the settings page by one deal field (e.g. «Источник»)
and the values of it that count as marketing; with nothing chosen every deal counts.
"""
import asyncio
import json
import os
import time

WON, LOST = 142, 143
FRESH = 300  # seconds between syncs from page views


def configured() -> bool:
    return bool(os.getenv("AMO_DOMAIN") and os.getenv("AMO_TOKEN"))


def base() -> str:
    d = os.getenv("AMO_DOMAIN", "").strip().removeprefix("https://").strip("/")
    return f"https://{d}/api/v4"


def headers() -> dict:
    return {"Authorization": f"Bearer {os.getenv('AMO_TOKEN', '').strip()}"}


_READY = False


def ensure_tables(con):
    global _READY
    if _READY:
        return  # one round trip per statement is slow on a remote database: do it once per process
    _READY = True
    con.execute("create table if not exists amo_deals (id bigint primary key, price bigint, status bigint, pipeline bigint,"
                " created bigint, closed bigint, updated bigint, cf text)")
    con.execute("create index if not exists amo_deals_created on amo_deals (created)")
    con.execute("create index if not exists amo_deals_closed on amo_deals (closed)")
    for col in ("mkt smallint", "resp bigint"):
        try:
            con.execute(f"alter table amo_deals add column {col}")
        except Exception:
            pass  # already there


def kv_get(con, k, default=None):
    row = con.execute("select v from kv where k = ?", (k,)).fetchone()
    return json.loads(row[0]) if row and row[0] else default


def kv_set(con, k, v):
    if k == "mkt_settings":
        invalidate()
        _mark_all(con, v or {})
    con.execute("insert into kv values (?, ?, ?) on conflict (k) do update set v = excluded.v, ts = excluded.ts",
                (k, json.dumps(v), int(time.time())))


WEBINAR = "Вебинар"  # a webinar deal always counts as marketing, whatever is ticked in the settings


def settings(con) -> dict:
    st = kv_get(con, "mkt_settings", {}) or {}
    if st.get("source_field") and WEBINAR not in (st.get("sources") or []):
        st = {**st, "sources": [*(st.get("sources") or []), WEBINAR]}
        kv_set(con, "mkt_settings", st)  # also re-marks the deals already copied
    return st


def first_sync_from() -> int:
    """Start of the previous month: enough for this month and the comparison with the last one."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=5)))
    prev = (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(prev.timestamp())


UPSERT = ("insert into amo_deals (id, price, status, pipeline, created, closed, updated, cf, mkt, resp) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
          " on conflict (id) do update set price = excluded.price, status = excluded.status, pipeline = excluded.pipeline,"
          " created = excluded.created, closed = excluded.closed, updated = excluded.updated, cf = excluded.cf, mkt = excluded.mkt,"
          " resp = excluded.resp")


async def sync(http, con, force=False, budget: float = 4) -> dict:  # page views wait ≤4 s; the watchdog and the night job copy the rest
    """Copy changed deals, page by page, for at most `budget` seconds; progress is kept,
    so a big first copy simply continues on the next page view or nightly run."""
    if not configured():
        return {"ok": False, "error": "amoCRM қосылмаған"}
    ensure_tables(con)
    state = kv_get(con, "amo_sync", {}) or {}
    if not state.get("resp"):  # deals copied before the responsible user was kept: copy them all once more
        state = {"resp": 1, "behind": True}
    if not force and not state.get("behind") and time.time() - state.get("at", 0) < FRESH:
        return {"ok": True, "error": state.get("error"), "count": 0}
    started = time.time()
    since = state.get("updated") or first_sync_from()
    newest, count, error, behind = since, 0, None, False
    for page in range(1, 200):
        if time.time() - started > budget:
            behind = True
            break
        r = await http.get(f"{base()}/leads", headers=headers(), params={
            "filter[updated_at][from]": since, "order[updated_at]": "asc", "limit": 250, "page": page}, timeout=30)
        if r.status_code == 204:
            break
        if r.status_code != 200:
            error = f"amoCRM {r.status_code}: {r.text[:150]}"
            break
        deals = (r.json().get("_embedded") or {}).get("leads", [])
        rows = []
        st = settings(con)
        for d in deals:
            cf = {str(f["field_id"]): [str(v.get("value")) for v in f.get("values") or []]
                  for f in d.get("custom_fields_values") or []}
            cfj = json.dumps(cf, ensure_ascii=False)
            rows.append((d["id"], d.get("price") or 0, d.get("status_id"), d.get("pipeline_id"), d.get("created_at"),
                         d.get("closed_at"), d.get("updated_at"), cfj, 1 if _is_marketing(cfj, d.get("pipeline_id"), st) else 0,
                         d.get("responsible_user_id")))
            newest = max(newest, d.get("updated_at") or 0)
        if rows:
            con.executemany(UPSERT, rows)
            count += len(rows)
            invalidate()
            kv_set(con, "amo_sync", {"at": state.get("at", 0), "updated": newest, "error": None, "behind": True, "resp": 1})
        if len(deals) < 250:
            break
        await asyncio.sleep(0.6)  # ≤ 2 requests a second: the account was blocked for bursts before
    kv_set(con, "amo_sync", {"at": int(time.time()), "updated": newest, "error": error, "behind": behind, "resp": 1})
    return {"ok": error is None, "error": error, "count": count, "behind": behind}


async def fields(http) -> list:
    """Deal fields with fixed choices (lists), for the settings page."""
    if not configured():
        return []
    r = await http.get(f"{base()}/leads/custom_fields", headers=headers(), params={"limit": 250}, timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for f in (r.json().get("_embedded") or {}).get("custom_fields", []):
        if f.get("enums"):
            out.append({"id": str(f["id"]), "name": f["name"], "values": [e["value"] for e in f["enums"]]})
    return out


_USERS = {"at": 0.0, "list": []}


async def users(http) -> list:
    """amoCRM users [{id, name}], for choosing whose deals count for a staff member; kept an hour."""
    if not configured():
        return []
    if time.time() - _USERS["at"] < 3600 and _USERS["list"]:
        return _USERS["list"]
    r = await http.get(f"{base()}/users", headers=headers(), params={"limit": 250}, timeout=30)
    if r.status_code == 200:
        _USERS.update(at=time.time(), list=[{"id": u["id"], "name": u.get("name") or str(u["id"])}
                                            for u in (r.json().get("_embedded") or {}).get("users", [])])
    return _USERS["list"]


def matches(who, resp, cf: dict) -> bool:
    """Whose deal it is: the staff member's amoCRM users, or their values of one deal field (e.g. a source).
    With nothing chosen every marketing deal counts (the shared result)."""
    if not active(who):
        return True
    ids, field, values = set(who.get("users") or []), who.get("field"), set(who.get("values") or [])
    return bool((ids and resp in ids) or (field and values and values & set(cf.get(str(field), []))))


def active(who) -> bool:
    return bool(who and (who.get("users") or (who.get("field") and who.get("values"))))


async def pipelines(http) -> list:
    if not configured():
        return []
    r = await http.get(f"{base()}/leads/pipelines", headers=headers(), timeout=30)
    if r.status_code != 200:
        return []
    return [{"id": p["id"], "name": p["name"]} for p in (r.json().get("_embedded") or {}).get("pipelines", [])]


def value_counts(con, field: str, since: int) -> dict:
    """How many deals created since `since` carry each value of a field (for the settings page)."""
    ensure_tables(con)
    out: dict = {}
    for (cf,) in con.execute("select cf from amo_deals where created >= ?", (since,)):
        for v in json.loads(cf or "{}").get(str(field), []) or ["(бос)"]:
            out[v] = out.get(v, 0) + 1
    return out


def pipeline_counts(con, since: int) -> dict:
    ensure_tables(con)
    return {r[0]: r[1] for r in con.execute("select pipeline, count(*) from amo_deals where created >= ? group by pipeline", (since,))}


def _is_marketing(cf_json: str, pipeline, st: dict) -> bool:
    field, values = st.get("source_field"), set(st.get("sources") or [])
    deal = set(json.loads(cf_json or "{}").get(str(field), [])) if field else set()
    if WEBINAR in deal:
        return True
    pipes = st.get("pipelines") or []
    if pipes and pipeline not in pipes:
        return False
    values -= {WEBINAR}  # webinars alone do not mean «only these»: nothing else ticked is still every deal
    if not field or not values:
        return True
    return bool(values & deal)


# Deals of the last WINDOW seconds, already sorted into marketing / not, kept for CACHE_TTL seconds.
# The dashboard asks for many ranges (period, previous period, week, month, calendar, streak, 14 days):
# one query instead of dozens, and the custom-field check runs once per deal.
WINDOW = 130 * 86400
CACHE_TTL = 600  # a sync that brings new deals clears it at once
_cache = {"at": 0.0, "key": None, "from": 0, "rows": []}


def invalidate():
    _cache["at"] = 0.0


def _mark_all(con, st: dict, only_missing: bool = False):
    """Set amo_deals.mkt from the custom fields: all rows after a settings change, or only rows saved without it."""
    q = "select id, cf, pipeline from amo_deals" + (" where mkt is null" if only_missing else "")
    rows = [(1 if _is_marketing(cf, pipe, st) else 0, i) for i, cf, pipe in con.execute(q)]
    if rows:
        con.executemany("update amo_deals set mkt = ? where id = ?", rows)


_FILLED = False


def _fill_missing(con):
    global _FILLED
    if _FILLED:
        return
    _FILLED = True
    if con.execute("select 1 from amo_deals where mkt is null limit 1").fetchone():
        _mark_all(con, settings(con), only_missing=True)


def _rows(con, since: int, who=None):
    """[(created, closed, won, price)] for marketing deals (only `who`'s when given), or None when `since` is older than the window."""
    st = settings(con)
    key = json.dumps(st, sort_keys=True)
    now = time.time()
    if not (_cache["key"] == key and now - _cache["at"] < CACHE_TTL):
        start = int(now) - WINDOW
        _fill_missing(con)
        rows = [(created or 0, closed or 0, status == WON, price or 0, resp, json.loads(cf or "{}"))
                for created, closed, status, price, resp, cf in con.execute(
                    "select created, closed, status, price, resp, cf from amo_deals where mkt = 1 and (created >= ? or closed >= ?)",
                    (start, start))]
        _cache.update(at=now, key=key, rows=rows, **{"from": start})
    if since < _cache["from"]:
        return None
    return [r[:4] for r in _cache["rows"] if not active(who) or matches(who, r[4], r[5])]


def _old_rows(con, since: int, until: int, who):
    """Rows older than the cache window, straight from the database."""
    _fill_missing(con)
    return [(c or 0, cl or 0, st == WON, pr or 0) for c, cl, st, pr, resp, cf in con.execute(
        "select created, closed, status, price, resp, cf from amo_deals where mkt = 1"
        " and ((created >= ? and created < ?) or (closed >= ? and closed < ?))",
        (since, until, since, until)) if matches(who, resp, json.loads(cf or "{}"))]


def numbers(con, since: int, until: int, who=None) -> dict:
    """Leads, sales count and sales amount for [since, until) — the team's, or `who`'s only."""
    ensure_tables(con)
    rows = _rows(con, since, who)
    if rows is None:
        rows = _old_rows(con, since, until, who)
    leads = sum(1 for c, _, _, _ in rows if since <= c < until)
    sales = [pr for _, cl, won, pr in rows if won and since <= cl < until]
    return {"leads": leads, "sales": len(sales), "amount": sum(sales)}


def daily(con, first_ts: int, days: int, who=None) -> list:
    """Per-day leads / sales / amount for `days` days starting at first_ts (Astana midnight)."""
    ensure_tables(con)
    end = first_ts + days * 86400
    out = [{"leads": 0, "sales": 0, "amount": 0} for _ in range(days)]
    rows = _rows(con, first_ts, who)
    if rows is None:
        rows = _old_rows(con, first_ts, end, who)
    for created, closed, won, price in rows:
        if first_ts <= created < end:
            out[(created - first_ts) // 86400]["leads"] += 1
        if won and first_ts <= closed < end:
            i = (closed - first_ts) // 86400
            out[i]["sales"] += 1
            out[i]["amount"] += price
    return out


def recent_sales(con, since: int) -> list:
    """[(closed, price, responsible user)] of marketing sales since `since`, newest first (for the office board)."""
    ensure_tables(con)
    return list(con.execute("select closed, price, resp from amo_deals where mkt = 1 and status = ? and closed >= ? order by closed desc",
                            (WON, since)))


# ---------- how fast managers touch a new marketing lead ----------
# A touch = the first action of a person (not a robot) on the deal or its contact after the deal appeared:
# a call made or answered, a chat message, a note, a stage change; a deal a manager created himself counts
# as touched at once. Handing the deal to another manager is not a touch. amoCRM keeps these as events.
TOUCH_TYPES = ("outgoing_call", "incoming_call", "outgoing_chat_message", "entity_direct_message", "outgoing_sms",
               "common_note_added", "lead_status_changed", "lead_added")
SLOW_MIN = 15
_SPEED = {"at": 0.0, "key": None, "data": None}
_LAST_EVENTS: dict = {}  # how the last events download went, for the diagnostics endpoint


async def _get(http, path: str, params: dict):
    """GET from amoCRM with one retry (it sometimes drops the connection); None when it still fails."""
    for attempt in range(2):
        try:
            return await http.get(f"{base()}{path}", headers=headers(), params=params, timeout=30)
        except Exception:
            if attempt:
                return None
            await asyncio.sleep(1)


async def _events(http, since: int, until: int, people: list, deadline: float, save, pos: tuple = (0, 1),
                  types=TOUCH_TYPES):
    """People's events in [since, until] on deals and contacts, handed to save(events) page by page.
    Robots (the mailing pipelines) leave most events, so only staff users are asked for, 10 per request.
    Starts at pos = (user group, page); returns None when the slice is done, the position to go on from when
    time ran out, or "error" when amoCRM failed."""
    groups = [people[i:i + 10] for i in range(0, len(people), 10)] or [[]]
    base_params = {"filter[created_at][from]": since, "filter[created_at][to]": until, "filter[type]": ",".join(types),
                   "filter[entity]": "lead,contact", "limit": 100}
    g0, p0 = pos
    for gi in range(g0, len(groups)):
        params = dict(base_params)
        for i, uid in enumerate(groups[gi]):
            params[f"filter[created_by][{i}]"] = uid
        for page in range(p0 if gi == g0 else 1, 10000):
            if time.time() > deadline:
                return (gi, page)
            r = await _get(http, "/events", {**params, "page": page})
            if r is None or r.status_code not in (200, 204):
                _LAST_EVENTS.update(error="no answer" if r is None else f"{r.status_code} {r.text[:150]}")
                return "error"
            ev = (r.json().get("_embedded") or {}).get("events", []) if r.status_code == 200 else []
            _LAST_EVENTS["pages"] = _LAST_EVENTS.get("pages", 0) + 1
            save([e for e in ev if e.get("created_by") and e.get("entity_type") in ("lead", "contact") and e.get("type") in types])
            await asyncio.sleep(0.6)
            if len(ev) < 100:
                break
    return None


TOUCH_WINDOW = 3 * 3600  # events are copied in 3-hour slices; a busy slice goes on page by page over several runs
TOUCH_KEEP = 62 * 86400
_TOUCH_READY = False


def _touch_table(con):
    global _TOUCH_READY
    if _TOUCH_READY:
        return
    _TOUCH_READY = True
    con.execute("create table if not exists amo_touch (etype text, eid bigint, ts bigint, who bigint, primary key (etype, eid, ts, who))")
    con.execute("create index if not exists amo_touch_ts on amo_touch (ts)")


async def sync_touches(http, con, budget: float = 15) -> dict:
    """Copy people's touch events from amoCRM into amo_touch within `budget` seconds.
    The first run starts a week back; kv touch_sync keeps how far the copy is complete (cursor)
    and, inside an unfinished slice, the position to go on from."""
    _touch_table(con)
    now = int(time.time())
    st = kv_get(con, "touch_sync", {}) or {}
    cursor = st.get("cursor") or now - 7 * 86400
    st.setdefault("from", cursor)
    if now - cursor < 120:
        return st
    deadline = time.time() + budget
    try:
        people = [u["id"] for u in await users(http)]
    except Exception:
        return st
    _LAST_EVENTS.update(pages=0, error=None)

    def save(ev):
        rows = {(e["entity_type"], e["entity_id"], e["created_at"], e["created_by"]) for e in ev}
        if rows:
            con.executemany("insert into amo_touch (etype, eid, ts, who) values (?, ?, ?, ?) on conflict do nothing", list(rows))
    while cursor < now - 60 and deadline - time.time() > 3:
        end = st.get("end") or min(cursor + TOUCH_WINDOW, now)
        res = await _events(http, cursor, end, people, deadline, save, tuple(st.get("pos") or (0, 1)))
        if res == "error":
            break
        if res is not None:  # out of time inside the slice: remember where
            st.update(end=end, pos=list(res))
            kv_set(con, "touch_sync", st)
            break
        cursor = end
        st.update(cursor=cursor, end=None, pos=None)
        kv_set(con, "touch_sync", st)
    if st.get("pruned", 0) < now - 86400:
        con.execute("delete from amo_touch where ts < ?", (now - TOUCH_KEEP,))
        st["pruned"] = now
        st["from"] = max(st["from"], now - TOUCH_KEEP)
        kv_set(con, "touch_sync", st)
    _LAST_EVENTS.update(cursor=cursor, behind_min=round((now - cursor) / 60), pos=st.get("pos"))
    return st


async def _contacts_of(http, ids: list) -> dict:
    """{deal id: [contact ids]} for up to 250 deals in one request."""
    out = {}
    for chunk in (ids[i:i + 250] for i in range(0, len(ids), 250)):
        params = {"with": "contacts", "limit": 250}
        for i, x in enumerate(chunk):
            params[f"filter[id][{i}]"] = x
        r = await _get(http, "/leads", params)
        if r is not None and r.status_code == 200:
            for d in (r.json().get("_embedded") or {}).get("leads", []):
                out[d["id"]] = [c["id"] for c in (d.get("_embedded") or {}).get("contacts", [])]
        await asyncio.sleep(0.6)
    return out


async def lead_speed(http, con, since: int, until: int | None = None, ttl: int = 600, budget: float = 15) -> dict | None:
    """Marketing deals created in [since, until): minutes to the first touch, and the ones still untouched.
    Touches come from amo_touch (copied by sync_touches); the answer is kept `ttl` seconds.
    None when the copy does not reach that far back yet."""
    if not configured():
        return None
    now = int(time.time())
    until = min(until or now, now)
    key = (since, until if until < now - 60 else "now")
    if _SPEED["key"] == key and time.time() - _SPEED["at"] < ttl:
        return _SPEED["data"]
    kv_key = f"lead_speed:{since}:{key[1]}"
    saved = kv_get(con, kv_key) if ttl else None  # serverless instances do not share memory: keep it in the database too
    if saved and time.time() - saved.get("at", 0) < ttl:
        _SPEED.update(at=saved["at"], key=key, data=saved["data"])
        return saved["data"]
    st = await sync_touches(http, con, budget)
    horizon = min(now, until + 12 * 3600)  # a deal from late evening is answered next morning
    if since < st.get("from", now):
        return None
    covered = st.get("cursor", 0)
    ensure_tables(con)
    _fill_missing(con)
    deals = list(con.execute("select id, created, resp from amo_deals where mkt = 1 and created >= ? and created < ? order by created",
                             (since, until)))
    data = {"total": len(deals), "touched": 0, "median": None, "within": None, "slow": [], "waiting": [], "by_user": {},
            "partial": covered < horizon - 900}
    if deals:
        contacts = await _contacts_of(http, [d[0] for d in deals])
        first: dict = {}
        for etype, eid, ts, who in con.execute("select etype, eid, ts, who from amo_touch where ts >= ? and ts <= ?", (since, horizon)):
            first.setdefault((etype, eid), []).append((ts, who))
        try:
            names = {u["id"]: u["name"] for u in await users(http)}
        except Exception:
            names = {}
        rows, waiting = [], []
        for did, created, resp in deals:
            cand = [x for x in first.get(("lead", did), []) if x[0] >= created]
            for cid in contacts.get(did, []):
                cand += [x for x in first.get(("contact", cid), []) if x[0] >= created]
            if cand:
                t, who = min(cand)
                rows.append({"id": did, "min": round((t - created) / 60), "who": names.get(who) or names.get(resp) or ""})
            else:
                waiting.append({"id": did, "min": round((min(horizon, max(covered, created)) - created) / 60), "who": names.get(resp) or ""})
        mins = sorted(r["min"] for r in rows)
        by_user: dict = {}
        for r in rows:
            u = by_user.setdefault(r["who"] or "—", {"n": 0, "sum": 0, "fast": 0})
            u["n"] += 1
            u["sum"] += r["min"]
            u["fast"] += r["min"] <= SLOW_MIN
        data.update(touched=len(rows), median=mins[len(mins) // 2] if mins else None,
                    within=round(sum(1 for x in mins if x <= SLOW_MIN) / len(mins) * 100) if mins else None,
                    slow=sorted((r for r in rows if r["min"] > SLOW_MIN), key=lambda r: -r["min"])[:10],
                    waiting=sorted((w for w in waiting if w["min"] > SLOW_MIN), key=lambda w: -w["min"]), by_user=by_user)
    _SPEED.update(at=time.time(), key=key, data=data)
    if not data["partial"]:
        kv_set(con, kv_key, {"at": time.time(), "data": data})
    return data


async def probe_events(http, since: int) -> dict:
    """Diagnostics: which kinds of events people and robots leave, counted (no names or ids)."""
    out, started = {}, time.time()
    for page in range(1, 15):
        if time.time() - started > 20:
            break
        r = await _get(http, "/events", {"filter[created_at][from]": since, "limit": 100, "page": page})
        if r is None or r.status_code != 200:
            out["_error"] = "no answer" if r is None else f"{r.status_code} {r.text[:120]}"
            break
        ev = (r.json().get("_embedded") or {}).get("events", [])
        for e in ev:
            k = f'{e.get("type")}|{e.get("entity_type")}|{"person" if e.get("created_by") else "robot"}'
            out[k] = out.get(k, 0) + 1
        if len(ev) < 100:
            break
        await asyncio.sleep(0.6)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------- when leads and sales come: weekday × hour ----------

def hour_counts(con, since: int, until: int, who=None) -> list:
    """Marketing leads per hour of the day (Astana) created in [since, until)."""
    out = [0] * 24
    for created, _, _, _ in _period_rows(con, since, until, who):
        if since <= created < until:
            out[((created + 5 * 3600) // 3600) % 24] += 1
    return out


def week_hours(con, since: int, until: int, who=None) -> dict:
    """{"leads": 7×24, "sales": 7×24, "amount": 7×24} by weekday (Mon=0) and hour, Astana time."""
    m = {k: [[0] * 24 for _ in range(7)] for k in ("leads", "sales", "amount")}
    days = set()
    for created, closed, won, price in _period_rows(con, since, until, who):
        if since <= created < until:
            t = created + 5 * 3600
            days.add(t // 86400)
            m["leads"][(t // 86400 + 3) % 7][(t // 3600) % 24] += 1
        if won and since <= closed < until:
            t = closed + 5 * 3600
            m["sales"][(t // 86400 + 3) % 7][(t // 3600) % 24] += 1
            m["amount"][(t // 86400 + 3) % 7][(t // 3600) % 24] += price
    m["weeks"] = max(1, round((max(days) - min(days) + 1) / 7)) if days else 1  # the source field is filled only since October
    return m


def _period_rows(con, since: int, until: int, who=None) -> list:
    ensure_tables(con)
    rows = _rows(con, since, who)
    return rows if rows is not None else _old_rows(con, since, until, who)
