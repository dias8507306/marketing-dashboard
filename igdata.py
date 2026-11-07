"""Instagram numbers for the dashboard and the daily report, cached in the database.

Day metrics (reach, likes, comments…) are asked per Astana day and kept; a day is
final two days after it ends, when Meta has settled its counts, and is not asked again.
New followers per day come from the «follower_count» series (last 30 days, not today).
"""
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))  # Astana
DAY_METRICS = ["reach", "views", "profile_views", "accounts_engaged", "total_interactions",
               "likes", "comments", "shares", "saves"]
FINAL_AFTER = 3 * 86400
PENDING_DAYS = 3  # Meta reports 0 new followers for the last days until it has counted them
MEDIA_FRESH = 3 * 3600


_READY = False  # tables are created once per process: each statement is a round trip to the database


def ensure_tables(con):
    global _READY
    if _READY:
        return
    _READY = True
    con.execute("create table if not exists ig_day (day text primary key, data text, final integer, ts bigint)")
    con.execute("create table if not exists ig_media (id text primary key, data text, ts bigint)")
    con.execute("create table if not exists daily (day text primary key, followers bigint, media bigint, ts bigint)")


def day_start(dt: datetime) -> datetime:
    return dt.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def today() -> datetime:
    return day_start(datetime.now(TZ))


def key(day: datetime) -> str:
    return day.strftime("%Y-%m-%d")


async def _get(http, url, auth, params):
    r = await http.get(url, headers=auth, params=params)
    try:
        body = r.json()
    except Exception:
        body = {}
    return r.status_code, body


_PROFILE = {"at": 0.0, "body": {}}


async def profile(http, api, auth) -> dict:
    """The account card; kept 5 minutes in memory (it is asked by several pages and changes slowly)."""
    if time.time() - _PROFILE["at"] < 300 and _PROFILE["body"]:
        return _PROFILE["body"]
    code, body = await _get(http, f"{api}/me", auth,
                            {"fields": "username,name,followers_count,follows_count,media_count,profile_picture_url"})
    if code == 200:
        _PROFILE.update(at=time.time(), body=body)
    return body if code == 200 else {}


async def _day_from_api(http, api, auth, day: datetime) -> dict:
    since, until = int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
    code, body = await _get(http, f"{api}/me/insights", auth, {
        "metric": ",".join(DAY_METRICS), "period": "day", "metric_type": "total_value", "since": since, "until": until})
    if code != 200:
        return {"_error": (body.get("error") or {}).get("message", str(code))}
    return {m["name"]: (m.get("total_value") or {}).get("value") for m in body.get("data", [])}


async def new_followers_series(http, api, auth, con):
    """Store Meta's daily new-follower counts (one call covers the last 30 days)."""
    now = int(time.time())
    code, body = await _get(http, f"{api}/me/insights", auth, {
        "metric": "follower_count", "period": "day", "since": now - 29 * 86400, "until": now})
    if code != 200:
        return {}
    out = {}
    for m in body.get("data", []):
        for v in m.get("values", []):
            # end_time is the end of Meta's day; the counted day is the one before it.
            end = datetime.strptime(v["end_time"][:10], "%Y-%m-%d")
            day = end - timedelta(days=1)
            val = v.get("value")
            if not val and (datetime.now().date() - day.date()).days < PENDING_DAYS:
                val = None  # not counted yet, not a real zero
            out[day.strftime("%Y-%m-%d")] = val
    return out


async def days(http, api, auth, con, first: datetime, last: datetime) -> dict:
    """{'YYYY-MM-DD': metrics} for every day from first to last (inclusive)."""
    ensure_tables(con)
    wanted = []
    d = first
    while d <= last:
        wanted.append(d)
        d += timedelta(days=1)
    cached = {r[0]: (json.loads(r[1]), r[2], r[3]) for r in con.execute(
        "select day, data, final, ts from ig_day where day >= ? and day <= ?", (key(first), key(last)))}
    now = time.time()
    tkey = key(today())

    def stale(d):
        k = key(d)
        if k not in cached:
            return True
        if cached[k][1]:
            return False
        # Today changes all the time; past days only settle late counts, the nightly cron covers them.
        return now - cached[k][2] > (900 if k == tkey else 6 * 3600)

    todo = [d for d in wanted if stale(d)]
    sem = asyncio.Semaphore(8)

    async def one(d):
        async with sem:
            return d, await _day_from_api(http, api, auth, d)

    need_series = any(key(d) != tkey for d in todo)  # Meta's series never has today
    results, series = await asyncio.gather(
        asyncio.gather(*(one(d) for d in todo)) if todo else asyncio.sleep(0, []),
        new_followers_series(http, api, auth, con) if need_series else asyncio.sleep(0, {}))
    for d, data in results:
        if "_error" in data:
            continue
        old = cached.get(key(d), ({}, 0, 0))[0]
        data["new_followers"] = series.get(key(d), old.get("new_followers"))
        final = 1 if now - (d + timedelta(days=1)).timestamp() > FINAL_AFTER and data["new_followers"] is not None else 0
        con.execute("insert into ig_day values (?, ?, ?, ?) on conflict (day) do update set data = excluded.data,"
                    " final = excluded.final, ts = excluded.ts", (key(d), json.dumps(data), final, int(now)))
        cached[key(d)] = (data, final, now)
    out = {key(d): dict(cached.get(key(d), ({}, 0, 0))[0]) for d in wanted}
    for k, v in out.items():  # rows cached before Meta finished counting
        if not v.get("new_followers") and (today() - datetime.strptime(k, "%Y-%m-%d").replace(tzinfo=TZ)).days < PENDING_DAYS:
            v["new_followers"] = None
    return out


def snapshot(con, followers, media):
    ensure_tables(con)
    con.execute("insert into daily values (?, ?, ?, ?) on conflict (day) do update set followers = excluded.followers,"
                " media = excluded.media, ts = excluded.ts", (key(today()), followers, media, int(time.time())))


def followers_on(con, day: str):
    ensure_tables(con)
    row = con.execute("select followers from daily where day = ?", (day,)).fetchone()
    return row[0] if row else None


async def media(http, api, auth, con, first: datetime, last: datetime) -> list:
    """Posts and reels published in the range, newest first, each with its own insights."""
    ensure_tables(con)
    start, end = first.timestamp(), (last + timedelta(days=1)).timestamp()
    posts, after = [], None
    for _ in range(6):  # up to 300 posts back
        params = {"fields": "id,timestamp,media_product_type,media_type,like_count,comments_count,permalink,caption,"
                            "thumbnail_url,media_url", "limit": 50}
        if after:
            params["after"] = after
        code, body = await _get(http, f"{api}/me/media", auth, params)
        if code != 200:
            break
        older = False
        for m in body.get("data", []):
            ts = datetime.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            m["ts"] = ts
            if ts < start:
                older = True
            elif ts < end:
                posts.append(m)
        after = (body.get("paging") or {}).get("cursors", {}).get("after")
        if older or not after or not (body.get("paging") or {}).get("next"):
            break
    cached = {r[0]: (json.loads(r[1]), r[2]) for r in con.execute("select id, data, ts from ig_media")} if posts else {}
    now = time.time()
    sem = asyncio.Semaphore(8)

    async def stats(m):
        hit = cached.get(m["id"])
        if hit and (now - hit[1] < MEDIA_FRESH or now - m["ts"] > 14 * 86400 and now - hit[1] < 86400):
            return hit[0]
        async with sem:
            code, body = await _get(http, f"{api}/{m['id']}/insights", auth,
                                    {"metric": "reach,views,saved,shares,total_interactions"})
        data = {x["name"]: (x.get("values") or [{}])[0].get("value") for x in body.get("data", [])} if code == 200 else {}
        if data:
            con.execute("insert into ig_media values (?, ?, ?) on conflict (id) do update set data = excluded.data,"
                        " ts = excluded.ts", (m["id"], json.dumps(data), int(now)))
        return data or (hit[0] if hit else {})

    insights = await asyncio.gather(*(stats(m) for m in posts)) if posts else []
    for m, ins in zip(posts, insights):
        m.update({k: v for k, v in ins.items() if v is not None})
    return posts


def direct_messages(con, since, until, skip=()) -> int:
    rows = con.execute("select distinct igsid from events where event = 'msg' and ts >= ? and ts < ?", (since, until))
    return len({r[0] for r in rows} - set(skip))


def total(rows: dict, metric: str):
    vals = [r.get(metric) for r in rows.values() if r.get(metric) is not None]
    return sum(vals) if vals else None


_RECENT_FU: dict = {}


async def follow_stats(http, api, auth, con, day: datetime, cache: dict | None = None):
    """(follows, unfollows) for one Astana day from Instagram's «follows_and_unfollows», or None while not counted.
    Finished counts are kept in kv so each day is asked once."""
    import json as _json
    k = f"fu:{key(day)}"
    row = (cache.get(k),) if cache is not None else con.execute("select v from kv where k = ?", (k,)).fetchone()
    if row and row[0]:
        v = _json.loads(row[0])
        return tuple(v) if v else None
    hit = _RECENT_FU.get(k)
    if hit and time.time() - hit[0] < 1800:  # the last days are re-asked at most every 30 minutes
        return hit[1]
    code, body = await _get(http, f"{api}/me/insights", auth, {
        "metric": "follows_and_unfollows", "period": "day", "metric_type": "total_value", "breakdown": "follow_type",
        "since": int(day.timestamp()), "until": int((day + timedelta(days=1)).timestamp())})
    if code != 200:
        return None
    res = {}
    for m in body.get("data", []):
        for b in (m.get("total_value") or {}).get("breakdowns", []):
            for r in b.get("results", []):
                res[(r.get("dimension_values") or [""])[0]] = r.get("value") or 0
    if not res:
        _RECENT_FU[k] = (time.time(), None)
        return None  # not counted yet
    out = (res.get("FOLLOWER", 0), res.get("NON_FOLLOWER", 0))
    _RECENT_FU[k] = (time.time(), out)
    if (today() - day).days >= 3:  # recent days may still change
        con.execute("insert into kv values (?, ?, ?) on conflict (k) do update set v = excluded.v, ts = excluded.ts",
                    (k, _json.dumps(out), int(time.time())))
    return out
