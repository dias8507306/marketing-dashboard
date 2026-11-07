"""Shared look for every page: tokens and base CSS, line icons, the top bar, praise texts."""
import datetime as _dt
import hashlib
import html

# Lucide icons (MIT), stroke-only
ICON = {
    "wallet": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    "receipt": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "percent": '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "gift": '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
    "instagram": '<rect width="20" height="20" x="2" y="2" rx="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 13H8"/><path d="M16 17H8"/><path d="M16 13h-2"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "right": '<path d="m9 18 6-6-6-6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>', "up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    "down": '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    "logo": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    "left": '<path d="m15 18-6-6 6-6"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "sparkles": '<path d="M9.94 14.06 4 20"/><path d="m14 4 1.2 2.8L18 8l-2.8 1.2L14 12l-1.2-2.8L10 8l2.8-1.2Z"/><path d="M19 14l.6 1.4L21 16l-1.4.6L19 18l-.6-1.4L17 16l1.4-.6Z"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "trophy": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "trend": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "award": '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "star": '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
    "arrow": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "grid": '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    "bot": '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    "film": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
    "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "menu": '<line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
}


_BADGE_N = [0]


def badge(n=None, cls="fx") -> str:
    """The streak badge (violet-rimmed gold hexagon on violet ribbons). With n — the number of days in the middle,
    without — a star (small marks: «plan met» days, notes). Replaces the old flame everywhere."""
    _BADGE_N[0] += 1
    k = f"b{_BADGE_N[0]}"
    if n is None:
        mid = (f'<path d="M42 26.5l4.3 8.7 9.6 1.4-6.95 6.8 1.64 9.55L42 48.4l-8.6 4.55 1.64-9.55-6.95-6.8 9.6-1.4Z" fill="url(#{k}s)" '
               f'filter="url(#{k}t)"/>')
    else:
        txt = str(n)
        fs = 26 if len(txt) <= 2 else 19 if len(txt) == 3 else 15
        mid = (f'<text x="42" y="{40 + fs * .36:.1f}" text-anchor="middle" font-family="Golos Text,system-ui,sans-serif" font-weight="900" '
               f'font-size="{fs}" letter-spacing="-.5" fill="url(#{k}s)" filter="url(#{k}t)">{txt}</text>')
    return (f'<svg class="{cls} zbadge" viewBox="0 0 84 104" aria-hidden="true"><defs>'
            f'<linearGradient id="{k}f" x1=".2" y1="0" x2=".8" y2="1"><stop offset="0" stop-color="#FFD54F"/><stop offset=".6" stop-color="#FFB800"/><stop offset="1" stop-color="#F29A00"/></linearGradient>'
            f'<linearGradient id="{k}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#FFE9A8"/></linearGradient>'
            f'<linearGradient id="{k}l" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9B6BFF"/><stop offset="1" stop-color="#5E27D8"/></linearGradient>'
            f'<linearGradient id="{k}r" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7C45FF"/><stop offset="1" stop-color="#3F1797"/></linearGradient>'
            f'<linearGradient id="{k}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<filter id="{k}d" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#2F0E51" flood-opacity=".35"/></filter>'
            f'<filter id="{k}t" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#B86E00" flood-opacity=".6"/></filter></defs>'
            f'<path d="M27 58 18 98l9.5-6.5 7 8.5 7.5-30Z" fill="url(#{k}l)"/><path d="M57 58l9 40-9.5-6.5-7 8.5-7.5-30Z" fill="url(#{k}r)"/>'
            f'<path d="M24 70l2.2 1.4-5.4 23-1.9 1.3Z" fill="#FEC200"/><path d="M60 70l-2.2 1.4 5.4 23 1.9 1.3Z" fill="#FEC200"/>'
            f'<circle cx="42" cy="40" r="35" fill="#FEC200" opacity=".14"/>'
            f'<g filter="url(#{k}d)"><path d="M42 6 71.4 23v34L42 74 12.6 57V23Z" fill="url(#{k}l)"/>'
            f'<path d="M42 6 71.4 23 63.6 27.5 42 15Z" fill="#fff" opacity=".25"/><path d="M12.6 23 42 6v9L20.4 27.5Z" fill="#fff" opacity=".3"/>'
            f'<path d="M71.4 57 42 74v-9l21.6-12.5Z" fill="#1C0B35" opacity=".3"/>'
            f'<path d="M42 15 63.6 27.5v25L42 65 20.4 52.5v-25Z" fill="url(#{k}f)" stroke="#FFF1B8" stroke-opacity=".8" stroke-width="1.2"/></g>'
            f'<path d="M42 15 63.6 27.5v8C52 31 34 31 20.4 36v-8.5Z" fill="url(#{k}g)"/>{mid}</svg>')


def flame(cls="fx"):
    """Former flame mark: now the badge with a star (kept under the old name for every page that calls it)."""
    return badge(None, cls)


def old_flame(cls="fx"):
    """Filled flame mark (the streak sign), coloured with currentColor."""
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>'


def icon(name, cls="i"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICON[name]}</svg>'


STYLE = """<style>
:root{--r:14px}
:root,:root[data-theme=light]{--bg:#F4F2F8;--surface:#ffffff;--surface2:#EEEAF5;--border:#E0D9EC;--text:#1B1430;--muted:#4A4163;--faint:#675D80;--accent:#7336F7;--accent2:#5E27D8;--green:#177A3A;--red:#C8372D;--amber:#9A5200;--gold:#8A6400;--orange:#C2541F;--yellow:#F0B90B;--shadow:0 1px 2px rgba(42,15,76,.06);--shadow-lg:0 2px 4px rgba(42,15,76,.06),0 12px 28px -8px rgba(42,15,76,.16);--bar:#E3DDEE;--board:#2A0F4C;--board2:#200A3B;--bline:#4A2A78;--bink:#F7F5FB;--bmuted:#C3B4DD;--gilt:#F0B90B;--gink:#241600;--hero:var(--board);--on-accent:#fff}
:root[data-theme=dark]{--bg:#120A1F;--surface:#1B1230;--surface2:#241940;--border:#33264E;--text:#F3EFFA;--muted:#CFC4E2;--faint:#A497BF;--accent:#A98BFF;--accent2:#C4AEFF;--green:#5FD08A;--red:#FF8A90;--amber:#FFB86B;--gold:#F0B90B;--orange:#FF9F6E;--yellow:#F0B90B;--shadow:0 1px 2px rgba(0,0,0,.3);--shadow-lg:0 2px 4px rgba(0,0,0,.3),0 12px 28px -8px rgba(0,0,0,.6);--bar:#3A2D57;--board:#2A1250;--board2:#1D0B37;--bline:#4D2F7E;--bink:#F7F5FB;--bmuted:#C9BBE3;--gilt:#F0B90B;--gink:#241600;--hero:var(--board);--on-accent:#160A2B}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#120A1F;--surface:#1B1230;--surface2:#241940;--border:#33264E;--text:#F3EFFA;--muted:#CFC4E2;--faint:#A497BF;--accent:#A98BFF;--accent2:#C4AEFF;--green:#5FD08A;--red:#FF8A90;--amber:#FFB86B;--gold:#F0B90B;--orange:#FF9F6E;--yellow:#F0B90B;--shadow:0 1px 2px rgba(0,0,0,.3);--shadow-lg:0 2px 4px rgba(0,0,0,.3),0 12px 28px -8px rgba(0,0,0,.6);--bar:#3A2D57;--board:#2A1250;--board2:#1D0B37;--bline:#4D2F7E;--bink:#F7F5FB;--bmuted:#C9BBE3;--gilt:#F0B90B;--gink:#241600;--hero:var(--board);--on-accent:#160A2B}}
:root{--glass2:var(--surface2);--grad:var(--hero);--magenta:var(--accent);--cyan:var(--accent2)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;accent-color:var(--accent);caret-color:var(--accent);scrollbar-color:var(--bar) transparent}
::selection{background:color-mix(in srgb,var(--accent) 24%,transparent)}:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Golos Text,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}button{font:inherit}
.i{width:16px;height:16px;flex:none;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.ti{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round}
.ck{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.aurora{display:none}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
.glass,.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--shadow)}
.rise{animation:fade .35s ease both}@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.top{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--border)}
.top-in{max-width:1200px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;gap:24px}
.brand{display:flex;align-items:center;gap:8px;font-weight:600;white-space:nowrap}
.mark{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:var(--text);color:var(--bg)}.mark.logo{width:32px;height:32px;background:none;border-radius:9px;box-shadow:0 4px 12px -4px rgba(46,15,76,.45)}.mark.logo svg{width:100%;height:100%;display:block}
.tabs{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}.tabs::-webkit-scrollbar{display:none}
.tab{padding:6px 12px;border-radius:8px;color:var(--muted);font-weight:500;white-space:nowrap}.tab:hover,.tab.on{color:var(--text);background:var(--surface2)}
.right{margin-left:auto;display:flex;align-items:center;gap:8px}
.who select{height:32px;padding:0 8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font:500 0.8125rem Golos Text,sans-serif}
.ib{display:grid;place-items:center;width:32px;height:32px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer}
.ib:hover{color:var(--text)}
.user{display:flex;flex-direction:column;line-height:1.25;text-align:right}.user b{font-weight:600;font-size:0.8125rem}.user span{font-size:0.75rem;color:var(--faint)}
.ph1{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:16px;margin:8px 0 24px}
.ph1 h1{margin:0;font-size:1.5rem;line-height:1.333;font-weight:600;letter-spacing:-.02em}.ph1 p{margin:0;color:var(--muted)}
.ctrl{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.segs{display:flex;padding:2px;border-radius:10px;background:var(--surface2);border:1px solid var(--border)}
.seg{padding:6px 14px;border-radius:8px;color:var(--muted);font-weight:500}.seg.on{background:var(--surface);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.1)}
.date{display:flex;align-items:center;border:1px solid var(--border);border-radius:10px;background:var(--surface);height:36px}
.date input{border:0;background:transparent;color:var(--text);font:500 0.8125rem Golos Text,sans-serif;padding:0 4px;color-scheme:light dark;height:100%}
.step{display:grid;place-items:center;width:32px;height:100%;color:var(--muted)}.step:hover{color:var(--text)}.step.off{opacity:.3}
.banner{display:flex;gap:12px;align-items:center;padding:10px 14px;border-radius:8px;border:1px solid var(--border);margin-bottom:10px;background:var(--surface);font-size:0.8125rem}
.banner.warn{border-color:var(--amber);color:var(--amber)}
.banner.success{border-color:var(--green);animation:glow 2.4s ease-out 1}
.banner.success b{display:block;font-weight:600}.banner.success span{color:var(--muted)}
.badge-ok{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--green);color:#fff;flex:none}
.badge-ok .ck{stroke-dasharray:24;stroke-dashoffset:24;animation:draw .6s .2s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}@keyframes glow{0%{box-shadow:0 0 0 0 rgba(34,197,94,.35)}100%{box-shadow:0 0 0 14px rgba(34,197,94,0)}}
.kpis{display:grid;grid-template-columns:1.25fr 1.25fr 1fr 1fr;gap:16px}
.g2{display:grid;grid-template-columns:1.5fr 1fr;gap:16px;margin-top:16px}
.g2b{display:grid;grid-template-columns:1fr 1.5fr;gap:16px;margin-top:16px}
.card{padding:20px;min-width:0}
.kpi header{display:flex;align-items:center;gap:8px;color:var(--muted);font-weight:500;min-height:22px}
.kpi header .tr{margin-left:auto}
.fig{font-size:1.75rem;line-height:1.286;font-weight:600;letter-spacing:-.02em;margin-top:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.fig.xl{font-size:2rem;line-height:1.25}.fig.gold{color:var(--gold)}
.kpi footer{display:flex;justify-content:space-between;margin-top:12px;color:var(--muted);font-size:0.8125rem}.kpi footer b{color:var(--text);font-weight:600}
.kpi footer b.pos{color:var(--green)}
.note{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0 0;font-size:0.75rem;color:var(--faint)}.muted{margin:0;color:var(--muted)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:16px}.split>div{min-width:0}.split>div+div{border-left:1px solid var(--border);padding-left:16px}
.tr{display:inline-flex;align-items:center;gap:2px;font-size:0.75rem;font-weight:600;padding:1px 6px;border-radius:6px}
.tr.up{color:var(--green);background:rgba(34,197,94,.1)}.tr.down{color:var(--red);background:rgba(248,113,113,.1)}.tr.flat{color:var(--faint)}
.pg{height:6px;border-radius:999px;background:var(--bar);overflow:hidden;margin-top:8px}
.pg i{display:block;height:100%;width:0;border-radius:inherit;background:var(--accent);transition:width .9s cubic-bezier(.2,.8,.2,1)}
.pg.ok i{background:var(--green)}.go .pg i{width:var(--w)}
.ch{display:flex;align-items:center;gap:8px;margin-bottom:16px;min-height:28px}.ch h2{margin:0;font-size:0.9375rem;font-weight:600}
.ch .meta,.ch .more,.ch .btn{margin-left:auto}.meta{color:var(--faint);font-size:0.75rem;display:flex;align-items:center;gap:6px;text-align:right}
.more{display:inline-flex;align-items:center;gap:4px;color:var(--muted);font-weight:500}.more:hover{color:var(--text)}
.prow+.prow{margin-top:16px;padding-top:16px;border-top:1px solid var(--border)}
.ph{display:flex;justify-content:space-between;font-weight:500}.ph b{font-weight:600;font-variant-numeric:tabular-nums}
.ps{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-top:8px;font-size:0.75rem;color:var(--faint);font-variant-numeric:tabular-nums}
.bonus.won{border-color:var(--gold)}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
.cal .wd{font-size:0.6875rem;color:var(--faint);text-align:center;padding-bottom:4px;text-transform:uppercase}
.cal .d{position:relative;display:grid;place-items:center;height:40px;border-radius:8px;font-size:0.75rem;font-weight:500;color:var(--muted);background:var(--surface2);font-variant-numeric:tabular-nums}
.cal .d:hover{box-shadow:inset 0 0 0 1px var(--border)}
.cal .d.fut{opacity:.35;pointer-events:none}.cal .d.now{box-shadow:inset 0 0 0 1.5px var(--text)}
.cal .d.done{background:rgba(34,197,94,.14);color:var(--text)}
.cal .d .ck{position:absolute;top:3px;right:3px;width:10px;height:10px;color:var(--green)}
.cal .d em{position:absolute;bottom:4px;width:4px;height:4px;border-radius:50%;background:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin-top:12px;font-size:0.75rem;color:var(--faint)}.legend span{display:flex;align-items:center;gap:6px}
.legend .ck{color:var(--green)}.legend em{width:4px;height:4px;border-radius:50%;background:var(--accent)}
.chart{height:240px}.chart svg{width:100%;height:100%;display:block}
.sw{display:inline-block;width:8px;height:8px;border-radius:2px}.sw.a{background:var(--accent)}.sw.b{background:var(--text);border-radius:50%}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
thead th{font-size:0.75rem;font-weight:500;color:var(--faint)}th:first-child{text-align:left;padding-left:0}tbody th{font-weight:500}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
td.pc{width:32%;min-width:130px}td.pc .pg{display:inline-block;width:calc(100% - 52px);vertical-align:middle;margin:0 8px 0 0}td.pc span{display:inline-block;width:44px;color:var(--muted)}
.btn{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-weight:500;cursor:pointer}
.btn:hover{background:var(--surface2)}.btn.sm{height:28px;padding:0 10px;font-size:0.75rem}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--text);background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px}
.btn2{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 14px;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-weight:500;cursor:pointer}
.nav{display:grid;place-items:center;width:32px;height:32px;border-radius:8px;color:var(--muted)}
@media (max-width:1100px){.kpis{grid-template-columns:1fr 1fr}.g2,.g2b{grid-template-columns:1fr}}
@media (max-width:720px){.wrap{padding:16px}.top-in{flex-wrap:wrap;height:auto;padding:8px 16px;gap:8px 12px}.user{display:none}
.tabs{order:3;width:100%;margin:0 -4px}.kpis{grid-template-columns:1fr;gap:12px}.g2,.g2b{gap:12px;margin-top:12px}.card{padding:16px}
.ph1{margin:4px 0 16px}.ph1 h1{font-size:1.25rem;line-height:1.4}.ctrl{width:100%}.segs{flex:1}.seg{flex:1;text-align:center}
.fig.xl{font-size:1.75rem;line-height:1.286}.fig{font-size:1.5rem;line-height:1.333}.chart{height:200px}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}.pg i{width:var(--w)}}
</style>"""



HEAD = """<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="apple-touch-icon" href="/logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script>try{var q=new URLSearchParams(location.search).get('theme'),t=q||localStorage.getItem('mk-theme');if(t)document.documentElement.dataset.theme=t}catch(e){}</script>"""

# Shell: a left sidebar on computers (as in the EduApp dashboards), a bottom bar with «Тағы» on phones.
SHELL_CSS = """<style>
body{font-family:Golos Text,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:0.875rem}
.side{position:fixed;inset:0 auto 0 0;width:248px;z-index:40;display:flex;flex-direction:column;gap:2px;padding:18px 12px;
background:var(--board);color:var(--bink);border-right:0;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--bline) transparent}
.side .brand{display:flex;align-items:center;gap:10px;padding:2px 8px 4px;font-weight:800;font-size:1rem;letter-spacing:-.01em}
.side .brand .mark{width:36px;height:36px;flex:none}.side .bn{font-weight:900;font-size:1rem;letter-spacing:-.02em;line-height:1.1}.side .bn b{font-weight:600;color:var(--bmuted)}.side .sub{padding:0 8px 14px;font-size:0.75rem;color:var(--bmuted);font-weight:500}
.side .who{margin:0 0 12px;padding:12px;border-radius:10px;background:rgba(255,255,255,.07);display:flex;gap:10px;align-items:center}
.side .who .av{display:grid;place-items:center;flex:none;width:40px;height:40px;border-radius:50%;font-size:0.9375rem;font-weight:900;line-height:1;background:var(--bink);color:var(--board)}
.side .who small{display:block;font-size:0.75rem;font-weight:500;color:var(--bmuted)}
.side .who b{display:block;font-size:0.875rem;font-weight:600;line-height:1.25}
.side .grp{margin:16px 12px 6px;padding-top:12px;border-top:1px solid var(--bline);font-size:0.75rem;font-weight:500;color:var(--bmuted)}
.side .nl{display:flex;align-items:center;gap:12px;min-height:42px;padding:0 12px;border-radius:8px;color:var(--bmuted);font-weight:500;font-size:0.875rem;transition:background .15s,color .15s}
.side .nl .i{width:19px;height:19px;stroke-width:1.9}
.side .nl:hover{background:rgba(255,255,255,.07);color:var(--bink)}
.side .nl.on{background:rgba(255,255,255,.13);color:#fff;font-weight:600}
.side .foot{margin-top:auto;padding-top:14px;display:grid;gap:10px}
.side .foot .extra select,.side .foot .extra .wsel{width:100%}
.side .tools{display:flex;align-items:center;gap:6px;padding:4px;border-radius:10px;background:rgba(255,255,255,.07)}
.side .tools .ib{flex:1;width:auto;height:36px;border:0;border-radius:8px;background:transparent;color:var(--bmuted)}
.side .tools .ib:hover{background:rgba(255,255,255,.1);color:var(--bink)}
.side .tools .ib .i{width:18px;height:18px}
body{padding-left:248px}
.top{display:none}
.wrap{padding:28px clamp(16px,3vw,36px)}
.card,.k{border-radius:var(--r);border:1px solid var(--border);box-shadow:none}
/* apple-design «Response»: hover lifts only where a real pointer hovers — on a phone they would stay stuck after a tap */
@media (hover:hover){.card:hover,.k:hover,.hero:hover{transform:none;box-shadow:none}}
.hero,.ph{border-radius:var(--r);box-shadow:none}
.hero:after,.ph:after,.hero:before,.ph:before{content:none!important}
.btnp{background:var(--accent);color:var(--on-accent);box-shadow:none;border-radius:10px}
.btnp:hover{background:var(--accent2)}
.btng,.btny{border-radius:10px}.btny{background:var(--gilt);color:var(--gink);box-shadow:none}
.segs{border:1px solid var(--border);padding:3px;border-radius:10px;background:var(--surface)}
.seg,.segs a{white-space:nowrap}
.seg{border-radius:7px;font-weight:500;min-height:36px;display:inline-flex;align-items:center;justify-content:center}
.seg.on{background:var(--board);color:var(--bink);font-weight:600;box-shadow:none}
.ptag,.pill{font-weight:800}
.mbar,.msheet,.side .mtt{display:none}@media (prefers-reduced-transparency:reduce){.msheet.open{background:rgba(18,10,34,.82)}.zdlg::backdrop{background:rgba(18,10,34,.85)}}@media (prefers-contrast:more){:root,:root[data-theme=light]{--muted:#2E2840;--faint:#4A4460;--border:#B3A9C9}:root[data-theme=dark]{--muted:#F4F0FC;--faint:#E2DAF2;--border:#7A68A6}.zdlg,.ztoast,.msheet .in{outline:2px solid var(--text);outline-offset:-2px}.ztoast{background:#000}.msheet.open{background:rgba(18,10,34,.82)}}@media (prefers-contrast:more) and (prefers-color-scheme:dark){:root:not([data-theme=light]){--muted:#F4F0FC;--faint:#E2DAF2;--border:#7A68A6}}@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
/* apple-design «Response»: a switch shows its new state at once, and a thin bar says the page is on its way */
.zload{position:fixed;left:0;top:0;height:3px;width:0;z-index:100;background:var(--accent);opacity:0;pointer-events:none}
.zbusy .zload{opacity:1;animation:zld 1.6s cubic-bezier(.1,.7,.3,1) forwards}@keyframes zld{0%{width:0}60%{width:70%}100%{width:88%}}
.zbusy main{opacity:.55;transition:opacity .2s .15s}
@media (prefers-reduced-motion:reduce){.zbusy .zload{animation:none;width:100%}}
/* apple-design «Response»: every control answers the instant it is pressed (pointer-down), not when the next page arrives */
button,.btn,.btn2,.btnp,.btng,.btny,.rcb,.seg,.segs a,.nl,.mbar a,.mbar button,.zcv-tabs button,.askp button,.tadd,.cbx,.tdel,.step,.ib,.more,.pedit,.chip-btn,.pc,.vas select{
-webkit-tap-highlight-color:transparent;transition:transform .1s ease-out,background-color .15s,color .15s,box-shadow .15s}
button:active,.btn:active,.btn2:active,.btnp:active,.btng:active,.btny:active,.rcb:active,.seg:active,.segs a:active,.zcv-tabs button:active,
.askp button:active,.tadd:active,.cbx:active,.tdel:active,.step:active,.ib:active,.more:active,.pedit:active,.mbar button:active{transform:scale(.97);transition:transform .1s ease-out}
.nl:active{transform:scale(.98);background:color-mix(in srgb,var(--accent) 14%,var(--surface2))}
.mbar a:active{transform:scale(.94);background:color-mix(in srgb,var(--accent) 12%,transparent)}
.pc:active,.k:active,.zbc:active{transform:scale(.99)}.zdlg{border:0;padding:0;border-radius:24px;background:var(--surface);color:var(--text);width:min(420px,calc(100vw - 32px));box-shadow:0 30px 80px -20px rgba(18,10,34,.55)}.zdlg::backdrop{background:rgba(18,10,34,.45)}.zdlg[open],.pdlg[open]{animation:zdin .2s cubic-bezier(0,0,.2,1)}.zdlg[open]::backdrop,.pdlg[open]::backdrop{animation:zbin .2s cubic-bezier(0,0,.2,1)}.zdlg[open].out,.pdlg[open].out{animation:zdout .18s cubic-bezier(.8,0,1,1) forwards}.zdlg[open].out::backdrop,.pdlg[open].out::backdrop{animation:zbout .18s cubic-bezier(.8,0,1,1) forwards}@keyframes zdout{to{opacity:0;transform:scale(.9)}}@keyframes zbin{from{opacity:0}}@keyframes zbout{to{opacity:0}}@keyframes zdin{from{opacity:0;transform:scale(.9)}}.zdlg .in{padding:22px}.zdlg h3{margin:0 0 6px;font-size:1.125rem;font-weight:700;letter-spacing:-.02em}.zdlg p{margin:0 0 18px;color:var(--muted);line-height:1.5}.zdlg .row{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}.zdlg button{height:44px;padding:0 18px;border:0;border-radius:10px;font:600 0.875rem Golos Text,sans-serif;cursor:pointer}.zdlg .no{background:var(--surface2);color:var(--text)}.zdlg .yes{background:var(--red);color:#fff}.ztoast{position:fixed;left:50%;bottom:24px;z-index:90;display:flex;align-items:center;gap:14px;padding:12px 12px 12px 18px;border-radius:16px;background:#1C1530;color:#fff;font-size:0.875rem;font-weight:700;box-shadow:0 18px 40px -12px rgba(18,10,34,.5);transform:translate(-50%,0);transition:opacity .22s cubic-bezier(0,0,.2,1),transform .22s cubic-bezier(0,0,.2,1)}.ztoast.err{box-shadow:inset 4px 0 0 var(--red),0 18px 40px -12px rgba(18,10,34,.5)}.ztoast .x{width:36px;padding:0;background:transparent;color:#fff;font-size:1.375rem;line-height:1}:root[data-theme=dark] .ztoast{background:#3B2D61;box-shadow:0 0 0 1px rgba(255,255,255,.16),0 18px 40px -12px rgba(0,0,0,.75)}:root[data-theme=dark] .ztoast.err{box-shadow:inset 4px 0 0 var(--red),0 0 0 1px rgba(255,255,255,.16),0 18px 40px -12px rgba(0,0,0,.75)}@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .ztoast{background:#3B2D61;box-shadow:0 0 0 1px rgba(255,255,255,.16),0 18px 40px -12px rgba(0,0,0,.75)}:root:not([data-theme=light]) .ztoast.err{box-shadow:inset 4px 0 0 var(--red),0 0 0 1px rgba(255,255,255,.16),0 18px 40px -12px rgba(0,0,0,.75)}}.ztoast.out{opacity:0;transform:translate(-50%,12px);pointer-events:none;transition-timing-function:cubic-bezier(.8,0,1,1)}.ztoast button{height:36px;padding:0 14px;border:0;border-radius:8px;background:#fff;color:#2A0F4C;font:600 0.8125rem Golos Text,sans-serif;cursor:pointer}@media (max-width:860px){.ztoast{bottom:calc(84px + env(safe-area-inset-bottom))}}[data-undo-row].zgone{display:none}
.cardin{opacity:1!important;transform:none!important;animation:none!important}
.pbar i,.pr-b i,.pg i{width:var(--w)!important;transition:none!important}
.spark .ln,.zcv-ln,.line{animation:none!important;stroke-dashoffset:0!important}.zcv-ar,.area{opacity:1!important;animation:none!important}
.zb-cols i,.zf-b i,.bar{animation:none!important;transform:none!important}.zb-ring .ra{animation:none!important;stroke-dashoffset:var(--o)!important}
.okc,.okc svg{animation:none!important;transform:none!important;stroke-dashoffset:0!important}
.vas{display:grid;gap:6px}.vas label{font-size:0.75rem;font-weight:500;color:var(--bmuted);padding:0 4px}
.vas select{width:100%;height:42px;padding:0 12px;border-radius:8px;border:1px solid var(--bline);background:var(--board2);color:var(--bink);font:700 0.8125rem Golos Text,sans-serif}
.vab{position:sticky;top:0;z-index:45;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;padding:10px 16px;
background:var(--gilt);color:var(--gink);font-size:0.8125rem;font-weight:600}
.vab b{font-weight:700}.vab a{padding:5px 12px;border-radius:8px;background:var(--board);color:#fff;font-weight:600}.vab .i{width:16px;height:16px}
.hero>*,.ph>*{position:relative;z-index:1}
.sp-c .glow{filter:blur(3px)}
@media (max-width:860px){
 body{padding-left:0;padding-bottom:calc(74px + env(safe-area-inset-bottom))}
 .side{position:sticky;inset:auto;top:0;width:auto;height:auto;flex-direction:row;align-items:center;padding:8px 16px;border-right:0;border-bottom:0;overflow:visible}
 .side .sub,.side .who,.side .grp,.side .nl,.side .foot .extra{display:none}
 .side .brand{padding:0;font-size:0.9375rem}.side .brand .mark{width:30px;height:30px}
 .side .foot{margin:0 0 0 auto;padding:0}.side .tools{background:transparent;padding:0}.side .tools .ib{color:var(--bmuted)}.side .tools .ib{width:40px;flex:none;height:40px}
 .mbar{position:fixed;left:0;right:0;bottom:0;z-index:60;display:grid;grid-template-columns:repeat(5,1fr);gap:2px;
  padding:6px 6px calc(6px + env(safe-area-inset-bottom));background:color-mix(in srgb,var(--surface) 74%,transparent);-webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);border-top:1px solid color-mix(in srgb,var(--border) 70%,transparent)}
 .side{z-index:50;background:var(--board)}
 @supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){.mbar{background:var(--surface)}}
 @media (prefers-reduced-transparency:reduce),(prefers-contrast:more){.mbar{background:var(--surface);-webkit-backdrop-filter:none;backdrop-filter:none;border-top-color:var(--border)}}
 .side .mtt{display:block;font-weight:600;font-size:1.0625rem;letter-spacing:-.02em;margin-left:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .side.ttl .bn{display:none}
 .mbar a,.mbar button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:54px;border:0;border-radius:14px;
  background:transparent;color:var(--faint);font:500 0.75rem Golos Text,sans-serif;cursor:pointer}
 .mbar .i{width:22px;height:22px;stroke-width:1.9}
 .mbar .on{color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent);font-weight:600}
 /* the sheet and its scrim are moved by a spring in SHEET_JS (no CSS transitions), so they can be caught mid-flight */
 .msheet{position:fixed;inset:0;z-index:70;display:flex;align-items:flex-end;visibility:hidden;pointer-events:none;background:rgba(18,10,34,0)}
 .msheet.open{visibility:visible;pointer-events:auto;background:rgba(18,10,34,.45)}
 .msheet .in{width:100%;max-height:80vh;overflow-y:auto;overscroll-behavior:contain;background:var(--surface);border-radius:24px 24px 0 0;
  padding:0 16px calc(18px + env(safe-area-inset-bottom));transform:translateY(105%);will-change:transform}
 .msheet.open .in{transform:none}
 .msheet .hd{position:sticky;top:0;z-index:1;display:block;height:30px;margin:0 -16px 4px;background:var(--surface);touch-action:none;cursor:grab}
 .msheet .hd:after{content:"";position:absolute;left:50%;top:12px;width:44px;height:5px;margin-left:-22px;border-radius:9px;background:var(--border)}
 .msheet .nl{display:flex;align-items:center;gap:14px;min-height:52px;padding:0 14px;border-radius:10px;color:var(--text);font-weight:500;font-size:0.9375rem}
 .msheet .nl .i{width:21px;height:21px;color:var(--accent)}
 .msheet .nl.on{background:var(--surface2);font-weight:600}
 .msheet .grp{margin:12px 14px 4px;font-size:0.75rem;font-weight:500;color:var(--faint)}
 .msheet .extra{padding:8px 14px}
 .wrap{padding:16px}
 .ph h1{font-size:1.375rem;line-height:1.273}
}
@keyframes sheet{from{transform:translateY(30px);opacity:0}to{transform:none;opacity:1}}
/* re-audit 2.1: a KPI title is never cut — on narrow cards it takes its own line */
@media (max-width:640px){.kh{flex-wrap:wrap;row-gap:8px}.kh .kl{order:3;flex-basis:100%;white-space:normal;overflow:visible;line-height:1.3;font-weight:700;color:var(--text)}}
/* re-audit 2.2: on touch screens every control is at least 44×44 */
@media (pointer:coarse){
 html .side .tools .ib{width:44px;height:44px}html .side .brand{min-height:44px;min-width:44px}
 html .date{height:44px}html .step{width:44px}
 html .seg,html .segs a,html .zcv-tabs button{min-height:44px}
 html .btn,html .btn2,html .btn.sm{height:44px}
 html .cbx{position:relative}html .cbx::after{content:"";position:absolute;inset:-10px}
 html .tk .tdel{width:44px;height:44px;margin:-4px -8px -4px 0}
 html .heat .hd{height:44px}html a.step{height:44px;min-width:44px}
}
/* re-audit 2.5: a segmented switch never wraps on a phone — it scrolls, and the edge fade says there is more */
@media (max-width:640px){html .zcv-tabs{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;scroll-snap-type:x proximity;
 -webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 32px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 32px),transparent)}
 html .zcv-tabs::-webkit-scrollbar{display:none}html .zcv-tabs.end{-webkit-mask-image:none;mask-image:none}
 html .zcv-tabs button{flex:none;white-space:nowrap;scroll-snap-align:start}}
/* re-audit 2.6: with large text a card header wraps instead of pushing the page sideways */
.ch{flex-wrap:wrap;row-gap:4px}.ch>*{min-width:0}.ch .meta{overflow-wrap:anywhere}.sf2 input{min-width:0}.row4>label,.row4>.tmw{min-width:0}
/* one type scale on every page: card title 17, tile number 26 (22 on a phone), label 13, caption and note 12 */
html body main h2{font-size:1.0625rem;font-weight:600;letter-spacing:-.01em}
html body main .rw .rv,html body main .k .kv,html body main .pnum b,html body main .adsg b{font-size:1.625rem;line-height:1.2;font-weight:700;letter-spacing:-.025em;font-variant-numeric:tabular-nums}
html body main .rs,html body main .ksub,html body main .card .sub,html body main .note,html body main label small,html body main .who small,html body main .streak small{font-size:.75rem;font-weight:400;color:var(--faint)}
html body main thead th{font-size:.75rem;font-weight:500;color:var(--faint)}html body main .ch a.meta{color:var(--accent)}
@media (min-width:721px){html body main .rw .rl,html body main .kh .kl,html body main .pnum span,html body main .adsg span{font-size:.8125rem;font-weight:500;color:var(--muted)}html body main .zc-lbl{font-size:.8125rem;font-weight:500}}
@media (max-width:720px){html body main .rw .rv,html body main .k .kv,html body main .pnum b,html body main .adsg b{font-size:1.375rem}}
</style>"""

SHEET_JS = r"""(function(){var m=document.getElementById("mmore"),s=document.getElementById("msheet");if(!m)return;var inn=s.querySelector(".in");
/* apple-design: the sheet is driven by a spring, not a CSS transition — it can be caught at any moment, starts from where it
   is on screen and keeps the finger's speed. y = px below the open position (0 = open, H = hidden) */
var y=0,v=0,goal=0,raf=0,last=0,H=1,RM=matchMedia("(prefers-reduced-motion: reduce)"),
 SOLID=matchMedia("(prefers-reduced-transparency: reduce), (prefers-contrast: more)");
function full(){return inn.offsetHeight*1.05}
function paint(){inn.style.transform="translateY("+y.toFixed(2)+"px)";
 s.style.backgroundColor="rgba(18,10,34,"+((SOLID.matches?.82:.45)*Math.max(0,Math.min(1,1-y/H))).toFixed(3)+")"}
/* while the sheet is up, the page behind it is out of reach (keyboard, screen reader); focus goes in and comes back to «Тағы» */
var held=[];
function hold(on){if(on){held=[].filter.call(document.body.children,function(x){return !x.contains(s)&&!/^(SCRIPT|STYLE|DIALOG)$/.test(x.tagName)&&!x.classList.contains("ztoast")&&!x.inert});
  held.forEach(function(x){x.inert=true})}else{held.forEach(function(x){x.inert=false});held=[]}}
function settle(){raf=0;y=goal;v=0;if(goal>0){var back=s.contains(document.activeElement);s.classList.remove("open");inn.style.transform="";s.style.backgroundColor="";
 hold(false);if(back)m.focus({preventScroll:true})}else paint()}
/* critically damped spring (damping 1.0, response .34 s): no overshoot, so the sheet never lifts off the bottom edge */
var K=Math.pow(2*Math.PI/.34,2),C=4*Math.PI/.34;
function step(t){var dt=Math.min(.064,Math.max(0,t-last)/1000),n=Math.max(1,Math.ceil(dt/.004)),h=dt/n;last=t;
 for(var i=0;i<n;i++){v+=(-K*(y-goal)-C*v)*h;y+=v*h}
 if(Math.abs(y-goal)<.5&&Math.abs(v)<20){settle();return}paint();raf=requestAnimationFrame(step)}
/* vel undefined = keep the current speed, so a reversal blends instead of hitting a wall */
function go(to,vel){goal=to;if(vel!==undefined)v=vel;
 if(RM.matches){if(raf)cancelAnimationFrame(raf);settle();if(to===0&&inn.animate)inn.animate([{opacity:0},{opacity:1}],{duration:200});return}
 if(!raf){last=performance.now();raf=requestAnimationFrame(step)}}
function open(){H=full();if(!s.classList.contains("open")){y=H;v=0;s.classList.add("open");paint();hold(true);
 var f=inn.querySelector(".nl.on")||inn.querySelector("a,button,select");if(f)f.focus({preventScroll:true})}go(0)}
function close(vel){if(!s.classList.contains("open"))return;H=full();go(H,vel)}
m.onclick=open;s.addEventListener("click",function(e){if(e.target===s)close()});
document.addEventListener("keydown",function(e){if(e.key==="Escape")close()});
/* drag down to dismiss — 1:1 with the finger, from where it was grabbed; a moving sheet is caught on touch-down */
var base=0,c0=0,drag=false,armed=false,pid=null,hist=[];
function rubber(o,d){return(o*d*.55)/(d+.55*Math.abs(o))}
function project(v){return(v/1000)*.998/(1-.998)}
inn.addEventListener("pointerdown",function(e){if(e.pointerType==="mouse"&&e.button!==0)return;
 var moving=!!raf,onHandle=!!e.target.closest(".hd");if(!moving&&!onHandle&&inn.scrollTop>0)return;
 if(moving){cancelAnimationFrame(raf);raf=0;v=0}
 H=full();pid=e.pointerId;base=y;c0=e.clientY;hist=[{y:e.clientY,t:e.timeStamp}];
 armed=moving?"m":onHandle?"h":"c";drag=moving;if(drag){try{inn.setPointerCapture(pid)}catch(_){}}});
inn.addEventListener("pointermove",function(e){if(!armed||e.pointerId!==pid)return;var dy=e.clientY-c0;
 if(!drag){if(Math.abs(dy)<10)return;if(dy<0&&armed==="c"){armed=false;return}drag=true;c0=e.clientY;dy=0;try{inn.setPointerCapture(pid)}catch(_){}}
 var raw=base+dy;y=raw<0?rubber(raw,H):raw;paint();
 hist.push({y:e.clientY,t:e.timeStamp});if(hist.length>6)hist.shift();e.preventDefault()});
function end(e){if(!armed||e.pointerId!==pid)return;armed=false;if(!drag)return;drag=false;
 var a=hist[0],b=hist[hist.length-1],vel=hist.length>1&&e.timeStamp-b.t<80?(b.y-a.y)/Math.max(1,b.t-a.t)*1000:0;
 if(y+project(vel)>H*.5)close(vel);else go(0,vel)}
inn.addEventListener("pointerup",end);inn.addEventListener("pointercancel",end);
/* when the list does not scroll, the whole sheet is draggable; otherwise the handle and the top of the list are */
new ResizeObserver(function(){inn.style.touchAction=inn.scrollHeight>inn.clientHeight+2?"pan-y":"none"}).observe(inn)})();"""


CONFIRM_JS = '<dialog class="zdlg" id="zdlg"><form method="dialog" class="in"><h3 id="zdt"></h3><p id="zdp"></p><div class="row">\n<button class="no" value="no">Бас тарту</button><button class="yes" value="yes" id="zdy"></button></div></form></dialog>\n<script>(function(){\n/* apple-design «Spatial consistency»: a dialog grows out of the button that opened it and shrinks back into it */\nfunction from(d,el){if(!el||!el.getBoundingClientRect){d.style.transformOrigin=\'\';return}var r=el.getBoundingClientRect();\n /* measure the dialog at rest (the entry animation is already scaling it), then let the animation start fresh */\n d.style.animation=\'none\';var q=d.getBoundingClientRect();d.style.animation=\'\';\n d.style.transformOrigin=(r.left+r.width/2-q.left)+\'px \'+(r.top+r.height/2-q.top)+\'px\'}\nwindow.zDlgOpen=function(d,el){d.classList.remove(\'out\');d.showModal();from(d,el)};\nwindow.zDlgClose=function(d,v){if(!d.open||d.classList.contains(\'out\'))return;\n if(matchMedia(\'(prefers-reduced-motion: reduce)\').matches){d.close(v);return}\n d.classList.add(\'out\');setTimeout(function(){d.classList.remove(\'out\');d.close(v)},180)};\n/* confirm only what cannot be undone: data-confirm="Title|Text|Button" on a form or a submit button */\nvar dl=document.getElementById(\'zdlg\');\nfunction ask(spec,go,el){var p=(spec||\'\').split(\'|\');document.getElementById(\'zdt\').textContent=p[0]||\'Сенімдісіз бе?\';\n document.getElementById(\'zdp\').textContent=p[1]||\'\';document.getElementById(\'zdy\').textContent=p[2]||\'Иә\';\n if(!dl.showModal){if(window.confirm((p[0]||\'\')+\'\\n\'+(p[1]||\'\')))go();return}\n dl.returnValue=\'\';dl._go=go;zDlgOpen(dl,el)}\n/* leave the way it came: the action starts at once, the dialog and its scrim fade back out meanwhile */\nfunction shut(v){if(!dl.open||dl.classList.contains(\'out\'))return;var g=dl._go;dl._go=null;if(v===\'yes\'&&g)g();zDlgClose(dl,v)}\ndl.addEventListener(\'cancel\',function(e){e.preventDefault();shut(\'no\')});\ndl.querySelector(\'form\').addEventListener(\'submit\',function(e){e.preventDefault();shut(e.submitter&&e.submitter.value)});\n/* toasts arrive and leave along the same path */\nfunction tin(x){x.classList.add(\'out\');document.body.appendChild(x);void x.offsetWidth;x.classList.remove(\'out\')}\nfunction tout(x){x.classList.add(\'out\');setTimeout(function(){x.remove()},260)}\ndocument.addEventListener(\'click\',function(e){var b=e.target.closest&&e.target.closest(\'button[data-confirm]\');if(!b||b.dataset.ok)return;\n e.preventDefault();ask(b.dataset.confirm,function(){b.dataset.ok=1;b.form.requestSubmit?b.form.requestSubmit(b):b.click()},b)},true);\ndocument.addEventListener(\'submit\',function(e){var f=e.target;\n if(f.dataset.confirm&&!f.dataset.ok){e.preventDefault();ask(f.dataset.confirm,function(){f.dataset.ok=1;f.submit()},e.submitter||f);return}\n /* small deletions: hide at once, «Қайтару» for 5 s, then really send */\n if(f.dataset.undo){e.preventDefault();var row=f.closest(\'[data-undo-row]\');if(row)row.classList.add(\'zgone\');\n  var data=new FormData(f),done=false,t=document.createElement(\'div\');t.className=\'ztoast\';t.setAttribute(\'role\',\'status\');\n  t.innerHTML=\'<span></span><button type="button">Қайтару</button>\';t.firstChild.textContent=f.dataset.undo;tin(t);\n  function commit(){if(done)return;done=true;removeEventListener(\'pagehide\',commit);\n   tout(t);\n   if(navigator.sendBeacon&&document.visibilityState===\'hidden\'){navigator.sendBeacon(f.action,data);return}\n   send()}\n  /* the row stays hidden while the server works; it is removed only on a real «done», and comes back on failure */\n  function send(){fetch(f.action,{method:\'POST\',body:data,credentials:\'same-origin\',headers:{\'X-Undo\':\'1\'}}).then(function(r){\n    if(r.ok){if(row)row.remove();return}\n    return r.json().catch(function(){return {}}).then(function(j){\n     fail(j.error||(r.status===401?\'кіру мерзімі бітті, қайта кіріңіз\':r.status===403?\'бұл әрекетке рұқсат жоқ\':\'сервер қатесі (\'+r.status+\')\'),r.status>=500)})\n   },function(){fail(\'интернет байланысы жоқ\',true)})}\n  function fail(msg,retry){if(row)row.classList.remove(\'zgone\');\n   document.querySelectorAll(\'.ztoast.err\').forEach(tout);\n   var e=document.createElement(\'div\');e.className=\'ztoast err\';e.setAttribute(\'role\',\'alert\');\n   e.innerHTML=\'<span></span>\'+(retry?\'<button type="button" class="re">Қайталау</button>\':\'\')+\'<button type="button" class="x" aria-label="Жабу">&times;</button>\';\n   e.firstChild.textContent=(f.dataset.undoFail||\'Өшірілмеді\')+\': \'+msg;tin(e);\n   var re=e.querySelector(\'.re\');if(re)re.onclick=function(){tout(e);if(row)row.classList.add(\'zgone\');send()};\n   e.querySelector(\'.x\').onclick=function(){tout(e)}}\n  var tm=setTimeout(commit,5000);addEventListener(\'pagehide\',commit);\n  t.querySelector(\'button\').onclick=function(){clearTimeout(tm);done=true;removeEventListener(\'pagehide\',commit);if(row)row.classList.remove(\'zgone\');\n   tout(t)}}\n});})();</script>'


ROLE_NAMES = {"admin": "Әкімші", "superadmin": "Әкімші", "lead": "Маркетинг жетекшісі", "smm": "Маркетолог"}
MOBILE_MAIN = ("home", "instagram", "content", "bot")


def nav_items(user: dict | None) -> list:
    """(key, href, label, icon, group) the person may open; the menu and the phone bar are built from it."""
    role = (user or {}).get("r", "admin")
    is_admin = not user or role == "admin"
    items = [("home", "/", "Шолу", "home", "Негізгі"), ("instagram", "/api/igbot/stats", "Instagram", "instagram", "Негізгі"),
             ("content", "/content", "Контент", "film", "Негізгі"), ("bot", "/bot", "Бот", "bot", "Негізгі"),
             ("archive", "/api/igbot/archive", "Тарих", "history", "Негізгі"), ("competitors", "/competitors", "Бәсекелестер", "trend", "Негізгі"),
             ("trends", "/trends", "Трендтер", "flame", "Негізгі")]
    if user:
        items += [("dept", "/dept", "Маркетинг бөлімі", "target", "Бөлім")]
    if role == "lead":
        items += [("ads", "/ads", "Жарнама", "megaphone", "Бөлім")]
    if is_admin and user:
        items += [("ads", "/ads", "Жарнама", "megaphone", "Басқару"), ("team", "/team", "Команда", "users", "Басқару"),
                  ("telegram", "/telegram", "Telegram", "send", "Басқару"), ("settings", "/settings", "Баптау", "settings", "Басқару"),
                  ("status", "/status", "Жүйе", "activity", "Басқару")]
    return items


THEME_JS = """<script>(function(){var r=document.documentElement,b=document.getElementById('theme');if(!b)return;
function swap(){var d=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
r.dataset.theme=d?'light':'dark';try{localStorage.setItem('mk-theme',r.dataset.theme)}catch(e){}
document.dispatchEvent(new Event('themechange'))}
/* the whole page changes as one picture: a single cross-fade, no per-element colour transitions running out of step */
b.onclick=function(){if(document.startViewTransition&&!matchMedia('(prefers-reduced-motion: reduce)').matches){document.startViewTransition(swap);return}
r.classList.add('zthm');swap();void r.offsetWidth;requestAnimationFrame(function(){r.classList.remove('zthm')})}})();</script>
<style>.zthm,.zthm *,.zthm *::before,.zthm *::after{transition:none!important}
::view-transition-old(root),::view-transition-new(root){animation-duration:.28s;animation-timing-function:cubic-bezier(.32,.72,0,1)}</style>"""


FORM_JS = "<script>(function(){if(window.zFormV)return;window.zFormV=1;\nvar st=document.createElement('style');st.textContent='small.ferr,.f small.ferr{display:block;margin-top:2px;font-size:.8125rem;font-weight:700;color:var(--red)}'\n +'[aria-invalid=true]{border-color:var(--red)!important;box-shadow:0 0 0 4px color-mix(in srgb,var(--red) 14%,transparent)!important}';document.head.appendChild(st);\nvar SEL='input,select,textarea',n=0;\nfunction text(el){var v=el.validity,a=function(k){return el.getAttribute(k)};\n if(v.valueMissing)return el.tagName==='SELECT'?'Біреуін таңдаңыз':'Бұл жолды толтырыңыз';\n if(v.badInput)return el.type==='date'?'Күнді толық енгізіңіз':'Тек сан енгізіңіз';\n if(v.patternMismatch)return a('data-err')||'Тек латын әріптері, сан және . _ - болады';\n if(v.tooShort)return 'Кемінде '+a('minlength')+' таңба керек (қазір '+el.value.length+')';\n if(v.rangeUnderflow)return el.type==='date'?'Ертерек күн болмайды':'Кемінде '+a('min');\n if(v.rangeOverflow)return el.type==='date'?'Болашақ күнді таңдауға болмайды':a('max')+'-ден аспауы керек';\n if(v.stepMismatch)return a('step')==='1'?'Бүтін сан енгізіңіз':'Сан дұрыс емес';\n if(v.typeMismatch)return 'Пішімі дұрыс емес';return el.validationMessage}\nfunction show(el){if(!el.willValidate)return true;var ok=el.checkValidity(),m=el._zerr;\n if(ok){el.removeAttribute('aria-invalid');if(m){m.remove();el._zerr=null}return true}\n if(!m){m=document.createElement('small');m.className='ferr';m.id='ferr'+(++n);m.setAttribute('aria-live','polite');el.insertAdjacentElement('afterend',m);el._zerr=m;\n  el.setAttribute('aria-describedby',((el.getAttribute('aria-describedby')||'')+' '+m.id).trim())}\n m.textContent=text(el);el.setAttribute('aria-invalid','true');return false}\nfunction watched(f){return f&&f.tagName==='FORM'&&f.method!=='dialog'&&f.querySelector('[required],[pattern],[min],[max],[minlength],[type=number],[type=email]')}\ndocument.querySelectorAll('form').forEach(function(f){if(watched(f))f.noValidate=true});\ndocument.addEventListener('focusout',function(e){var el=e.target;if(el.matches&&el.matches(SEL)&&watched(el.form)&&(el.value!==''||el._zt))show(el)},true);\ndocument.addEventListener('input',function(e){var el=e.target;if(!el.form||!watched(el.form))return;el._zt=1;if(el._zerr)show(el)},true);\ndocument.addEventListener('change',function(e){var el=e.target;if(el._zerr)show(el)},true);\ndocument.addEventListener('submit',function(e){var f=e.target;if(!watched(f))return;var bad=null;\n f.querySelectorAll(SEL).forEach(function(el){if(!show(el)&&!bad)bad=el});\n if(bad){e.preventDefault();e.stopImmediatePropagation();bad.focus({preventScroll:true});bad.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})}},true);\n})();</script>"


# Brand mark (rounded Z with a yellow sparkle); the same file is the favicon
LOGO = (__import__("pathlib").Path(__file__).with_name("logo.svg").read_text(encoding="utf-8")
        .replace("<svg ", '<svg aria-hidden="true" ', 1))


def topbar(user: dict | None, active: str, extra: str = "") -> str:
    """The page shell shared by all pages: left sidebar (computer), top strip and bottom bar (phone).
    Kept under the old name so every page keeps calling topbar(user, active, extra)."""
    items = nav_items(user)
    groups, links, sheet = [], [], []
    for key, href, label, ic, grp in items:
        if grp not in groups:
            groups.append(grp)
            links.append(f'<div class="grp">{grp}</div>')
            sheet.append(f'<div class="grp">{grp}</div>')
        on = " on" if key == active else ""
        a = f'<a class="nl{on}" href="{href}"{" aria-current=page" if on else ""}>{icon(ic)}<span>{label}</span></a>'
        links.append(a)
        sheet.append(a)
    who = ""
    if user:
        role = ROLE_NAMES.get(user.get("r"), "Маркетолог")
        who = (f'<div class="who"><span class="av">{html.escape(initials(user.get("n", "")))}</span><div><small>{role}</small>'
               f'<b>{html.escape(user.get("n", ""))}</b></div></div>')
    view_sel = ""
    if user and user.get("_staff"):
        cur = user["u"] if user.get("viewas") else ""
        role_short = {"lead": "жетекші", "smm": "маркетолог"}
        opts = '<option value="">Өзім · әкімші</option>' + "".join(
            f'<option value="{html.escape(lg)}"{" selected" if lg == cur else ""}>{html.escape(nm)} · {role_short.get(rl, rl)}</option>'
            for lg, nm, rl in user["_staff"])
        view_sel = (f'<form class="vas" method="get" action="/viewas"><label for="vas">Кімнің көзімен қарау</label>'
                    f'<select id="vas" name="u" onchange="this.form.submit()">{opts}</select></form>')
    banner = (f'<div class="vab">{icon("eye") if "eye" in ICON else ""}<span><b>{html.escape(user.get("n", ""))}</b> көзімен қарап тұрсыз · тек көру</span>'
              f'<a href="/viewas">Өзіме қайту</a></div>') if user and user.get("viewas") else ""
    extra = view_sel + extra
    main = {k: (h, t, ic) for k, h, t, ic, _ in items}
    bar = "".join(f'<a class="{"on" if k == active else ""}" href="{main[k][0]}">{icon(main[k][2])}<span>{main[k][1]}</span></a>'
                  for k in MOBILE_MAIN if k in main)
    more_on = " on" if active not in MOBILE_MAIN else ""
    title = main[active][1] if active in main else ""
    mtt = f'<span class="mtt" aria-hidden="true">{html.escape(title)}</span>' if title else ""
    return (SHELL_CSS + f'<aside class="side{" ttl" if title else ""}" aria-label="Мәзір"><a class="brand" href="/"><span class="mark logo">{LOGO}</span><span class="bn">EduApp <b>Marketing</b></span></a>{mtt}'
            f'<div class="sub">Аналитика панелі</div>{who}<nav aria-label="Бөлімдер">{"".join(links)}</nav>'
            f'<div class="foot">{f"<div class=extra>{extra}</div>" if extra else ""}<div class="tools">'
            f'<button class="ib" id="theme" type="button" aria-label="Тақырыпты ауыстыру" title="Күндізгі / түнгі">{icon("moon")}</button>'
            f'<a class="ib" href="/logout" aria-label="Шығу" title="Шығу">{icon("logout")}</a></div></div></aside>'
            f'<nav class="mbar" aria-label="Негізгі бөлімдер">{bar}<button type="button" class="{more_on.strip()}" id="mmore" aria-label="Тағы">'
            f'{icon("menu")}<span>Тағы</span></button></nav>'
            f'<div class="msheet" id="msheet"><div class="in" role="dialog" aria-modal="true" aria-label="Барлық бөлімдер"><div class="hd"></div>'
            f'{f"<div class=extra>{extra}</div>" if extra else ""}{"".join(sheet)}</div></div>'
            '<script>' + SHEET_JS + '(function(){var r=document.documentElement,t=0;function f(){t=0;r.classList.toggle("zscr",scrollY>4)}addEventListener("scroll",function(){if(!t)t=requestAnimationFrame(f)},{passive:true});f()})();(function(){function e(t){t.classList.toggle("end",t.scrollLeft+t.clientWidth>=t.scrollWidth-2)}document.addEventListener("scroll",function(v){var t=v.target;if(t.classList&&t.classList.contains("zcv-tabs"))e(t)},true);document.addEventListener("click",function(v){var b=v.target.closest&&v.target.closest(".zcv-tabs button");if(b)b.scrollIntoView({block:"nearest",inline:"nearest",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"})});addEventListener("load",function(){document.querySelectorAll(".zcv-tabs").forEach(e)})})();</script>' + CONFIRM_JS + '<script>'
            'document.addEventListener("touchstart",function(){},{passive:true});'
            '(function(){var bar=document.createElement("div");bar.className="zload";document.body.appendChild(bar);\nfunction busy(el){if(el){var g=el.closest(".segs,.zcv-tabs,nav,.mbar,.pills");if(g)g.querySelectorAll(".on").forEach(function(x){if(x!==el)x.classList.remove("on")});el.classList.add("on")}\ndocument.documentElement.classList.add("zbusy")}\ndocument.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href]");if(!a||e.defaultPrevented||e.metaKey||e.ctrlKey||e.shiftKey||a.target==="_blank")return;\nvar u=new URL(a.href,location.href);if(u.origin!==location.origin||u.hash&&u.pathname===location.pathname&&u.search===location.search)return;busy(a)});\ndocument.addEventListener("submit",function(e){var f=e.target;if(!e.defaultPrevented&&(f.method||"get").toLowerCase()==="get")busy(null)});\naddEventListener("pageshow",function(){document.documentElement.classList.remove("zbusy")})})();'
            '(function(){var done={};function pf(e){var a=e.target.closest&&e.target.closest("a.nl,.mbar a");if(!a||done[a.href]||a.href===location.href)return;'
            'done[a.href]=1;var l=document.createElement("link");l.rel="prefetch";l.href=a.href;document.head.appendChild(l)}'
            'document.addEventListener("mouseover",pf,{passive:true});document.addEventListener("touchstart",pf,{passive:true})})();</script>')


# Praise and motivation: one line of the day per person, and a fresh one on every press of the button.
PRAISE = [
    "{name}, сен орасан зор жұмыс атқарып жүрсің. Ең бастысы — мақсатқа сеніммен жүру!",
    "{name}, бүгінгі әр лид — үлкен нәтижеге жасалған қадам.",
    "{name}, тұрақтылық — сенің мықты жағың. Осылай жалғастыр!",
    "{name}, сенің еңбегің нәтижеге айналып жатыр. Алға!",
    "{name}, қарқының жақсы. Осы екпінмен жалғастырайық!",
    "{name}, нәтиже күнделікті әрекеттен құралады — сенің қолыңнан бұл жақсы келіп жатыр.",
    "{name}, сенің еңбегің көрініп тұр. Ортақ нәтижеге қосқан үлесің үшін рақмет!",
    "{name}, бүгінгі жоспар — қолжетімді мақсат. Сенім мен табандылық бәрін шешеді.",
    "{name}, мықты күн алғашқы лидтен басталады.",
    "{name}, назар мақсатта болса — жоспар міндетті түрде орындалады.",
    "{name}, сен команданы алға сүйреп келесің.",
    "{name}, әр күн — жаңа мүмкіндік. Нәтижең өсіп келеді!",
    "{name}, бүгінгі сенімді қадам — ай соңындағы үлкен нәтиже.",
    "{name}, жүйелі жұмыс әрқашан нәтиже береді. Сен дұрыс жолдасың.",
    "{name}, өсу қарқының керемет. Деңгейді түсірмейік!",
    "{name}, сен командаға үлкен үлес қосып жүрсің.",
    "{name}, жұмысыңның сапасы сандардан көрініп тұр.",
    "{name}, тағы аздап күш салсақ — мақсатқа жетеміз.",
    "{name}, кәсіпқойлық — нәтиженің тұрақты болуы. Бұл дәл сен туралы.",
    "{name}, мақсатқа қадам сайын жақындап келеміз.",
    "{name}, сен күн сайын EduApp-дің өсуіне үлес қосып жүрсің.",
    "{name}, қарқыныңды сақта — сенде керемет шығып жатыр.",
    "{name}, жоспар — бағыт, ал нәтиже — сенің еңбегің.",
    "{name}, бүгін кешегі нәтижеден асып түсуге тамаша күн.",
]

# Hidden lines for the five-tap easter egg on the celebration badge.
EGGS = [
    "{name}, құпия бөлім ашылды. Ұсақ-түйекті байқай білу — сенің мықты жағың.",
    "{name}, бүгін 200% режимде жұмыс істеп жатырсың.",
    "{name}, мұндай жұмыс үшін бүкіл командадан ерекше рақмет.",
]

STREAK_LINES = [
    "{name}, {days} күн қатарынан жоспар орындалды. Бұл енді жүйе!",
    "{name}, {days} күн қатарынан жоспар орындалды. Керемет тұрақтылық!",
    "{name}, {days} күн қатарынан — кәсіпқойды ерекшелейтін тұрақтылық.",
]


def praise_of_day(name: str, day: _dt.date | None = None) -> str:
    """Same line all day for one person, a different one tomorrow."""
    day = day or _dt.date.today()
    k = int(hashlib.sha256(f"{name}|{day.isoformat()}".encode()).hexdigest(), 16) % len(PRAISE)
    return PRAISE[k].format(name=name)


# ---------- B + C component kit: cards, chips, pills, thick plan bars, sparklines, heatmap ----------
KIT = """.hero{position:relative;overflow:hidden;border-radius:28px;padding:28px;color:#fff;background:var(--hero);box-shadow:var(--shadow-lg);transition:transform .25s,box-shadow .25s}
.hh{display:flex;justify-content:space-between;align-items:center;gap:8px;font-weight:500;opacity:.92}
.hv{font-size:3.375rem;line-height:1.05;font-weight:800;letter-spacing:-.035em;margin:14px 0 4px;font-variant-numeric:tabular-nums;white-space:nowrap}
.hero{display:flex;flex-direction:column}.hsp{flex:1;min-height:84px;margin:0 -28px}.spark{width:100%;height:100%;display:block;overflow:visible}
.spark .ln{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.2s .35s cubic-bezier(.4,0,.2,1) forwards}@keyframes draw{to{stroke-dashoffset:0}}
.hp{margin-top:6px}.hpt{display:flex;justify-content:space-between;gap:12px;font-weight:600}.hpt.s{font-weight:500;opacity:.88;margin-top:10px;font-size:0.8125rem}
.k,.card{background:var(--surface);border-radius:var(--r);padding:18px;box-shadow:none;border:1px solid var(--border)}
.kh{display:flex;align-items:center;gap:8px;color:var(--muted);font-weight:500;font-size:0.8125rem}.kh .pill{margin-left:auto}.kl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;color:var(--c);background:color-mix(in srgb,var(--c) 13%,transparent);flex:none}
.chip .i{width:17px;height:17px;stroke-width:2}
.kv{font-size:1.875rem;line-height:1.267;font-weight:700;letter-spacing:-.03em;margin:12px 0 0;font-variant-numeric:tabular-nums;white-space:nowrap}
.ksub{margin:2px 0 0;color:var(--faint);font-size:0.75rem}.ks{height:44px;margin-top:8px}
.pill{display:inline-flex;align-items:center;gap:3px;padding:3px 9px;border-radius:999px;font-size:0.75rem;font-weight:700;white-space:nowrap}
.pill.up{color:var(--green);background:color-mix(in srgb,var(--green) 12%,transparent)}.pill.down{color:var(--red);background:color-mix(in srgb,var(--red) 12%,transparent)}
.pill.flat{color:var(--faint);background:var(--surface2)}.pill.w{color:#fff;background:rgba(255,255,255,.18)}
.ch{display:flex;align-items:center;gap:8px;margin-bottom:14px}.ch h2{margin:0;font-size:1.0625rem;font-weight:600;letter-spacing:-.01em}.ch .meta,.ch .more,.ch .btn{margin-left:auto}
.meta{color:var(--faint);font-size:0.75rem;text-align:right}.more{display:inline-flex;align-items:center;gap:4px;color:var(--accent);font-weight:600}
.pbar{position:relative;height:8px;border-radius:2px;background:var(--bar);margin-top:10px}
.pbar i{position:absolute;inset:0 auto 0 0;width:0;border-radius:inherit;transition:width 1.4s cubic-bezier(.2,.8,.2,1)}
.go .pbar i{width:var(--w)}
.pbar b{position:absolute;top:-3px;width:2px;height:18px;border-radius:2px;background:color-mix(in srgb,var(--text) 18%,transparent);transform:translateX(-1px)}
.pbar.purple i{background:var(--accent)}.pbar.orange i{background:var(--orange)}
.pbar.gold i{background:var(--gilt)}
.hero .pbar{background:var(--bline)}.hero .pbar b{background:var(--bmuted)}.hero .pbar i{background:var(--bink)}
.pbar.ok i{background:var(--green)!important}
.okc{position:absolute;right:-6px;top:50%;width:24px;height:24px;margin-top:-12px;border-radius:50%;background:var(--green);display:grid;place-items:center;box-shadow:0 0 0 3px var(--surface);transform:scale(0);animation:okpop .4s 1.4s cubic-bezier(.3,1.6,.5,1) forwards}
.okc svg{width:14px;height:14px;fill:none;stroke:#fff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:24;stroke-dashoffset:24;animation:okdraw .4s 1.6s forwards}
@keyframes okpop{to{transform:scale(1)}}@keyframes okdraw{to{stroke-dashoffset:0}}
.pbar.sm{height:8px;margin:0}.pbar.sm b,.pbar.sm .okc{display:none}
.heat{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}.heat .wd{font-size:0.6875rem;text-align:center;color:var(--faint);text-transform:uppercase}
.heat .hd{position:relative;display:grid;place-items:center;height:40px;border-radius:4px;font-size:0.75rem;font-weight:600;color:var(--muted);background:var(--surface2);font-variant-numeric:tabular-nums;transition:transform .15s}
@media (hover:hover){.heat a.hd:hover{transform:scale(1.06)}}.heat .hd.fut{background:transparent;color:var(--faint);opacity:.6}.heat .hd.now{box-shadow:inset 0 0 0 2px var(--text)}
.heat em{position:absolute;top:-7px;right:-4px;font-size:0.875rem;font-style:normal}
.l0{background:var(--surface2)}.heat .l1,.hl .l1{background:#ddd2f5}.heat .l2,.hl .l2{background:#bba5ec}.heat .l3,.hl .l3{background:#8f6ad9;color:#fff}.heat .l4,.hl .l4{background:#7336F7;color:#fff}
:root[data-theme=dark] .heat .l1,:root[data-theme=dark] .hl .l1{background:#2e2552}:root[data-theme=dark] .heat .l2,:root[data-theme=dark] .hl .l2{background:#4a3794}
:root[data-theme=dark] .heat .l3,:root[data-theme=dark] .hl .l3{background:#6f4fd0}:root[data-theme=dark] .heat .l4,:root[data-theme=dark] .hl .l4{background:#9b7bff;color:#0e0b1a}
.hl{display:flex;align-items:center;justify-content:flex-end;gap:4px;margin-top:10px;font-size:0.6875rem;color:var(--faint)}.hl i{width:14px;height:14px;border-radius:4px}.hl .l0{background:var(--surface2)}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}thead th{font-size:0.75rem;font-weight:500;color:var(--faint)}
th:first-child{text-align:left;padding-left:0}tbody th{font-weight:600}tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
td.pc{width:32%;min-width:130px}td.pc .pbar{display:inline-block;width:calc(100% - 52px);vertical-align:middle;margin-right:8px}td.pc span{display:inline-block;width:44px;color:var(--muted)}
pre{border-radius:8px}
.cardin{opacity:0;transform:translateY(14px);animation:cin .6s cubic-bezier(.2,.8,.2,1) forwards;animation-delay:calc(var(--i,0)*70ms)}
@keyframes cin{to{opacity:1;transform:none}}
.hero{padding:20px;border-radius:var(--r)}.hv{font-size:2.5rem}.hsp{margin:0 -20px;height:64px}.k{padding:14px;border-radius:20px}.kv{font-size:1.375rem;line-height:1.364}
.frz .cardin,.frz .spark .ln,.frz .okc,.frz .okc svg,.frz .streakc .fl{animation:none!important;opacity:1!important;transform:none!important;stroke-dashoffset:0!important}.frz .pbar i{transition:none!important;width:var(--w)!important}
@media (max-width:720px){.hero{padding:20px;border-radius:var(--r)}.hv{font-size:2.5rem}.hsp{margin:0 -20px;height:64px}.k{padding:14px;border-radius:var(--r)}.kv{font-size:1.375rem;line-height:1.364}.card{padding:16px;border-radius:var(--r)}.heat{gap:4px}.heat .hd{height:34px}}
@media (prefers-reduced-motion:reduce){.cardin{opacity:1;transform:none;animation:none}.spark .ln{stroke-dashoffset:0;animation:none}.pbar i{transition:none}}
"""

KIT_JS = """<script>(function(){var r=document.documentElement,f=new URLSearchParams(location.search).get('freeze')!==null;if(f)r.classList.add('frz');
var red=matchMedia('(prefers-reduced-motion: reduce)').matches,nf=function(n){return Math.round(n).toLocaleString('ru-RU').replace(/\u00a0/g,' ')};
/* apple-design «Response»: numbers are final on the first frame — no count-up from zero, bars already at their value */
document.body.classList.add('go')})();</script>"""
KIT_JS += FORM_JS

FONT = '<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'


def _smooth(pts) -> str:
    """Soft curve through the points (Catmull-Rom as cubic Bézier)."""
    if len(pts) < 2:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        d += (f" C{p1[0] + (p2[0] - p0[0]) / 6:.1f},{p1[1] + (p2[1] - p0[1]) / 6:.1f}"
              f" {p2[0] - (p3[0] - p1[0]) / 6:.1f},{p2[1] - (p3[1] - p1[1]) / 6:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return d


ACCENT = "#7336F7"


def spark(vals, color, w=240, h=44, fill=True, sw=2.2, cls="spark"):
    """Sparkline. On the dark hero (white colour asked) — style C «space»: a violet→yellow glowing line and a
    shining end point. Everywhere else — style A «quiet»: one brand-violet line, a faint fill, a ringed end point.
    Strokes and dots keep their size however the SVG is stretched (non-scaling stroke)."""
    vals = [v or 0 for v in vals] or [0]
    mx, mn = max(vals), min(vals)
    rng = (mx - mn) or 1
    step = (w - w * .04) / max(1, len(vals) - 1)  # keep the end point off the card's edge
    pts = [(i * step, h - 5 - (v - mn) / rng * (h - 12)) for i, v in enumerate(vals)]
    d = _smooth(pts)
    gid = f"s{abs(hash((tuple(vals), color, w))) % 10**7}"
    ex, ey = pts[-1]
    ns = 'vector-effect="non-scaling-stroke"'
    if color.lower() in ("#fff", "#ffffff", "white"):
        return (f'<svg class="{cls} sp-c" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><defs>'
                f'<linearGradient id="{gid}l" x1="0" x2="1"><stop offset="0" stop-color="#9B6BFF"/><stop offset=".7" stop-color="#E2C6FF"/><stop offset="1" stop-color="#FEC200"/></linearGradient>'
                f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C686F8" stop-opacity=".32"/><stop offset="1" stop-color="#C686F8" stop-opacity="0"/></linearGradient></defs>'
                + (f'<path d="{d} L{w},{h} L0,{h} Z" fill="url(#{gid})"/>' if fill else "")
                + f'<path class="ln glow" d="{d}" fill="none" stroke="url(#{gid}l)" stroke-width="8" stroke-opacity=".35" stroke-linecap="round" pathLength="1"/>'
                f'<path class="ln" d="{d}" fill="none" stroke="url(#{gid}l)" stroke-width="{sw + .6}" stroke-linecap="round" pathLength="1"/>'
                f'<path d="M{ex:.1f},{ey:.1f}h0" stroke="#FEC200" stroke-opacity=".25" stroke-width="22" stroke-linecap="round" {ns}/>'
                f'<path d="M{ex:.1f},{ey:.1f}h0" stroke="#FEC200" stroke-width="9" stroke-linecap="round" {ns}/></svg>')
    c = ACCENT
    return (f'<svg class="{cls} sp-a" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{c}" stop-opacity=".14"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient></defs>'
            + (f'<path d="{d} L{w},{h} L0,{h} Z" fill="url(#{gid})"/>' if fill else "")
            + f'<path class="ln" d="{d}" fill="none" stroke="{c}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" pathLength="1"/>'
            f'<path d="M{ex:.1f},{ey:.1f}h0" stroke="{c}" stroke-width="10" stroke-linecap="round" {ns}/>'
            f'<path d="M{ex:.1f},{ey:.1f}h0" stroke="var(--surface)" stroke-width="5" stroke-linecap="round" {ns}/></svg>')


def pill_pct(p, light=False):
    if p is None:
        return f'<span class="pill flat{" w" if light else ""}">—</span>'
    return f'<span class="pill {"up" if p >= 0 else "down"}{" w" if light else ""}">{"▲" if p >= 0 else "▼"} {abs(p)}%</span>'


def pbar(p, tone, label):
    w = max(0, min(100, p or 0))
    ok = (p or 0) >= 100
    return (f'<div class="pbar {tone}{" ok" if ok else ""}" role="progressbar" aria-label="{html.escape(label)}" aria-valuenow="{p or 0}" '
            f'aria-valuemin="0" aria-valuemax="100"><i style="--w:{w}%"></i><b style="left:50%"></b><b style="left:75%"></b><b style="left:100%"></b>'
            + ('<span class="okc"><svg viewBox="0 0 24 24"><path d="M5 12.5 10 17l9-10"/></svg></span>' if ok else "") + "</div>")


def initials(name: str) -> str:
    return "".join(w[0] for w in (name or "Z").split()[:2]).upper()


# Secondary pages (Тарих, Есеп, Команда, Баптау, Кіру, План): gradient page head, forms, primary button
PAGES = """.ph{position:relative;overflow:hidden;border-radius:var(--r);padding:26px 28px;margin:8px 0 22px;color:var(--bink);background:var(--board);box-shadow:none;
display:flex;flex-wrap:wrap;gap:18px;align-items:center;justify-content:space-between}
.ph>*{position:relative;z-index:1}.ph h1{margin:0;font-size:1.75rem;line-height:1.286;font-weight:700;letter-spacing:-.025em}.ph p{margin:4px 0 0;color:var(--bmuted)}
.ph .act{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.ph .date{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.25)}.ph .date input{color:#fff;color-scheme:dark}.ph .step{color:rgba(255,255,255,.75)}.ph .step:hover{color:#fff}
.ph .stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.ph .stats span{padding:4px 10px;border-radius:4px;background:rgba(255,255,255,.1);font-size:0.75rem;font-weight:500}
.btny{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:40px;padding:0 18px;border:0;border-radius:12px;font:600 0.875rem Golos Text,sans-serif;color:var(--gink);
background:var(--gilt);cursor:pointer;transition:transform .15s}
.btnp{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border:0;border-radius:12px;font:600 0.875rem Golos Text,sans-serif;color:#fff;
background:var(--accent);cursor:pointer;transition:transform .15s,background-color .15s}
@media (hover:hover){.btnp:hover{background:var(--accent2)}}
.btng{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:40px;padding:0 16px;border-radius:12px;border:0;background:var(--surface2);color:var(--text);font:600 0.8125rem Golos Text,sans-serif;cursor:pointer}
.btng:hover{background:color-mix(in srgb,var(--accent) 10%,var(--surface2));color:var(--accent)}
form.f{display:grid;gap:16px}.f label{display:grid;gap:6px;font-weight:600;font-size:0.8125rem}
.f input,.f select{font:500 0.875rem Golos Text,sans-serif;height:46px;padding:0 14px;border-radius:8px;border:1.5px solid var(--border);background:var(--surface2);color:var(--text);transition:border-color .15s,box-shadow .15s,background .15s}
.f input:focus,.f select:focus{outline:0;border-color:var(--accent);background:var(--surface);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 15%,transparent)}
.f select[multiple]{height:auto;min-height:140px;padding:8px}.f small{font-weight:500;color:var(--faint)}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.row3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.msg{padding:12px 16px;border-radius:14px;margin-bottom:16px;font-weight:600}
.msg.ok{color:var(--green);background:color-mix(in srgb,var(--green) 12%,transparent)}.msg.err{color:var(--red);background:color-mix(in srgb,var(--red) 12%,transparent)}
.av{display:grid;place-items:center;width:46px;height:46px;border-radius:8px;flex:none;color:#fff;font-weight:700;font-size:1rem;background:var(--a1,var(--board))}
.ptag{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;color:var(--c);background:color-mix(in srgb,var(--c) 12%,transparent);white-space:nowrap}
.narrow{max-width:860px;margin:0 auto}.card h2{margin:0 0 14px;font-size:1.0625rem;font-weight:600}.card>p{color:var(--muted);margin:0 0 16px}
@media (max-width:720px){.ph{padding:20px;border-radius:var(--r)}.ph h1{font-size:1.375rem;line-height:1.273}.ph .act{width:100%}.row2,.row3{grid-template-columns:1fr}}
"""


DR_MONTHS = ["қаң", "ақп", "нау", "сәу", "мам", "мау", "шіл", "там", "қыр", "қаз", "қар", "жел"]
DR_CSS = """
.drw{position:relative}.dr{display:flex;align-items:center;gap:7px;height:100%;padding:0 6px;border:0;background:none;color:var(--text);font:600 .8125rem 'Golos Text',sans-serif;font-variant-numeric:tabular-nums;white-space:nowrap;cursor:pointer}.dr svg{width:15px;height:15px;color:var(--muted);flex:none}.dr:hover svg{color:var(--text)}
.drp{position:absolute;right:0;top:calc(100% + 8px);z-index:45;display:flex;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:14px;box-shadow:0 12px 32px rgba(27,20,48,.14);animation:drin .15s ease-out}.drp[hidden]{display:none}
@keyframes drin{from{opacity:0;transform:translateY(-4px)}}
.drp-pre{display:grid;align-content:start;gap:2px;width:148px;padding:12px 8px;border-right:1px solid var(--border)}.drp-pre button{min-height:36px;padding:0 10px;border:0;border-radius:8px;background:none;color:var(--text);font:500 .8125rem 'Golos Text',sans-serif;text-align:left;white-space:nowrap;cursor:pointer}.drp-pre button:hover{background:var(--surface2)}.drp-pre button.on{background:var(--surface2);font-weight:600}
.drp-main{padding:14px 16px 12px;min-width:0}.drp-cals{display:flex;gap:24px}.drm{width:280px}.drm-h{display:flex;align-items:center;justify-content:space-between;height:36px;margin-bottom:4px;font-weight:600;font-size:.875rem}.drm-h button{display:grid;place-items:center;width:36px;height:36px;border:0;border-radius:8px;background:none;color:var(--muted);cursor:pointer}.drm-h button:hover{background:var(--surface2);color:var(--text)}.drm-h button:disabled{visibility:hidden}.drm-h svg{width:16px;height:16px}
.drg{display:grid;grid-template-columns:repeat(7,1fr);row-gap:2px}.drg i{height:28px;display:grid;place-items:center;font:500 .75rem 'Golos Text',sans-serif;color:var(--faint)}
.dd{position:relative;height:40px;padding:0;border:0;background:none;color:var(--text);font:500 .8125rem 'Golos Text',sans-serif;font-variant-numeric:tabular-nums;cursor:pointer}.dd span{position:relative;display:grid;place-items:center;width:40px;height:40px;margin:auto;border-radius:10px}.dd:not(:disabled):hover span{background:var(--surface2)}.dd:disabled{color:var(--faint);opacity:.45;cursor:default}
.dd.now span::after{content:"";position:absolute;bottom:6px;width:4px;height:4px;border-radius:50%;background:currentColor}.dd.in{background:var(--surface2)}.dd.st{background:linear-gradient(90deg,transparent 50%,var(--surface2) 50%)}.dd.en{background:linear-gradient(90deg,var(--surface2) 50%,transparent 50%)}.dd.st.en{background:none}
.dd.st span,.dd.en span,.dd.st:hover span,.dd.en:hover span{background:#7336F7;color:#fff;font-weight:600}.dd:focus-visible{outline:0}.dd:focus-visible span{outline:2px solid var(--accent);outline-offset:1px}
.drp-ft{display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:12px;border-top:1px solid var(--border)}.drp-sum{flex:1;min-width:0;font-size:.8125rem;color:var(--muted);font-variant-numeric:tabular-nums}.drp-ft button{min-height:36px;padding:0 14px;border:0;border-radius:8px;font:600 .8125rem 'Golos Text',sans-serif;cursor:pointer}.drx{background:none;color:var(--muted)}.drx:hover{color:var(--text)}.dry{background:#7336F7;color:#fff}.dry:disabled{opacity:.4;cursor:default}
.drs{position:fixed;inset:0;z-index:79;background:rgba(18,10,31,.45)}.drs[hidden]{display:none}
@keyframes drup{from{transform:translateY(100%)}}
@media (max-width:980px){.drp-pre{width:128px}}
@media (max-width:720px){.drw{position:static}.drp{position:fixed;left:0;right:0;top:auto;bottom:0;z-index:80;flex-direction:column;max-height:88dvh;overflow:auto;border-width:1px 0 0;border-radius:18px 18px 0 0;padding-bottom:env(safe-area-inset-bottom);animation:drup .2s ease-out}
 .drp-pre{display:flex;width:auto;overflow-x:auto;padding:12px 16px 8px;border-right:0;scrollbar-width:none}.drp-pre::-webkit-scrollbar{display:none}.drp-pre button{flex:none;min-height:40px;border:1px solid var(--border)}
 .drp-main{padding:4px 16px 14px}.drp-cals,.drm{width:100%}.drm-h button{width:44px;height:44px}.dd,.dd span{height:44px}.dd span{width:100%;max-width:44px}.drp-ft button{min-height:44px}.dr svg{display:none}}
@media (prefers-reduced-motion:reduce){.drp{animation:none}}
"""
DR_JS = """<script>(function(){
var b=document.getElementById('dr'),box=document.getElementById('drp'),scr=document.getElementById('drs');if(!b)return;
var MF=['Қаңтар','Ақпан','Наурыз','Сәуір','Мамыр','Маусым','Шілде','Тамыз','Қыркүйек','Қазан','Қараша','Желтоқсан'],MS=['қаң','ақп','нау','сәу','мам','мау','шіл','там','қыр','қаз','қар','жел'],WD=['Дс','Сс','Ср','Бс','Жм','Сб','Жс'];
var L='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>',R=L.replace('m15 18-6-6 6-6','m9 18 6-6-6-6');
function P(k){var a=k.split('-');return new Date(+a[0],a[1]-1,+a[2])}
function K(d){return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2)}
function add(d,n){return new Date(d.getFullYear(),d.getMonth(),d.getDate()+n)}
var max=b.dataset.max,today=P(max),q=b.dataset.q||'',s,e,hov,view,cur;
function short(k){var d=P(k);return d.getDate()+' '+MS[d.getMonth()]+(d.getFullYear()!==today.getFullYear()?' '+d.getFullYear():'')}
function go(u){var a=document.createElement('a');a.href=u+q;document.body.appendChild(a);a.click()}
var u1=b.dataset.u1,um=b.dataset.um;function goRange(a,c){go(a===c?u1.replace(/@/g,a):'?p=range&d1='+a+'&d2='+c)}
var lm=new Date(today.getFullYear(),today.getMonth(),0);
var PRE=[['Бүгін',max,max],['Кеше',K(add(today,-1)),K(add(today,-1))],['Соңғы 7 күн',K(add(today,-6)),max],['Соңғы 30 күн',K(add(today,-29)),max],
 ['Осы ай',K(new Date(today.getFullYear(),today.getMonth(),1)),max,um&&um.replace('@',max)],['Өткен ай',K(new Date(lm.getFullYear(),lm.getMonth(),1)),K(lm),um&&um.replace('@',K(lm))]];
function months(){return matchMedia('(max-width:980px)').matches?1:2}
function month(y,m,first,last){var f=new Date(y,m,1),off=(f.getDay()+6)%7,n=new Date(y,m+1,0).getDate(),h='<div class="drm"><div class="drm-h">'+(first?'<button type="button" data-nav="-1" aria-label="Алдыңғы ай">'+L+'</button>':'<span></span>')+'<span>'+MF[m]+' '+y+'</span>'+(last?'<button type="button" data-nav="1" aria-label="Келесі ай"'+(new Date(y,m+1,1)>today?' disabled':'')+'>'+R+'</button>':'<span></span>')+'</div><div class="drg">';
 WD.forEach(function(w){h+='<i>'+w+'</i>'});for(var i=0;i<off;i++)h+='<b></b>';
 for(var d=1;d<=n;d++){var k=K(new Date(y,m,d));h+='<button type="button" class="dd'+(k===max?' now':'')+'" data-k="'+k+'" tabindex="-1" aria-label="'+d+' '+MF[m]+' '+y+'"'+(k>max?' disabled':'')+'><span>'+d+'</span></button>'}
 return h+'</div></div>'}
function render(){var n=months(),h='<div class="drp-pre">';PRE.forEach(function(p,i){h+='<button type="button" data-pre="'+i+'">'+p[0]+'</button>'});
 h+='</div><div class="drp-main"><div class="drp-cals">';for(var i=n-1;i>=0;i--){var d=new Date(view.getFullYear(),view.getMonth()-i,1);h+=month(d.getFullYear(),d.getMonth(),i===n-1,i===0)}
 box.innerHTML=h+'</div><div class="drp-ft"><span class="drp-sum" aria-live="polite"></span><button type="button" class="drx">Болдырмау</button><button type="button" class="dry">Қолдану</button></div></div>';paint()}
function paint(){var a=s,c=e;if(s&&!e&&hov){a=hov<s?hov:s;c=hov<s?s:hov}
 box.querySelectorAll('.dd').forEach(function(x){var k=x.dataset.k,st=k===a,en=k===(c||a);x.classList.toggle('st',!!a&&st);x.classList.toggle('en',!!a&&en);x.classList.toggle('in',!!(a&&c&&k>a&&k<c));x.setAttribute('aria-pressed',!!(a&&k>=a&&k<=(c||a)));x.tabIndex=k===cur?0:-1});
 box.querySelectorAll('[data-pre]').forEach(function(x){var p=PRE[+x.dataset.pre];x.classList.toggle('on',s===p[1]&&e===p[2])});
 var t=box.querySelector('.drp-sum'),n=s&&e?Math.round((P(e)-P(s))/864e5)+1:0;t.textContent=!s?'Бірінші күнді таңдаңыз':!e?short(s)+' · соңғы күнді таңдаңыз':s===e?short(s):short(s)+' – '+short(e)+' · '+n+' күн';
 box.querySelector('.dry').disabled=!s}
function focusDay(k){var x=box.querySelector('[data-k="'+k+'"]');if(x){cur=k;paint();x.focus()}}
function open(){s=b.dataset.first;e=b.dataset.last;hov=null;cur=e;view=new Date(P(e).getFullYear(),P(e).getMonth(),1);box.hidden=false;scr.hidden=!matchMedia('(max-width:720px)').matches;b.setAttribute('aria-expanded','true');render();place();focusDay(cur)}
function place(){box.style.left=box.style.right='';if(matchMedia('(max-width:720px)').matches)return;var sd=document.querySelector('.side'),w=sd?sd.getBoundingClientRect().right:0;if(box.getBoundingClientRect().left<w+8){box.style.right='auto';box.style.left='0'}}
function close(f){if(box.hidden)return;box.hidden=true;scr.hidden=true;b.setAttribute('aria-expanded','false');if(f)b.focus()}
b.addEventListener('click',function(){box.hidden?open():close(true)});scr.addEventListener('click',function(){close(true)});
document.addEventListener('pointerdown',function(ev){if(!box.hidden&&!box.contains(ev.target)&&!b.contains(ev.target)&&ev.target!==scr)close()});
box.addEventListener('click',function(ev){var t=ev.target.closest('button');if(!t||t.disabled)return;
 if(t.dataset.nav){view=new Date(view.getFullYear(),view.getMonth()+(+t.dataset.nav),1);render();return}
 if(t.dataset.pre){var p=PRE[+t.dataset.pre];p[3]?go(p[3]):goRange(p[1],p[2]);return}
 if(t.classList.contains('drx')){close(true);return}
 if(t.classList.contains('dry')){goRange(s,e||s);return}
 var k=t.dataset.k;if(!k)return;if(!s||e){s=k;e=null}else if(k<s){e=s;s=k}else e=k;hov=null;cur=k;paint()});
box.addEventListener('pointerover',function(ev){var t=ev.target.closest('.dd');if(t&&!t.disabled&&s&&!e&&ev.pointerType==='mouse'){hov=t.dataset.k;paint()}});
box.addEventListener('keydown',function(ev){if(ev.key==='Escape'){close(true);return}
 if(ev.key==='Tab'){var f=[].filter.call(box.querySelectorAll('button'),function(x){return !x.disabled&&x.tabIndex>=0}),i=f.indexOf(document.activeElement);if(ev.shiftKey&&i<=0){ev.preventDefault();f[f.length-1].focus()}else if(!ev.shiftKey&&i===f.length-1){ev.preventDefault();f[0].focus()}return}
 var t=ev.target.closest('.dd'),m={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[ev.key];if(!t||!m)return;ev.preventDefault();
 var nx=add(P(t.dataset.k),m),k=K(nx);if(k>max)return;if(!box.querySelector('[data-k="'+k+'"]')){view=new Date(nx.getFullYear(),nx.getMonth()+(m>0?0:months()-1),1);cur=k;render()}focusDay(k);if(s&&!e){hov=k;paint()}});
})();</script>"""


def dr_label(first, last, today) -> str:
    """Short text of the picked days for the date button: «30 қаз», «23–30 қаз», «28 қыр – 5 қаз»."""
    yr = lambda d: f" {d.year}" if d.year != today.year else ""
    if first == last:
        return f"{first.day} {DR_MONTHS[first.month - 1]}{yr(first)}"
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day}–{last.day} {DR_MONTHS[last.month - 1]}{yr(last)}"
    return f"{first.day} {DR_MONTHS[first.month - 1]}{yr(first)} – {last.day} {DR_MONTHS[last.month - 1]}{yr(last)}"


def date_range(first, last, today, prev_href: str, next_href: str | None, u1: str, q: str = "", um: str = "") -> str:
    """The date button with its calendar (every page with a period): `u1` / `um` are this page's links for one day / a
    month with @ for the date; any other span opens ?p=range&d1=…&d2=…"""
    label = dr_label(first, last, today)
    nxt = (f'<a class="step" href="{next_href}" aria-label="Келесі">{icon("right")}</a>' if next_href
           else f'<span class="step off">{icon("right")}</span>')
    return (f'<style>{DR_CSS}</style><div class="drw"><div class="date"><a class="step" href="{prev_href}" aria-label="Алдыңғы">{icon("left")}</a>'
            f'<button class="dr" id="dr" type="button" aria-haspopup="dialog" aria-expanded="false" aria-label="Күндерді таңдау: {label}" '
            f'data-first="{first:%Y-%m-%d}" data-last="{min(last, today):%Y-%m-%d}" data-max="{today:%Y-%m-%d}" data-q="{html.escape(q)}" data-u1="{u1}" data-um="{um}">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>{label}</button>{nxt}</div>'
            f'<div class="drp" id="drp" role="dialog" aria-label="Күндерді таңдау" hidden></div></div><div class="drs" id="drs" hidden></div>{DR_JS}')
