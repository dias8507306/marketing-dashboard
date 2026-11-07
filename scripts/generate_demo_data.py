"""Generate the random demo dataset used by `python demo.py`.

Everything is relative to "today" (`ago` = days back), so the demo always looks current.
Plausible shapes, not real numbers: weekday seasonality (quiet Sundays, busy Mon-Tue), a slow
upward trend, ad spend that drives part of the leads, ~5-7 % lead->sale conversion, and an
Instagram funnel (reach > views > likes > comments > saves/shares).

    python scripts/generate_demo_data.py [--days 95] [--seed 7]
"""
import argparse
import json
import math
import random
from pathlib import Path

WEEKDAY = [1.12, 1.10, 1.04, 1.0, 0.94, 0.80, 0.70]  # Mon..Sun
CITIES = ["Алматы", "Астана", "Шымкент", "Қарағанды", "Ақтөбе", "Тараз", "Павлодар", "Өскемен", "Қостанай", "Атырау", "Қаскелең"]
TOPICS = ["Математика", "Ағылшын", "Алтын сақа"]
SOURCES = ["Таргет (Instagram / Facebook)", "Органика Instagram", "Вебинар", "Сайт"]
PRICES = [6500, 14000, 24900, 39000]
CAPTIONS = ["Олимпиадаға 30 күнде дайындық", "5 сыныпқа дейін білуі керек 7 тақырып", "Ағылшын: күніне 15 минут",
            "Ата-аналарға кеңес: үй тапсырмасы", "Алтын сақа: өткен жылғы есептер талдауы", "Логика есебі: 10 секундта шеш",
            "Оқушымыздың нәтижесі: 100/100", "Тегін вебинар: тіркелу ашық", "Математика: бөлшектерді ойын арқылы",
            "Мұғаліммен 1 күн", "Тоқсан қорытындысы: не өзгерді?", "Ағылшын: 20 жиі қолданылатын сөз"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=95)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "demo" / "demo_data.json"))
    a = ap.parse_args()
    r = random.Random(a.seed)

    days, deals, spend, nid = [], [], [], 1
    for ago in range(a.days, -1, -1):
        wd = ago % 7  # weekly cycle (the data is stored relative to today, so the phase is fixed per dataset)
        trend = 1 + (a.days - ago) / a.days * 0.25
        season = WEEKDAY[wd] * trend
        ad = round(r.uniform(9000, 24000) * (1.15 if wd < 2 else 0.85 if wd > 4 else 1) / 100) * 100
        spend.append({"ago": ago, "amount": ad})
        reach = int(r.gauss(9500, 1600) * season)
        views = int(reach * r.uniform(2.0, 2.6))
        likes = int(views * r.uniform(0.012, 0.02))
        comments = int(likes * r.uniform(0.15, 0.3))
        days.append({"ago": ago, "reach": reach, "views": views, "likes": likes, "comments": comments,
                     "saves": int(likes * r.uniform(0.06, 0.14)), "shares": int(likes * r.uniform(0.04, 0.1)),
                     "profile_views": int(reach * r.uniform(0.03, 0.06)), "total_interactions": int(likes * 1.5),
                     "accounts_engaged": int(reach * r.uniform(0.015, 0.03)), "follows": r.randint(15, 60),
                     "unfollows": r.randint(2, 12)})
        n = max(5, int(r.gauss(95, 14) * season * (0.45 if ago == 0 else 1)))  # today is not over yet
        for _ in range(n):
            target = r.random() < 0.35 + ad / 60000
            src = SOURCES[0] if target else r.choices(SOURCES[1:], (6, 2, 1))[0]
            won = r.random() < (0.07 if src == SOURCES[2] else 0.055)
            sec = int(r.triangular(8 * 3600, 23 * 3600, 20 * 3600))
            # compact row: id, ago, second of day, won, price, seconds to close, source index, responsible user
            deals.append([nid, ago, sec, int(won), r.choice(PRICES) if won else 0,
                          r.randint(1800, 3 * 86400) if won else 0, SOURCES.index(src), r.choice([501, 502, 503])])
            nid += 1

    media = []
    for i, ago in enumerate(range(1, 40, 3)):
        reels = i % 3 != 2
        v = int(r.lognormvariate(math.log(4200 if reels else 1800), 0.55))
        media.append({"id": f"demo_media_{i}", "ago": ago, "type": "REELS" if reels else "FEED", "caption": CAPTIONS[i % len(CAPTIONS)],
                      "views": v, "reach": int(v * r.uniform(0.6, 0.8)), "likes": int(v * r.uniform(0.02, 0.05)),
                      "comments": r.randint(4, 90), "saved": r.randint(5, 140), "shares": r.randint(3, 120)})

    people = []
    for i in range(140):
        ago, sec = r.randint(0, 29), r.randint(9 * 3600, 22 * 3600)
        steps = ["comment", "welcome"]
        if r.random() < 0.62: steps.append("lead_answer")
        if r.random() < 0.38: steps.append("lead_phone")
        p = {"igsid": f"demo_{1000 + i}", "username": f"parent_demo_{i:03d}", "ago": ago, "sec": sec, "steps": steps,
             "topic": r.choice(TOPICS), "city": r.choice(CITIES), "grade": str(r.randint(2, 7))}
        if "lead_phone" in steps:
            p["phone"] = f"+7 700 {r.randint(100, 999)} {r.randint(10, 99)} {r.randint(10, 99)}"
        people.append(p)

    data = {
        "plan": {"amount": 9_000_000, "leads_day": 95, "bonus_pct": 1.0},
        "followers_now": 18_400,
        "mkt_settings": {"source_field": "1000001", "sources": SOURCES[:3]},
        "sources": SOURCES,
        "deal_columns": ["id", "ago", "sec", "won", "price", "close_after", "source", "resp"],
        "staff": [{"login": "aigerim", "name": "Айгерім Нұрланқызы", "role": "smm"},
                  {"login": "dana", "name": "Дана Серікқызы", "role": "smm"},
                  {"login": "erlan", "name": "Ерлан Сапаров", "role": "lead"}],
        "tasks": [{"login": "aigerim", "title": "Рилс: олимпиада нәтижелері", "due_in": 0, "done": False},
                  {"login": "dana", "title": "Сторис: вебинар туралы еске салу", "due_in": 1, "done": False},
                  {"login": "aigerim", "title": "Таргет: жаңа креатив жүктеу", "due_in": 2, "done": False},
                  {"login": "erlan", "title": "Апталық есепті тексеру", "due_in": -1, "done": True}],
        "ig_days": days, "media": media, "deals": deals, "ad_spend": spend, "bot_people": people,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(deals)} deals, {len(days)} days, {len(media)} posts, {len(people)} bot people -> {a.out}")


if __name__ == "__main__":
    main()
