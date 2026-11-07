"""Warm words for an employee, for the director to forward: praise when the plan was closed, support when not.

Each text is put together from a few pools, so pressing «Басқа нұсқа» gives a new one.
"""
import random

PRAISE_OPEN = [
    "{name}, жарайсың! 🎉🔥",
    "{name}, сен нағыз жұлдызсың! 🌟",
    "Ураааа, {name}! 🥳🎊",
    "{name}, міне нәтиже деген! 💪😍",
    "{name}, кешегі күн — толығымен сенің күнің болды! 🏆✨",
    "{name}, сенімен мақтанамыз! 🥰👏",
    "Браво, {name}! 👏👏👏",
    "{name}, тағы да дәлелдедің — сен бәрін істей аласың! 🚀",
]
PRAISE_FACT = [
    "Жоспар {goal} лид еді, сен {leads} лид жинадың 📈 Бұл жай сан емес — бұл сенің кешегі ұқыптылығың, шыдамдылығың және әр клиентке деген ықыласың.",
    "{leads} лид! 🔥 Жоспардан да асып түстің. Әр лидтің артында бір ата-ана, бір баланың болашағы тұр — сен соларға жол ашып жатырсың 💜",
    "Кеше {leads} лид келді, ал жоспар {goal} болатын ✅ Мұндай нәтиже өздігінен келмейді, оның артында сенің үлкен еңбегің тұр.",
    "{goal} лидтік жоспар орындалды — нәтиже {leads} лид 🎯 Сен мақсат қойсаң, оны міндетті түрде орындайтыныңды тағы көрсеттің.",
    "Кешегі {leads} лид — командаға қосылған зор үлес 🙌 Сенің арқаңда EduApp күн сайын жаңа отбасыларға жетіп жатыр.",
]
STREAK = [
    "Оның үстіне қатарынан {streak} күн жоспар жабылды 🔥🔥🔥 Бұл енді кездейсоқтық емес, бұл — сенің стилің! 😎",
    "{streak} күн қатарынан! 🏅 Мұндай тұрақтылық сирек кездеседі, сен бүкіл командаға үлгісің.",
    "Қатарынан {streak} күн! 🔥 Тоқтатуға болмайтын адамсың ғой 😄",
]
PRAISE_PUSH = [
    "Осы қалпыңнан тайма! Сенің жігерің мен энергияң бүкіл командаға күш береді 💫",
    "Сенімен бір командада жұмыс істеу — үлкен бақыт 🤗 Шын жүректен рақмет!",
    "Бұл қарқынмен айлық жоспар да алыс емес, оны бірге тойлаймыз 🥂",
    "Әр күнгі еңбегің нәтижеге айналып жатыр — соны ешқашан ұмытпа 💪",
    "Біз сенің жетістігіңе шын жүректен қуанамыз, сен оған әбден лайықсың 💐",
    "Сенің нәтижең — команданың мақтанышы. Басыңды тік ұстап жүр 👑",
]
PRAISE_CLOSE = [
    "Алға, чемпион! 🏆",
    "Бүгінгі күнің де дәл осындай сәтті болсын ☀️",
    "Сенімен мақтанамыз! ❤️",
    "Жарайсың, жарайсың, жарайсың! 🎉🎉🎉",
    "Бүгін де жарқырай бер ✨",
]

SUPPORT_OPEN = [
    "{name}, сәлем! 🤗",
    "{name}, қалайсың? ☀️",
    "{name}, бір жылы сөз айтқым келді 💜",
    "{name}, кешегі күн оңай болмаған шығар 🫂",
]
SUPPORT_FACT = [
    "Кеше {leads} лид болды, жоспар {goal}. Жоспарға {pct}% жеттің — бұл да еңбек, бұл да нәтиже 👍",
    "Жоспарға дейін небәрі {left} лид қалды 📊 Бұл — бір қадамдық қашықтық қана!",
    "Кешегі нәтиже {leads} / {goal}. Әр күн бірдей бола бермейді, бұл мүлде қалыпты жағдай 🙂",
]
SUPPORT_PUSH = [
    "Сен бұрын талай рет жоспарды жапқансың, бүгін де қолыңнан келеді 💪 Біз саған толық сенеміз!",
    "Бір күннің нәтижесі сенің еңбегіңді анықтамайды. Біз сенің жұмысыңды көріп, бағалап жүрміз 💜",
    "Әр күн — жаңа мүмкіндік 🌅 Бүгін міндетті түрде өз деңгейіңе қайта шығасың!",
    "Қандай көмек керек болса, айта бер — бірге шешеміз 🤝 Сен жалғыз емессің.",
]
SUPPORT_CLOSE = [
    "Алға, {name}! Бүгін сенің күнің болсын 🚀",
    "Сенің жаныңдамыз. Сәттілік! 🍀",
    "Бүгін жаңа нәтижеге жетесің деп сенеміз ✨",
    "Жігер жоғалтпа, бәрі жақсы болады 🌈",
]


def compose(name: str, leads: int, goal: int, streak: int = 0, used=(), salt: str = "") -> tuple[str, str]:
    """(text, key): a combination this person has not had yet (key = which lines were used)."""
    first = (name or "").split()[0] if name else "Әріптес"
    d = {"name": first, "leads": leads, "goal": goal, "streak": streak,
         "pct": round(leads / goal * 100) if goal else 0, "left": max(0, goal - leads)}
    won = bool(goal) and leads >= goal
    pools = ([PRAISE_OPEN, PRAISE_FACT] + ([STREAK] if streak >= 2 else []) + [PRAISE_PUSH, PRAISE_CLOSE]) if won         else [SUPPORT_OPEN, SUPPORT_FACT if d["pct"] >= 70 else [f for f in SUPPORT_FACT if "{left}" not in f],
              SUPPORT_PUSH, SUPPORT_CLOSE]
    used = set(used)
    r = random.Random(f"{name}|{salt}|{len(used)}")
    for _ in range(500):
        idx = [r.randrange(len(p)) for p in pools]
        key = ("p" if won else "s") + ":" + "-".join(map(str, idx))
        if key not in used:
            break
    lines = [p[i].format(**d) for p, i in zip(pools, idx)]
    # greeting on its own line, the body as one paragraph, the wish at the end — reads like a message from a person
    return lines[0] + "\n\n" + " ".join(lines[1:-1]) + "\n\n" + lines[-1], key


def text(name: str, leads: int, goal: int, streak: int = 0, seed: int = 0) -> str:
    return compose(name, leads, goal, streak, salt=str(seed))[0]
