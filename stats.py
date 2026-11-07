"""Stats page for the Instagram bot: KPI tiles, funnel, daily chart, popular trainings.

Counts are unique people (Instagram user ids), not events, so one parent
tapping «Тексеру» five times is still one person. Light theme by default,
a violet dark theme behind the sun/moon toggle (remembered per browser).
"""
import html
import json
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))  # Astana (all of Kazakhstan is UTC+5)
TOPICS = [("all", "Все"), ("math", "Математика"), ("english", "Ағылшын"), ("saka", "Алтын сақа")]
KIND_NAMES = {"quarter": "Тоқсандық", "mega": "Мега қайталау", "altyn_saka": "Алтын сақа", "english": "Ағылшын"}
KIND_TOPIC = {"quarter": "Математика", "mega": "Математика", "altyn_saka": "Алтын сақа", "english": "Ағылшын"}
PERIODS = [(1, "Сегодня"), (7, "7 дней"), (30, "30 дней"), (0, "Всё время")]
EVENTS = ("start", "gate", "subscribed", "already_follower", "follow_unknown", "links", "click", "repeat_ignored")


def day_start(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def period_bounds(days: int):
    """(since, prev_since) as unix ts; prev is the same-length window before."""
    if days <= 0:
        return 0, None
    today = day_start(datetime.now(TZ))
    since = today - timedelta(days=days - 1)
    return int(since.timestamp()), int((since - timedelta(days=days)).timestamp())


def people(rows, event, topic=None, pred=None) -> int:
    return len({r[1] for r in rows if r[2] == event and (topic in (None, "all") or r[3] == topic)
                and (pred is None or pred(r))})


def funnel_for(rows, topic) -> dict:
    f = {e: people(rows, e, topic) for e in EVENTS}
    f["passed"] = f["subscribed"] + f["already_follower"] + f["follow_unknown"]
    return f


def pct(a: int, b: int):
    return round(a * 100 / b) if b else None


def choice_name(detail: str) -> str:
    kind, _, rest = (detail or "").partition(":")
    if kind == "english":
        return f"English {rest}"
    return f"{KIND_NAMES.get(kind, kind)} · {rest} сынып"


def trend(cur: int, prev) -> str:
    """Delta chip vs the previous window. Icon + words, never color alone."""
    if prev is None:
        return '<span class="delta flat">за всё время</span>'
    if prev == 0:
        return ('<span class="delta flat">● нет данных за прошлый период</span>' if cur == 0
                else '<span class="delta up">▲ новое</span>')
    d = round((cur - prev) * 100 / prev)
    if d == 0:
        return '<span class="delta flat">● как в прошлом периоде</span>'
    cls, icon = ("up", "▲") if d > 0 else ("down", "▼")
    return f'<span class="delta {cls}">{icon} {abs(d)}% к прошлому периоду</span>'


# Lucide icons (ISC licence), inlined: 24px grid, 1.75 stroke, currentColor.
ICONS = {
    "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                 '<path d="M19 8v6"/><path d="M22 11h-6"/>',
    "click": '<path d="M14 4.1 12 6"/><path d="m5.1 8-2.9-.8"/><path d="m6 12-1.9 2"/><path d="M7.2 2.2 8 5.1"/>'
             '<path d="M9.04 9.69a.5.5 0 0 1 .65-.65l11 4.5a.5.5 0 0 1-.07.95l-4.35 1.04a1 1 0 0 0-.74.74l-1.04 4.35'
             'a.5.5 0 0 1-.95.07z"/>',
    "link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8'
            'a2 2 0 0 1 2-2h6"/>',
}


# Duotone layer: the same shapes filled at low opacity under the outline.
DUO = {
    "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/>',
    "user-plus": '<circle cx="9" cy="7" r="4"/><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2z"/>',
    "click": '<path d="M9.04 9.69a.5.5 0 0 1 .65-.65l11 4.5a.5.5 0 0 1-.07.95l-4.35 1.04a1 1 0 0 0-.74.74l-1.04 4.35'
             'a.5.5 0 0 1-.95.07z"/>',
    "link": '<rect x="3" y="6" width="15" height="15" rx="2"/>',
}


def icon(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<g fill="currentColor" stroke="none" opacity=".22">{DUO[name]}</g>{ICONS[name]}</svg>')


def kpi(i: int, ico: str, label: str, value, suffix: str, sub: str, delta: str, accent=False) -> str:
    shown = "—" if value is None else f'<span data-count="{value}">0</span>{suffix}'
    return (f'<article class="kpi rise{" kpi-accent" if accent else ""}" style="--i:{i}">'
            f'<div class="kpi-top"><h3>{label}</h3><span class="kpi-ico">{icon(ico)}</span></div>'
            f'<p class="kpi-value">{shown}</p><p class="kpi-sub">{sub}</p>{delta}</article>')


EMPTY_BC = '<section class="card"><p class="empty">Рассылок пока не было.</p></section>'
CAMPAIGN_NAMES = {"registered_check": "«Тіркелдіңіз бе?»", "pick_topic": "«Тренинг таңдауға көмектесейік пе?»",
                  "welcome": "«Сәлеметсіз бе! … 3 сұрақ»"}
ANSWERS = [("fu_help", "Көмек керек", "bad"), ("fu_notyet", "Әлі тіркелмедім", "warn"), ("fu_done", "Тіркелдім", "good")]
PICK_NAMES = [("math", "Математика"), ("english", "Ағылшын"), ("saka", "Алтын сақа")]


SHORT_MON = ["ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН", "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК"]
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
KIND_LABEL = {"registered_check": "проверка регистрации", "pick_topic": "выбор направления",
              "welcome": "сбор контактов: город, класс, номер"}
CHEVRON = ('<svg class="chev" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>')


LEAD_TOPICS = {"math": "Математика", "english": "Ағылшын", "saka": "Алтын сақа"}
SHEET_ICON = ('<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/>'
              '<path d="M3 9h18M3 15h18M9 3v18"/></svg>')


def leads_html(con, skip: list, sheet_url: str = "") -> tuple[str, int]:
    """«Лидтер» tab: the same rows that go to Google Sheets, newest first, with a search box."""
    con.execute("create table if not exists leads (igsid text primary key, username text, topic text, city text,"
                " grade text, phone text, texts text, first_ts bigint, updated_ts bigint, thanked integer default 0,"
                " synced integer default 0)")
    rows = [r for r in con.execute("select igsid, username, topic, city, grade, phone, texts, first_ts, thanked, synced"
                                   " from leads order by first_ts desc") if r[0] not in set(skip)]
    welcomed = len(rows)
    answered = sum(1 for r in rows if r[6])
    phones = sum(1 for r in rows if r[5])
    tiles = "".join(f'<div class="bc-tile"><span>{t}</span><b>{v}</b></div>' for t, v in (
        ("Сәлемдесу мәтінін алды", welcomed), ("Жауап берді", f"{answered} · {pct(answered, welcomed) or 0}%"),
        ("Нөмір қалдырды", f"{phones} · {pct(phones, welcomed) or 0}%"),
        ("Кестеге түспегені", sum(1 for r in rows if not r[9])),
    ))
    esc = html.escape
    body = []
    for igsid, user, topic, city, grade, phone, texts_, first_ts, thanked, synced in rows:
        who = (f'<a href="https://instagram.com/{esc(user)}" target="_blank" rel="noopener">@{esc(user)}</a>'
               if user else f'<span class="muted-id">…{igsid[-4:]}</span>')
        phone_cell = esc(phone) if phone else '<span class="muted-id">—</span>'
        texts_cell = esc(texts_) if texts_ else '<span class="muted-id">жауап жоқ</span>'
        thanks_cell = '<span class="chip good">✓</span>' if thanked else ""
        body.append(
            f'<tr><td class="nowrap">{datetime.fromtimestamp(first_ts, TZ):%d.%m %H:%M}</td><td>{who}</td>'
            f'<td>{esc(LEAD_TOPICS.get(topic or "", ""))}</td><td>{esc(city or "")}</td><td>{esc(grade or "")}</td>'
            f'<td class="nowrap">{phone_cell}</td><td class="answers">{texts_cell}</td><td>{thanks_cell}</td></tr>')
    table = (f'<div class="tbl leads-tbl"><table id="leadsTable"><thead><tr><th>Уақыты</th><th>Instagram</th><th>Бағыт</th>'
             f'<th>Қала</th><th>Сынып</th><th>Телефон</th><th>Жауаптары</th><th>Рақмет</th></tr></thead>'
             f'<tbody>{"".join(body)}</tbody></table></div>' if body else
             '<p class="empty">Әзірге ешкім сәлемдесу мәтінін алған жоқ.</p>')
    link = (f'<a class="sheet-btn" href="{esc(sheet_url)}" target="_blank" rel="noopener">{SHEET_ICON}Google кестені ашу</a>'
            if sheet_url else "")
    return (f"""<section class="card rise" style="--i:4">
  <div class="card-head"><div><h2>Лидтер</h2><div class="hint">сәлемдесу мәтінінің 3 сұрағына жауаптар · Google кестеге де осылар түседі</div></div>{link}</div>
  <div class="bc-tiles">{tiles}</div>
  <input type="search" id="leadSearch" class="lead-search" placeholder="Іздеу: ник, қала, телефон…" aria-label="Лидтерді іздеу">
  {table}
</section>""", welcomed)


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def broadcasts_html(con, skip: list) -> str:
    """Broadcasts grouped by send day (latest day open, older days folded); inside a day
    each broadcast is a compact row with a big date/time badge that expands to details."""
    con.execute("create table if not exists profiles (igsid text primary key, username text, ts bigint)")
    rows = con.execute("select substr(event, 9), min(ts) from events where event like 'fu_sent:%'"
                       " and event not like 'fu_sent:test_%' group by event order by min(ts) desc").fetchall()
    if not rows:
        return ""
    testers = {r[0] for r in con.execute("select distinct igsid from events where event like 'fu_sent:test_%'")} | set(skip)
    days: dict = {}
    for camp, ts in rows:
        days.setdefault(datetime.fromtimestamp(ts, TZ).date(), []).append(campaign_data(con, camp, testers, ts))
    today = datetime.now(TZ).date()
    out = []
    for gi, (d, items) in enumerate(days.items()):
        name = "Сегодня" if d == today else "Вчера" if d == today - timedelta(days=1) else WEEKDAYS[d.weekday()].capitalize()
        sent, urgent = sum(c["sent"] for c in items), sum(c["urgent"] for c in items)
        alert = (f'<span class="live bad"><span class="beacon" aria-hidden="true"></span>{urgent} ждут менеджера</span>'
                 if urgent else "")
        out.append(f"""<details class="bc-day rise" style="--i:{4 + gi}"{" open" if gi == 0 else ""}>
  <summary><span class="day-badge"><b>{d.day}</b><small>{SHORT_MON[d.month - 1]}</small></span>
    <span class="day-title"><b>{name}</b><small>{d:%d.%m.%Y} · {len(items)} {plural(len(items), "рассылка", "рассылки", "рассылок")} · {sent} {plural(sent, "получатель", "получателя", "получателей")}</small></span>
    {alert}{CHEVRON}</summary>
  <div class="day-body">{"".join(card_html(c) for c in items)}</div>
</details>""")
    return "".join(out)


def card_html(c: dict) -> str:
    """Compact row: time badge, name, key numbers; click expands the full breakdown."""
    t = datetime.fromtimestamp(c["ts"], TZ)
    urgent = (f'<span class="live bad"><span class="beacon" aria-hidden="true"></span>Срочно: {c["urgent"]}</span>'
              if c["urgent"] else "")
    return f"""<details class="bc-card">
  <summary><span class="time-badge">{t.day} {SHORT_MON[t.month - 1]} · {t:%H:%M}</span>
    <span class="bc-name"><b>{html.escape(c["title"])}</b><small>{c["kind_label"]}</small></span>
    <span class="bc-mini"><span><b>{c["sent"]}</b><small>отправлено</small></span>
      <span><b>{c["key_value"]}</b><small>{c["key_label"]}</small></span></span>
    {urgent}{CHEVRON}</summary>
  <div class="bc-body">{c["body"]}</div>
</details>"""


def campaign_data(con, camp: str, testers: set, started: int) -> dict:
    recipients = {r[0] for r in con.execute("select distinct igsid from events where event = ?", (f"fu_sent:{camp}",))} - testers
    failed = {r[0] for r in con.execute("select distinct igsid from events where event = ?", (f"fu_fail:{camp}",))} - testers
    kind = camp.split("@")[0]
    if "welcome" in camp:
        data = welcome_html(con, recipients, failed)
    elif "pick" in camp:
        data = pick_html(con, recipients, failed)
    else:
        data = registered_html(con, recipients, failed)
    return {**data, "title": CAMPAIGN_NAMES.get(kind, camp), "kind_label": KIND_LABEL.get(kind, ""), "ts": started,
            "sent": len(recipients)}


def welcome_html(con, recipients, failed) -> dict:
    """«Welcome questions» broadcast: who answered and who left a phone (names link to Instagram)."""
    con.execute("create table if not exists leads (igsid text primary key, username text, topic text, city text,"
                " grade text, phone text, texts text, first_ts bigint, updated_ts bigint, thanked integer default 0,"
                " synced integer default 0)")
    rows = {r[0]: r for r in con.execute("select igsid, username, city, grade, phone, texts from leads")}
    answered = [rows[i] for i in recipients if i in rows and rows[i][5]]
    phones = [r for r in answered if r[4]]
    tiles = "".join(f'<div class="bc-tile"><span>{t}</span><b>{v}</b></div>' for t, v in (
        ("Отправлено", len(recipients)), ("Ответили", f"{len(answered)} · {pct(len(answered), len(recipients)) or 0}%"),
        ("Оставили номер", f"{len(phones)} · {pct(len(phones), len(recipients)) or 0}%"), ("Ошибок отправки", len(failed))))
    items = "".join(
        f'<li><a href="https://instagram.com/{html.escape(u)}" target="_blank" rel="noopener">@{html.escape(u)}</a>'
        f'<time>{html.escape(" · ".join(x for x in (c, (g + " сынып") if g else "") if x))}</time></li>' if u else ""
        for _, u, c, g, p, t in phones)
    people = f'<ul class="who">{items}</ul>' if items else '<p class="empty">Пока никто не оставил номер.</p>'
    body = (f'<p class="bc-note">Приветствие с тремя вопросами · ответы — во вкладке «Лидтер» и в Google Таблице</p>'
            f'<div class="bc-tiles">{tiles}</div><div class="bc-col good"><h3>Оставили номер <em>{len(phones)}</em></h3>{people}</div>')
    return {"body": body, "urgent": 0, "key_label": "оставили номер",
            "key_value": f"{len(phones)} · {pct(len(phones), len(recipients)) or 0}%"}


def pick_html(con, recipients, failed) -> dict:
    """«Choose a direction» broadcast: which direction people tapped and how far they got."""
    picks = {}
    # Latest tap per person wins (ordered by time, later rows overwrite).
    for igsid, topic in con.execute("select igsid, topic from events where event = 'fu_pick' order by ts"):
        if igsid in recipients:
            picks[igsid] = topic
    got_links = {r[0] for r in con.execute("select distinct igsid from events where event = 'links'")} & set(picks)
    tiles = "".join(f'<div class="bc-tile"><span>{t}</span><b>{v}</b></div>' for t, v in (
        ("Отправлено", len(recipients)), ("Выбрали направление", f"{len(picks)} · {pct(len(picks), len(recipients)) or 0}%"),
        ("Дошли до ссылок", len(got_links)), ("Ошибок отправки", len(failed))))
    top = max([sum(1 for t in picks.values() if t == k) for k, _ in PICK_NAMES] + [1])
    chosen = sorted(((sum(1 for t in picks.values() if t == k), n) for k, n in PICK_NAMES), reverse=True)
    bars = "".join(
        f'<li class="rank"><span class="rank-n">{j}</span><div class="rank-body"><div class="rank-head"><b>{n}</b></div>'
        f'<div class="bar"><i data-w="{max(c * 100 / top, 3 if c else 0):.1f}"></i></div></div>'
        f'<span class="chip good">{c} чел.</span></li>'
        for j, (c, n) in enumerate(chosen, 1))
    body = (f'<p class="bc-note">Тем, кто не дошёл до ссылок · тестовые аккаунты не учитываются</p>'
            f'<div class="bc-tiles">{tiles}</div><ol class="ranks neon">{bars}</ol>')
    return {"body": body, "urgent": 0, "key_label": "выбрали направление",
            "key_value": f"{len(picks)} · {pct(len(picks), len(recipients)) or 0}%"}


def registered_html(con, recipients, failed) -> dict:
    """«Тіркелдіңіз бе?» broadcast: answers and who to contact by name."""
    latest = {}  # igsid -> (ts, answer): a person's last tap is their answer
    for igsid, ev, ts in con.execute("select igsid, event, ts from events where event in ('fu_done','fu_help','fu_notyet')"
                                      " order by ts"):
        if igsid in recipients and ts >= latest.get(igsid, (0, ""))[0]:
            latest[igsid] = (ts, ev)
    names = dict(con.execute("select igsid, username from profiles"))
    clicks = len({r[0] for r in con.execute("select distinct igsid from events where event = 'click' and topic = 'followup'")}
                 & recipients)
    counts = {ev: sum(1 for _, a in latest.values() if a == ev) for ev, _, _ in ANSWERS}
    answered = len(latest)

    def who(ev):
        people = sorted(((ts, i) for i, (ts, a) in latest.items() if a == ev), reverse=True)
        if not people:
            return '<p class="empty">Пока никого.</p>'
        items = []
        for ts, i in people:
            n = names.get(i)
            label = (f'<a href="https://instagram.com/{html.escape(n)}" target="_blank" rel="noopener">@{html.escape(n)}</a>'
                     if n else f'<span class="muted-id">…{i[-4:]}</span>')
            items.append(f'<li>{label}<time>{datetime.fromtimestamp(ts, TZ):%d.%m %H:%M}</time></li>')
        return f'<ul class="who">{"".join(items)}</ul>'

    tiles = "".join(f'<div class="bc-tile"><span>{t}</span><b>{v}</b></div>' for t, v in (
        ("Отправлено", len(recipients)), ("Ответили", f"{answered} · {pct(answered, len(recipients)) or 0}%"),
        ("Нажали «Тіркелу»", clicks), ("Ошибок отправки", len(failed))))
    urgent = counts["fu_help"]
    pulse = '<span class="beacon" aria-hidden="true"></span>'
    note = '<p class="bc-note">Бот пообещал, что напишет менеджер — ответьте в Директе</p>'
    cols = "".join(
        '<div class="bc-col ' + cls + '"><h3>' + (pulse if ev == "fu_help" and urgent else "")
        + f'{title} <em>{counts[ev]}</em></h3>' + (note if ev == "fu_help" else "") + who(ev) + "</div>"
        for ev, title, cls in ANSWERS)
    body = (f'<p class="bc-note">Тем, кто получил ссылки на тренинг · тестовые аккаунты не учитываются</p>'
            f'<div class="bc-tiles">{tiles}</div><div class="bc-cols">{cols}</div>')
    return {"body": body, "urgent": urgent, "key_label": "ответили",
            "key_value": f"{answered} · {pct(answered, len(recipients)) or 0}%"}


MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря"]
DOW_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
CAL_SVG = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/>'
           '<path d="M16 2v4M8 2v4M3 10h18"/></svg>')
CHEV = {"‹": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>',
        "›": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>'}


def relative_day(d: datetime, today: datetime) -> str:
    n = (today - d).days
    return "сегодня" if n == 0 else "вчера" if n == 1 else f"{n} дня назад" if n < 5 else f"{n} дней назад"


def day_pill(day, shown: datetime, today: datetime, min_day: datetime, period_label: str) -> str:
    """Floating pill: glowing calendar button, arrows, date with a relative caption,
    and «Сегодня» / «Вчера» quick picks. Links work without JS; JS adds the popover."""
    def nav(d, sym, label):
        if min_day <= d <= today:
            return f'<a class="dp-nav" href="?date={d:%Y-%m-%d}" aria-label="{label}">{CHEV[sym]}</a>'
        return f'<span class="dp-nav off" aria-hidden="true">{CHEV[sym]}</span>'
    yesterday = today - timedelta(days=1)
    chip = lambda d, name: (f'<a class="dp-chip" href="?date={d:%Y-%m-%d}" aria-pressed="{"true" if day and d == day else "false"}">{name}</a>'
                            if d >= min_day else "")
    caption = relative_day(shown, today) if day else f"период: {period_label}"
    return (f'<div class="dp{" on" if day else ""}">'
            f'<button type="button" class="dp-cal" id="dpOpen" aria-haspopup="dialog" aria-expanded="false" '
            f'aria-label="Открыть календарь">{CAL_SVG}</button>'
            f'{nav(shown - timedelta(days=1), "‹", "Предыдущий день")}'
            f'<span class="dp-label"><b>{DOW_SHORT[shown.weekday()]}, {shown.day} {MONTHS_GEN[shown.month - 1]}</b>'
            f'<small>{html.escape(caption)}</small></span>'
            f'{nav(shown + timedelta(days=1), "›", "Следующий день")}'
            f'<span class="dp-quick">{chip(today, "Сегодня")}{chip(yesterday, "Вчера")}</span></div>')


def parse_day(date: str | None):
    """«2026-09-27» -> start of that day in Astana time, or None if absent/invalid/future."""
    if not date:
        return None
    try:
        d = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=TZ)
    except ValueError:
        return None
    return d if d <= day_start(datetime.now(TZ)) else None


def render(con, days: int, texts: dict, exclude: str = "", bot_ok: bool = True, date: str | None = None,
           sheet_url: str = "") -> str:
    day = parse_day(date)
    today = day_start(datetime.now(TZ))
    if day:  # one calendar day, compared with the day before
        since, until, prev_since = int(day.timestamp()), int((day + timedelta(days=1)).timestamp()), \
            int((day - timedelta(days=1)).timestamp())
    else:
        since, prev_since = period_bounds(days)
        until = int((today + timedelta(days=1)).timestamp())
    skip = [x.strip() for x in exclude.split(",") if x.strip()]
    lower = prev_since if prev_since is not None else since
    where = "ts >= ? and ts < ?" + (f" and igsid not in ({','.join('?' * len(skip))})" if skip else "")
    all_rows = con.execute(f"select ts, igsid, event, topic, detail from events where {where}",
                           [lower, until, *skip]).fetchall()
    rows = [r for r in all_rows if r[0] >= since]
    prev = [r for r in all_rows if prev_since is not None and r[0] < since]
    has_prev = prev_since is not None

    # ---- KPI tiles
    cur_f, prev_f = funnel_for(rows, "all"), funnel_for(prev, "all")
    clicks_total = sum(1 for r in rows if r[2] == "click")
    prev_clicks_total = sum(1 for r in prev if r[2] == "click")
    sub_pct, conv = pct(cur_f["subscribed"], cur_f["gate"]), pct(cur_f["click"], cur_f["start"])
    tiles = "".join([
        kpi(0, "megaphone", "Лиды из рекламы", cur_f["start"], "", "написали с ключевым словом",
            trend(cur_f["start"], prev_f["start"] if has_prev else None)),
        kpi(1, "user-plus", "Новые подписчики", cur_f["subscribed"], "",
            f"{sub_pct}% из тех, кого бот попросил подписаться" if sub_pct is not None
            else "бот ещё никого не просил подписаться",
            trend(cur_f["subscribed"], prev_f["subscribed"] if has_prev else None)),
        kpi(2, "click", "Конверсия в клик", conv, "%", f"{cur_f['click']} из {cur_f['start']} нажали на тренинг",
            trend(cur_f["click"], prev_f["click"] if has_prev else None), accent=True),
        kpi(3, "link", "Клики по ссылкам", clicks_total, "", f"{cur_f['click']} уникальных людей",
            trend(clicks_total, prev_clicks_total if has_prev else None)),
    ])

    # ---- funnel data per topic (drawn client-side so the topic filter is instant)
    funnels = {t: funnel_for(rows, t) for t, _ in TOPICS}

    # ---- trainings: popularity bar + conversion chip
    details = {r[4] for r in rows if r[2] == "links" and r[4]}
    ranked = []
    for d in details:
        sent = people(rows, "links", pred=lambda r, d=d: r[4] == d)
        clicked = people(rows, "click", pred=lambda r, d=d: (r[4] or "").split("|")[0] == d)
        ranked.append((sent, clicked, d))
    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
    top = ranked[0][0] if ranked else 1
    items = []
    for i, (sent, clicked, d) in enumerate(ranked, 1):
        c = pct(clicked, sent) or 0
        state = ("good", "✓ высокая") if c >= 50 else ("warn", "◐ средняя") if c >= 20 else ("bad", "✕ низкая")
        pulse = ' <span class="beacon" aria-hidden="true"></span>' if state[0] == "bad" else ""
        items.append(f"""<li class="rank rise" style="--i:{min(i, 12)}">
  <span class="rank-n">{i}</span>
  <div class="rank-body">
    <div class="rank-head"><b>{html.escape(choice_name(d))}</b><span class="tag">{KIND_TOPIC.get(d.split(':')[0], '')}</span></div>
    <div class="bar" role="img" aria-label="Получили ссылки: {sent}"><i data-w="{max(sent * 100 / top, 3):.1f}"></i></div>
    <div class="rank-meta">{sent} получили ссылки · {clicked} нажали</div>
  </div>
  <span class="chip {state[0]}" title="Конверсия в клик">{pulse}{c}% · {state[1]}</span>
</li>""")
    trainings = (f'<ol class="ranks">{"".join(items)}</ol>' if items else
                 '<p class="empty">За этот период никто ещё не получил ссылки.</p>')

    # ---- chart series: by hour for a single day, otherwise by day (zeros included)
    hourly = bool(day) or days == 1
    buckets = {}
    if hourly:
        for ts, igsid, event, topic, detail in rows:
            buckets.setdefault(datetime.fromtimestamp(ts, TZ).hour, {}).setdefault(event, set()).add(igsid)
        last_hour = 23 if day else datetime.now(TZ).hour
        series = [{"d": f"{h:02d}:00", "start": len(buckets.get(h, {}).get("start", ())),
                   "click": len(buckets.get(h, {}).get("click", ())), "links": len(buckets.get(h, {}).get("links", ()))}
                  for h in range(last_hour + 1)]
    else:
        first = min((r[0] for r in rows), default=None)
        begin = day_start(datetime.fromtimestamp(since, TZ)) if days > 0 else \
            (day_start(datetime.fromtimestamp(first, TZ)) if first else today)
        for ts, igsid, event, topic, detail in rows:
            buckets.setdefault(datetime.fromtimestamp(ts, TZ).date(), {}).setdefault(event, set()).add(igsid)
        series, d = [], begin
        while d <= today:
            b = buckets.get(d.date(), {})
            series.append({"d": d.strftime("%d.%m"), "start": len(b.get("start", ())),
                           "click": len(b.get("click", ())), "links": len(b.get("links", ()))})
            d += timedelta(days=1)

    tabs ="".join(f'<a href="?days={p}" role="tab" aria-selected="{"true" if p == days and not day else "false"}">{n}</a>'
                   for p, n in PERIODS)

    # ---- day picker («floating pill»): calendar button, arrows, date + relative label, quick picks
    first_ever = con.execute("select min(ts) from events").fetchone()[0]
    min_day = day_start(datetime.fromtimestamp(first_ever, TZ)) if first_ever else today
    shown = day or today
    period_label = (f"день {day:%d.%m.%Y} · сравнение с предыдущим днём" if day
                    else dict(PERIODS).get(days, "").lower())
    picker = day_pill(day, shown, today, min_day, period_label)
    data_days = sorted({datetime.fromtimestamp(r[0], TZ).strftime("%Y-%m-%d")
                        for r in con.execute("select distinct ts / 3600 * 3600 from events")})
    day_info = {"min": f"{min_day:%Y-%m-%d}", "max": f"{today:%Y-%m-%d}",
                "sel": f"{day:%Y-%m-%d}" if day else None, "has": data_days}
    data = json.dumps({"funnels": funnels, "series": series, "hourly": hourly, "day": day_info}, ensure_ascii=False)
    chart_title, chart_hint = (("Динамика по часам", "уникальные люди в час · наведите на график") if hourly
                               else ("Динамика по дням", "уникальные люди в день · наведите на график"))
    topic_tabs = "".join(f'<button type="button" data-topic="{t}" aria-pressed="{"true" if t == "all" else "false"}">{n}</button>'
                         for t, n in TOPICS)
    status = ('<span class="live ok"><span class="beacon" aria-hidden="true"></span>Бот работает</span>' if bot_ok else
              '<span class="live bad"><span class="beacon" aria-hidden="true"></span>Внимание: бот не на связи</span>')
    now = datetime.now(TZ).strftime("%d.%m.%Y, %H:%M")
    bc = broadcasts_html(con, skip)
    leads_block, leads_count = leads_html(con, skip, sheet_url)
    return (PAGE.replace("{{LEADS}}", leads_block).replace("{{LEADS_COUNT}}", str(leads_count)).replace("{{TABS}}", tabs).replace("{{PICKER}}", picker).replace("{{PERIOD}}", html.escape(period_label))
            .replace("{{CHART_TITLE}}", chart_title).replace("{{CHART_HINT}}", chart_hint)
            .replace("{{NOW}}", now).replace("{{KPIS}}", tiles)
            .replace("{{STATUS}}", status).replace("{{TOPIC_TABS}}", topic_tabs)
            .replace("{{TRAININGS}}", trainings).replace("{{BROADCASTS}}", bc or EMPTY_BC)
            .replace("{{BC_COUNT}}", str(bc.count('class="bc-card"')))
            .replace("{{DATA}}", data.replace("</", "<\\/")))


PAGE = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Статистика Instagram-бота</title>
<script>try{if(localStorage.getItem("zd-theme")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}</script>
<style>
:root{
  color-scheme:light;
  --page:#F6F5FC; --card:#FFFFFF; --card-2:#FAF9FF; --line:#ECE9F7; --line-2:#DCD6F2;
  --ink:#17132B; --ink-2:#4B4668; --muted:#8C87A6; --grid:#EEEBF7; --axis:#D8D3EC;
  --brand:#6D4AE8; --brand-2:#9A7BFF; --brand-soft:#F0ECFF; --brand-glow:rgba(109,74,232,.35);
  --s-leads:#6D4AE8; --s-clicks:#12A374;
  --good:#0E9F4F; --good-bg:#E6F7EE; --warn:#A86A00; --warn-bg:#FFF4DC; --bad:#D9480F; --bad-bg:#FDECE4;
  --shadow:0 1px 2px rgba(23,19,43,.04),0 8px 24px rgba(76,56,160,.08);
  --shadow-up:0 2px 4px rgba(23,19,43,.05),0 18px 40px rgba(76,56,160,.16);
  --skel:#EEEBF7; --skel-hi:#F8F7FD; --tip:#FFFFFF;
  --glow-a:rgba(154,123,255,.28); --glow-b:rgba(18,163,116,.14);
  --soft-shadow:rgba(108,92,231,.14); --soft-shadow-up:rgba(108,92,231,.26);
  --kb-1:rgba(109,74,232,.30); --kb-2:rgba(154,123,255,.14);
  --glass-1:rgba(109,74,232,.12); --glass-2:rgba(154,123,255,.03); --glass-line:rgba(109,74,232,.16);
  --drop-glow:rgba(217,72,15,.30);
  --glass-bar:rgba(255,255,255,.72); --seg-track:rgba(109,74,232,.07);
  --kpi-bg:linear-gradient(160deg,#FFFFFF 0%,#F7F4FF 100%);
  --kpi-inner:inset 0 1px 0 rgba(255,255,255,.9),inset 0 0 0 1px rgba(109,74,232,.06);
  --kpi-accent:linear-gradient(145deg,#8B5CF6 0%,#6D4AE8 45%,#4F2FD0 100%);
  --r:16px;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --page:#191430; --card:#231C40; --card-2:#2A2250; --line:#342B5C; --line-2:#44397A;
  --ink:#F5F2FF; --ink-2:#CFC8EE; --muted:#9D95C4; --grid:#30285A; --axis:#453A7C;
  --brand:#9580F2; --brand-2:#B7A6FF; --brand-soft:#2F2659; --brand-glow:rgba(149,128,242,.45);
  --s-leads:#9580F2; --s-clicks:#1FAE7E;
  --good:#4ADE80; --good-bg:rgba(34,197,94,.14); --warn:#FBBF24; --warn-bg:rgba(251,191,36,.12); --bad:#FB8A5C; --bad-bg:rgba(251,138,92,.13);
  --shadow:0 1px 2px rgba(0,0,0,.2),0 10px 30px rgba(8,4,24,.35);
  --shadow-up:0 2px 4px rgba(0,0,0,.25),0 22px 48px rgba(8,4,24,.55);
  --skel:#2E2654; --skel-hi:#3A3168; --tip:#2E2654;
  --glow-a:rgba(149,128,242,.30); --glow-b:rgba(31,174,126,.14);
  --soft-shadow:rgba(6,2,20,.55); --soft-shadow-up:rgba(6,2,20,.75);
  --kb-1:rgba(183,166,255,.40); --kb-2:rgba(149,128,242,.18);
  --glass-1:rgba(183,166,255,.16); --glass-2:rgba(149,128,242,.04); --glass-line:rgba(183,166,255,.22);
  --drop-glow:rgba(251,138,92,.28);
  --glass-bar:rgba(35,28,64,.62); --seg-track:rgba(0,0,0,.22);
  --kpi-bg:radial-gradient(120% 90% at 100% 0%,rgba(149,128,242,.20) 0%,transparent 55%),
           linear-gradient(160deg,#2B2255 0%,#1F1840 100%);
  --kpi-inner:inset 0 1px 0 rgba(255,255,255,.07),inset 0 0 40px rgba(149,128,242,.10);
  --kpi-accent:radial-gradient(120% 100% at 100% 0%,rgba(255,255,255,.28) 0%,transparent 50%),
               linear-gradient(145deg,#A78BFA 0%,#7C5CF0 40%,#5B3BDA 100%);
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--page);color:var(--ink);min-height:100vh;transition:background .35s,color .35s;position:relative;overflow-x:hidden}
body::before{content:"";position:fixed;inset:-20%;z-index:-1;pointer-events:none;
  background:radial-gradient(40% 35% at 85% 5%,var(--glow-a),transparent 70%),radial-gradient(35% 30% at 5% 25%,var(--glow-b),transparent 70%)}
main{max-width:1100px;margin:0 auto;padding:28px 16px 56px;display:grid;gap:20px}

/* ---------- header ---------- */
header{display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between}
.title{display:grid;gap:6px}
h1{font-size:clamp(22px,3vw,30px);margin:0;letter-spacing:-.02em;text-wrap:balance;
  background:linear-gradient(90deg,var(--ink),var(--brand));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--muted);font-size:0.8125rem;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
/* Toolbar: one glass bar holding the macOS-style segmented control, the compact
   day picker and the theme icon button. */
.tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:5px;border-radius:14px;
  background:var(--glass-bar);border:1px solid var(--glass-line);box-shadow:var(--shadow);
  backdrop-filter:blur(18px) saturate(1.4);-webkit-backdrop-filter:blur(18px) saturate(1.4)}
.seg{display:inline-flex;padding:2px;gap:0;border-radius:10px;background:var(--seg-track);position:relative}
.seg a,.seg button{appearance:none;border:0;background:transparent;color:var(--ink-2);font:500 0.8125rem/1 inherit;
  padding:8px 13px;border-radius:8px;text-decoration:none;cursor:pointer;white-space:nowrap;position:relative;
  transition:background .2s,color .2s,box-shadow .2s}
.seg a+a::before,.seg button+button::before{content:"";position:absolute;left:0;top:25%;height:50%;width:1px;background:var(--line-2);transition:opacity .2s}
.seg a:hover,.seg button:hover{color:var(--ink)}
.seg [aria-selected=true],.seg [aria-pressed=true]{color:#fff;font-weight:600;
  background:linear-gradient(180deg,var(--brand-2),var(--brand));
  box-shadow:0 1px 0 rgba(255,255,255,.25) inset,0 4px 14px -2px var(--brand-glow)}
.seg [aria-selected=true]::before,.seg [aria-selected=true]+a::before,
.seg [aria-pressed=true]::before,.seg [aria-pressed=true]+button::before{opacity:0}
.period{font-size:0.8125rem;color:var(--muted)} .period b{color:var(--ink);font-weight:600}
.tool-sep{width:1px;height:22px;background:var(--line-2);margin:0 2px}
/* Day picker: floating pill with a glowing calendar button and quick picks */
.dp{display:inline-flex;align-items:center;gap:4px;padding:3px 5px 3px 3px;border-radius:999px;background:var(--card);
  border:1px solid var(--line);box-shadow:0 8px 24px -12px var(--brand-glow);transition:box-shadow .2s,border-color .2s}
.dp.on{border-color:color-mix(in srgb,var(--brand) 55%,var(--line))}
.dp-cal{appearance:none;border:0;cursor:pointer;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;color:#fff;
  background:linear-gradient(135deg,var(--brand-2),var(--brand));box-shadow:0 0 0 3px var(--brand-soft),0 0 18px var(--brand-glow);
  transition:transform .2s,box-shadow .2s}
.dp-cal:hover,.dp-cal[aria-expanded="true"]{transform:scale(1.06);box-shadow:0 0 0 5px var(--brand-soft),0 0 26px var(--brand-glow)}
.dp-nav{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;color:var(--ink-2);text-decoration:none;transition:all .2s}
a.dp-nav:hover{background:var(--brand-soft);color:var(--brand)}
.dp-nav.off{opacity:.3}
.dp-label{display:grid;line-height:1.15;min-width:104px;padding:0 2px}
.dp-label b{font-size:0.8125rem;font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums}
.dp-label small{font-size:0.6875rem;color:var(--muted);white-space:nowrap}
.dp-quick{display:inline-flex;gap:4px;padding-left:6px;margin-left:2px;border-left:1px solid var(--line)}
.dp-chip{font-size:0.75rem;font-weight:600;padding:5px 10px;border-radius:999px;border:1px solid var(--line-2);color:var(--ink-2);
  text-decoration:none;transition:all .2s;white-space:nowrap}
.dp-chip:hover{border-color:var(--brand);color:var(--brand)}
.dp-chip[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:#fff;box-shadow:0 4px 12px -3px var(--brand-glow)}
/* calendar popover */
.cal-pop{position:absolute;z-index:30;width:296px;padding:14px;border-radius:16px;background:var(--tip);border:1px solid var(--line-2);
  box-shadow:0 24px 60px -18px rgba(20,12,50,.45);animation:popIn .18s cubic-bezier(.2,.8,.2,1)}
@keyframes popIn{from{opacity:0;transform:translateY(-6px) scale(.97)}to{opacity:1;transform:none}}
.cal-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cal-head b{font-size:0.875rem;font-weight:700;text-transform:capitalize}
.cal-head button{appearance:none;border:0;background:transparent;color:var(--ink-2);width:30px;height:30px;border-radius:8px;cursor:pointer;
  display:grid;place-items:center;transition:all .2s}
.cal-head button:hover:not(:disabled){background:var(--brand-soft);color:var(--brand)}
.cal-head button:disabled{opacity:.3;cursor:default}
.cal-dow,.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.cal-dow span{font-size:0.6875rem;color:var(--muted);text-align:center;font-weight:600;padding:4px 0}
.cal-grid button{appearance:none;border:0;background:transparent;color:var(--ink);height:36px;border-radius:10px;cursor:pointer;
  font:500 0.8125rem inherit;font-variant-numeric:tabular-nums;position:relative;transition:all .15s}
.cal-grid button:hover:not(:disabled){background:var(--brand-soft);color:var(--brand)}
.cal-grid button.out{opacity:.45}
.cal-grid button:disabled{color:var(--muted);opacity:.28;cursor:not-allowed}
.cal-grid button.has{font-weight:800}
.cal-grid button.today::after{content:"";position:absolute;left:50%;bottom:5px;width:4px;height:4px;margin-left:-2px;border-radius:50%;background:var(--brand)}
.cal-grid button.sel{background:linear-gradient(135deg,var(--brand-2),var(--brand));color:#fff;box-shadow:0 6px 16px -4px var(--brand-glow)}
.cal-grid button.sel::after{background:#fff}
.cal-foot{display:flex;gap:6px;margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
.cal-foot button{flex:1;appearance:none;border:1px solid var(--line-2);background:transparent;color:var(--ink-2);border-radius:9px;padding:7px 0;
  font:600 0.7812rem inherit;cursor:pointer;transition:all .2s}
.cal-foot button:hover{border-color:var(--brand);color:var(--brand);background:var(--brand-soft)}
.cal-note{margin:8px 0 0;font-size:0.6875rem;color:var(--muted);text-align:center}
.theme{appearance:none;border:0;background:transparent;width:34px;height:32px;border-radius:9px;cursor:pointer;padding:0;
  display:grid;place-items:center;color:var(--ink-2);transition:background .2s,color .2s}
.theme:hover{background:var(--brand-soft);color:var(--brand)}
.theme .knob{display:grid;place-items:center;transition:transform .4s cubic-bezier(.3,1.4,.5,1)}
.theme:active .knob{transform:rotate(-30deg) scale(.9)}
a:focus-visible,button:focus-visible{outline:2px solid var(--brand);outline-offset:2px}

.live{display:inline-flex;align-items:center;gap:7px;font-size:0.75rem;font-weight:600;padding:4px 10px;border-radius:999px}
.live.ok{background:var(--good-bg);color:var(--good)} .live.bad{background:var(--bad-bg);color:var(--bad)}
.beacon{width:8px;height:8px;border-radius:50%;background:currentColor;position:relative;display:inline-block;flex:none}
.beacon::after{content:"";position:absolute;inset:0;border-radius:50%;background:currentColor;animation:ping 1.6s cubic-bezier(0,0,.2,1) 3}
@keyframes ping{75%,100%{transform:scale(2.6);opacity:0}}

/* ---------- cards ---------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:20px;box-shadow:var(--shadow);
  transition:box-shadow .25s,border-color .25s,background .35s}
.card-head{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px}
h2{font-size:1.0625rem;margin:0;letter-spacing:-.01em}
.hint{color:var(--muted);font-size:0.8125rem;margin-top:2px}

.rise{opacity:0;transform:translateY(14px);animation:rise .6s cubic-bezier(.2,.8,.2,1) forwards;animation-delay:calc(var(--i,0) * 70ms)}
@keyframes rise{to{opacity:1;transform:none}}

.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
/* Smart Analytics Cards: deep violet gradient + inner glow, big high-contrast
   figures, small muted captions. */
.kpi{position:relative;overflow:hidden;border:1px solid var(--glass-line);border-radius:16px;padding:18px 18px 16px;
  display:grid;gap:2px;align-content:start;background:var(--kpi-bg);
  box-shadow:var(--kpi-inner),0 12px 32px -14px var(--soft-shadow);
  transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s,border-color .3s}
.kpi::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  background:linear-gradient(180deg,rgba(255,255,255,.06),transparent 40%)}
.kpi:hover{transform:translateY(-4px);border-color:var(--kb-1);box-shadow:var(--kpi-inner),0 22px 44px -16px var(--soft-shadow-up)}
.kpi-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.kpi-ico{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;flex:none;color:var(--brand);
  background:var(--glass-1);border:1px solid var(--glass-line);transition:color .3s,background .3s,transform .3s,box-shadow .3s}
.kpi-ico svg{width:20px;height:20px}
.kpi:hover .kpi-ico{color:#fff;background:linear-gradient(135deg,var(--brand-2),var(--brand));transform:rotate(-6deg) scale(1.06);
  box-shadow:0 6px 16px -4px var(--brand-glow)}
.kpi h3{margin:0;font-size:0.6875rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.kpi-value{margin:10px 0 2px;font-size:2.5rem;font-weight:800;letter-spacing:-.04em;line-height:1;color:var(--ink);
  font-variant-numeric:tabular-nums}
.kpi-sub{margin:0;color:var(--muted);font-size:0.7812rem;line-height:1.4}
.kpi-accent{background:var(--kpi-accent);border-color:rgba(255,255,255,.22);color:#fff;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35),inset 0 0 40px rgba(255,255,255,.10),0 18px 40px -14px var(--brand-glow)}
.kpi-accent .kpi-value{color:#fff;text-shadow:0 2px 18px rgba(255,255,255,.25)}
.kpi-accent h3,.kpi-accent .kpi-sub{color:rgba(255,255,255,.8)}
.kpi-accent .kpi-ico{color:#fff;background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.3)}
.kpi-accent:hover .kpi-ico{background:#fff;color:var(--brand)}
.kpi-accent .delta{color:#fff!important;opacity:.92}
.kpi-accent:hover{border-color:rgba(255,255,255,.4);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 26px 52px -16px var(--brand-glow)}
.delta{font-size:0.75rem;font-weight:600;margin-top:6px}
.delta.up{color:var(--good)} .delta.down{color:var(--bad)} .delta.flat{color:var(--muted)}

/* ---------- funnel ---------- */
/* Funnel: slim pill progress bars, width = share of everyone who wrote.
   Stages are joined by a dashed connector carrying a glass drop-off badge. */
.funnel{display:grid;padding:4px 0}
.f-row{display:grid;grid-template-columns:minmax(150px,220px) 1fr 104px;gap:18px;align-items:center;padding:12px 12px;border-radius:14px;
  position:relative;transition:transform .25s cubic-bezier(.2,.8,.2,1),background .25s;animation:rowIn .6s cubic-bezier(.16,1,.3,1) backwards;
  animation-delay:calc(var(--k) * 110ms)}
@keyframes rowIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.f-row:hover,.f-row:focus-visible{transform:scale(1.01);background:var(--card-2);outline:none}
.f-label{display:grid;gap:2px}
.f-label b{font-size:0.875rem;font-weight:600;color:var(--ink)}
.f-label span{font-size:0.75rem;color:var(--muted)}
.f-track{height:20px;border-radius:9999px;background:var(--grid);position:relative;overflow:visible}
.f-fill{height:100%;width:0;border-radius:9999px;background:linear-gradient(90deg,#6C5CE7,var(--f-end));
  box-shadow:0 0 15px rgba(108,92,231,.35);animation:fillProgress 1.2s cubic-bezier(.16,1,.3,1) forwards;
  animation-delay:calc(var(--k) * 140ms + 150ms);transition:box-shadow .25s,filter .25s;position:relative}
.f-fill::after{content:"";position:absolute;inset:0;border-radius:inherit;
  background:linear-gradient(180deg,rgba(255,255,255,.35),rgba(255,255,255,0) 60%)}
@keyframes fillProgress{from{width:0}to{width:var(--w)}}
.f-row:hover .f-fill,.f-row:focus-visible .f-fill{box-shadow:0 0 22px rgba(108,92,231,.55),0 0 34px color-mix(in srgb,var(--f-end) 45%,transparent);filter:saturate(1.15)}
.f-row.last .f-fill{box-shadow:0 0 15px rgba(16,185,129,.35)}
.f-right{display:grid;justify-items:end;line-height:1.1}
.f-num{font-size:1.375rem;font-weight:750;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.f-pct{font-size:0.75rem;font-weight:600;color:var(--brand);opacity:0;animation:pctIn .5s ease forwards;
  animation-delay:calc(var(--k) * 140ms + 900ms);font-variant-numeric:tabular-nums}
@keyframes pctIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.f-link{display:grid;grid-template-columns:minmax(150px,220px) 1fr 104px;gap:18px;padding:0 12px;height:34px}
.f-conn{position:relative;display:flex;align-items:center}
.f-conn::before{content:"";position:absolute;left:10px;top:-8px;bottom:-8px;border-left:2px dashed var(--line-2)}
.drop{position:relative;margin-left:26px;display:inline-flex;align-items:center;gap:5px;font-size:0.75rem;font-weight:700;padding:4px 10px;
  border-radius:999px;white-space:nowrap;color:var(--bad);border:1px solid color-mix(in srgb,var(--bad) 35%,transparent);
  background:color-mix(in srgb,var(--bad-bg) 70%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  box-shadow:0 4px 14px -4px var(--drop-glow)}
.drop::before{content:"";position:absolute;inset:-1px;border-radius:inherit;border:1px solid var(--bad);opacity:0;animation:dropPulse 2.2s ease-out 3}
@keyframes dropPulse{0%{opacity:.55;transform:scale(1)}100%{opacity:0;transform:scale(1.35)}}
.drop svg{width:13px;height:13px}
.drop small{font-weight:500;opacity:.8}
.drop.ok{color:var(--good);border-color:color-mix(in srgb,var(--good) 35%,transparent);background:color-mix(in srgb,var(--good-bg) 70%,transparent);box-shadow:none}
.drop.ok::before{display:none}
.f-tip{position:absolute;left:50%;bottom:calc(100% - 2px);transform:translate(-50%,6px);z-index:3;min-width:240px;
  background:var(--tip);color:var(--ink);border:1px solid var(--line-2);border-radius:12px;padding:10px 12px;font-size:0.75rem;
  box-shadow:var(--shadow-up);opacity:0;pointer-events:none;transition:opacity .18s,transform .18s;display:grid;gap:4px;
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
.f-tip b{font-size:0.8125rem}
.f-tip div{display:flex;justify-content:space-between;gap:16px;color:var(--ink-2)}
.f-tip div span:last-child{font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.f-row:hover .f-tip,.f-row:focus-visible .f-tip{opacity:1;transform:translate(-50%,0)}
.gate{margin-top:12px;padding:12px 14px;border-radius:12px;background:var(--card-2);border:1px dashed var(--line-2);font-size:0.8125rem;color:var(--ink-2)}
.win{margin-top:14px;display:flex;align-items:center;gap:16px;padding:16px 20px;border-radius:16px;color:#fff;
  background:linear-gradient(120deg,#0E8F65,#2BC48E);box-shadow:0 14px 34px rgba(18,163,116,.32)}
.win-num{font-size:2.125rem;font-weight:900;letter-spacing:-.03em}
.win p{margin:0;font-size:0.875rem;opacity:.95}
.win.empty-win{background:var(--card-2);color:var(--muted);box-shadow:none}
@media (prefers-reduced-motion:no-preference){.win:not(.empty-win){animation:none}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}}

/* ---------- chart ---------- */
.legend{display:flex;gap:16px;font-size:0.8125rem;color:var(--ink-2);font-weight:500}
.legend span{display:inline-flex;align-items:center;gap:7px}
.legend i{width:16px;height:4px;border-radius:2px;display:inline-block}
.chart-wrap{position:relative}
svg.chart{width:100%;height:auto;display:block;overflow:visible}
svg.chart .line{stroke-dasharray:var(--len);stroke-dashoffset:var(--len);animation:draw 1.4s .2s cubic-bezier(.4,0,.2,1) forwards}
svg.chart .area{opacity:0;animation:fade .8s .7s forwards}
@keyframes draw{to{stroke-dashoffset:0}} @keyframes fade{to{opacity:1}}
.tip{position:absolute;pointer-events:none;background:var(--tip);border:1px solid var(--line-2);border-radius:12px;
  padding:9px 12px;font-size:0.75rem;color:var(--ink);box-shadow:var(--shadow-up);transform:translate(-50%,calc(-100% - 12px));
  white-space:nowrap;opacity:0;transition:opacity .12s,left .08s,top .08s}
.tip b{display:block;margin-bottom:3px;color:var(--muted);font-weight:600}
.tip i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
details{margin-top:12px;font-size:0.8125rem;color:var(--ink-2)}
details summary{cursor:pointer;color:var(--muted)}
.tbl{overflow-x:auto;margin-top:8px}
.tbl table{border-collapse:collapse;width:100%;min-width:360px;font-variant-numeric:tabular-nums}
.tbl th,.tbl td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right}
.tbl th:first-child,.tbl td:first-child{text-align:left}

/* ---------- trainings ---------- */
.ranks{list-style:none;margin:0;padding:0;display:grid;gap:8px 18px;grid-template-columns:repeat(auto-fill,minmax(min(100%,420px),1fr))}
.rank{display:grid;grid-template-columns:30px 1fr auto;gap:12px;align-items:center;padding:12px;border-radius:14px;
  border:1px solid transparent;transition:transform .2s,background .2s,border-color .2s,box-shadow .2s}
.rank:hover{transform:translateY(-3px);background:var(--card-2);border-color:var(--line);box-shadow:var(--shadow)}
.rank-n{width:30px;height:30px;border-radius:10px;display:grid;place-items:center;font-weight:800;font-size:0.8125rem;
  background:var(--brand-soft);color:var(--brand)}
.rank:nth-child(1) .rank-n{background:linear-gradient(135deg,#FFD66B,#F2A900);color:#3a2600;box-shadow:0 0 16px rgba(242,169,0,.55)}
.rank:nth-child(2) .rank-n{background:linear-gradient(135deg,#E9EDF5,#BCC5D6);color:#2b3240}
.rank:nth-child(3) .rank-n{background:linear-gradient(135deg,#F3C9A4,#C98552);color:#3b1f08}
.rank-body{display:grid;gap:6px;min-width:0}
.rank-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.rank-head b{font-weight:600;font-size:0.875rem}
.tag{font-size:0.6875rem;color:var(--muted);border:1px solid var(--line-2);padding:2px 8px;border-radius:999px}
.bar{height:8px;border-radius:4px;background:var(--grid);overflow:hidden}
.bar i{display:block;height:100%;width:0;border-radius:4px;background:linear-gradient(90deg,var(--brand),var(--brand-2));transition:width 1.1s cubic-bezier(.2,.8,.2,1)}
.rank-meta{font-size:0.75rem;color:var(--muted)}
.chip{font-size:0.75rem;font-weight:700;padding:6px 10px;border-radius:999px;white-space:nowrap;display:inline-flex;align-items:center;gap:6px}
.chip.good{background:var(--good-bg);color:var(--good)} .chip.warn{background:var(--warn-bg);color:var(--warn)} .chip.bad{background:var(--bad-bg);color:var(--bad)}
.empty{color:var(--muted);margin:0}

/* ---------- section tabs: «Бот» / «Рассылки» ---------- */
.view-tabs{display:flex;gap:4px;border-bottom:1px solid var(--line)}
.view-tabs button{appearance:none;border:0;background:transparent;color:var(--muted);font:600 0.875rem inherit;padding:10px 14px 12px;
  cursor:pointer;position:relative;display:inline-flex;align-items:center;gap:8px;transition:color .2s}
.view-tabs button:hover{color:var(--ink)}
.view-tabs button::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;
  background:linear-gradient(90deg,var(--brand),var(--brand-2));transform:scaleX(0);transition:transform .25s}
.view-tabs button[aria-selected="true"]{color:var(--ink)}
.view-tabs button[aria-selected="true"]::after{transform:scaleX(1);box-shadow:0 0 12px var(--brand-glow)}
.view-tabs em{font-style:normal;font-size:0.6875rem;font-weight:700;padding:2px 7px;border-radius:999px;background:var(--brand-soft);color:var(--brand)}
.view{display:grid;gap:20px} .view[hidden]{display:none}

/* ---------- leads tab ---------- */
.sheet-btn{display:inline-flex;align-items:center;gap:8px;padding:9px 14px;border-radius:10px;font-weight:600;font-size:0.8125rem;
  color:#fff;text-decoration:none;background:linear-gradient(135deg,#1FA463,#0F9D58);box-shadow:0 6px 16px -6px rgba(15,157,88,.55);
  transition:transform .2s,box-shadow .2s}
.sheet-btn:hover{transform:translateY(-1px);box-shadow:0 10px 22px -8px rgba(15,157,88,.65)}
.lead-search{width:100%;margin:4px 0 12px;padding:10px 14px;border-radius:12px;border:1px solid var(--line-2);background:var(--card-2);
  color:var(--ink);font:500 0.875rem inherit}
.lead-search:focus{outline:2px solid var(--brand);outline-offset:1px}
.leads-tbl{max-height:640px;overflow:auto;border:1px solid var(--line);border-radius:12px}
.leads-tbl table{min-width:880px}
.leads-tbl thead th{position:sticky;top:0;background:var(--card-2);z-index:1;text-align:left;font-size:0.75rem;color:var(--muted)}
.leads-tbl td{text-align:left;vertical-align:top;font-size:0.8125rem}
.leads-tbl td.answers{min-width:260px;max-width:420px;color:var(--ink-2)}
.leads-tbl td.nowrap{white-space:nowrap}
.leads-tbl tr:hover td{background:var(--card-2)}
.leads-tbl a{color:var(--ink);font-weight:600;text-decoration:none}
.leads-tbl a:hover{color:var(--brand);text-decoration:underline}

/* ---------- broadcasts: day groups (accordion) → compact expandable rows ---------- */
.bc-day{border:1px solid var(--line);border-radius:18px;background:var(--card);box-shadow:var(--shadow);overflow:hidden}
.bc-day[open]{border-color:var(--glass-line);background:radial-gradient(90% 120% at 0% 0%,var(--glass-1),transparent 55%),var(--card)}
.bc-day>summary,.bc-card>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:14px}
.bc-day>summary::-webkit-details-marker,.bc-card>summary::-webkit-details-marker{display:none}
.bc-day>summary{padding:14px 18px}
.bc-day>summary:hover{background:var(--card-2)}
.chev{flex:none;margin-left:auto;color:var(--muted);transition:transform .3s cubic-bezier(.2,.8,.2,1),color .2s}
details[open]>summary>.chev{transform:rotate(180deg);color:var(--brand)}
.live+.chev{margin-left:0}
.bc-day>summary .live{margin-left:auto}
.day-badge{flex:none;width:52px;height:56px;border-radius:14px;display:grid;place-content:center;text-align:center;color:#fff;
  background:linear-gradient(160deg,var(--brand-2),var(--brand));box-shadow:0 8px 20px -8px var(--brand-glow),inset 0 1px 0 rgba(255,255,255,.3)}
.day-badge b{font-size:1.375rem;font-weight:800;line-height:1;letter-spacing:-.02em}
.day-badge small{font-size:0.6562rem;font-weight:700;letter-spacing:.1em;opacity:.9;margin-top:3px}
.bc-day:not([open]) .day-badge{background:var(--brand-soft);color:var(--brand);box-shadow:none}
.day-title{display:grid;gap:2px;min-width:0}
.day-title b{font-size:1.0625rem;font-weight:700;letter-spacing:-.01em}
.day-title small{font-size:0.7812rem;color:var(--muted)}
.day-body{display:grid;gap:10px;padding:4px 14px 16px}

.bc-card{border:1px solid var(--line);border-radius:14px;background:var(--card-2);transition:border-color .2s,box-shadow .2s}
.bc-card:hover{border-color:var(--glass-line)}
.bc-card[open]{border-color:color-mix(in srgb,var(--brand) 45%,var(--line));box-shadow:0 12px 30px -16px var(--brand-glow)}
.bc-card>summary{padding:12px 14px;flex-wrap:wrap}
.time-badge{flex:none;font-size:0.8125rem;font-weight:800;letter-spacing:.04em;color:#fff;padding:7px 11px;border-radius:10px;white-space:nowrap;
  background:linear-gradient(135deg,var(--brand-2),var(--brand));box-shadow:0 6px 16px -6px var(--brand-glow);font-variant-numeric:tabular-nums}
.bc-name{display:grid;gap:1px;min-width:0;flex:1 1 200px}
.bc-name b{font-size:0.9062rem;font-weight:650}
.bc-name small{font-size:0.75rem;color:var(--muted)}
.bc-mini{display:flex;gap:18px}
.bc-mini>span{display:grid;text-align:right;line-height:1.15}
.bc-mini b{font-size:1.125rem;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.bc-mini small{font-size:0.6875rem;color:var(--muted)}
.bc-body{padding:4px 14px 16px;animation:bodyIn .3s cubic-bezier(.2,.8,.2,1)}
@keyframes bodyIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.bc-body .bc-note{margin:0 0 12px}
@media (max-width:640px){ .bc-mini{order:3;width:100%;justify-content:flex-start} .bc-mini>span{text-align:left}
  .day-badge{width:46px;height:50px} }

/* ---------- broadcasts: neon direction bars ---------- */
.neon .bar{height:12px;border-radius:999px;background:var(--grid)}
.neon .bar i{border-radius:999px;background:linear-gradient(90deg,#7C5CFF,#22D3EE 50%,#10B981,#7C5CFF);background-size:300% 100%;
  box-shadow:0 0 14px rgba(124,92,255,.45);animation:neonFlow 4s cubic-bezier(.32,.72,0,1) 1}
@keyframes neonFlow{from{background-position:0% 0}to{background-position:300% 0}}
.neon .rank:hover .bar i{box-shadow:0 0 20px rgba(34,211,238,.55)}
.bc-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
.bc-tile{padding:12px 14px;border-radius:14px;background:var(--card-2);border:1px solid var(--line);display:grid;gap:4px}
.bc-tile span{font-size:0.75rem;color:var(--muted);font-weight:600}
.bc-tile b{font-size:1.375rem;font-weight:750;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.bc-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.bc-col{padding:14px;border-radius:14px;border:1px solid var(--line);background:var(--card)}
.bc-col h3{margin:0 0 8px;font-size:0.875rem;display:flex;align-items:center;gap:8px}
.bc-col h3 em{font-style:normal;margin-left:auto;font-size:0.75rem;padding:2px 9px;border-radius:999px}
.bc-col.bad h3{color:var(--bad)} .bc-col.bad h3 em{background:var(--bad-bg)}
.bc-col.warn h3{color:var(--warn)} .bc-col.warn h3 em{background:var(--warn-bg)}
.bc-col.good h3{color:var(--good)} .bc-col.good h3 em{background:var(--good-bg)}
.bc-col.bad{border-color:color-mix(in srgb,var(--bad) 35%,var(--line));box-shadow:0 8px 22px -12px var(--drop-glow)}
.bc-note{margin:0 0 8px;font-size:0.75rem;color:var(--ink-2)}
.who{list-style:none;margin:0;padding:0;display:grid;gap:4px;max-height:260px;overflow:auto}
.who li{display:flex;justify-content:space-between;gap:10px;padding:7px 10px;border-radius:10px;font-size:0.8125rem;transition:background .15s}
.who li:hover{background:var(--card-2)}
.who a{color:var(--ink);font-weight:600;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.who a:hover{color:var(--brand);text-decoration:underline}
.who time{color:var(--muted);font-size:0.75rem;white-space:nowrap;font-variant-numeric:tabular-nums}
.muted-id{color:var(--muted)}
@media (max-width:860px){.bc-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}.bc-cols{grid-template-columns:1fr}}

/* ---------- skeleton ---------- */
.skel{border-radius:10px;background:linear-gradient(90deg,var(--skel) 0%,var(--skel-hi) 50%,var(--skel) 100%);background-size:200% 100%;
  animation:shimmer 1.2s linear infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.skel-row{height:38px;margin:8px 0} .skel-chart{height:220px}

.info{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border-radius:16px;background:var(--brand-soft);
  border:1px solid var(--line-2);font-size:0.8125rem;color:var(--ink-2)}
.info svg{flex:none;margin-top:1px}
.info code{background:var(--card);padding:1px 6px;border-radius:6px;color:var(--ink);font-size:0.75rem;border:1px solid var(--line)}

@media (max-width:860px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:520px){
  .kpi-value{font-size:1.875rem}
  .f-row{grid-template-columns:1fr 64px;gap:6px 12px}.f-label{grid-column:1/3}.f-track{grid-column:1/2}
  .f-link{grid-template-columns:1fr;height:30px}.f-link>div:first-child,.f-link>div:last-child{display:none}.f-tip{display:none}
  .seg{overflow-x:auto;max-width:100%}
  .tools{width:100%;justify-content:space-between}.tool-sep{display:none}.kpi-value{font-size:2rem}
  .dp-quick{display:none}
}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.rise{opacity:1;transform:none}
  .f-fill{width:var(--w)}.f-pct{opacity:1}}
</style></head><body><main>

<header class="rise" style="--i:0">
  <div class="title"><h1>Статистика Instagram-бота</h1>
    <div class="sub">{{STATUS}}<span>@eduapp_demo · обновлено {{NOW}} (Астана)</span></div>
    <div class="period">Показано: <b>{{PERIOD}}</b></div></div>
  <div class="tools">
    <nav class="seg" role="tablist" aria-label="Период">{{TABS}}</nav>
    <span class="tool-sep" aria-hidden="true"></span>
    {{PICKER}}
    <span class="tool-sep" aria-hidden="true"></span>
    <button class="theme" id="theme" type="button" aria-label="Переключить тему"><span class="knob" id="knob"></span></button>
  </div>
</header>

<nav class="view-tabs" role="tablist" aria-label="Раздел">
  <button type="button" role="tab" data-view="bot" aria-selected="true">Бот</button>
  <button type="button" role="tab" data-view="leads" aria-selected="false">Лидтер <em>{{LEADS_COUNT}}</em></button>
  <button type="button" role="tab" data-view="bc" aria-selected="false">Рассылки <em>{{BC_COUNT}}</em></button>
</nav>

<div class="view" id="view-leads" hidden>
{{LEADS}}
</div>

<div class="view" id="view-bc" hidden>
{{BROADCASTS}}
</div>

<div class="view" id="view-bot">
<section class="kpis" aria-label="Главные показатели">{{KPIS}}</section>

<section class="card rise" style="--i:4" aria-labelledby="h-funnel">
  <div class="card-head">
    <div><h2 id="h-funnel">Воронка конверсии</h2><div class="hint">уникальные люди · под каждой полосой — сколько отсеялось</div></div>
    <div class="seg" role="group" aria-label="Направление">{{TOPIC_TABS}}</div>
  </div>
  <div class="funnel" id="funnel"><div class="skel skel-row"></div><div class="skel skel-row" style="width:80%"></div>
    <div class="skel skel-row" style="width:65%"></div><div class="skel skel-row" style="width:45%"></div></div>
  <div class="gate" id="gate"></div>
  <div class="win" id="win" aria-live="polite"></div>
</section>

<section class="card rise" style="--i:5" aria-labelledby="h-days">
  <div class="card-head"><div><h2 id="h-days">{{CHART_TITLE}}</h2><div class="hint">{{CHART_HINT}}</div></div>
    <div class="legend"><span><i style="background:var(--s-leads)"></i>Написали</span>
      <span><i style="background:var(--s-clicks)"></i>Нажали на ссылку</span></div></div>
  <div class="chart-wrap" id="chartWrap"><div class="skel skel-chart" id="chartSkel"></div>
    <svg class="chart" id="chart" role="img" aria-label="График по дням: написали и нажали на ссылку"></svg>
    <div class="tip" id="tip"></div></div>
  <details><summary>Показать таблицей</summary><div class="tbl" id="daysTable"></div></details>
</section>

<section class="card rise" style="--i:6" aria-labelledby="h-tr">
  <div class="card-head"><div><h2 id="h-tr">Какие тренинги выбирают</h2>
    <div class="hint">длина полосы — сколько получили ссылку, справа — конверсия в клик</div></div></div>
  {{TRAININGS}}
</section>

</div>

<aside class="info rise" style="--i:7">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 11v6M12 7.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
  <div><b style="color:var(--ink)">Покупки бот не видит</b> — они происходят в приложении eduapp_demo. Все ссылки из бота помечены
  <code>utm_source=instagram_bot</code> с названием тренинга и классом: по этой метке покупки можно найти в аналитике сайта.</div>
</aside>
</main>

<script>
const DATA = {{DATA}};
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---- theme toggle (light by default, remembered per browser) ---- */
const root = document.documentElement, knob = document.getElementById("knob");
/* Heroicons outline sun / moon (MIT), currentColor */
const SUN = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"/></svg>';
function syncKnob(){ knob.innerHTML = root.dataset.theme === "dark" ? MOON : SUN; }
syncKnob();
document.getElementById("theme").addEventListener("click", () => {
  if (root.dataset.theme === "dark") delete root.dataset.theme; else root.dataset.theme = "dark";
  try { localStorage.setItem("zd-theme", root.dataset.theme || "light"); } catch (e) {}
  syncKnob(); drawChart(false);
});

/* ---- section tabs; #broadcasts in the address opens «Рассылки» ---- */
(function(){
  const tabs = document.querySelectorAll("[data-view]");
  const HASH = {bc: "#broadcasts", leads: "#leads", bot: ""};
  function show(v){
    tabs.forEach(t => t.setAttribute("aria-selected", String(t.dataset.view === v)));
    ["bot", "leads", "bc"].forEach(k => { document.getElementById("view-" + k).hidden = k !== v; });
    if (v === "bc") fillBars();
    history.replaceState(null, "", location.search + HASH[v]);
  }
  tabs.forEach(t => t.addEventListener("click", () => show(t.dataset.view)));
  if (location.hash === "#broadcasts") show("bc");
  if (location.hash === "#leads") show("leads");
  // Lead search: filters table rows by any text (nick, city, phone, answers).
  const q = document.getElementById("leadSearch");
  if (q) q.addEventListener("input", () => {
    const s = q.value.trim().toLowerCase();
    document.querySelectorAll("#leadsTable tbody tr").forEach(tr => { tr.hidden = s && !tr.textContent.toLowerCase().includes(s); });
  });
  // Opening a broadcast row replays its bars filling up.
  document.querySelectorAll(".bc-card").forEach(d => d.addEventListener("toggle", () => {
    if (!d.open) return;
    d.querySelectorAll(".bar i").forEach(b => { b.style.width = "0"; });
    requestAnimationFrame(() => requestAnimationFrame(() => d.querySelectorAll(".bar i").forEach(b => { b.style.width = b.dataset.w + "%"; })));
  }));
})();

/* ---- calendar popover: picking a day opens that day's stats ---- */
(function(){
  const D = DATA.day, btn = document.getElementById("dpOpen");
  if (!btn || !D) return;
  const MON = ["январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"];
  const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  const parse = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const min = parse(D.min), max = parse(D.max), sel = D.sel ? parse(D.sel) : null, has = new Set(D.has || []);
  const go = d => { location.search = "?date=" + iso(d); };
  const chevL = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>';
  const chevR = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>';
  const pop = document.createElement("div");
  pop.className = "cal-pop"; pop.hidden = true; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Календарь");
  pop.innerHTML = `<div class="cal-head"><button type="button" data-m="-1" aria-label="Предыдущий месяц">${chevL}</button><b></b>
    <button type="button" data-m="1" aria-label="Следующий месяц">${chevR}</button></div>
    <div class="cal-dow"><span>Пн</span><span>Вт</span><span>Ср</span><span>Чт</span><span>Пт</span><span>Сб</span><span>Вс</span></div>
    <div class="cal-grid"></div>
    <div class="cal-foot"><button type="button" data-j="0">Сегодня</button><button type="button" data-j="1">Вчера</button><button type="button" data-j="6">Неделю назад</button></div>
    <p class="cal-note">Жирным — дни, когда были клиенты. Раньше ${min.getDate()}.${String(min.getMonth()+1).padStart(2,"0")} данных нет.</p>`;
  document.body.appendChild(pop);
  const grid = pop.querySelector(".cal-grid");
  let view = new Date((sel || max).getFullYear(), (sel || max).getMonth(), 1);
  function draw(){
    const start = new Date(view); start.setDate(1 - ((view.getDay() + 6) % 7));
    pop.querySelector(".cal-head b").textContent = `${MON[view.getMonth()]} ${view.getFullYear()}`;
    pop.querySelector('[data-m="-1"]').disabled = view <= new Date(min.getFullYear(), min.getMonth(), 1);
    pop.querySelector('[data-m="1"]').disabled = view >= new Date(max.getFullYear(), max.getMonth(), 1);
    let h = "";
    for (let i = 0; i < 42; i++){
      const d = new Date(start); d.setDate(start.getDate() + i);
      const cls = [d.getMonth() !== view.getMonth() && "out", +d === +max && "today", sel && +d === +sel && "sel", has.has(iso(d)) && "has"].filter(Boolean).join(" ");
      h += `<button type="button" class="${cls}" data-d="${iso(d)}" ${d < min || d > max ? "disabled" : ""}>${d.getDate()}</button>`;
    }
    grid.innerHTML = h;
  }
  function place(){
    const r = btn.getBoundingClientRect(), w = pop.offsetWidth;
    const left = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, document.documentElement.clientWidth - w - 12));
    pop.style.left = (left + scrollX) + "px"; pop.style.top = (r.bottom + 10 + scrollY) + "px";
  }
  function open(){ pop.hidden = false; btn.setAttribute("aria-expanded", "true"); draw(); place();
    (grid.querySelector(".sel") || grid.querySelector(".today"))?.focus({preventScroll: true}); }
  function close(){ pop.hidden = true; btn.setAttribute("aria-expanded", "false"); }
  btn.addEventListener("click", e => { e.stopPropagation(); pop.hidden ? open() : close(); });
  pop.addEventListener("click", e => {
    e.stopPropagation();
    const m = e.target.closest("[data-m]"), d = e.target.closest("[data-d]"), j = e.target.closest("[data-j]");
    if (m && !m.disabled){ view = new Date(view.getFullYear(), view.getMonth() + +m.dataset.m, 1); draw(); }
    if (d && !d.disabled) go(parse(d.dataset.d));
    if (j){ const t = new Date(max); t.setDate(t.getDate() - +j.dataset.j); go(t < min ? min : t); }
  });
  document.addEventListener("click", close);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !pop.hidden){ close(); btn.focus(); } });
  addEventListener("resize", () => { if (!pop.hidden) place(); });
})();

/* ---- count-up numbers ---- */
function countUp(el, to, ms = 900){
  if (reduce || !to) { el.textContent = to; return; }
  const t0 = performance.now();
  (function step(t){ const p = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * e); if (p < 1) requestAnimationFrame(step); })(t0);
}
document.querySelectorAll("[data-count]").forEach((el, i) => setTimeout(() => countUp(el, +el.dataset.count), 150 + i * 70));

/* ---- funnel ---- */
const STEPS = [
  ["start",  "Написали по рекламе",       "лиды с ключевым словом"],
  ["passed", "Прошли проверку подписки",  "подписаны на @eduapp_demo"],
  ["links",  "Получили ссылки",           "выбрали тренинг и класс"],
  ["click",  "Нажали на ссылку тренинга", "перешли в приложение"],
];
const ENDS = ["#00F2FE", "#00F2FE", "#00F2FE", "#10B981"];
const ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>';
const CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
function drawFunnel(topic){
  const f = DATA.funnels[topic];
  const pctOf = (a, b) => b ? Math.round(a * 100 / b) : 0;
  document.getElementById("funnel").innerHTML = STEPS.map(([k, label, hint], i) => {
    const v = f[k], share = pctOf(v, f.start);
    const w = f.start ? v * 100 / f.start : 0;            // strictly proportional
    const prev = i ? f[STEPS[i - 1][0]] : v, lost = Math.max(prev - v, 0), stepConv = pctOf(v, prev);
    const tip = `<div class="f-tip" role="tooltip"><b>${label}</b>
      ${i ? `<div><span>Пришло с прошлого шага</span><span>${prev}</span></div>` : ""}
      <div><span>Дошло до этого шага</span><span>${v}</span></div>
      ${i ? `<div><span>Вышло на шаге</span><span>${lost}</span></div>
             <div><span>Конверсия шага</span><span>${stepConv}%</span></div>` : ""}
      <div><span>От всех написавших</span><span>${share}%</span></div></div>`;
    let link = "";
    if (i) {
      const badge = !prev ? `<span class="drop ok">нет данных</span>`
        : lost ? `<span class="drop">${ARROW}−${lost} чел. <small>· дошли ${stepConv}%</small></span>`
               : `<span class="drop ok">${CHECK}без потерь</span>`;
      link = `<div class="f-link"><div></div><div class="f-conn">${badge}</div><div></div></div>`;
    }
    return `${link}<div class="f-row${i === STEPS.length - 1 ? " last" : ""}" tabindex="0" style="--k:${i}">
      <div class="f-label"><b>${label}</b><span>${hint}</span></div>
      <div class="f-track"><div class="f-fill" style="--w:${w.toFixed(1)}%;--f-end:${ENDS[i]}"></div></div>
      <div class="f-right"><span class="f-num" data-count="${v}">0</span><span class="f-pct">${share}%</span></div>${tip}</div>`;
  }).join("");
  document.querySelectorAll(".f-num").forEach((el, i) => setTimeout(() => countUp(el, +el.dataset.count, 900), i * 140 + 150));
  const sp = f.gate ? Math.round(f.subscribed * 100 / f.gate) : null;
  document.getElementById("gate").innerHTML = f.gate
    ? `Бот попросил подписаться <b>${f.gate}</b> чел. → подписались <b>${f.subscribed}</b> (${sp}%). Уже были подписчиками: <b>${f.already_follower}</b>.`
    : `Все, кто написал, уже были подписчиками (${f.already_follower}).`;
  const conv = f.start ? Math.round(f.click * 100 / f.start) : null, win = document.getElementById("win");
  win.classList.toggle("empty-win", conv === null);
  win.innerHTML = conv === null ? `<p>Пока нет лидов за этот период.</p>`
    : `<div class="win-num"><span data-count="${conv}">0</span>%</div><p>из написавших нажали на ссылку тренинга<br>${f.click} из ${f.start} человек</p>`;
  const wc = win.querySelector("[data-count]"); if (wc) countUp(wc, conv, 900);
}
document.querySelectorAll("[data-topic]").forEach(btn => btn.addEventListener("click", () => {
  document.querySelectorAll("[data-topic]").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
  drawFunnel(btn.dataset.topic);
}));

/* ---- training bars ---- */
function fillBars(){ document.querySelectorAll(".bar i").forEach(b => b.style.width = b.dataset.w + "%"); }

/* ---- smooth area chart (monotone cubic: no overshoot below zero) ---- */
const S = DATA.series, svg = document.getElementById("chart"), tip = document.getElementById("tip");
const W = 960, H = 280, P = {l: 36, r: 16, t: 16, b: 30};
function nice(max){ if (max <= 4) return 4; const m = Math.pow(10, Math.floor(Math.log10(max))); const n = max / m;
  return (n <= 2 ? 2 : n <= 5 ? 5 : 10) * m; }
function monotone(pts){
  if (pts.length < 2) return pts.length ? `M${pts[0][0]},${pts[0][1]}` : "";
  const n = pts.length, dx = [], m = [], t = [];
  for (let i = 0; i < n - 1; i++){ dx[i] = pts[i+1][0] - pts[i][0]; m[i] = (pts[i+1][1] - pts[i][1]) / dx[i]; }
  t[0] = m[0]; t[n-1] = m[n-2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i-1] * m[i] <= 0 ? 0 : 3 * (dx[i-1] + dx[i]) / ((2*dx[i] + dx[i-1]) / m[i-1] + (dx[i] + 2*dx[i-1]) / m[i]);
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++){ const h = dx[i] / 3;
    d += `C${(pts[i][0]+h).toFixed(1)},${(pts[i][1]+t[i]*h).toFixed(1)} ${(pts[i+1][0]-h).toFixed(1)},${(pts[i+1][1]-t[i+1]*h).toFixed(1)} ${pts[i+1][0].toFixed(1)},${pts[i+1][1].toFixed(1)}`; }
  return d;
}
function drawChart(animate){
  const lead = css("--s-leads"), clk = css("--s-clicks"), grid = css("--grid"), axis = css("--axis"), muted = css("--muted"), card = css("--card");
  const maxV = nice(Math.max(1, ...S.map(d => Math.max(d.start, d.click))));
  const x = i => P.l + (S.length === 1 ? (W - P.l - P.r) / 2 : i * (W - P.l - P.r) / (S.length - 1));
  const y = v => H - P.b - v * (H - P.t - P.b) / maxV;
  const ticks = [0, .25, .5, .75, 1].map(f => Math.round(maxV * f)).filter((v, i, a) => a.indexOf(v) === i);
  const every = Math.max(1, Math.ceil(S.length / 8));
  const line = k => monotone(S.map((d, i) => [x(i), y(d[k])]));
  const area = k => `${line(k)}L${x(S.length - 1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z`;
  const anim = animate && !reduce ? "" : ' style="animation:none;stroke-dasharray:none;opacity:1"';
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `
    <defs>
      <linearGradient id="gL" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${lead}" stop-opacity=".28"/><stop offset="1" stop-color="${lead}" stop-opacity="0"/></linearGradient>
      <linearGradient id="gC" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${clk}" stop-opacity=".26"/><stop offset="1" stop-color="${clk}" stop-opacity="0"/></linearGradient>
    </defs>
    ${ticks.map(t => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" stroke="${t ? grid : axis}" stroke-width="1"/>
      <text x="${P.l - 10}" y="${y(t) + 4}" text-anchor="end" font-size="12" fill="${muted}">${t}</text>`).join("")}
    ${S.map((d, i) => i % every === 0 || i === S.length - 1 ? `<text x="${x(i)}" y="${H - 8}" text-anchor="middle" font-size="12" fill="${muted}">${d.d}</text>` : "").join("")}
    <path class="area" d="${area("start")}" fill="url(#gL)"${anim}/><path class="area" d="${area("click")}" fill="url(#gC)"${anim}/>
    <path class="line" d="${line("start")}" fill="none" stroke="${lead}" stroke-width="2.5" stroke-linecap="round"${anim}/>
    <path class="line" d="${line("click")}" fill="none" stroke="${clk}" stroke-width="2.5" stroke-linecap="round"${anim}/>
    <line id="cross" y1="${P.t}" y2="${H - P.b}" stroke="${muted}" stroke-opacity=".5" stroke-dasharray="3 4" visibility="hidden"/>
    <circle id="dL" r="6" fill="${lead}" stroke="${card}" stroke-width="3" visibility="hidden"/>
    <circle id="dC" r="6" fill="${clk}" stroke="${card}" stroke-width="3" visibility="hidden"/>
    <rect x="${P.l - 10}" y="0" width="${W - P.l - P.r + 20}" height="${H}" fill="transparent" id="hit"/>`;
  svg.querySelectorAll(".line").forEach(p => p.style.setProperty("--len", Math.ceil(p.getTotalLength())));
  const hit = svg.querySelector("#hit"), cross = svg.querySelector("#cross"), dL = svg.querySelector("#dL"), dC = svg.querySelector("#dC");
  function show(evt){
    const r = svg.getBoundingClientRect(), sx = (evt.clientX - r.left) * W / r.width;
    const i = S.length === 1 ? 0 : Math.max(0, Math.min(S.length - 1, Math.round((sx - P.l) * (S.length - 1) / (W - P.l - P.r))));
    const d = S[i], px = x(i);
    cross.setAttribute("x1", px); cross.setAttribute("x2", px);
    dL.setAttribute("cx", px); dL.setAttribute("cy", y(d.start)); dC.setAttribute("cx", px); dC.setAttribute("cy", y(d.click));
    [cross, dL, dC].forEach(e => e.setAttribute("visibility", "visible"));
    const conv = d.start ? Math.round(d.click * 100 / d.start) + "%" : "—";
    tip.innerHTML = `<b>${d.d}</b><div><i style="background:${lead}"></i>Написали: <b style="display:inline;color:var(--ink)">${d.start}</b></div>
      <div><i style="background:${clk}"></i>Нажали: <b style="display:inline;color:var(--ink)">${d.click}</b></div><div style="color:var(--muted);margin-top:3px">конверсия ${conv}</div>`;
    tip.style.left = (px * r.width / W) + "px"; tip.style.top = (Math.min(y(d.start), y(d.click)) * r.height / H) + "px";
    tip.style.opacity = 1;
  }
  function hide(){ [cross, dL, dC].forEach(e => e.setAttribute("visibility", "hidden")); tip.style.opacity = 0; }
  hit.addEventListener("pointermove", show); hit.addEventListener("pointerdown", show); hit.addEventListener("pointerleave", hide);
}
document.getElementById("daysTable").innerHTML = `<table><thead><tr><th>${DATA.hourly ? "Час" : "День"}</th><th>Написали</th><th>Получили ссылки</th><th>Нажали</th></tr></thead><tbody>${
  S.slice().reverse().map(d => `<tr><td>${d.d}</td><td>${d.start}</td><td>${d.links}</td><td>${d.click}</td></tr>`).join("")}</tbody></table>`;

/* ---- first paint: skeletons for a beat, then everything animates in ---- */
setTimeout(() => {
  document.getElementById("chartSkel").remove();
  drawFunnel("all"); drawChart(true); fillBars();
}, reduce ? 0 : 450);
</script>
</body></html>"""
