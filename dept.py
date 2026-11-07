"""Marketing department: roles, the one shared monthly plan (draft → approved), tasks and the change log.

Roles (session "r"): admin = the owner (super admin, from the environment login), lead = head of marketing
(Ерлан), smm = marketers (Айгерім, Дана). The plan belongs to the whole department, not to a person:
kv `dept_plan` = {"YYYY-MM": {"draft": {...}, "approved": {...}}}. Only an approved plan drives the overview,
the bonus and the reports; a draft is what the lead is still working on.
"""
import html
import json
import secrets
import time
from datetime import datetime

import amo
import home
import igdata
import ui

PERMS = {
    "admin": {"*"},
    "lead": {"dept.edit", "dept.approve", "tasks.edit", "ads", "view"},
    "smm": {"view", "tasks.own"},
}
ROLES = [("smm", "Маркетолог"), ("lead", "Маркетинг жетекшісі")]
MONTHS = ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан"]
FIELDS = (("amount", "Айлық сатылым жоспары, ₸"), ("leads_day", "Күндік лид жоспары"), ("bonus_pct", "Бонус, % сатылымнан"))


def can(user: dict | None, perm: str) -> bool:
    p = PERMS.get((user or {}).get("r"), set())
    return "*" in p or perm in p


_READY = False


def ensure_tables(con):
    global _READY
    if _READY:
        return
    _READY = True
    con.execute("create table if not exists tasks (id text primary key, login text, title text, due text,"
                " status text, created_by text, ts bigint, done_ts bigint)")
    con.execute("create table if not exists audit (ts bigint, actor text, action text, target text, detail text)")


def log(con, actor: str, action: str, target: str = "", detail: str = ""):
    ensure_tables(con)
    con.execute("insert into audit values (?, ?, ?, ?, ?)", (int(time.time()), actor, action, target, detail[:500]))


def month_key(day) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def plans_all(con) -> dict:
    return amo.kv_get(con, "dept_plan", {}) or {}


def plan_for(con, day) -> dict | None:
    """The approved plan for the month of `day`; else the latest approved one before it."""
    allp = plans_all(con)
    key = month_key(day)
    for k in sorted(allp, reverse=True):
        if k <= key and (allp[k] or {}).get("approved"):
            return allp[k]["approved"]
    return None


def clean(fields: dict) -> dict:
    def num(k, cast=int):
        raw = str(fields.get(k) or "").replace(" ", "").replace(" ", "").replace(",", ".")
        if cast is int:
            raw = "".join(ch for ch in raw if ch.isdigit())
        try:
            return cast(raw or 0)
        except ValueError:
            return 0
    amount = num("amount")
    return {"amount": amount if amount >= 1000 else 0, "leads_day": num("leads_day") or 100,
            "bonus_pct": max(0.0, min(100.0, num("bonus_pct", float)))}


def save_draft(con, month: str, fields: dict, actor: str):
    allp = plans_all(con)
    cur = allp.get(month) or {}
    cur["draft"] = {**clean(fields), "by": actor, "at": int(time.time())}
    allp[month] = cur
    amo.kv_set(con, "dept_plan", allp)
    d = cur["draft"]
    log(con, actor, "plan.draft", month, f"сатылым {d['amount']}, лид/күн {d['leads_day']}, бонус {d['bonus_pct']}%")


def approve(con, month: str, actor: str) -> bool:
    allp = plans_all(con)
    cur = allp.get(month) or {}
    if not cur.get("draft"):
        return False
    cur["approved"] = {**{k: cur["draft"][k] for k, _ in FIELDS}, "by": actor, "at": int(time.time())}
    allp[month] = cur
    amo.kv_set(con, "dept_plan", allp)
    log(con, actor, "plan.approve", month)
    return True


# ---- personal plans: kv `staff_plan` = {"YYYY-MM": {"draft": {login: {...}}, "approved": {login: {...}}, "by", "at"}};
# each person's own monthly targets, measured against the department's shared result
PFIELDS = (("amount", "Айлық сатылым, ₸"), ("leads_day", "Күндік лид"))


def people_all(con) -> dict:
    return amo.kv_get(con, "staff_plan", {}) or {}


def person_plan_for(con, login: str, day) -> dict | None:
    """`login`'s approved personal plan for the month of `day`; else their latest approved one before it."""
    allp = people_all(con)
    key = month_key(day)
    for k in sorted(allp, reverse=True):
        p = ((allp[k] or {}).get("approved") or {}).get(login)
        if k <= key and p and p.get("amount"):
            return p
    return None


def save_people(con, month: str, fields: dict, people: dict, actor: str, approve_too: bool):
    """`people` = {login: name} of everyone who gets a plan."""
    allp = people_all(con)
    cur = allp.get(month) or {}
    draft = {}
    for lg in people:
        c = clean({"amount": fields.get(f"amount__{lg}"), "leads_day": fields.get(f"leads__{lg}")})
        draft[lg] = {"amount": c["amount"], "leads_day": c["leads_day"]}
    cur["draft"] = draft
    if approve_too:
        cur["approved"], cur["by"], cur["at"] = {k: dict(v) for k, v in draft.items()}, actor, int(time.time())
    allp[month] = cur
    amo.kv_set(con, "staff_plan", allp)
    log(con, actor, "pplan.approve" if approve_too else "pplan.draft", month,
        "; ".join(f"{people[lg]}: {home.money(v['amount'])}, {v['leads_day']} лид/күн" for lg, v in draft.items()))


def seed_from_staff(con, staff: list, day):
    """First run: the plan the admin had set per person becomes the approved department plan, so nothing changes."""
    if plans_all(con):
        return
    src = next((s["plans"] for s in staff if (s.get("plans") or {}).get("amount")), None)
    if src:
        p = {**clean(src), "by": "көшірілді", "at": int(time.time())}
        amo.kv_set(con, "dept_plan", {month_key(day): {"draft": dict(p), "approved": dict(p)}})


# ---- tasks
def add_task(con, login: str, title: str, due: str, actor: str):
    ensure_tables(con)
    tid = secrets.token_hex(6)
    con.execute("insert into tasks values (?, ?, ?, ?, 'todo', ?, ?, null)", (tid, login, title[:200], due or "", actor, int(time.time())))
    log(con, actor, "task.add", login, title[:120])


def set_task(con, tid: str, status: str, actor: str, own_only: str | None = None) -> bool:
    ensure_tables(con)
    row = con.execute("select login, title from tasks where id = ?", (tid,)).fetchone()
    if not row or (own_only and row[0] != own_only) or status not in ("todo", "done", "deleted"):
        return False
    if status == "deleted":
        con.execute("delete from tasks where id = ?", (tid,))
    else:
        con.execute("update tasks set status = ?, done_ts = ? where id = ?", (status, int(time.time()) if status == "done" else None, tid))
    log(con, actor, "task." + status, row[0], row[1][:120])
    return True


def tasks(con, login: str | None = None) -> list:
    ensure_tables(con)
    q = "select id, login, title, due, status, created_by, ts from tasks" + (" where login = ?" if login else "") + " order by status desc, due, ts desc"
    return [dict(zip(("id", "login", "title", "due", "status", "by", "ts"), r)) for r in con.execute(q, (login,) if login else ())]


def audit_rows(con, limit=20) -> list:
    ensure_tables(con)
    return list(con.execute("select ts, actor, action, target, detail from audit order by ts desc limit ?", (limit,)))


# ---- page
CSS = """<style>
.ppl{display:grid;margin-top:14px}.ppr{display:grid;grid-template-columns:minmax(0,1.2fr) 1fr 1fr;gap:12px;align-items:baseline;padding:12px 0;border-top:1px solid var(--border)}.ppr span{font-size:1.25rem;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}.ppr small{display:block;font-size:.75rem;font-weight:500;color:var(--faint);letter-spacing:0}.ppn{font-weight:600}.ppe{display:grid;grid-template-columns:minmax(0,.8fr) 1fr 1fr;gap:12px;align-items:end;margin-bottom:12px}.ppe .ppn{padding-bottom:12px}@media (max-width:720px){.ppr,.ppe{grid-template-columns:1fr 1fr}.ppr .ppn,.ppe .ppn{grid-column:1/-1;padding:0}}.dg{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:18px;margin-top:18px}.dg>*{min-width:0}@media (max-width:1000px){.dg{grid-template-columns:1fr}}
.pst{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;font-size:0.75rem;font-weight:800}
.pst.ok{color:var(--green);background:color-mix(in srgb,var(--green) 12%,transparent)}.pst.dr{color:var(--amber);background:color-mix(in srgb,var(--amber) 12%,transparent)}
.pnum{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}.pnum div{background:var(--surface2);border-radius:16px;padding:14px}
.pnum span{display:block;font-size:0.75rem;font-weight:700;color:var(--faint)}.pnum b{font-size:1.375rem;font-weight:800;letter-spacing:-.02em}
@media (max-width:560px){.pnum{grid-template-columns:1fr}}
.tl{display:grid;grid-template-columns:minmax(0,1fr);gap:8px}.tk{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:16px;background:var(--surface2)}
.tk form{margin:0}.tk .tt{flex:1;min-width:0}.tk .tt>b{display:block;font-weight:700;overflow-wrap:anywhere}.tk .tm{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin-top:3px}.tk .tm .tdue{white-space:nowrap}.tk .tt small{color:var(--faint);font-size:0.75rem}
.tk.done .tt b{text-decoration:line-through;color:var(--faint)}
.cbx{width:30px;height:30px;border-radius:10px;border:2px solid var(--border);background:var(--surface);display:grid;place-items:center;cursor:pointer;color:#fff;flex:none}
.cbx.on{background:var(--green);border-color:var(--green)}.cbx .i{width:16px;height:16px;stroke-width:3}
.tdel{border:0;background:transparent;color:var(--faint);cursor:pointer;width:36px;height:36px;border-radius:10px;display:grid;place-items:center}.tdel:hover{color:var(--red);background:var(--surface)}
.who2{font-size:0.6875rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin:14px 0 8px}
.lg{display:grid;gap:2px}.lg div{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:0.8125rem}.lg div:last-child{border:0}
.lg time{color:var(--faint);flex:none;width:92px}.lg b{font-weight:700}
.row4{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px 12px;align-items:end}.tmw{display:flex;align-items:flex-end;min-width:0}.tmw>label{width:100%}.tadd{height:46px;width:100%;border:1.5px dashed var(--border);border-radius:12px;background:transparent;color:var(--accent);font:800 0.8125rem Golos Text,sans-serif;cursor:pointer}.tadd:hover{background:var(--surface2)}.tadd[hidden],.tmf[hidden]{display:none}.row4>.btnp{height:46px}.tme{position:relative;display:block}.tme input{width:100%;padding-right:40px!important}.tme button{position:absolute;right:6px;top:50%;transform:translateY(-50%);width:30px;height:30px;border:0;border-radius:9px;background:transparent;color:var(--faint);cursor:pointer;display:grid;place-items:center}.tme button:hover{background:var(--surface);color:var(--red)}.tk .tt small b{color:var(--text)}.tk .tt .late{color:var(--red);font-weight:800;font-size:0.6875rem;padding:2px 8px;border-radius:999px;white-space:nowrap;background:color-mix(in srgb,var(--red) 12%,transparent)}.pedt{margin-top:4px}.pedt>summary{list-style:none;cursor:pointer;width:max-content;margin-bottom:14px}.pedt>summary::-webkit-details-marker{display:none}.pedt>summary .i{width:15px;height:15px}.pedt[open]>summary{background:transparent;color:var(--muted)}.row4>label:first-child{grid-column:1/-1}.row4 input,.row4 select{width:100%;min-width:0}@media (max-width:420px){.row4{grid-template-columns:minmax(0,1fr)}}
</style>"""

ACTIONS = {"plan.draft": "жоспар жобасын өзгертті", "plan.approve": "жоспарды бекітті", "task.add": "тапсырма берді",
           "task.done": "тапсырманы орындады", "task.todo": "тапсырманы қайта ашты", "task.deleted": "тапсырманы өшірді",
           "staff.save": "қызметкерді сақтады", "pplan.draft": "жеке жоспарлар жобасын өзгертті", "pplan.approve": "жеке жоспарларды бекітті", "report.save": "өзгертті", "report.reset": "бастапқы қалпына қайтарды", "comp.add": "бәсекелес қосты", "comp.remove": "бәсекелесті алып тастады"}


def page(con, user: dict, staff: list, today, month: str, note: str = "") -> str:
    e = html.escape
    allp = plans_all(con)
    cur = allp.get(month) or {}
    draft, appr = cur.get("draft"), cur.get("approved")
    y, mo = int(month[:4]), int(month[5:])
    mname = f"{MONTHS[mo - 1]} {y}"
    editor = can(user, "dept.edit")
    names = {s["login"]: s["name"] for s in staff}
    names.setdefault(user["u"], user.get("n", ""))
    names.setdefault(__import__("os").getenv("STATS_USER", "eduapp"), "Әкімші")

    def nums(p):
        return (f'<div class="pnum"><div><span>Айлық сатылым</span><b>{home.money(p.get("amount")) if p.get("amount") else "—"}</b></div>'
                f'<div><span>Күндік лид</span><b>{home.num(p.get("leads_day"))}</b></div><div><span>Бонус</span><b>{p.get("bonus_pct") or 0}%</b></div></div>')

    if appr and draft and all(draft.get(k) == appr.get(k) for k, _ in FIELDS):
        status = f'<span class="pst ok">{ui.icon("check")}Бекітілген · {e(names.get(appr.get("by"), appr.get("by") or ""))}</span>'
    elif appr:
        status = '<span class="pst dr">Өзгерістер бекітілмеген</span>'
    else:
        status = '<span class="pst dr">Бекітілмеген жоба</span>' if draft else '<span class="pst dr">Жоспар әлі жоқ</span>'
    shown = appr or plan_for(con, datetime(y, mo, 1, tzinfo=igdata.TZ)) or {}
    plan_card = (f'<article class="card cardin" style="--i:1"><div class="ch"><h2>Бөлімнің жоспары · {mname}</h2><span class="meta">{status}</span></div>'
                 f'<p class="note" style="margin:0">Бүкіл бөлімнің ортақ жоспары: бөлімнің Шолуы, бонус пайызы және Telegram есебі осы <b>бекітілген</b> жоспар бойынша. Әр адамның өз Шолуы — төмендегі жеке жоспары бойынша.</p>'
                 f'{nums(shown)}')
    if editor:
        d = draft or shown
        amt = f"{d['amount']:,}".replace(",", " ") if d.get("amount") else ""
        # the approved numbers are already on the cards above: the form opens on demand, or by itself when
        # there is nothing approved yet / the draft differs from the approved plan
        same = bool(appr and draft and all(draft.get(k) == appr.get(k) for k, _ in FIELDS))
        plan_card += (f'<details class="pedt"{"" if same else " open"}><summary class="btng">{ui.icon("edit")}Жоспарды өзгерту</summary>'
                      f'<form class="f" method="post" action="/dept/plan"><input type="hidden" name="month" value="{month}">'
                      f'<div class="row3"><label>Айлық сатылым, ₸<input name="amount" inputmode="numeric" value="{amt}" placeholder="10 000 000"></label>'
                      f'<label>Күндік лид<input name="leads_day" type="number" min="1" inputmode="numeric" value="{d.get("leads_day") or 100}"></label>'
                      f'<label>Бонус, %<input name="bonus_pct" type="number" min="0" max="100" step="0.1" inputmode="decimal" value="{d.get("bonus_pct") or ""}"></label></div>'
                      f'<div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btng" type="submit" name="do" value="draft">Жобаны сақтау</button>'
                      f'<button class="btnp" type="submit" name="do" value="approve">Сақтап, бекіту</button></div></form></details>')
    plan_card += "</article>"

    people = [s for s in staff if s.get("active", 1)]
    pcur = people_all(con).get(month) or {}
    pdraft, pappr = pcur.get("draft") or {}, pcur.get("approved") or {}
    first_day = datetime(y, mo, 1, tzinfo=igdata.TZ)
    pshown = {s["login"]: pappr.get(s["login"]) or person_plan_for(con, s["login"], first_day) or {} for s in people}
    psame = bool(pappr) and all(pdraft.get(s["login"]) == pappr.get(s["login"]) for s in people)
    pstatus = (f'<span class="pst ok">{ui.icon("check")}Бекітілген · {e(names.get(pcur.get("by"), pcur.get("by") or ""))}</span>' if psame
               else '<span class="pst dr">Өзгерістер бекітілмеген</span>' if pappr else
               '<span class="pst dr">Бекітілмеген жоба</span>' if pdraft else '<span class="pst dr">Жоспар әлі жоқ</span>')
    prow = "".join(f'<div class="ppr"><b class="ppn">{e(s["name"])}</b>'
                   f'<span><small>Айлық сатылым</small>{home.money(pshown[s["login"]].get("amount")) if pshown[s["login"]].get("amount") else "—"}</span>'
                   f'<span><small>Күндік лид</small>{home.num(pshown[s["login"]].get("leads_day")) if pshown[s["login"]].get("amount") else "—"}</span></div>'
                   for s in people) or '<p class="note">Команда бетінде қызметкер қосыңыз.</p>'
    people_card = (f'<article class="card cardin" style="--i:2;margin-top:18px"><div class="ch"><h2>Жеке жоспарлар · {mname}</h2><span class="meta">{pstatus}</span></div>'
                   f'<p class="note" style="margin:0">Әр адамның өз жоспары. Нәтиже — бөлімнің ортақ лидтері мен сатылымы; Шолуда әркім өз жоспарын көреді.</p>'
                   f'<div class="ppl">{prow}</div>')
    if editor and people:
        def val(lg, k):
            v = (pdraft.get(lg) or pshown.get(lg) or {}).get(k)
            return (f"{v:,}".replace(",", " ") if k == "amount" else str(v)) if v else ""
        fr = "".join(f'<div class="ppe"><b class="ppn">{e(s["name"])}</b>'
                     f'<label>Айлық сатылым, ₸<input name="amount__{e(s["login"])}" inputmode="numeric" value="{val(s["login"], "amount")}" placeholder="5 000 000"></label>'
                     f'<label>Күндік лид<input name="leads__{e(s["login"])}" type="number" min="1" inputmode="numeric" value="{val(s["login"], "leads_day")}" placeholder="50"></label></div>'
                     for s in people)
        people_card += (f'<details class="pedt"{"" if psame else " open"}><summary class="btng">{ui.icon("edit")}Жеке жоспарларды өзгерту</summary>'
                        f'<form class="f" method="post" action="/dept/people"><input type="hidden" name="month" value="{month}">{fr}'
                        f'<div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btng" type="submit" name="do" value="draft">Жобаны сақтау</button>'
                        f'<button class="btnp" type="submit" name="do" value="approve">Сақтап, бекіту</button></div></form></details>')
    people_card += "</article>"

    # tasks: the lead / admin see everyone's and give tasks; a marketer sees and ticks their own
    marketers = [s for s in staff if s.get("role") != "lead"]
    mine_only = not can(user, "tasks.edit")
    rows = tasks(con, user["u"] if mine_only else None)

    def task_row(t):
        done = t["status"] == "done"
        tick = (f'<form method="post" action="/dept/task"><input type="hidden" name="id" value="{t["id"]}"><input type="hidden" name="status" value="{"todo" if done else "done"}">'
                f'<button class="cbx{" on" if done else ""}" type="submit" aria-label="{"Қайта ашу" if done else "Орындалды"}">{ui.icon("check") if done else ""}</button></form>')
        dele = ("" if mine_only else f'<form method="post" action="/dept/task" data-undo="Тапсырма өшірілді"><input type="hidden" name="id" value="{t["id"]}"><input type="hidden" name="status" value="deleted">'
                f'<button class="tdel" type="submit" aria-label="Өшіру">{ui.icon("x")}</button></form>')
        # the person is already the group header (or it is your own list): the line under the title is only the deadline
        meta = ""
        if t.get("due") and len(t["due"]) >= 10:
            hhmm = t["due"][11:16] if len(t["due"]) >= 16 else ""
            meta = f'<span class="tdue">мерзімі {e(t["due"][8:10])}.{e(t["due"][5:7])}' + (f', <b>{e(hhmm)}-ге дейін</b>' if hhmm else "") + "</span>"
            now_key = datetime.now(igdata.TZ).strftime("%Y-%m-%d %H:%M")
            if not done and (t["due"][:16] if hhmm else t["due"][:10] + " 23:59") < now_key:
                meta += '<span class="late">мерзімі өтті</span>'
        return (f'<div class="tk{" done" if done else ""}" data-undo-row>{tick}<div class="tt"><b>{e(t["title"])}</b>'
                f'{f"<small class=tm>{meta}</small>" if meta else ""}</div>{dele}</div>')
    if mine_only:
        tl = "".join(task_row(t) for t in rows) or '<p class="note">Сізге әзірге тапсырма жоқ.</p>'
    else:
        tl = ""
        for s in marketers:
            mine = [t for t in rows if t["login"] == s["login"]]
            left = sum(1 for t in mine if t["status"] != "done")
            tl += f'<div class="who2">{e(s["name"])} · {left} орындалмаған</div>' + ("".join(task_row(t) for t in mine) or '<p class="note">Тапсырма жоқ.</p>')
        opts = "".join(f'<option value="{e(s["login"])}">{e(s["name"])}</option>' for s in marketers)
        tl = (f'<form class="f" method="post" action="/dept/task/add" style="margin-bottom:6px"><div class="row4">'
              f'<label>Тапсырма<input name="title" maxlength="200" required placeholder="Ертеңге 2 рилс түсіру"></label>'
              f'<label>Кімге<select name="login" required>{opts}</select></label>'
              f'<label>Мерзімі<input name="due" type="date" value="{igdata.key(today)}"></label>'
              f'<div class="tmw"><button type="button" class="tadd" data-tadd>+ Уақыт қосу</button><label class="tmf" hidden>Уақыты<span class="tme"><input name="due_time" type="time" step="900" id="dtime"><button type="button" aria-label="Уақытты алып тастау" data-clear="dtime">{ui.icon("x")}</button></span></label></div>'
              f'<button class="btnp" type="submit">Беру</button></div></form>' if marketers else '<p class="note">Команда бетінде маркетолог қосыңыз.</p>') + tl
    task_card = f'<article class="card cardin" style="--i:2"><div class="ch"><h2>Тапсырмалар</h2></div><div class="tl">{tl}</div></article>'
    task_card += ('<script>(function(){var a=document.querySelector("[data-tadd]");if(!a)return;var f=a.parentNode.querySelector(".tmf"),'
                  'i=document.getElementById("dtime");a.onclick=function(){a.hidden=true;f.hidden=false;i.focus()};'
                  'document.querySelector("[data-clear]").onclick=function(){i.value="";f.hidden=true;a.hidden=false}})()</script>')

    log_card = ""
    if editor:
        lr = "".join(f'<div><time>{datetime.fromtimestamp(t, igdata.TZ):%d.%m %H:%M}</time><span><b>{e(names.get(a, a))}</b> '
                     f'{ACTIONS.get(ac, ac)}{(" · " + e(names.get(tg, tg))) if ac.startswith(("task", "staff")) else (" · " + e(tg)) if tg else ""}'
                     f'{(": " + e(dt)) if dt else ""}</span></div>' for t, a, ac, tg, dt in audit_rows(con))
        log_card = (f'<article class="card cardin" style="--i:3;margin-top:18px"><div class="ch"><h2>Өзгерістер журналы</h2>'
                    f'<span class="meta">кім, не, қашан</span></div><div class="lg">{lr or "<p class=note>Әзірге өзгеріс жоқ.</p>"}</div></article>')

    prev_m = f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"
    next_m = f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"
    nav = (f'<div class="act"><a class="btng" href="/dept?m={prev_m}">{ui.icon("left")}</a>'
           f'<span style="font-weight:800;color:#fff">{mname}</span><a class="btng" href="/dept?m={next_m}">{ui.icon("right")}</a></div>')
    import admin
    body = (f'{CSS}<main class="wrap"><section class="ph cardin"><div><h1>Маркетинг бөлімі</h1>'
            f'<p>Ортақ және жеке жоспарлар, кім не өзгерткені</p></div>{nav}</section>'
            f'{admin.msg(note)}<div class="dg" style="grid-template-columns:minmax(0,1fr)">{plan_card}{people_card}</div>{log_card}</main>')
    return admin.page("Маркетинг бөлімі · EduApp", body, user, "dept")
