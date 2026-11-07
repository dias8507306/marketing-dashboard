"""Login, team (employees and their plans) and amoCRM settings pages."""
import html

import amo
import home
import ui

SHELL = """<!doctype html><html lang="kk"><head>__HEAD____FONT__<title>__TITLE__</title>
__STYLE__<style>__KIT__
.people{display:grid;gap:12px}
.person{display:flex;align-items:center;gap:14px;padding:14px;border-radius:18px;background:var(--surface2);transition:transform .15s}
@media (hover:hover){.person:hover{transform:translateX(3px)}}.person .who{flex:1;min-width:0}.person .btng{background:var(--surface)}@media (max-width:560px){.person{flex-wrap:wrap}.person .btng{width:100%}}
.person b{display:block;font-weight:700;font-size:0.9375rem}.person small{color:var(--faint)}
.person .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.ptag .i{width:13px;height:13px;stroke-width:2}
.login{min-height:100vh;display:grid;grid-template-columns:1.1fr 1fr;background:var(--bg)}
.lside{position:relative;overflow:hidden;background:var(--hero);color:#fff;padding:48px;display:flex;flex-direction:column;justify-content:space-between}
.lside:after{content:"";position:absolute;width:520px;height:520px;right:-160px;top:-200px;border-radius:50%;background:radial-gradient(circle,rgba(254,194,0,.45),transparent 70%)}
.lside:before{content:"";position:absolute;width:420px;height:420px;left:-140px;bottom:-180px;border-radius:50%;background:radial-gradient(circle,rgba(243,91,47,.35),transparent 70%)}
.lside>*{position:relative;z-index:1}.lside h2{margin:0;font-size:2.5rem;line-height:1.1;font-weight:800;letter-spacing:-.03em;max-width:460px}
.lside p{opacity:.85;max-width:420px;font-size:0.9375rem}.lbrand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.125rem}
.llogo{display:block;width:48px;height:48px;border-radius:14px;box-shadow:0 0 0 3px rgba(255,255,255,.18),0 10px 24px -8px rgba(0,0,0,.4)}.llogo svg{width:100%;height:100%;display:block}
.lstats{display:flex;gap:10px;flex-wrap:wrap}.lstats .i,.lstats .fx{width:15px;height:15px;color:#fec200}.lstats span{display:inline-flex;align-items:center;gap:7px;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.14);font-weight:600;font-size:0.8125rem}
.lform{display:grid;place-items:center;padding:32px 20px}.lform .card{width:100%;max-width:400px;padding:32px}
.lform h1{margin:0 0 4px;font-size:1.625rem;font-weight:800;letter-spacing:-.02em}.lform .card>p{margin:0 0 22px}
.lform .btnp{width:100%;margin-top:4px}
.attr{border:1px solid var(--border);border-radius:16px;padding:14px;display:grid;gap:8px;margin:0}.attr legend{font-weight:700;padding:0 6px}
.chks{display:flex;flex-wrap:wrap;gap:8px}.chk{display:inline-flex !important;flex-direction:row !important;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;background:var(--surface2);font-size:0.8125rem;font-weight:600;cursor:pointer}
.cks{margin:0;padding:0;border:0;min-width:0}.cks legend{padding:0;margin-bottom:6px;font-size:.8125rem;font-weight:600}.cks>small{display:block;margin-top:6px}.ckl{border:1px solid var(--border);border-radius:12px;overflow:hidden}
.ckr{display:grid !important;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;min-height:44px;margin:0;padding:8px 12px;font-weight:400 !important;font-size:.875rem;cursor:pointer}.ckr+.ckr{border-top:1px solid var(--border)}.ckr:hover{background:var(--surface2)}.ckr input{width:18px !important;height:18px !important;min-height:0 !important;margin:0;padding:0;accent-color:#7336F7}.ckr small{display:block;font-size:.75rem;color:var(--faint)}.ckr em{font-style:normal;font-size:.75rem;color:var(--faint);font-variant-numeric:tabular-nums;white-space:nowrap}
.chk input{width:auto !important;height:auto !important;margin:0}
@media (max-width:860px){.login{grid-template-columns:1fr;grid-template-rows:auto 1fr}.lside{padding:28px 20px}.lside h2{font-size:1.625rem}.lside .lstats,.lside p{display:none}.lform{place-items:start center}}
</style></head><body>__BODY__</body></html>"""


def page(title, body, user=None, active=""):
    top = ui.topbar(user, active) if user else ""
    return (SHELL.replace("__HEAD__", ui.HEAD).replace("__FONT__", ui.FONT).replace("__TITLE__", html.escape(title))
            .replace("__STYLE__", ui.STYLE).replace("__KIT__", ui.KIT + ui.PAGES)
            .replace("__BODY__", top + body + (ui.THEME_JS if user else "") + ui.KIT_JS))


_EMOJI = __import__("re").compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]+ ?")


def _no_emoji(text: str) -> str:
    """The site shows no emoji (the Telegram message itself keeps them)."""
    return _EMOJI.sub("", text or "")


def msg(text, ok=True):
    return f'<div class="msg {"ok" if ok else "err"}">{html.escape(text)}</div>' if text else ""


def login_page(error: str = "", nxt: str = "/") -> str:
    return page("Кіру · EduApp", f"""<div class="login"><aside class="lside">
<div class="lbrand"><span class="llogo">{ui.LOGO}</span>EduApp Marketing</div>
<div><h2>Бүгінгі жоспарды бірге орындаймыз</h2><p>Сатылым, лидтер және Instagram нәтижесі — бір экранда. Әр күннің жеңісі есептеледі.</p></div>
<div class="lstats"><span>{ui.icon("wallet")}Сатылым</span><span>{ui.icon("target")}Лид жоспары</span><span>{ui.flame()}Streak</span></div></aside>
<div class="lform"><div class="card cardin"><h1>Қош келдіңіз</h1><p>Логин мен құпиясөзді енгізіңіз</p>{msg(error, False)}
<form class="f" method="post" action="/login"><input type="hidden" name="next" value="{html.escape(nxt)}">
<label>Логин<input name="user" autocomplete="username" required autofocus></label>
<label>Құпиясөз<input name="pwd" type="password" autocomplete="current-password" required></label>
<button class="btnp" type="submit">Кіру</button></form></div></div></div>""")


AVATAR = [("#7336F7", "#2A78D6"), ("#f35b2f", "#fec200"), ("#048848", "#2A78D6"), ("#7648c3", "#f35b2f")]


ROLE_LABEL = {"smm": "Маркетолог", "lead": "Маркетинг жетекшісі"}


def team_page(staff: list, edit: dict | None, note: str = "", err: str = "", user: dict | None = None,
              amo_users: list | None = None, src: dict | None = None) -> str:
    amo_users, src = amo_users or [], src or {}
    unames = {u["id"]: u["name"] for u in amo_users}
    rows = "".join(
        f'<div class="person"><span class="av" style="--a1:{AVATAR[i % 4][0]};--a2:{AVATAR[i % 4][1]}">{html.escape(ui.initials(s["name"]))}</span>'
        f'<div class="who"><b>{html.escape(s["name"])}</b><small>@{html.escape(s["login"])}</small><div class="tags">'
        f'<span class="ptag" style="--c:{"#A85100" if s.get("role") == "lead" else "#7336F7"}">{ROLE_LABEL.get(s.get("role"), "Маркетолог")}</span></div></div>'
        f'<a class="btng" href="/team?edit={html.escape(s["login"])}">Өзгерту</a></div>'
        for i, s in enumerate(staff)) or '<p class="note">Әзірге қызметкер жоқ.</p>'
    e = edit or {"login": "", "name": "", "plans": {}}
    pl = e.get("plans") or {}
    editing = bool(edit)
    form = f"""<form class="f" method="post" action="/team">
<div class="row2"><label>Аты-жөні<input name="name" value="{html.escape(e['name'])}" placeholder="Айгерім" required></label>
<label>Логин<input name="login" value="{html.escape(e['login'])}" placeholder="aigerim" {'readonly' if editing else ''} required pattern="[A-Za-z0-9._\\-]+" data-err="Логинде тек латын әріптері, сан және . _ - болады"></label></div>
<label>Құпиясөз<input name="pwd" type="password" autocomplete="new-password" {'' if editing else 'required'} minlength="6">
<small>{'Өзгертпесеңіз, бос қалдырыңыз' if editing else 'Кемінде 6 таңба — қызметкерге өзіңіз беріңіз'}</small></label>
<label>Рөлі<select name="role">{"".join(f'<option value="{k}"{" selected" if (e.get("role") or "smm") == k else ""}>{t}</option>' for k, t in ROLE_LABEL.items())}</select>
<small>Маркетинг жетекшісі ортақ жоспарды жасап бекітеді, тапсырма береді, Жарнама бетін көреді. Маркетолог жоспар мен өз тапсырмаларын көреді.</small></label>
<small>Жоспар енді бүкіл бөлімге ортақ — «Маркетинг бөлімі» бетінде.</small>
<button class="btnp" type="submit">{'Сақтау' if editing else 'Қызметкер қосу'}</button>
{f'<button class="btng" type="submit" name="deactivate" value="1" formnovalidate data-confirm="{html.escape(e['name'])} өшірілсін бе?|Ол сайтқа кіре алмайды. Кейін қайта қосу үшін аккаунтын жаңадан сақтау керек.|Өшіру">Өшіру (кіре алмайды)</button>' if editing else ''}</form>"""
    return page("Команда · EduApp", f"""<main class="wrap narrow">
<section class="ph cardin"><div><h1>Команда</h1><p>Кім кіре алады және қандай рөлмен. Жоспар — «Маркетинг бөлімі» бетінде, бүкіл бөлімге ортақ.</p>
<div class="stats"><span>{len(staff)} қызметкер</span></div></div>
<div class="act"><a class="btny" href="/team#new">+ Жаңа қызметкер</a></div></section>
{msg(note)}{msg(err, False)}<section class="card cardin" style="--i:1"><h2>Қызметкерлер</h2><div class="people">{rows}</div></section>
<section class="card cardin" id="new" style="--i:2;margin-top:18px"><h2>{html.escape(e['name']) if editing else 'Жаңа қызметкер'}</h2>{form}</section>
<a class="note" href="/" style="margin-top:14px">← Шолуға оралу</a></main>""", user, "team")


def attr_label(a, unames: dict) -> str:
    if not a or not (a.get("users") or a.get("values")):
        return "ортақ нәтиже"
    parts = [unames.get(i, str(i)) for i in a.get("users") or []] + list(a.get("values") or [])
    return "жеке: " + html.escape(", ".join(parts)[:60])


def attr_fields(a: dict, amo_users: list, src: dict) -> str:
    """Which deals are this person's: amoCRM responsible users and / or values of the source field."""
    users = set(a.get("users") or [])
    vals = set(a.get("values") or [])
    ub = "".join(f'<label class="chk"><input type="checkbox" name="attr_user" value="{u["id"]}"{" checked" if u["id"] in users else ""}>'
                 f'{html.escape(u["name"])}</label>' for u in amo_users) or '<small>amoCRM пайдаланушылары жүктелмеді</small>'
    vb = "".join(f'<label class="chk"><input type="checkbox" name="attr_value" value="{html.escape(v)}"{" checked" if v in vals else ""}>'
                 f'{html.escape(v)}</label>' for v in src.get("values") or [])
    return f"""<fieldset class="attr"><legend>Жеке нәтиже: қай сделкалар осы қызметкердікі</legend>
<small>Ештеңе белгіленбесе — ортақ нәтиже (барлық маркетинг сделкалары). Белгіленсе — жоспар, бонус, серия тек осы сделкалар бойынша.</small>
<b>amoCRM-дағы жауапты менеджер</b><div class="chks">{ub}</div>
{f'<b>«{html.escape(src.get("name") or "Қайдан келді")}» мәні</b><div class="chks">{vb}</div><input type="hidden" name="attr_field" value="{html.escape(str(src.get("id") or ""))}">' if vb else ''}
</fieldset>"""


def settings_page(configured: bool, sync_state: dict, fields: list, pipes: list, st: dict, note: str = "",
                  counts: dict | None = None, pcounts: dict | None = None, user: dict | None = None) -> str:
    counts, pcounts = counts or {}, pcounts or {}
    if not configured:
        body = """<p>amoCRM әлі қосылмаған. Vercel → <project> → Environment Variables бөліміне екі баптау қосу керек:</p>
<p><b>AMO_DOMAIN</b> — мысалы <code>YOUR_AMO_SUBDOMAIN</code> (amoCRM account domain)<br><b>AMO_TOKEN</b> — amoCRM-дағы ұзақ мерзімді кілт (Secret түрінде).</p>"""
    else:
        fopts = '<option value="">— барлық сделка маркетинг деп саналады —</option>' + "".join(
            f'<option value="{f["id"]}"{" selected" if str(st.get("source_field")) == f["id"] else ""}>{html.escape(f["name"])}</option>'
            for f in fields)
        cur = next((f for f in fields if f["id"] == str(st.get("source_field"))), None)
        def tick(name, value, title, n, on, always=False):
            return (f'<label class="ckr"><input type="checkbox" name="{name}" value="{html.escape(str(value))}"{" checked" if on else ""}{" disabled" if always else ""}>'
                    f'<span>{html.escape(title)}{"<small>әрқашан маркетинг</small>" if always else ""}</span><em>{n} сделка</em></label>')
        vopts = "".join(tick("sources", v, v, counts.get(v, 0), v in (st.get("sources") or []) or v == amo.WEBINAR, v == amo.WEBINAR)
                        for v in sorted(cur["values"] if cur else [], key=lambda v: -counts.get(v, 0)))
        popts = "".join(tick("pipelines", p["id"], p["name"], pcounts.get(p["id"], 0), p["id"] in (st.get("pipelines") or [])) for p in pipes)
        state = (f'Соңғы жаңарту: {sync_state.get("when", "—")}' + (f' · қате: {html.escape(sync_state["error"])}' if sync_state.get("error") else " · сәтті"))
        body = f"""<p><span class="ptag" style="--c:{'#f35b2f' if sync_state.get('error') else '#048848'}">{state}</span></p><form class="f" method="post" action="/settings">
<label>Лидтің қайдан келгенін көрсететін өріс<select name="source_field" onchange="this.form.submit()">{fopts}</select>
<small>Мысалы «Источник». Таңдаған соң төменде мәндері шығады.</small></label>
{f'<fieldset class="cks"><legend>Маркетинг деп саналатын мәндер</legend><div class="ckl">{vopts}</div><small>Сандар — осы айда ашылған сделкалар. Ештеңе белгіленбесе — барлық сделка.</small></fieldset>' if cur else ''}
<fieldset class="cks"><legend>Воронкалар</legend><div class="ckl">{popts}</div><small>Ештеңе белгіленбесе — барлық воронка</small></fieldset>
<button class="btnp" type="submit">Сақтау</button></form>"""
    return page("Баптау · EduApp", f"""<main class="wrap narrow">
<section class="ph cardin"><div><h1>amoCRM баптауы</h1><p>Қай сделкалар маркетингтен келді деп саналатынын осында таңдайсыз</p>
<div class="stats"><span>{'қосылған' if configured else 'қосылмаған'}</span></div></div></section>
{msg(note)}<section class="card cardin" style="--i:1">{body}</section><section class="card cardin" style="--i:2;margin-top:18px"><h2>Telegram есеп</h2><p>Таңғы 08:00-де директорға кешегі есеп: кім жоспарды жапты, кім жаппады.</p><a class="btnp" href="/telegram">Telegram баптауы</a></section></main>""", user, "settings")


def telegram_page(configured: bool, bot: str, chats: list, cands: list, note: str = "", err: str = "", user: dict | None = None,
                  sample: str = "", team: list | None = None, links: dict | None = None, seen: list | None = None,
                  owner=None, db_mb=None) -> str:
    if not configured:
        body = """<h2>Бот әлі қосылмаған</h2><ol class="steps">
<li>Telegram-да <b>@BotFather</b> ашып, <code>/newbot</code> жазыңыз, атын ойлап табыңыз. Ол <b>токен</b> береді.</li>
<li>Vercel → <project> → Settings → Environment Variables → <b>TELEGRAM_BOT_TOKEN</b> атымен токенді сақтаңыз.</li>
<li>Vercel-де Deployments → соңғысы → <b>Redeploy</b> басыңыз (немесе маған жазыңыз).</li>
<li>Осы бетке қайта кіріңіз.</li></ol>"""
    else:
        rows = "".join(f'''<div class="person"><span class="av">{html.escape(ui.initials(c["name"]))}</span><div class="who"><b>{html.escape(c["name"])}</b><small>chat {c["id"]}</small></div>
{'<span class="ptag" style="--c:#048848">резерв осыған келеді</span>' if c["id"] == owner else f'<form method="post" action="/telegram"><input type="hidden" name="action" value="owner"><input type="hidden" name="id" value="{c["id"]}"><button class="btng" type="submit" title="Резервтік көшірме мен база ескертуі тек осы адамға келеді">Резерв маған</button></form>'}
<form method="post" action="/telegram"><input type="hidden" name="action" value="remove"><input type="hidden" name="id" value="{c["id"]}"><button class="btng" type="submit">Өшіру</button></form></div>''' for c in chats) \
            or '<p class="note">Әзірге ешкім қосылмаған.</p>'
        cand = "".join(f'''<div class="person"><span class="av" style="--a1:#048848;--a2:#2A78D6">{html.escape(ui.initials(c["name"]))}</span><div class="who"><b>{html.escape(c["name"])}</b><small>{"@" + html.escape(c["username"]) if c["username"] else "chat " + str(c["id"])}</small></div>
<form method="post" action="/telegram"><input type="hidden" name="action" value="add"><input type="hidden" name="id" value="{c["id"]}"><input type="hidden" name="name" value="{html.escape(c["name"])}"><button class="btnp" type="submit">Қосу</button></form></div>''' for c in cands)
        link = f'<a href="https://t.me/{html.escape(bot)}" target="_blank" rel="noopener">@{html.escape(bot)}</a>' if bot else "ботты"
        body = f"""<h2>Есепті алатындар</h2><div class="people">{rows}</div>
<h2 style="margin-top:22px">Жаңа адам қосу</h2><p>Директор Telegram-да {link} ашып, <b>Start</b> басады. Сосын осы бетті жаңартыңыз — ол төменде шығады.</p>
<div class="people">{cand or '<p class="note">Start басқан жаңа адам көрінбейді. Start басқан соң бетті жаңартыңыз.</p>'}</div>
{staff_links(team or [], links or {}, (seen or []) + chats)}
<form method="post" action="/telegram" style="margin-top:22px"><input type="hidden" name="action" value="test"><button class="btny" type="submit">Кешегі есепті қазір жіберу (тест)</button></form>
<h2 style="margin-top:26px">Резервтік көшірме</h2><p>Күн сайын таңертең лидтер, бот тарихы, қызметкерлер, есептер мен баптаулар бір файлмен тек «резерв осыған келеді» белгісі бар адамға жіберіледі. Басқаларға тек есеп барады.
База көлемі қазір: <b>{db_mb if db_mb is not None else "—"} МБ / 500 МБ</b>.</p>
<form method="post" action="/telegram"><input type="hidden" name="action" value="backup"><button class="btnp" type="submit">Резервті қазір жіберу</button></form>"""
    return page("Telegram · EduApp", f"""<main class="wrap narrow">
<section class="ph cardin"><div><h1>Telegram есеп</h1><p>Күн сайын таңғы 08:00-де (Астана) кешегі толық күннің есебі: кім жоспарды жапты, кім жаппады, сосын толық есеп.</p>
<div class="stats"><span>{'бот қосылған' if configured else 'бот қосылмаған'}</span><span>{len(chats)} алушы</span></div></div></section>
{msg(note)}{msg(err, False)}<section class="card cardin" style="--i:1">{body}</section>
<section class="card cardin" style="--i:2;margin-top:18px"><h2>Ертеңгі хабарлама үлгісі</h2><pre class="tgs">{html.escape(_no_emoji(sample))}</pre></section>
</main>
<style>.steps{{margin:0;padding-left:20px;display:grid;gap:10px;color:var(--muted)}}.steps b{{color:var(--text)}}
.people{{display:grid;gap:12px}}.person{{display:flex;align-items:center;gap:14px;padding:14px;border-radius:18px;background:var(--surface2)}}
.person .who{{flex:1;min-width:0}}.person b{{display:block;font-weight:700}}.person small{{color:var(--faint)}}.person .btng{{background:var(--surface)}}.person .btnp{{height:40px}}.tgs{{white-space:pre-wrap;font:500 0.875rem/1.6 Golos Text,sans-serif;margin:0;padding:16px;border-radius:16px;background:var(--surface2);border:0}}</style>""", user, "telegram")


def staff_links(team: list, links: dict, chats: list) -> str:
    """Which Telegram account belongs to which employee (for the «...ға жіберу» button)."""
    if not team:
        return ""
    names = {}
    for c in chats:
        names[c["id"]] = c["name"] + (f" (@{c['username']})" if c.get("username") else "")
    rows = ""
    for s in team:
        cur = links.get(s["login"])
        opts = '<option value="">— таңдалмаған —</option>' + "".join(
            f'<option value="{cid}"{" selected" if cid == cur else ""}>{html.escape(n)}</option>' for cid, n in names.items())
        if cur and cur not in names:
            opts += f'<option value="{cur}" selected>chat {cur}</option>'
        rows += (f'<form class="person" method="post" action="/telegram"><input type="hidden" name="action" value="link">'
                 f'<input type="hidden" name="login" value="{html.escape(s["login"])}"><span class="av">{html.escape(ui.initials(s["name"]))}</span>'
                 f'<div class="who"><b>{html.escape(s["name"])}</b><select name="id" class="tsel">{opts}</select></div>'
                 f'<button class="btnp" type="submit">Сақтау</button></form>')
    return ('<h2 style="margin-top:22px">Қызметкерлердің Telegram-ы</h2>'
            '<p>Директор «...ға жіберу» батырмасын басқанда мәтін осы аккаунтқа кетеді. Қызметкер алдымен ботта Start басады, сосын осы жерден оның атын таңдайсыз.</p>'
            f'<div class="people">{rows}</div><style>.tsel{{margin-top:6px;height:38px;border-radius:10px;border:1.5px solid var(--border);background:var(--surface);color:var(--text);padding:0 10px;font:500 0.8125rem Golos Text,sans-serif;max-width:100%}}</style>')


def report_text_page(tpl: str, default: str, preview: str, variables: tuple, note: str = "", changed: bool = False, user: dict | None = None) -> str:
    """Owner-only editor of the report text (Telegram, WhatsApp and the overview use it)."""
    e = html.escape
    rows = "".join(f'<tr><td><code>{{{e(k)}}}</code></td><td>{e(t)}</td></tr>' for k, t in variables)
    return page("Есеп мәтіні · EduApp", f"""<main class="wrap">
<section class="ph cardin"><div><h1>Есеп мәтіні</h1><p>Telegram, WhatsApp және Шолудағы есептің мәтіні. Тек әкімші өзгерте алады.</p></div></section>
{msg(note)}<div class="rtg">
<section class="card cardin" style="--i:1"><div class="ch"><h2>Мәтін</h2><span class="meta">{"өзгертілген" if changed else "бастапқы мәтін"}</span></div>
<form class="f" method="post" action="/report-text"><textarea name="tpl" rows="24" spellcheck="false" class="rtx">{e(tpl)}</textarea>
<div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btng" type="submit" name="do" value="preview">Алдын ала көру</button>
<button class="btnp" type="submit" name="do" value="save">Сақтау</button>
{'<button class="btng" type="submit" name="do" value="reset" data-confirm="Бастапқы мәтінге қайтару керек пе?|Сіздің өзгерістеріңіз өшеді.">Бастапқы мәтінге қайтару</button>' if changed else ""}</div></form></section>
<section class="card cardin" style="--i:2"><div class="ch"><h2>Алдын ала көру</h2><span class="meta">осы айдың сандарымен</span></div><pre class="rtp">{e(preview)}</pre></section>
<section class="card cardin" style="--i:3"><div class="ch"><h2>Сандар</h2></div>
<p class="note">Мәтінге <code>{{лид}}</code> сияқты атауларды жазыңыз — олардың орнына сан қойылады. Атаудың мәні жоқ болса, сол жол есептен шығып қалады. Ал <code>[ ... ]</code> ішіндегі бөлік тек өзі ғана шығып қалады: мысалы, жоспар қойылмаса <code>[ (жоспар: {{лид_жоспар}})]</code> жазылмайды. Жұлдызша <code>*мәтін*</code> — Telegram-да қалың әріп.</p>
<table class="rtv">{rows}</table></section></div></main>
<style>.rtg{{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:18px;margin-top:18px}}.rtg>section:last-child{{grid-column:1/-1}}
.rtx,.rtp{{font:0.8125rem/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;width:100%}}.rtx{{resize:vertical;min-height:420px}}
.rtp{{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;padding:16px;border-radius:12px;background:var(--surface2)}}
.rtv{{width:100%;border-collapse:collapse;margin-top:10px;font-size:.8125rem}}.rtv td{{padding:7px 8px;border-top:1px solid var(--border);vertical-align:top}}.rtv td:first-child{{white-space:nowrap;width:1%}}
@media (max-width:900px){{.rtg{{grid-template-columns:1fr}}}}</style>""", user, "telegram")
