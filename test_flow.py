"""Offline walk through the conversation: Instagram calls are replaced by fakes."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["CONF_DIR"] = str(HERE / "conf")
os.environ["TRACK_BASE_URL"] = "https://bot.example"
os.environ["FLOW"] = "menu"  # the older menu flow is tested first; the welcome flow at the end
os.environ["STATS_PASSWORD"] = "test-pass"
sys.path.insert(0, str(HERE))
import app  # noqa: E402


async def _no_history(igsid):  # tests have no Instagram: nobody chatted before
    return False


app.talked_before = _no_history

sent = []
following = {"value": False}


async def fake_send(igsid, message):
    sent.append(message)
    return True


async def fake_follows(igsid):
    return following["value"]


async def fake_username(igsid):
    return None


app.send = fake_send
app.follows = fake_follows
app.remember_username = fake_username


def last(n=1):
    return sent[-n:]


def show(msg):
    if "attachment" in msg:
        p = msg["attachment"]["payload"]
        btns = [(b["title"], b.get("url") or b.get("payload")) for b in p["buttons"]]
        return f"[BUTTONS] {p['text'][:60]!r}... {btns}"
    q = [(x["title"], x["payload"]) for x in msg.get("quick_replies", [])]
    return f"[TEXT] {msg['text'][:60]!r}... {q}"


async def step(title, coro):
    before = len(sent)
    await coro
    print(f"\n== {title}")
    for m in sent[before:]:
        print("  ", show(m))
    return sent[before:]


def check(cond, what):
    print(("  OK  " if cond else "  FAIL ") + what)
    if not cond:
        check.failed = True


check.failed = False


async def main():
    u = "1000000000000001"
    # Math, not following yet
    out = await step("math ad text, not subscribed", app.on_text(u, "Математика бойынша тренинг туралы толық ақпарат білгім келеді"))
    check(out[0]["attachment"]["payload"]["buttons"][0]["payload"] == "CHECK:math", "follow gate with CHECK:math")
    out = await step("press Тексеру, still not subscribed", app.on_payload(u, "CHECK:math"))
    check("Жазылу расталмады" in out[0]["attachment"]["payload"]["text"], "asks again")
    following["value"] = True
    out = await step("press Тексеру, subscribed", app.on_payload(u, "CHECK:math"))
    check(len(out) == 1, "thanks + menu in ONE message")
    menu = out[0]["attachment"]["payload"]
    check(menu["text"].startswith("Парақшаға сәтті тіркелдіңіз! 🎉\n\nБалаңыздың математикадан"), "menu starts with success line")
    check("🔹 Тоқсандық\n⏱ 90 күн • 💰 6 500 ₸\n⏱ 1 күн • 💰 1 200 ₸" in menu["text"], "new math menu format")
    check([b["payload"] for b in menu["buttons"]] == ["T:quarter", "T:mega"], "math menu: stacked postback buttons")
    check(menu["buttons"][0]["title"] == "Тоқсандық" and menu["buttons"][0]["type"] == "postback", "Тоқсандық is a stacked button")
    out = await step("Алтын сақа ad, subscribed", app.on_text(u, "«Алтын сақа» олимпиадасына дайындық туралы толық ақпарат білгім келеді"))
    check(len(out) == 1, "greeting + saka menu in ONE message")
    check("олимпиадасы туралы толығырақ" in out[0]["text"], "saka greeting")
    check("Парақшаға сәтті" not in out[0]["text"], "no 'subscribed' line for old subscriber")
    check("«Алтын сақа» олимпиадасына дайындықты қазір бастаңыз!" in out[0]["text"], "saka menu text")
    check([q["payload"] for q in out[0]["quick_replies"]] == ["G:altyn_saka:3", "G:altyn_saka:4", "G:altyn_saka:5", "G:altyn_saka:6"], "grade buttons under saka menu")
    out = await step("choose 3 сынып", app.on_payload(u, "G:altyn_saka:3"))
    b = out[0]["attachment"]["payload"]["buttons"]
    check([x["title"] for x in b] == ["1-жинақ", "2-жинақ", "3-жинақ"], "3 buttons named 1-/2-/3-жинақ")
    check("кезең" not in out[0]["attachment"]["payload"]["text"], "no 'кезең' in links message")
    check(all(x["url"].startswith("https://bot.example/r/") for x in b), "buttons go through click counter")
    first = await app.click(b[0]["url"].rsplit("/", 1)[1])
    target = first.headers["location"]
    check("a66b0d38-9d95-847e-bd29-9753a7677796/chapter?utm_source=instagram_bot" in target, "grade 3 stage I link + utm")
    check("utm_campaign=saka" in target and "utm_content=altyn_saka%3A3" in target, "utm campaign/content")
    third = await app.click(b[2]["url"].rsplit("/", 1)[1])
    check("d4ea65d0-03d7-1684-9f85-58a628518867/chapter" in third.headers["location"], "grade 3 stage III link")
    bad = await app.click("nope")
    check(bad.headers["location"] == "https://eduapp.example.com/login", "unknown token falls back to login page")
    check("youtube" in out[1]["text"], "video message after links")
    check("қайтарылмайды" not in out[1]["text"], "refund line removed")

    # Quarter grade 4 typed instead of tapped
    await app.on_payload(u, "T:quarter")
    out = await step("types '4 сынып' instead of tapping", app.on_text(u, "4 сынып"))
    b = out[0]["attachment"]["payload"]["buttons"]
    check([x["title"] for x in b] == ["A деңгей", "B деңгей"], "A and B buttons")
    urls = [(await app.click(x["url"].rsplit("/", 1)[1])).headers["location"] for x in b]
    check("73ab4876" in urls[0] and "902a174f" in urls[1], "grade 4 quarter A/B links")

    out = await step("mega grade 6", app.on_payload(u, "G:mega:6"))
    b = out[0]["attachment"]["payload"]["buttons"]
    urls = [(await app.click(x["url"].rsplit("/", 1)[1])).headers["location"] for x in b]
    check("99809225" in urls[0] and "ec3fbf4d" in urls[1], "grade 6 mega A/B links")

    # English, already subscribed: no gate
    v = "1000000000000002"
    out = await step("english ad text, already subscribed", app.on_text(v, "Ағылшын тілі бойынша тренинг туралы толық ақпарат білгім келеді"))
    menu = out[0]["attachment"]["payload"]
    check(not menu["text"].startswith("Сәлеметсіз бе!\nТолық ақпарат"), "no follow gate for subscriber")
    check([b["payload"] for b in menu["buttons"]] == ["EN:A0", "EN:Low A1", "EN:Mid A1"], "english level: 3 stacked buttons")
    out = await step("choose Аздап біледі", app.on_payload(v, "EN:Low A1"))
    en = await app.click(out[0]["attachment"]["payload"]["buttons"][0]["url"].rsplit("/", 1)[1])
    check("e3eff9c0" in en.headers["location"], "Low A1 link")

    # Direct Алтын сақа question skips the type menu
    w = "1000000000000003"
    following["value"] = False
    out = await step("Алтын сақа ad, not subscribed", app.on_text(w, "алтын сака туралы"))
    check(out[0]["attachment"]["payload"]["buttons"][0]["payload"] == "CHECK:saka", "saka follow gate")
    following["value"] = True
    out = await step("press Тексеру on saka", app.on_payload(w, "CHECK:saka"))
    check(out[0]["quick_replies"][0]["payload"] == "G:altyn_saka:3", "saka menu with grades after check")

    # Unrelated message is left for managers
    out = await step("unrelated message", app.on_text("1000000000000004", "Сәлеметсіз бе, баға қанша?"))
    check(out == [], "bot stays silent")
    out = await step("Meta stock ad question -> Алтын сақа", app.on_text("1000000000000006", "Здравствуйте! Можно узнать об этом подробнее?"))
    check(len(out) == 1 and "«Алтын сақа» олимпиадасы туралы толығырақ" in out[0]["text"], "stock question opens Алтын сақа")
    out = await step("'олимпиада' alone no longer triggers", app.on_text("1000000000000005", "олимпиада қашан болады?"))
    check(out == [], "олимпиада alone: silent")

    # Same topic mentioned again mid-conversation: no second menu
    out = await step("same person writes 'алтын сақа' again", app.on_text(w, "алтын сақа 3 кезеңі де керек пе?"))
    check(out == [], "repeat within 24h: silent, left for managers")
    out = await step("but a different topic still works", app.on_text(w, "математика туралы айтыңызшы"))
    check(len(out) == 1, "new topic for same person: menu sent")
    check("мектепішілік" not in app.texts()["links_altyn_saka"], "(I кезең — мектепішілік) removed")

    # Stats: funnel numbers are unique people
    with app.db() as con:
        page = app.stats.render(con, 0, app.texts())
        counts = dict(con.execute("select event, count(distinct igsid) from events group by event").fetchall())
    print("\n== stats events:", counts)
    check(counts.get("start") == 4 and counts.get("gate") == 2 and counts.get("subscribed") == 2, "funnel: start/gate/subscribed")
    check(counts.get("already_follower") == 4 and counts.get("click") == 2 and counts.get("links") == 2, "funnel: followers/links/clicks")
    check("Алтын сақа · 3 сынып" in page and "English Low A1" in page, "stats page lists choices")
    check('"funnels"' in page and "drawFunnel" in page, "stats page carries funnel data and chart code")
    with app.db() as con:
        page_ex = app.stats.render(con, 0, app.texts(), exclude=u)
    check(page_ex != page, "excluding a test account changes the numbers")
    import datetime as _dt
    today = _dt.datetime.now(app.stats.TZ).strftime("%Y-%m-%d")
    with app.db() as con:
        day_page = app.stats.render(con, 7, app.texts(), date=today)
        bad_page = app.stats.render(con, 7, app.texts(), date="2099-01-01")
    check("Динамика по часам" in day_page and '"sel": "' + today + '"' in day_page and "сравнение с предыдущим днём" in day_page,
          "stats: a chosen day shows hourly chart and the picker on that day")
    check('class="dp on"' in day_page and 'id="dpOpen"' in day_page and 'aria-pressed="true">Сегодня' in day_page,
          "stats: floating pill with calendar button and «Сегодня» pressed")
    check('"23:00"' in day_page, "stats: a chosen day has all 24 hours")
    check("Динамика по дням" in bad_page, "stats: a future/invalid date falls back to the period view")
    from starlette.requests import Request as _R
    def req(auth):
        return _R({"type": "http", "headers": [(b"authorization", auth.encode())] if auth else []})
    import base64 as _b
    check(app.stats_auth_ok(req("Basic " + _b.b64encode(b"eduapp:test-pass").decode())), "stats: right password accepted")
    check(not app.stats_auth_ok(req("Basic " + _b.b64encode(b"eduapp:wrong").decode())), "stats: wrong password rejected")
    check(not app.stats_auth_ok(req("")), "stats: no password rejected")

    # Follow-up broadcast: only people with links, inside the window, never twice
    rec = app.followup_recipients("t1")
    check(set(rec) == {u, v}, f"followup recipients = people who got links ({len(rec)})")
    with app.db() as con:  # push v outside the 24 h window
        con.execute("update events set ts = ts - 30*3600 where igsid = ?", (v,))
        con.execute("update users set ts = ts - 30*3600 where igsid = ?", (v,))
    rec = app.followup_recipients("t1")
    check(rec == [u], "person silent for 30 h is skipped")
    await app.handle_event({"sender": {"id": v}, "message": {"mid": "m-plain-1", "text": "рахмет"}})
    check(set(app.followup_recipients("t1")) == {u, v}, "a plain message (no keyword) reopens the window")
    with app.db() as con:
        con.execute("update events set ts = ts - 30*3600 where igsid = ?", (v,))
    out = await step("send followup", app.send_followup(u, "t1"))
    b = out[0]["attachment"]["payload"]["buttons"]
    check([x["payload"] for x in b] == ["FU:done", "FU:help", "FU:notyet"] and b[0]["title"] == "✅ Тіркелдім", "3 stacked buttons")
    check(app.followup_recipients("t1") == [], "same campaign never sent twice")
    check(u not in app.followup_recipients("t1@2026-09-30"), "a later send of the same kind skips people who already got it")
    out = await step("answer: not yet", app.on_payload(u, "FU:notyet"))
    check("Тіркелу оңай" in out[0]["attachment"]["payload"]["text"] and out[0]["attachment"]["payload"]["buttons"][0]["title"] == "Тіркелу", "notyet -> login button")
    out = await step("answer: help", app.on_payload(u, "FU:help"))
    check("Менеджеріміз" in out[0]["text"], "help -> manager will write")
    out = await step("answer: done", app.on_payload(u, "FU:done"))
    check("сәттілік" in out[0]["text"], "done -> good luck")
    # «pick» campaign: people who never got links, three direction buttons
    x = "1000000000000009"
    await app.handle_event({"sender": {"id": x}, "message": {"mid": "m-plain-9", "text": "сәлем"}})
    check("1000000000000009" in app.followup_recipients("pick_topic") and u not in app.followup_recipients("pick_topic"),
          "pick campaign targets people without links only")
    out = await step("send pick", app.send_followup(x, "pick_topic"))
    b = out[0]["attachment"]["payload"]["buttons"]
    check([y["payload"] for y in b] == ["PICK:math", "PICK:english", "PICK:saka"], "pick: 3 direction buttons")
    following["value"] = True
    out = await step("tap 🏆 Алтын сақа", app.on_payload(x, "PICK:saka"))
    check([q["payload"] for q in out[0]["quick_replies"]][0] == "G:altyn_saka:3", "pick starts the normal saka flow")
    with app.db() as con:
        con.execute("insert into profiles values (?, ?, ?) on conflict (igsid) do update set username = excluded.username",
                    (u, "parent_test", 0))
        page = app.stats.render(con, 0, app.texts())
    check('class="bc-card"' in page and 'class="bc-day' in page and "@parent_test" in page, "stats: broadcast block lists people by @username")
    check("Тренинг таңдауға көмектесейік пе?" in page and "Выбрали направление" in page, "stats: pick campaign has its own card")
    check('id="view-bc" hidden' in page and 'data-view="bc"' in page and "Рассылки <em>" in page, "stats: broadcasts live in their own tab")
    check("Тіркелдім <em>1</em>" in page, "stats: last tap counts as the answer (done)")

    # ---------- welcome flow: three questions, answers to the sheet, thanks on phone ----------
    L = app.leads
    for raw, want in [("+7 (700) 123-45-67", "+7 700 123 45 67"), ("8 700 123 45 67", "+7 700 123 45 67"),
                      ("87001234567", "+7 700 123 45 67"), ("7001234567", "+7 700 123 45 67"), ("нөмірім жоқ", None),
                      ("Астана\n3\n77000000080", "+7 700 000 00 80")]:
        check(L.find_phone(raw) == want, f"phone {raw!r} -> {want}")
    for raw, want in [("5-сынып", "5"), ("5 класс", "5"), ("5", "5"), ("3 сыныпта оқиды", "3"), ("87001234567", None),
                      ("Астана\n3\n77000000080", "3"), ("Алматы, 4, 87001234567", "4"), ("Астана\n77000000080", None),
                      ("4а", "4"), ("Экибастуз 3 сыныр 87001234567", "3"), ("5 Б", "5"), ("Үштөбе ауылы", None)]:
        check(L.find_grade(raw) == want, f"grade {raw!r} -> {want}")
    check(L.find_city("Алматы қаласынанмын") == "Алматы" and L.find_city("шымкенттен") == "Шымкент", "known cities")
    check(L.guess_city("Қаскелең") == "Қаскелең" and L.guess_city("балам 5 сыныпта оқиды, телефон 8707") is None, "village guess")

    for txt, want in [("+", True), ("+++", True), ("Керемет екен. Қалай алса болады?", True), ("Нешінші сынып", True),
                      ("Бізге 5 сынып керек қоой", True), ("Тегін емес қой", True), ("19", False), ("1800 см куб", False),
                      ("15×15×8", False), ("🔥🔥🔥", False), ("Арсен красавчик😍🔥", False), ("@demo_user_kz ❤️", False),
                      ("Результат қайдан көре аламыз?", False), ("Алтын сақа нәтиже шықпады ма?", False), ("Ок", False)]:
        check(app.wants_info(txt) == want, f"comment {txt!r} -> {'reply' if want else 'leave'}")
    app.FLOW = "welcome"
    y = "1000000000000077"
    following["value"] = False
    out = await step("welcome flow: first message from a new person", app.on_text(y, "Математика бойынша тренинг туралы толық ақпарат білгім келеді"))
    check(len(out) == 1 and out[0]["text"].startswith("Сәлеметсіз бе!\nEduApp app"), "first message: the welcome text right away, no follow gate")
    out = await step("same person writes again", app.on_text(y, "Алматы"))
    check(out == [], "welcome only once; the next message is collected as an answer")
    k = "1000000000000088"
    app.track(k, "msg")
    with app.db() as con:
        con.execute("update events set ts = ts - 3600 where igsid = ?", (k,))
    out = await step("someone already talking to a manager", app.on_text(k, "Сәлеметсіз бе, бағасы қанша?"))
    check(out == [], "people who wrote before the bot was switched on get no welcome")
    with app.db() as con:
        con.execute("delete from leads where igsid = ?", (y,))
    y = "1000000000000089"
    out = await step("welcome flow: new person", app.on_text(y, "Математика бойынша тренинг туралы толық ақпарат білгім келеді"))
    check("3. Байланыс нөміріңіз?" in out[0]["text"] and "quick_replies" not in out[0], "plain-text questions, no buttons")
    out = await step("answer: city", app.on_text(y, "Қаскелең"))
    check(out == [], "no reply to a city")
    out = await step("answer: grade with a topic word", app.on_text(y, "балам 4 сыныпта, математика керек"))
    check(out == [], "an answer mentioning «математика» is collected, not restarting the menu")
    out = await step("answer: phone", app.on_text(y, "Нөмірім 8 (700) 555 44 33"))
    check(len(out) == 1 and out[0]["text"] == "Кері байланысыңыз үшін рақмет!🙌🏻\nМенеджеріміз жақын арада сізбен байланысады.", "thanks after the phone number")
    out = await step("another message after phone", app.on_text(y, "рахмет"))
    check(out == [], "thanks only once")
    with app.db() as con:
        lead = L.get_lead(con, y)
    check(lead["city"] == "Қаскелең" and lead["grade"] == "4" and lead["phone"] == "+7 700 555 44 33" and lead["thanked"] == 1,
          f"lead row: {lead['city']}, {lead['grade']}, {lead['phone']}")
    row = L.sheet_row(lead)
    check(row["topic"] == "Математика" and row["thanked"] == "иә" and "Қаскелең | балам 4 сыныпта" in row["texts"], "sheet row")
    check(not any(str(v).startswith("=") for v in row.values()), "sheet row has no formulas (locale-proof)")
    with app.db() as con:
        check([x["igsid"] for x in L.unsynced(con)] == [y], "row waits for the sheet sync")
        L.mark_synced(con, y, lead["updated_ts"])
        check(L.unsynced(con) == [], "synced row is not sent again")

    with app.db() as con:
        page = app.stats.render(con, 7, app.texts(), sheet_url="https://docs.google.com/spreadsheets/d/x/edit")
    check('id="view-leads" hidden' in page and "Лидтер <em>1</em>" in page and "+7 700 555 44 33" in page
          and "Google кестені ашу" in page, "stats: «Лидтер» tab lists the lead with phone and sheet button")

    z = "1000000000000078"
    out = await step("welcome flow: already a follower", app.on_text(z, "«Алтын сақа» олимпиадасына дайындық туралы"))
    check(len(out) == 1 and out[0]["text"].startswith("Сәлеметсіз бе!\nEduApp app"), "follower gets the welcome text only")
    app.track("1000000000000079", "msg")  # wrote before the bot was on, so no automatic welcome
    with app.db() as con:
        con.execute("update events set ts = ts - 3600 where igsid = ?", ("1000000000000079",))
    await app.handle_event({"sender": {"id": "1000000000000079"}, "message": {"mid": "m-w1", "text": "сәлем"}})
    rec = app.followup_recipients("welcome@2026-09-30")
    check("1000000000000079" in rec and y not in rec and z not in rec, "welcome broadcast skips people who already got it")
    out = await step("welcome broadcast send", app.send_followup("1000000000000079", "welcome@2026-09-30"))
    check(out[0]["text"].startswith("Сәлеметсіз бе!\nEduApp app"), "welcome broadcast text")
    check("1000000000000079" not in app.followup_recipients("welcome@2026-10-01"), "welcome never sent twice")
    with app.db() as con:
        page = app.stats.render(con, 7, app.texts())
    check("сбор контактов: город, класс, номер" in page and "оставили номер" in page, "stats: welcome broadcast has its own card")
    app.FLOW = "menu"

    # Length limits: a stacked-button message is cut at 640, so greeting + menu must fit
    t = app.texts()
    longest_top = max(len(t["thanks_follow"]), max(len(t["hello_follower"].format(topic=t[k])) for k in ("topic_math", "topic_english", "topic_saka")))
    for key in ("math_menu", "english_menu", "saka_menu"):
        n = longest_top + 2 + len(t[key].strip())
        check(n <= 640, f"greeting + {key}: {n} chars (<=640)")
    check(all(len(t["grade_button"].format(grade=g)) <= 3 for g in "3456"), "grade buttons short enough for one row")
    for key in ["math_menu", "english_menu", "saka_menu", "links_quarter", "links_mega", "links_altyn_saka", "links_english", "after_links", "follow_gate", "not_following"]:
        n = len(app.texts()[key].encode("utf-16-le")) // 2
        check(n <= 640, f"{key}: {n} chars (<=640)")

    print("\nRESULT:", "FAILED" if check.failed else "ALL PASSED")


asyncio.run(main())
