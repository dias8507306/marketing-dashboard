"""Contact collection: parse city / grade / phone from free-text answers,
keep one row per person in the bot DB, and mirror it to Google Sheets.

The DB is the source of truth; the sheet is synced in the background, so a
Google hiccup never loses an answer (unsynced rows are retried).
"""
import re
import time
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))
TOPIC_NAMES = {"math": "Математика", "english": "Ағылшын", "saka": "Алтын сақа"}

KZ = str.maketrans("әғқңөұүһі", "агкноуухи")

# Normalized spelling (Kazakh letters folded, lower case) -> display name.
CITIES = [
    ("астана", "Астана"), ("нур-султан", "Астана"), ("нурсултан", "Астана"), ("алматы", "Алматы"), ("алма-ата", "Алматы"),
    ("шымкент", "Шымкент"), ("караганд", "Қарағанды"), ("актобе", "Ақтөбе"), ("актюбинск", "Ақтөбе"), ("тараз", "Тараз"),
    ("павлодар", "Павлодар"), ("оскемен", "Өскемен"), ("усть-каменогорск", "Өскемен"), ("семей", "Семей"),
    ("семипалатинск", "Семей"), ("атырау", "Атырау"), ("костанай", "Қостанай"), ("кызылорд", "Қызылорда"),
    ("орал", "Орал"), ("уральск", "Орал"), ("петропавл", "Петропавл"), ("актау", "Ақтау"), ("туркестан", "Түркістан"),
    ("кокшетау", "Көкшетау"), ("талдыкорган", "Талдықорған"), ("экибастуз", "Екібастұз"), ("екибастуз", "Екібастұз"),
    ("жезказган", "Жезқазған"), ("конаев", "Қонаев"), ("капшагай", "Қонаев"), ("капчагай", "Қонаев"), ("темиртау", "Теміртау"),
    ("балкаш", "Балқаш"), ("балхаш", "Балқаш"), ("жанаозен", "Жаңаөзен"), ("кульсары", "Құлсары"), ("кулсары", "Құлсары"),
    ("сатпаев", "Сәтбаев"), ("сатбаев", "Сәтбаев"), ("степногорск", "Степногорск"), ("аральск", "Арал"), ("жаркент", "Жаркент"),
    ("кентау", "Кентау"), ("сарыагаш", "Сарыағаш"), ("рудный", "Рудный"), ("щучинск", "Щучинск"), ("байконыр", "Байқоңыр"),
]
# Spaces, dashes and brackets may sit inside a number, line breaks may not: «Астана\n3\n8707…»
# must stay three answers, not one long «number».
PHONE_RE = re.compile(r"\+?\d[\d \t\-()]{8,17}\d")
# «сын…» also catches typos like «сыныр»; «кл»/«класс» for Russian; ordinal endings for «3-ші».
GRADE_RE = re.compile(r"(?<!\d)(1[01]|[1-9])\s*(?:-?\s*(?:сын\w*|класс\w*|кл\b|ші|шы|інші|ыншы|нші|ншы|nші))", re.I)
# A grade written alone, optionally with its letter: «3», «4а», «5 Б».
BARE_GRADE_RE = re.compile(r"(1[01]|[1-9])\s*-?\s*[а-яәa-zА-ЯӘA-Z]?", re.I)


def norm(s: str) -> str:
    return (s or "").lower().translate(KZ)


def find_phone(text: str):
    """Kazakhstan mobile in any common spelling -> «+7 700 123 45 67»."""
    for m in PHONE_RE.finditer(text or ""):
        d = re.sub(r"\D", "", m.group())
        if len(d) == 11 and d[0] in "78":
            d = d[1:]
        if len(d) == 10 and d[0] == "7":
            return f"+7 {d[:3]} {d[3:6]} {d[6:8]} {d[8:]}"
    return None


def find_grade(text: str):
    t = PHONE_RE.sub(" ", text or "")
    m = GRADE_RE.search(t)
    if m:
        return m.group(1)
    # A bare 1-11 on its own line or as a separate piece: «Астана\n3\n8707…», «Астана, 3, 8707…».
    for piece in re.split(r"[\n,;/|]+", t):
        m = BARE_GRADE_RE.fullmatch(piece.strip(" .,!?)("))
        if m:
            return m.group(1)
    return None


def reparse(con) -> int:
    """Fill grade/city/phone that an older parser missed, from the stored answers."""
    ensure_table(con)
    fixed = 0
    for igsid, texts, city, grade, phone in con.execute("select igsid, texts, city, grade, phone from leads").fetchall():
        parts = [p for p in (texts or "").split(" | ") if p]
        g = grade or next((x for x in map(find_grade, parts) if x), None)
        c = city or next((x for x in map(find_city, parts) if x), None)
        p = phone or next((x for x in map(find_phone, parts) if x), None)
        if (g, c, p) != (grade, city, phone):
            con.execute("update leads set grade = ?, city = ?, phone = ?, synced = 0, updated_ts = updated_ts + 1"
                        " where igsid = ?", (g, c, p, igsid))
            fixed += 1
    return fixed


def find_city(text: str):
    t = norm(PHONE_RE.sub(" ", text or ""))
    for key, name in CITIES:
        if key in t:
            return name
    return None


def guess_city(text: str):
    """A short answer with no digits and no known city is most likely a town or village name."""
    t = (text or "").strip(" .,!?")
    if not t or re.search(r"\d", t) or len(t.split()) > 3 or len(t) > 40:
        return None
    return t[:1].upper() + t[1:]


_READY = False  # tables are created once per process: each statement is a round trip to the database


def ensure_table(con):
    global _READY
    if _READY:
        return
    _READY = True
    con.execute("create table if not exists leads (igsid text primary key, username text, topic text, city text,"
                " grade text, phone text, texts text, first_ts bigint, updated_ts bigint, thanked integer default 0,"
                " synced integer default 0)")


def start_lead(con, igsid: str, topic: str | None):
    ensure_table(con)
    now = int(time.time())
    con.execute("insert into leads (igsid, topic, texts, first_ts, updated_ts) values (?, ?, '', ?, ?)"
                " on conflict (igsid) do nothing",
                (igsid, topic, now, now))


def get_lead(con, igsid: str):
    ensure_table(con)
    row = con.execute("select igsid, username, topic, city, grade, phone, texts, first_ts, updated_ts, thanked"
                      " from leads where igsid = ?", (igsid,)).fetchone()
    if not row:
        return None
    keys = ("igsid", "username", "topic", "city", "grade", "phone", "texts", "first_ts", "updated_ts", "thanked")
    return dict(zip(keys, row))


def add_answer(con, igsid: str, text: str, username: str | None) -> dict:
    """Merge one message into the person's row. Returns the updated row and
    whether this message carried their first phone number."""
    lead = get_lead(con, igsid)
    phone, grade = find_phone(text), find_grade(text)
    city = find_city(text) or (None if lead["city"] else guess_city(text) if not (phone or grade) else None)
    texts = (lead["texts"] + " | " if lead["texts"] else "") + text.strip()
    new_phone = bool(phone) and not lead["phone"]
    con.execute("update leads set username = coalesce(?, username), city = coalesce(?, city), grade = coalesce(?, grade),"
                " phone = coalesce(phone, ?), texts = ?, updated_ts = ?, synced = 0 where igsid = ?",
                (username, city, grade, phone, texts[:2000], int(time.time()), igsid))
    return {**get_lead(con, igsid), "new_phone": new_phone}


def mark_thanked(con, igsid: str):
    now = int(time.time())
    con.execute("update leads set thanked = 1, synced = 0,"
                " updated_ts = case when updated_ts + 1 > ? then updated_ts + 1 else ? end where igsid = ?",
                (now, now, igsid))


def sheet_row(lead: dict) -> dict:
    fmt = lambda ts: datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M") if ts else ""
    user = lead.get("username")
    return {
        "id": lead["igsid"],
        "first": fmt(lead["first_ts"]),
        # A plain URL, not =HYPERLINK(): formula separators depend on the sheet's locale
        # («,» vs «;») and broke as #ERROR!; Sheets makes a bare URL clickable in any locale.
        "instagram": f"https://instagram.com/{user}" if user else "",
        "topic": TOPIC_NAMES.get(lead.get("topic") or "", ""),
        "city": lead.get("city") or "",
        "grade": lead.get("grade") or "",
        "phone": lead.get("phone") or "",
        "texts": lead.get("texts") or "",
        "thanked": "иә" if lead.get("thanked") else "",
        "updated": fmt(lead["updated_ts"]),
    }


def unsynced(con, limit: int = 20) -> list:
    ensure_table(con)
    ids = [r[0] for r in con.execute("select igsid from leads where synced = 0 order by updated_ts limit ?", (limit,))]
    return [get_lead(con, i) for i in ids]


def mark_synced(con, igsid: str, updated_ts: int):
    # Only if nothing changed since we read it; otherwise the next pass sends the newer row.
    con.execute("update leads set synced = 1 where igsid = ? and updated_ts = ?", (igsid, updated_ts))
