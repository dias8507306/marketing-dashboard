"""Saved daily reports: one frozen KPI summary per Astana day.

«auto»     — the cron right after midnight saves the day that just ended (followers = end of day);
«manual»   — the «Снимок жасау» button saves today as it is at that moment;
«restored» — days before saving started, rebuilt from Instagram's daily insights (no follower total).
New followers arrive from Meta 1–2 days late, so saved days of the last week get that number filled in later.
"""
import json
import time
from datetime import datetime, timedelta

import igdata

KIND_NAMES = {"auto": "Авто · күн соңы", "manual": "Қолмен сақталды", "restored": "Қалпына келтірілді"}


_READY = False  # tables are created once per process: each statement is a round trip to the database


def ensure_table(con):
    global _READY
    if _READY:
        return
    _READY = True
    con.execute("create table if not exists reports (day text primary key, data text, kind text, ts bigint)")


async def summary(http, api, auth, con, day, followers, skip=()) -> dict:
    rows = await igdata.days(http, api, auth, con, day, day)
    m = dict(rows.get(igdata.key(day)) or {})
    posts = await igdata.media(http, api, auth, con, day, day)
    since, until = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    out = {k: m.get(k) for k in igdata.DAY_METRICS + ["new_followers"]}
    out.update(followers=followers, posts=len(posts),
               direct=igdata.direct_messages(con, since, until, skip),
               er=round(m["total_interactions"] / m["reach"] * 100, 1) if m.get("reach") and m.get("total_interactions") is not None else None)
    return out


def save(con, day_key: str, data: dict, kind: str, keep_better: bool = False):
    """Upsert one day. A restored row never overwrites a real snapshot."""
    ensure_table(con)
    old = get(con, day_key)
    if old and keep_better and old["kind"] != "restored":
        return
    con.execute("insert into reports values (?, ?, ?, ?) on conflict (day) do update set data = excluded.data,"
                " kind = excluded.kind, ts = excluded.ts", (day_key, json.dumps(data), kind, int(time.time())))


def get(con, day_key: str):
    ensure_table(con)
    row = con.execute("select day, data, kind, ts from reports where day = ?", (day_key,)).fetchone()
    return {"day": row[0], "data": json.loads(row[1]), "kind": row[2], "ts": row[3]} if row else None


def all_reports(con) -> list:
    ensure_table(con)
    return [{"day": r[0], "data": json.loads(r[1]), "kind": r[2], "ts": r[3]}
            for r in con.execute("select day, data, kind, ts from reports order by day desc")]


def fill_late_followers(con, rows: dict):
    """Put Meta's late new-follower counts into saved days that were saved without them."""
    ensure_table(con)
    for k, v in rows.items():
        rep = get(con, k)
        if rep and rep["data"].get("new_followers") is None and v.get("new_followers") is not None:
            rep["data"]["new_followers"] = v["new_followers"]
            con.execute("update reports set data = ? where day = ?", (json.dumps(rep["data"]), k))


async def restore(http, api, auth, con, days_back: int = 30, skip=()):
    """Rebuild missing past days from Instagram (once; existing rows are left alone)."""
    ensure_table(con)
    have = {r[0] for r in con.execute("select day from reports")}
    today = igdata.today()
    first = today - timedelta(days=days_back)
    rows = await igdata.days(http, api, auth, con, first, today - timedelta(days=1))
    for k, m in rows.items():
        if k in have or not m:
            continue
        d = datetime.strptime(k, "%Y-%m-%d").replace(tzinfo=igdata.TZ)
        since, until = int(d.timestamp()), int((d + timedelta(days=1)).timestamp())
        data = {x: m.get(x) for x in igdata.DAY_METRICS + ["new_followers"]}
        data.update(followers=igdata.followers_on(con, k), posts=None,
                    direct=igdata.direct_messages(con, since, until, skip),
                    er=round(m["total_interactions"] / m["reach"] * 100, 1) if m.get("reach") and m.get("total_interactions") is not None else None)
        save(con, k, data, "restored", keep_better=True)
    fill_late_followers(con, rows)
