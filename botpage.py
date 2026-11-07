"""«Бот» page: what the Instagram auto-reply did — Direct welcomes, comment replies, phones collected, texts in use."""
import html
import time
from datetime import datetime, timedelta

import charts
import ui
from igdata import TZ

REPLY_LOG_FROM = 1792217108
PERIODS = [("day", "Күн"), ("7d", "7 күн"), ("30d", "30 күн")]
MONTHS = ["қаң", "ақп", "нау", "сәу", "мам", "мау", "шіл", "там", "қыр", "қаз", "қар", "жел"]

CSS = """<style>""" + ui.KIT + ui.PAGES + """
.bh{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin:0 0 18px}
.segs{display:flex;gap:4px;padding:4px;border-radius:12px;background:var(--surface2)}
.segs a{padding:7px 14px;border-radius:9px;font-weight:600;color:var(--muted)}.segs a.on{background:var(--surface);color:var(--text);box-shadow:var(--shadow)}
.kgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.k .kv{font-size:2rem}.k .ksub{min-height:18px}
.two{display:grid;grid-template-columns:1.2fr 1fr;gap:18px;margin-top:18px}
.funnel{display:grid;gap:12px}.fr{display:grid;grid-template-columns:170px 1fr 60px;gap:12px;align-items:center;font-weight:600}
.fr .bar{height:12px;border-radius:999px;background:var(--bar);overflow:hidden}.fr .bar i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#7336F7,#9B6BFF)}
.fr span:last-child{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.days{display:flex;align-items:flex-end;gap:6px;height:140px;margin-top:8px}
.days .d{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;height:100%;justify-content:flex-end}
.days .col{width:100%;max-width:26px;display:flex;flex-direction:column-reverse;border-radius:8px 8px 4px 4px;overflow:hidden;background:var(--surface2);min-height:4px}
.days .w{background:#7648c3}.days .c{background:#f35b2f}.days .p{background:#048848}.days small{font-size:0.6875rem;color:var(--faint)}
.legend{display:flex;gap:14px;font-size:0.75rem;color:var(--muted);margin-top:10px}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.feed{display:grid;gap:8px;max-height:460px;overflow:auto}.ev{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:14px;background:var(--surface2)}
.ev .dot{width:9px;height:9px;border-radius:50%;margin-top:6px;flex:none}.ev b{font-weight:600}.ev small{display:block;color:var(--faint);font-size:0.75rem}
.texts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:18px}
.texts pre{white-space:pre-wrap;margin:0;padding:14px;border-radius:14px;background:var(--surface2);border:0;font:500 0.8125rem/1.55 Golos Text,sans-serif}
.rules{margin:0;padding-left:18px;color:var(--muted);display:grid;gap:6px}.rules b{color:var(--text)}
.status{display:inline-flex;align-items:center;gap:8px;font-weight:700}.status i{width:10px;height:10px;border-radius:50%}
table.ld td,table.ld th{text-align:left}
.sg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.sg div{padding:12px;border-radius:14px;background:var(--surface2)}.sg small{display:block;color:var(--faint);font-size:0.75rem}.sg b{font-size:1.375rem;font-weight:800}
.sf2{display:flex;gap:8px;margin-top:14px}.sf2 input{flex:1;height:42px;padding:0 12px;border-radius:12px;border:1.5px solid var(--border);background:var(--surface2);color:var(--text);font:500 0.875rem Golos Text,sans-serif}
@media (max-width:720px){.sg{grid-template-columns:1fr 1fr}}
.cmpn{margin:10px 4px 0;font-size:0.75rem;color:var(--faint)}
.ctl{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}.cbox{padding:14px;border-radius:18px;background:var(--surface2);display:grid;gap:8px;align-content:start}
.cbox p{margin:0}.cbox small{color:var(--faint);font-size:0.75rem}.cbox .qn{font-size:0.75rem;color:var(--muted);line-height:1.5;max-height:140px;overflow:auto}
.cbox .btnp,.cbox .btng{height:38px}
.tg{display:grid;grid-template-columns:1.1fr 1fr;gap:16px}.tg2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.tl{display:grid;gap:6px;margin-bottom:12px}.tl b{font-size:0.875rem}.tl small{color:var(--faint);font-size:0.75rem}
.tl textarea,.tl input{width:100%;font:500 0.875rem/1.5 Golos Text,sans-serif;padding:12px;border-radius:14px;border:1.5px solid var(--border);background:var(--surface2);color:var(--text);resize:vertical}
.tl textarea:focus,.tl input:focus{outline:0;border-color:var(--accent)}
.tl pre{white-space:pre-wrap;margin:0;padding:12px;border-radius:14px;background:var(--surface2);border:0;font:500 0.8125rem/1.55 Golos Text,sans-serif}
.tf{display:grid;gap:4px}.tf .btnp{justify-self:start;margin-top:4px}
.rule{padding:14px;border-radius:18px;background:var(--surface2);margin-bottom:12px}.rule .tl pre{background:var(--surface)}
.rp{display:flex;align-items:center;gap:12px;min-width:0;color:var(--text)!important}.rp img,.rp .noimg{width:64px;height:80px;border-radius:12px;object-fit:cover;flex:none;background:var(--surface);display:grid;place-items:center;color:var(--faint)}
.rp span{display:grid;gap:3px;min-width:0}.rp b{font-weight:700;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}.rp small{color:var(--accent);font-size:0.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rp:hover b{text-decoration:underline}
.rule .tg2{align-items:start}.rule .rs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.rule .rh{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:10px;font-weight:600}.rule .rh a{color:var(--accent)}
@media (max-width:980px){.tg,.tg2{grid-template-columns:1fr}}
@media (max-width:980px){.kgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.two,.texts{grid-template-columns:1fr}}
</style>"""

EV = {  # event -> (colour, text)
    "welcome": ("#7648c3", "Direct-ке сәлемдесу мәтіні жіберілді"),
    "welcome:comment": ("#2A78D6", "комментарийден кейін Direct-ке мәтін жіберілді"),
    "comment": ("#f35b2f", "ақпарат сұрап комментарий жазды"),
    "comment_reply": ("#f35b2f", "комментарийіне жауап жазылды"),
    "lead_phone": ("#048848", "телефон нөмірін қалдырды"),
    "lead_answer": ("#9aa0b4", "сұрақтарға жауап берді"),
    "fu_sent": ("#fec200", "бот қосылмай тұрып жазған: мәтін кейін жіберілді"),
}


def bounds(period: str, anchor: datetime):
    n = {"day": 1, "7d": 7, "30d": 30}[period]
    last = anchor
    first = last - timedelta(days=n - 1)
    return first, last


KINDS = ("msg", "welcome", "rule_dm", "comment", "comment_reply", "lead_answer", "lead_phone", "welcome_fail", "comment_reply_fail", "dm_fail")


def load(con, a: int, b: int) -> list:
    """All bot events of [a, b) in one query; the page counts them in memory (each query is a round trip)."""
    marks = ", ".join("?" * len(KINDS))
    return con.execute(f"select ts, igsid, event, detail from events where ts >= ? and ts < ?"
                       f" and (event in ({marks}) or event like 'fu_sent:welcome%')", (a, b, *KINDS)).fetchall()


def numbers(rows: list, a: int, b: int) -> dict:
    r = [x for x in rows if a <= x[0] < b]

    def people(ev):
        return len({x[1] for x in r if x[2] == ev})

    def n(pred):
        return sum(1 for x in r if pred(x))
    return {
        "wrote": people("msg"),
        "welcome_dm": n(lambda x: x[2] == "welcome" and x[3] != "comment"),
        "welcome_cm": n(lambda x: (x[2] == "welcome" and x[3] == "comment") or x[2] == "rule_dm"),
        "late": n(lambda x: x[2].startswith("fu_sent:welcome")),
        "comments": n(lambda x: x[2] == "comment"),
        # replies were not logged separately before REPLY_LOG_FROM: there every handled comment got its reply
        "replies": n(lambda x: x[2] == "comment_reply" or (x[2] == "comment" and x[0] < REPLY_LOG_FROM)),
        "answered": people("lead_answer"),
        "phones": people("lead_phone"),
        "fails": n(lambda x: x[2] in ("welcome_fail", "comment_reply_fail", "dm_fail")),
    }


SPEED_CARD = """
<article class="card cardin" style="--i:7;margin-top:18px"><div class="ch"><h2>Менеджерлердің жауап беру жылдамдығы</h2><span class="meta">Direct, соңғы 7 күн, боттың хабарламалары есептелмейді</span></div>
<div class="spd" id="spd">Есептеп жатыр…</div>
<form method="get" action="/person" class="sf2"><input name="q" placeholder="Адамды іздеу: @username немесе телефон"><button class="btng" type="submit">Іздеу</button></form>
</article>
<script>(async function(){var e=document.getElementById('spd');try{var d=await (await fetch('/bot/speed')).json();
e.innerHTML='<div class="sg"><div><small>Жауап берілген чат</small><b>'+d.answered+'</b></div><div><small>Орташа жауап уақыты</small><b>'+(d.median_min==null?'—':d.median_min+' мин')+'</b></div>'+
'<div><small>15 минут ішінде</small><b>'+(d.within_15==null?'—':d.within_15+'%')+'</b></div><div><small>1 сағаттан көп күтіп тұр</small><b style="color:'+(d.waiting_count?'#f35b2f':'inherit')+'">'+d.waiting_count+'</b></div></div>'+
(d.waiting.length?'<p class="note">Жауап күтіп тұрғандар: '+d.waiting.map(function(x){return '@'+(x.user||'?')+' ('+x.hours+' сағ)'}).join(', ')+'</p>':'')}catch(x){e.textContent='Есептеу мүмкін болмады'}})()</script>"""


def mask(phone):
    return "—" if not phone else phone[:-5].rstrip() + " ** **"


def control_card(c: dict) -> str:
    """Admin panel: bot switch, Instagram limit, queue, missed comments, who sees phone numbers."""
    on = c.get("on")
    until = c.get("blocked_until") or 0
    lim = (f'<span class="ptag" style="--c:#f35b2f">Instagram шектеуі бар · {datetime.fromtimestamp(until, TZ):%H:%M} дейін күтеміз</span>'
           if until else '<span class="ptag" style="--c:#048848">Instagram шектеуі жоқ</span>')
    names = ", ".join("@" + html.escape(n) if not n.startswith("…") else n for n in c.get("queue_names", []))
    more = c.get("queue", 0) - len(c.get("queue_names", []))

    confirm = {"queue_clear": f"Кезекті тазалау керек пе?|Кезектегі {c.get('queue', 0)} адамға хабарлама жіберілмейді. Бұл әрекетті қайтару мүмкін емес.|Тазалау",
               "backlog_send": "Барлығына жауап беру керек пе?|Соңғы 7 күндегі жауапсыз комменттердің бәріне бот жауап жазады. Жіберілген хабарламаны қайтару мүмкін емес.|Жіберу"}

    def btn(action, label, cls="btng", extra=""):
        cf = f' data-confirm="{html.escape(confirm[action])}"' if action in confirm else ""
        return (f'<form method="post" action="/bot/control" style="display:inline"{cf}><input type="hidden" name="action" value="{action}">{extra}'
                f'<button class="{cls}" type="submit">{label}</button></form>')
    return f"""<article class="card cardin" id="control" style="--i:4;margin-top:18px"><div class="ch"><h2>Басқару</h2><span class="meta">тек әкімшіге көрінеді</span></div>
<div class="ctl"><div class="cbox"><b>Бот</b><p>{'<span class="ptag" style="--c:#048848">қосулы — жауап береді</span>' if on else '<span class="ptag" style="--c:#f35b2f">өшірулі — тек санайды</span>'}</p>
{btn("off", "Өшіру") if on else btn("on", "Қосу", "btnp")}</div>
<div class="cbox"><b>Кілт сөз режимі</b><p>{'<span class="ptag" style="--c:#048848">қосулы</span>' if c.get("kw") else '<span class="ptag" style="--c:#f35b2f">өшірулі</span>'}</p>
{btn("kw_off", "Өшіру") if c.get("kw") else btn("kw_on", "Қосу", "btnp")}<small>Бот өшірулі кезде де: «сақа», «дайындық» деген комментке Direct-ке вебинар мәтіні, комментке «Толық ақпаратты direct-ке жібердік».</small></div>
<div class="cbox"><b>Instagram</b><p>{lim}</p><small>Шектеу кезінде бот Direct-ке жазбайды, комментке «Direct-ке жазыңыз» дейді.</small></div>
<div class="cbox"><b>Кезек: {c.get("queue", 0)} адам</b><p class="qn">{names or "бос"}{f" және тағы {more}" if more > 0 else ""}</p>
{btn("queue_send", "Жіберуді бастау", "btnp") if c.get("queue") else ""} {btn("queue_clear", "Тазалау") if c.get("queue") else ""}
<small>Әр 2 минутта бір хабарлама, тек бот қосулы кезде.</small></div>
<div class="cbox"><b>Жауапсыз комменттер</b><p><button class="btng" type="button" id="blcheck">Тексеру</button></p><div id="bllist" class="qn"></div>
{btn("backlog_send", "Бәріне жауап беру", "btnp")}<small>Соңғы 7 күн, ақпарат сұраған комменттер.</small></div>
<div class="cbox"><b>Телефон нөмірлері</b><p>{'қызметкерлер көреді' if c.get("see_phones", True) else 'қызметкерлерге жасырылған'}</p>
{btn("phones", "Жасыру", extra='<input type="hidden" name="v" value="0">') if c.get("see_phones", True) else btn("phones", "Көрсету", extra='<input type="hidden" name="v" value="1">')}</div></div>
<script>document.getElementById('blcheck').onclick=async function(){{var l=document.getElementById('bllist');l.textContent='Тексеріп жатыр…';
try{{var r=await fetch('/bot/backlog');var d=await r.json();l.innerHTML=d.length?d.slice(0,15).map(function(x){{return '@'+(x.user||'?')+': '+x.text.replace(/[<>&]/g,'')}}).join('<br>')+(d.length>15?'<br>… барлығы '+d.length:''):'Жауапсыз коммент жоқ'}}catch(e){{l.textContent='Қате, қайта басыңыз'}}}}</script></article>"""


def fix(n: dict) -> dict:
    """A late (broadcast) welcome is also logged as «welcome»: count it once, under «кейін»."""
    n["welcome_dm"] = max(0, n["welcome_dm"] - n["late"])
    return n


def render(con, texts: dict, enabled: bool, period: str, anchor: datetime, today: datetime, user: dict | None,
           rules: list | None = None, note: str = "", control: dict | None = None, picked: tuple | None = None) -> str:
    is_admin = (user or {}).get("r") == "admin"
    control = control or {}
    hide_phone = not is_admin and not control.get("see_phones", True)
    first, last = picked or bounds(period, anchor)
    a, b = int(first.timestamp()), int((last + timedelta(days=1)).timestamp())
    pa, pb = int((first - (last - first) - timedelta(days=1)).timestamp()), a
    # a period that is still running is compared with the same stretch of the previous one (today until now ↔
    # yesterday until this hour), never with the whole previous period — otherwise every morning reads «▼100%»
    now_ts = int(time.time())
    partial = a <= now_ts < b
    if partial:
        pb = min(pb, pa + (now_ts - a))
    t14 = int((today - timedelta(days=27)).timestamp())  # 14 days for the line and the 14 before them for the dotted one
    rows = load(con, min(pa, t14), max(b, int((today + timedelta(days=1)).timestamp())))
    n = fix(numbers(rows, a, b))
    p = fix(numbers(rows, pa, pb))
    sent = n["welcome_dm"] + n["welcome_cm"] + n["late"]
    psent = p["welcome_dm"] + p["welcome_cm"] + p["late"]

    def pct(x, y):
        return None if not y else round((x - y) / y * 100)

    def kpi(i, label, val, prev, color, ic, sub):
        return (f'<article class="k cardin" style="--i:{i};--c:{color}"><div class="kh"><span class="chip">{ui.icon(ic)}</span>'
                f'<span class="kl">{label}</span>{ui.pill_pct(pct(val, prev))}</div><div class="kv">{f"{val:,}".replace(",", " ")}</div>'
                f'<p class="ksub">{sub}</p></article>')

    conv = round(n["phones"] / sent * 100) if sent else None
    kpis = (kpi(1, "Бот жазды", sent, psent, "#7336F7", "users", f'Direct {n["welcome_dm"]} · коммент арқылы {n["welcome_cm"]} · кейін {n["late"]}')
            + kpi(2, "Комментке жауап", n["replies"], p["replies"], "#f35b2f", "instagram", f'ақпарат сұраған коммент: {n["comments"]}')
            + kpi(3, "Телефон қалдырды", n["phones"], p["phones"], "#048848", "check", f'жауап бергендер: {n["answered"]} · конверсия {conv if conv is not None else "—"}%')
            + kpi(4, "Direct-ке жазғандар", n["wrote"], p["wrote"], "#2A78D6", "chart", "бот қосылғанға дейінгілерді қоса, барлығы"))

    cmp_note = ('<p class="note cmpn">Пайыз — ' + ("кешегі осы уақытқа дейінгі" if period == "day" else "алдыңғы кезеңнің дәл осы уақытқа дейінгі")
                + ' көрсеткішпен салыстыру.</p>') if partial else ""

    # funnel
    steps = [("Бот жазды", sent), ("Жауап берді", n["answered"]), ("Телефон қалдырды", n["phones"])]
    top = max(sent, 1)
    funnel = charts.funnel(steps)
    if n["fails"]:
        funnel += f'<p class="note">Жіберілмеген хабарлама: {n["fails"]} (Instagram қабылдамады)</p>'

    # 14 days
    days = [today - timedelta(days=i) for i in range(27, -1, -1)]
    vals = []
    for d in days:
        da, db = int(d.timestamp()), int((d + timedelta(days=1)).timestamp())
        day = [x for x in rows if da <= x[0] < db]
        w = sum(1 for x in day if x[2] == "welcome")  # a late welcome is logged as «welcome» too
        c = sum(1 for x in day if x[2] == "comment_reply" or (x[2] == "comment" and x[0] < REPLY_LOG_FROM))
        ph = len({x[1] for x in day if x[2] == "lead_phone"})
        wr = len({x[1] for x in day if x[2] == "msg"})
        vals.append((d, w, c, ph, wr))
    labels = [f"{d.day} {MONTHS[d.month - 1]}" for d, *_ in vals[14:]]

    def ser(tab, idx):
        cur, prv = [v[idx] for v in vals[14:]], [v[idx] for v in vals[:14]]
        return {"tab": tab, "label": f"{tab} · 14\u00a0күн", "cur": cur, "prev": prv, "total": sum(cur), "delta": charts.delta(sum(cur), sum(prv)), "unit": "", "unitBig": ""}
    canvas = charts.CSS + charts.canvas("Бот · 14\u00a0күн", [ser("Бот жазды", 1), ser("Комментке жауап", 2), ser("Телефон", 3), ser("Direct-ке жазғандар", 4)],
                                        labels, prev_label="алдыңғы 14 күнмен", last_label="бүгін") + charts.JS

    # feed
    rows = con.execute("select e.ts, e.igsid, e.event, e.detail, p.username from events e left join profiles p on p.igsid = e.igsid"
                       " where (e.event in ('welcome', 'comment_reply', 'lead_phone', 'lead_answer') or e.event like 'fu_sent:welcome%')"
                       " and e.ts >= ? and e.ts < ? order by e.ts desc limit 60", (a, b)).fetchall()
    feed = ""
    for ts, igsid, ev, detail, username in rows:
        key = "fu_sent" if ev.startswith("fu_sent") else ("welcome:comment" if ev == "welcome" and detail == "comment" else ev)
        color, label = EV.get(key, ("#9aa0b4", ev))
        who = f"@{html.escape(username)}" if username else f"..{igsid[-4:]}"
        when = datetime.fromtimestamp(ts, TZ)
        feed += f'<div class="ev"><span class="dot" style="background:{color}"></span><div><b>{who}</b> — {label}<small>{when:%d.%m %H:%M}</small></div></div>'
    feed = feed or '<p class="note">Бұл кезеңде әрекет болған жоқ.</p>'

    # leads collected
    try:
        lrows = con.execute("select l.username, l.city, l.grade, l.phone, l.updated_ts from leads l where l.updated_ts >= ? and l.updated_ts < ?"
                            " and (l.phone is not null or l.city is not null or l.grade is not null) order by l.updated_ts desc limit 15", (a, b)).fetchall()
    except Exception:
        lrows = []
    ltable = "".join(f'<tr><th scope="row">{"@" + html.escape(u) if u else "—"}</th><td>{html.escape(c or "—")}</td><td>{html.escape(str(g or "—"))}</td>'
                     f'<td>{html.escape(mask(ph) if hide_phone else (ph or "—"))}</td><td>{datetime.fromtimestamp(t, TZ):%d.%m %H:%M}</td></tr>' for u, c, g, ph, t in lrows)
    leads_card = (f'<article class="card cardin" style="--i:8;margin-top:18px"><div class="ch"><h2>Жиналған жауаптар</h2><span class="meta">Google кестеге де түседі</span></div>'
                  f'<div class="tw"><table class="ld"><thead><tr><th>Instagram</th><th>Қала</th><th>Сынып</th><th>Телефон</th><th>Уақыты</th></tr></thead><tbody>'
                  f'{ltable or "<tr><td colspan=5>Бұл кезеңде жауап болған жоқ</td></tr>"}</tbody></table></div></article>')

    def tx(k):
        return html.escape(str(texts.get(k) or "").strip())

    def box(k, title, rows=8, hint=""):
        if is_admin:
            return (f'<label class="tl"><b>{title}</b>{f"<small>{hint}</small>" if hint else ""}'
                    f'<textarea name="{k}" rows="{rows}">{tx(k)}</textarea></label>')
        return f'<div class="tl"><b>{title}</b><pre>{tx(k) or "—"}</pre></div>'
    form_a, form_b = ('<form method="post" action="/bot/texts" class="tf">', '<button class="btnp" type="submit">Мәтіндерді сақтау</button></form>') if is_admin else ("<div>", "</div>")
    texts_html = (f'<article class="card cardin" id="texts" style="--i:9"><div class="ch"><h2>Бот мәтіндері</h2>'
                  f'<span class="meta">{"өзгертсеңіз, бот 20 секундта жаңа мәтінмен жазады" if is_admin else "мәтіндерді әкімші өзгертеді"}</span></div>{form_a}'
                  f'<div class="tg">{box("welcome_text", "Direct: бірінші хабарлама", 12)}'
                  f'<div>{box("welcome_extra", "Бірінші хабарламаға қосымша (мысалы, вебинар)", 5, "белгілі бір күнге дейін ғана қосылады")}'
                  f'{box("welcome_extra_until", "Қосымша қай күнге дейін (ЖЖЖЖ-АА-КК)", 1)}'
                  f'{box("comment_reply", "Комментке жауап", 3)}'
                  f'{box("comment_reply_blocked", "Комментке жауап, Instagram Direct-ті уақытша шектегенде", 3, "Direct-ке жіберу мүмкін болмаған кезде осы жазылады")}'
                  f'{box("lead_thanks", "Телефон келгенде", 3)}</div></div>{form_b}</article>')
    rl = ""
    for r in rules or []:
        pic = (f'<img src="{html.escape(r["thumb"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if r.get("thumb")
               else f'<span class="noimg">{ui.icon("instagram")}</span>')
        rl += (f'<div class="rule"><div class="rh"><a class="rp" href="{html.escape(r.get("link") or "#")}" target="_blank" rel="noopener">{pic}'
               f'<span><b>{html.escape(r.get("caption") or "Instagram пост")}</b><small>{html.escape(r.get("link") or "")} ↗</small></span></a>'
               + (f'<form method="post" action="/bot/rules"><input type="hidden" name="action" value="delete"><input type="hidden" name="media_id" value="{html.escape(r["media_id"])}">'
                  f'<button class="btng" type="submit">Өшіру</button></form>' if is_admin else "")
               + f'</div><div class="rs"><span class="ptag" style="--c:#7336F7">кілт сөз: {html.escape(r.get("keyword") or "кез келген коммент")}</span>'
               f'<span class="ptag" style="--c:#f35b2f">комментке жауап: {(r.get("stats") or {}).get("replies", 0)}</span>'
               f'<span class="ptag" style="--c:#048848">Direct-ке жіберілді: {(r.get("stats") or {}).get("sent", 0)}</span>'
               + (f'<span class="ptag" style="--c:#b07b00">кезекте: {r["stats"]["queued"]}</span>' if (r.get("stats") or {}).get("queued") else "")
               + f'</div><div class="tg2"><div class="tl"><b>Комментке жауап</b><pre>{html.escape(r.get("reply") or "")}</pre></div>'
               f'<div class="tl"><b>Direct-ке</b><pre>{html.escape(r.get("dm") or "")}</pre></div></div></div>')
    add = ("""<form method="post" action="/bot/rules" class="tf"><b>Жаңа пост қосу</b>
<div class="tg2"><label class="tl"><small>Посттың сілтемесі</small><input name="link" placeholder="https://www.instagram.com/p/..." required></label>
<label class="tl"><small>Кілт сөз (бос қалса — әр комментке)</small><input name="keyword" placeholder="мысалы: дайындық"></label></div>
<div class="tg2"><label class="tl"><small>Комментке жауап</small><textarea name="reply" rows="3">Сәлеметсіз бе! Сілтемені direct-ке жібердік📩</textarea></label>
<label class="tl"><small>Direct-ке жіберілетін мәтін</small><textarea name="dm" rows="6" required></textarea></label></div>
<button class="btnp" type="submit">Постты қосу</button></form>""" if is_admin else "")
    rules_html = (f'<article class="card cardin" id="rules" style="--i:10;margin-top:18px"><div class="ch"><h2>Арнайы посттар</h2>'
                  f'<span class="meta">бұл посттардағы әр комментке осы мәтіндер кетеді (жалпы мәтіннің орнына)</span></div>'
                  f'{rl or "<p class=note>Әзірге арнайы пост жоқ.</p>"}{add}</article>')
    howto = ('<article class="card cardin" style="--i:11;margin-top:18px"><div class="ch"><h2>Бот қалай жұмыс істейді</h2></div><ul class="rules">'
             '<li><b>Direct:</b> адам алғаш рет жазғанда бірінші хабарлама бірден кетеді, бір адамға бір-ақ рет.</li>'
             '<li>Бұрын бізбен жазысқан адамдарға жазбайды — олар менеджерде.</li>'
             '<li><b>Коммент:</b> «+» немесе ақпарат сұраған комментке жауап береді; арнайы посттарда — әр комментке.</li>'
             '<li>Есептің жауабына, эмодзиге, мақтауға, нәтиже туралы сұраққа жауап бермейді — бұлар менеджерге.</li>'
             '<li>Жауаптар Google кестеге жазылады, телефон келгенде алғыс айтады. Әрі қарай — менеджер.</li></ul></article>')
    texts_html += rules_html + howto

    segs = "".join(f'<a class="{"on" if p_ == period else ""}" href="?p={p_}&d={anchor:%Y-%m-%d}">{t}</a>' for p_, t in PERIODS)
    prev_d, next_d = (anchor - timedelta(days=1)).strftime("%Y-%m-%d"), (anchor + timedelta(days=1)).strftime("%Y-%m-%d")
    n_days = (last - first).days + 1
    prev_href = f"?p=range&d1={first - timedelta(days=n_days):%Y-%m-%d}&d2={first - timedelta(days=1):%Y-%m-%d}" if picked else f"?p={period}&d={prev_d}"
    next_href = f"?p=range&d1={next_d}&d2={min(last + timedelta(days=n_days), today):%Y-%m-%d}" if picked else f"?p={period}&d={next_d}"
    span = (f"{first.day} {MONTHS[first.month - 1]}" if first == last else f"{first.day} {MONTHS[first.month - 1]} – {last.day} {MONTHS[last.month - 1]}")
    status = ('<span class="status"><i style="background:#22c55e"></i>Бот қосулы</span>' if enabled
              else '<span class="status"><i style="background:#fec200"></i>Тек кілт сөз: сақа, дайындық</span>' if (control or {}).get("kw")
              else '<span class="status"><i style="background:#f35b2f"></i>Бот өшірулі</span>')
    return f"""<!doctype html><html lang="kk"><head>{ui.HEAD}{ui.FONT}<title>Бот · EduApp</title>{ui.STYLE}{CSS}</head><body>
{ui.topbar(user, "bot")}<main class="wrap">
<section class="ph cardin"><div><h1>Instagram бот</h1><p>Direct-тегі автожауап пен комменттерге жауап · {span}</p>
<div class="stats"><span>{status}</span><span>@eduapp_demo</span></div></div></section>
<div class="bh"><div class="segs">{segs}</div>{ui.date_range(first, last, today, prev_href, next_href if anchor < today else None, "?p=day&d=@")}</div>
<section class="kgrid">{kpis}</section>{cmp_note}
{canvas}
<div class="two"><article class="card cardin" style="--i:5"><div class="ch"><h2>Воронка</h2><span class="meta">{span}</span></div>{funnel}
</article>
<article class="card cardin" style="--i:6"><div class="ch"><h2>Соңғы әрекеттер</h2></div><div class="feed">{feed}</div></article></div>
{control_card(control) if is_admin else ""}
{SPEED_CARD}
{leads_card}
{f'<div class="msg ok" style="margin-top:18px">{html.escape(note)}</div>' if note else ""}
<div style="margin-top:18px">{texts_html}</div>
</main>{ui.THEME_JS}{ui.KIT_JS}</body></html>"""
