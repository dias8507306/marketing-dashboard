# EduApp Marketing — PRODUCT

## What it is
An internal web dashboard for the marketing department of EduApp, a Kazakhstan education company (online preparation
of schoolchildren: mathematics, English, the «Алтын сақа» olympiad). Four people use it every day: the owner and three
marketers. It brings sales, leads, Instagram and the Instagram bot together and runs the department's shared plan and tasks.

- Interface language: Kazakh only. Time zone: Astana (UTC+5). Currency: ₸.
- Deployed as a serverless FastAPI app on Vercel; `python demo.py` runs it locally on generated data.

## Who uses it, and how
| Role | Person | Does |
|---|---|---|
| admin | owner | sees everything; manages team, bot, settings; can look through an employee's eyes (read-only) |
| lead | Ерлан | approves the shared plan, gives tasks, sees «Жарнама» |
| smm | Айгерім, Дана | see the plan and their own tasks, tick them off |

The plan is shared by the department, never personal.

Mode: **Operate.** A working tool opened many times a day. What matters most: how fast a number is read, a clear
hierarchy, predictability. Character comes from precise typography, colour with a job and small details — not decoration.

Typical questions the screen must answer at a glance:
1. Are we on track for the month? (revenue against plan, and where we should be today)
2. How did yesterday / today go? (leads, deals, conversion)
3. What do I have to do now? (tasks, deadlines, people waiting in Direct)

## Pages
- **Шолу** — revenue vs plan with progress and «should be today» mark, deals, average check, leads, conversion, daily
  chart, streak of days with the lead plan met, activity calendar, line of the day, celebration when the plan is met;
  periods Күн / Апта / Ай + date.
- **Instagram** — reach, views, likes, comments, saves, shares, followers.
- **Контент** — each post from views to comments, leads and sales.
- **Бот** — funnel, activity feed, collected answers, bot and queue control, texts, per-post rules.
- **Тарих** — monthly archive.
- **Маркетинг бөлімі** — plan with draft and approval, tasks with deadlines, change log.
- **Жарнама** — ad spend, leads, CPL, ROMI.
- **Команда, Telegram, Баптау, Жүйе, ИИ-көмекші.**

Data: amoCRM, Instagram Graph API, bot event database, Google Sheet, Telegram reports.

## Behaviour that must survive any redesign
- Numbers appear final on the first frame (no count-up); tabular figures.
- Instant press feedback (:active scale .97) and a thin loading bar on navigation.
- Task delete with «Қайтару» undo (5 s) and an honest error; confirmation only for irreversible actions.
- Phone «Тағы» sheet: 1:1 drag, momentum, spring.
- Translucent phone bars only where content scrolls beneath; the section name in the top strip.
- Inline field validation in Kazakh.
- prefers-reduced-motion, prefers-reduced-transparency, prefers-contrast; type in rem; touch targets ≥ 44 px.
- Light and dark theme with a switch (dark is required).
- Desktop: 248 px side menu. Phone 390 px: bottom bar with 5 items.

## Constraints
- No emoji on the site (Instagram / Telegram texts may have them).
- Python 3.12 + FastAPI; HTML is built with f-strings; CSS and JS inline; no React, template engine, bundler or
  external scripts. Style changes go through shared tokens in `ui.py` and `charts.py`.
- Inline CSS must not grow noticeably (serverless on Vercel).
- Fonts: at most 2 families; must cover Ә Ғ Қ Ң Ө Ұ Ү Һ І in every weight used, the ₸ sign and tabular figures.
- Secrets never appear in code, prompts or output.

## Brand commitments
- Purple stays (pinned by the owner, 26.10.2026): deep velvet purple for the shell and the board, brand
  violet #7336F7 for interactive state, gold/yellow for what was earned. No gradients or glow on it.

## Anti-references (the current look and the generic «AI dashboard»)
Purple used as a soft lavender SaaS wash, gradient headers, glow spots, a grid of identical rounded soft-shadow cards, the
«big number + grey label + green % pill + sparkline» tile repeated four times, coloured icon circles, decorative
progress rings, decorative glass, gradient text, coloured left stripes, eyebrow labels, 01/02/03 numbering, confetti,
trophies, flames, national ornament as stickers, the Linear/Vercel near-black-with-neon clone, and the usual AI fonts
(Inter, Space Grotesk, DM Sans, Outfit, Plus Jakarta Sans, Manrope, Poppins, Syne, IBM Plex, Playfair Display, Fraunces).
