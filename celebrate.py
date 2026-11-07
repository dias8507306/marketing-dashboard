"""The «victory moment»: a directed celebration overlay with four levels.

  motiv  — the «Күндік мотивация» button: card rises from the bottom, star burst, a motivation line (~1 s)
  daily  — daily lead plan 100 %: ring fills to 100 %, light wave and gold sparks, a trophy draws
           itself, the name types in, the bonus lands like a slot machine, chips pop (~3.5 s)
  streak — 5/10/15 days in a row: a gift box opens, the lid flies off, the gift card rises
  month  — monthly sales plan: the daily sequence plus full-screen fireworks

Every frame is a pure function of time (frame(t)), particles included (seeded and stepped),
so ?freeze=<ms> shows any moment exactly and ?freeze=1 shows the final frame. ?demo=<level>
(admin only) opens a level at any time. prefers-reduced-motion jumps to the final frame.
"""
import json

CSS = """
.cel{position:fixed;inset:0;z-index:90;display:grid;place-items:center;padding:16px}
.cel[hidden]{display:none}
.cel-bg{position:absolute;inset:0;background:rgba(20,10,40,.62)}
.cel canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.cel-card{position:relative;width:min(420px,100%);border-radius:28px;overflow:hidden;background:var(--surface);color:var(--text);
box-shadow:0 40px 100px -20px rgba(20,10,40,.6);transform-origin:50% 60%}
.cel-top{position:relative;height:210px;display:grid;place-items:center;background:var(--hero);overflow:hidden}
.cel-top:after{content:"";position:absolute;width:300px;height:300px;right:-90px;top:-130px;border-radius:50%;background:radial-gradient(circle,rgba(254,194,0,.45),transparent 70%)}
.cel-ring{position:absolute;width:168px;height:168px}
.cel-count{position:relative;z-index:2;text-align:center;color:#fff}
.cel-count b{display:block;font-size:2.75rem;line-height:1;font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.cel-count span{font-size:0.8125rem;opacity:.85}
.cel-trophy{position:absolute;z-index:3;width:132px;height:132px;filter:drop-shadow(0 14px 24px rgba(20,8,40,.45))}
.cel-wave{position:absolute;z-index:1;width:168px;height:168px;border-radius:50%;border:3px solid rgba(255,255,255,.9)}
.cel-gift{position:absolute;z-index:3;width:120px;height:120px}
.cel-giftcard{position:absolute;z-index:4;left:50%;width:200px;padding:12px 14px;border-radius:16px;background:#fff;color:#14112b;text-align:center;box-shadow:0 18px 40px -12px rgba(0,0,0,.45)}
.cel-giftcard small{display:block;font:700 0.625rem Golos Text,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#f35b2f}
.cel-giftcard b{display:block;margin-top:4px;font-size:1.25rem;font-weight:800}
.cel-body{padding:20px 22px 22px;text-align:center}
.cel-star{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;font-size:0.6875rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
color:#b07b00;background:#fff4cc;cursor:pointer;user-select:none}
:root[data-theme=dark] .cel-star{background:rgba(254,194,0,.14);color:#fec200}
.cel-name{margin:10px 0 4px;font-size:1.625rem;line-height:1.231;font-weight:800;letter-spacing:-.02em;min-height:32px}
.cel-msg{margin:0 auto;max-width:340px;min-height:48px;color:var(--muted);font-size:0.9375rem;line-height:1.5}
.cel-msg i{display:inline-block;width:2px;height:1em;background:var(--accent);vertical-align:-2px;margin-left:1px}
.cel-bonus{margin:16px 0 0;padding:12px;border-radius:18px;background:linear-gradient(160deg,#fff8dc,#fff 70%)}
:root[data-theme=dark] .cel-bonus{background:linear-gradient(160deg,rgba(254,194,0,.14),transparent 70%)}
.cel-bonus small{display:block;font-size:0.75rem;color:var(--muted)}
.slot{display:inline-flex;justify-content:center;height:44px;overflow:hidden;font-size:2.25rem;line-height:44px;font-weight:800;color:#b07b00;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
:root[data-theme=dark] .slot{color:#fec200}
.slot .col{display:block;height:44px;overflow:hidden}.slot .strip{display:block}.slot .strip span{display:block;height:44px}
.slot .ch{display:block;height:44px}
.cel-chips{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;margin-top:14px;min-height:34px}
.cel-chips svg{width:15px;height:15px;color:#f35b2f;flex:none}.medal{display:grid;place-items:center;width:108px;height:108px;margin:0 auto 10px;border-radius:50%;
background:radial-gradient(circle at 32% 26%,#fff1b3 0,#fec200 42%,#f35b2f 100%);
box-shadow:0 0 0 9px rgba(255,255,255,.12),0 0 0 18px rgba(255,255,255,.05),0 20px 40px -10px rgba(243,91,47,.7),inset 0 -8px 14px rgba(150,40,0,.25),inset 0 5px 10px rgba(255,255,255,.65)}
.medal.v{background:radial-gradient(circle at 32% 26%,#e6dcff 0,#9b7bff 42%,#2A78D6 100%);box-shadow:0 0 0 9px rgba(255,255,255,.12),0 0 0 18px rgba(255,255,255,.05),0 20px 40px -10px rgba(40,87,252,.7),inset 0 -8px 14px rgba(20,10,80,.3),inset 0 5px 10px rgba(255,255,255,.6)}
.medal.g{background:radial-gradient(circle at 32% 26%,#d4ffe6 0,#22c55e 45%,#048848 100%);box-shadow:0 0 0 9px rgba(255,255,255,.12),0 0 0 18px rgba(255,255,255,.05),0 20px 40px -10px rgba(4,136,72,.7),inset 0 -8px 14px rgba(0,60,20,.3),inset 0 5px 10px rgba(255,255,255,.6)}
.medal svg{width:54px;height:54px;fill:none;stroke:#fff;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 2px 3px rgba(60,20,0,.35))}
@media (max-width:480px){.medal{width:92px;height:92px}.medal svg{width:46px;height:46px}}.cel-chips span{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border-radius:999px;background:var(--surface2);font-weight:600;font-size:0.8125rem}
.cel-btns{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:16px}
.cel-btns button{display:inline-flex;align-items:center;gap:8px;height:42px;padding:0 16px;border-radius:14px;border:0;font:600 0.875rem Golos Text,sans-serif;cursor:pointer}
.cel-btns .pri{color:#fff;background:linear-gradient(90deg,#7336F7,#9B6BFF);box-shadow:0 10px 24px -10px rgba(87,46,162,.8)}
.cel-btns .sec{color:var(--text);background:var(--surface2)}
.cel-tools{position:absolute;top:10px;right:10px;z-index:6;display:flex;gap:6px}
.cel-sky{position:absolute;inset:0;width:100%;height:100%;display:none}
.cel-pctx{display:none;position:absolute;left:24px;bottom:14px;z-index:2;color:#fff;font-size:2.25rem;font-weight:900;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.cel-card.story .cel-pctx{display:block}
.cel-sub{display:none;margin:8px 0 0;font-size:0.875rem;line-height:1.45;color:rgba(255,255,255,.78)}
.cel-card.story{background:linear-gradient(180deg,#0f0a2a,#2F0E51 42%,#7336F7 76%,#2A78D6);color:#fff}
.cel-card.story .cel-top{height:300px;background:none}.cel-card.story .cel-top:after{display:none}
.cel-card.story .cel-sky{display:block}.cel-card.story .cel-count{display:none!important}
.cel-card.story .cel-body{text-align:left;padding:2px 24px 22px}
.cel-card.story .cel-star{background:rgba(254,194,0,.18);color:#fec200}
.cel-card.story .cel-name{font-size:1.875rem;line-height:1.2;margin:10px 0 6px}
.cel-card.story .cel-msg{margin:0;max-width:none;min-height:52px;color:#fff;font-size:1.1875rem;font-weight:800;line-height:1.35}
.cel-card.story .cel-msg i{background:#fec200}.cel-card.story .cel-sub{display:block}
.cel-card.story .cel-chips{justify-content:flex-start}.cel-card.story .cel-chips span{background:rgba(255,255,255,.14);color:#fff}
.cel-card.story .cel-chips svg{color:#fec200}
.cel-card.story .cel-btns{justify-content:flex-start}.cel-card.story .cel-btns .sec{background:rgba(255,255,255,.14);color:#fff}
.cel-card.story .cel-btns .pri{background:linear-gradient(90deg,#fec200,#f35b2f);color:#2F0E51;box-shadow:0 10px 24px -10px rgba(243,91,47,.8)}
.cel-card.story .cel-story{color:#ffe27a}
.cel-tw{animation:celtw 2.4s 2 both}@keyframes celtw{0%{opacity:.15}50%{opacity:1}100%{opacity:.9}}
.cel-planet{animation:celfl 3s ease-in-out 2}@keyframes celfl{50%{transform:translateY(-6px)}}
@media (prefers-reduced-motion:reduce){.cel-tw,.cel-planet{animation:none}}
.cel-tools button{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;border:0;background:rgba(255,255,255,.16);color:#fff;cursor:pointer}
.cel-tools .i{width:16px;height:16px}
.cel-story{margin-top:10px;background:none;border:0;color:var(--accent);font:600 0.8125rem Golos Text,sans-serif;cursor:pointer}
.cel.fly .cel-card{transition:transform .55s cubic-bezier(.5,0,.75,0),opacity .55s}
.streak.flash{animation:sflash .8s ease}@keyframes sflash{30%{transform:scale(1.15);box-shadow:0 0 0 8px rgba(243,91,47,.25)}}
@media (max-width:480px){.cel-top{height:190px}.cel-name{font-size:1.375rem}.slot{font-size:1.875rem}}
"""

HTML = """<div class="cel" id="cel" role="dialog" aria-modal="true" aria-labelledby="cel-name" hidden>
<div class="cel-bg" id="cel-bg" data-close></div><canvas id="cel-fx" aria-hidden="true"></canvas>
<div class="cel-card" id="cel-card">
 <div class="cel-top" id="cel-top">
  <div class="cel-tools"><button type="button" id="cel-snd" aria-label="Дыбыс"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></button>
  <button type="button" data-close aria-label="Жабу"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div>
  <svg class="cel-ring" id="cel-ring" viewBox="0 0 168 168" aria-hidden="true"><circle cx="84" cy="84" r="72" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="14"/>
  <circle id="cel-ring-v" cx="84" cy="84" r="72" fill="none" stroke="#fec200" stroke-width="14" stroke-linecap="round" transform="rotate(-90 84 84)" stroke-dasharray="452.4" stroke-dashoffset="452.4"/></svg>
  <div class="cel-wave" id="cel-wave"></div>
  <svg class="cel-sky" id="cel-sky" viewBox="0 0 420 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>
   <radialGradient id="celpl"><stop offset="0" stop-color="#ffe27a"/><stop offset="1" stop-color="#f35b2f"/></radialGradient>
   <linearGradient id="celtr" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#fec200" stop-opacity="0"/><stop offset="1" stop-color="#fec200"/></linearGradient></defs>
   <g fill="#fff"><circle class="cel-tw" cx="36" cy="44" r="1.6"/><circle class="cel-tw" cx="120" cy="120" r="1.1" style="animation-delay:.5s"/><circle class="cel-tw" cx="380" cy="190" r="1.6" style="animation-delay:1s"/>
   <circle class="cel-tw" cx="230" cy="200" r="1.2" style="animation-delay:1.5s"/><circle class="cel-tw" cx="60" cy="170" r="1.3" style="animation-delay:.2s"/><circle class="cel-tw" cx="190" cy="34" r="1.1" style="animation-delay:.8s"/>
   <circle class="cel-tw" cx="270" cy="150" r="1" style="animation-delay:1.2s"/><circle class="cel-tw" cx="400" cy="40" r="1.2" style="animation-delay:.4s"/></g>
   <g class="cel-planet"><circle cx="330" cy="68" r="30" fill="url(#celpl)"/><ellipse cx="330" cy="68" rx="46" ry="10" fill="none" stroke="rgba(255,226,122,.7)" stroke-width="3" transform="rotate(-15 330 68)"/>
   <text id="cel-goal" x="330" y="122" text-anchor="middle" fill="#fff" font-family="Golos Text,sans-serif" font-weight="800" font-size="13">100 лид</text></g>
   <path id="cel-path" d="M70 285 C80 205 175 140 292 84" fill="none" stroke="rgba(255,255,255,.22)" stroke-width="3" stroke-dasharray="2 9" stroke-linecap="round"/>
   <path id="cel-trail" d="M70 285 C80 205 175 140 292 84" fill="none" stroke="#fec200" stroke-width="5" stroke-linecap="round" style="filter:drop-shadow(0 0 6px rgba(254,194,0,.7))"/>
   <g id="cel-rk"><path d="M0-16c8 6 9 16 4 25h-8c-5-9-4-19 4-25z" fill="#fff"/><circle cy="-4" r="3.6" fill="#2A78D6"/><path d="M-5 9l-7 7 5 1zM5 9l7 7-5 1z" fill="#f35b2f"/><path d="M-3 11q3 14 6 0z" fill="#fec200"/></g>
   </svg><div class="cel-pctx" id="cel-pct">0%</div>
  <div class="cel-count" id="cel-count"><b id="cel-num">0</b><span>лид</span></div>
  <svg class="cel-trophy" id="cel-trophy" viewBox="0 0 96 96" aria-hidden="true"><defs>
  <linearGradient id="tgo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff4b8"/><stop offset=".42" stop-color="#ffd23f"/><stop offset="1" stop-color="#e08600"/></linearGradient>
  <linearGradient id="tgb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a5fe0"/><stop offset="1" stop-color="#2F0E51"/></linearGradient>
  <radialGradient id="tgl"><stop offset="0" stop-color="#fec200" stop-opacity=".55"/><stop offset="1" stop-color="#fec200" stop-opacity="0"/></radialGradient></defs>
  <circle cx="48" cy="42" r="46" fill="url(#tgl)" id="cel-tglow" opacity="0"/>
  <g id="cel-tfill" opacity="0">
   <path d="M28 21H17c0 14 6 21 15 22M68 21h11c0 14-6 21-15 22" fill="none" stroke="url(#tgo)" stroke-width="5" stroke-linecap="round"/>
   <path d="M26 13h44v19c0 13-10 23-22 23S26 45 26 32V13Z" fill="url(#tgo)"/>
   <rect x="23" y="10" width="50" height="6" rx="3" fill="#ffe680"/>
   <path d="M33 19v12c0 6 3 11 8 14" fill="none" stroke="#fff" stroke-opacity=".75" stroke-width="3.5" stroke-linecap="round"/>
   <path d="M51.0,23.0 L53.0,28.2 L58.6,28.5 L54.2,32.1 L55.7,37.5 L51.0,34.4 L46.3,37.5 L47.8,32.1 L43.4,28.5 L49.0,28.2Z" fill="#fff" fill-opacity=".92"/>
   <path d="M44 55h8l1 8h-10z" fill="#e8a000"/><rect x="37" y="62" width="22" height="5" rx="2" fill="#ffd23f"/>
   <rect x="29" y="67" width="38" height="15" rx="3.5" fill="url(#tgb)"/><rect x="39" y="71.5" width="18" height="5.5" rx="1.5" fill="#fec200"/>
  </g>
  <path id="cel-tp" d="M26 13h44v19c0 13-10 23-22 23S26 45 26 32V13Z M28 21H17c0 14 6 21 15 22 M68 21h11c0 14-6 21-15 22 M44 55h8 M37 62h22v5H37Z M29 67h38v15H29Z" fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>
  <svg class="cel-gift" id="cel-gift" viewBox="0 0 120 120" aria-hidden="true">
   <rect x="22" y="56" width="76" height="52" rx="6" fill="#f35b2f"/><rect x="54" y="56" width="12" height="52" fill="#fec200"/>
   <g id="cel-lid"><rect x="16" y="40" width="88" height="18" rx="5" fill="#ff7a4d"/><rect x="54" y="40" width="12" height="18" fill="#ffd84d"/>
   <path d="M60 40c-8-14-24-12-20-2 2 5 14 4 20 2Zm0 0c8-14 24-12 20-2-2 5-14 4-20 2Z" fill="#fec200"/></g></svg>
  <div class="cel-giftcard" id="cel-giftcard"><small>сыйлық ашылды</small><b id="cel-gift-t"></b></div>
 </div>
 <div class="cel-body">
  <span class="cel-star" id="cel-star"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Бүгінгі периодтың жұлдызы</span>
  <h2 class="cel-name" id="cel-name"></h2>
  <p class="cel-msg" id="cel-msg"></p>
  <p class="cel-sub" id="cel-sub"></p>
  <div class="cel-bonus" id="cel-bonus"><small id="cel-blabel"></small><div class="slot" id="cel-slot"></div></div>
  <div class="cel-chips" id="cel-chips"></div>
  <div class="cel-btns" id="cel-btns"><button class="sec" type="button" id="cel-more"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.94 14.06 4 20"/><path d="m14 4 1.2 2.8L18 8l-2.8 1.2L14 12l-1.2-2.8L10 8l2.8-1.2Z"/><path d="M19 14l.6 1.4L21 16l-1.4.6L19 18l-.6-1.4L17 16l1.4-.6Z"/></svg>Тағы мотивация</button><button class="pri" type="button" id="cel-go">Жалғастырамыз <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></button></div>
  <button class="cel-story" type="button" id="cel-png">Сторизге сақтау (PNG)</button>
 </div>
</div></div>"""

JS = r"""
(function(){
const C=__CEL__;const q=new URLSearchParams(location.search);
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const $=id=>document.getElementById(id);const el=$('cel'),card=$('cel-card'),bg=$('cel-bg'),cv=$('cel-fx'),cx=cv.getContext('2d');
const nf=n=>Math.round(n).toLocaleString('ru-RU').replace(/ /g,' ');
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),seg=(t,a,b)=>clamp((t-a)/(b-a),0,1);
const eo=k=>1-Math.pow(1-k,3),eb=k=>{const c=1.70158;return 1+(c+1)*Math.pow(k-1,3)+c*Math.pow(k-1,2)};
const fill=t=>t.replace(/\{name\}/g,C.name).replace(/\{NAME\}/g,C.name.toUpperCase()).replace(/\{days\}/g,C.streak);
let mode='daily',msgText='',t0=0,raf=0,frozen=null,muted=false,last=-1;try{muted=localStorage.getItem('mk-mute')==='1'}catch(e){}
const END={motiv:1600,daily:3600,streak:3900,month:4400};
/* ---------- deterministic particles ---------- */
function rng(seed){return function(){seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function burstAt(seed,n,cxp,cyp,speed,kinds){const r=rng(seed),a=[];for(let i=0;i<n;i++){const ang=r()*6.283,v=(r()*.8+.4)*speed;
 a.push({x:cxp,y:cyp,vx:Math.cos(ang)*v,vy:Math.sin(ang)*v-speed*.12,k:kinds[Math.floor(r()*kinds.length)],c:['#fec200','#ffe27a','#ffffff','#f35b2f','#9b7bff'][Math.floor(r()*5)],
 s:r()*3+2,rot:r()*6,vr:(r()-.5)*.3,life:r()*.5+.8,ph:r()*6})}return a}
function simulate(parts,tau,grav){const n=Math.floor(tau/16),k=.985,S=k*(1-Math.pow(k,n))/(1-k),G=grav/(1-k)*(n-S),out=[];
 for(const p of parts){const a=clamp(1-tau/1000/p.life,0,1);if(a<=0)continue;out.push({k:p.k,c:p.c,s:p.s,ph:p.ph,a,x:p.x+p.vx*S,y:p.y+p.vy*S+G,rot:p.rot+p.vr*n})}return out}
function star(x,y,r){cx.beginPath();for(let i=0;i<10;i++){const a=i*Math.PI/5-Math.PI/2,rr=i%2?r*.45:r;cx.lineTo(x+Math.cos(a)*rr,y+Math.sin(a)*rr)}cx.closePath();cx.fill()}
function drawParts(ps,d){ps.forEach(p=>{if(p.a<=0)return;cx.save();cx.globalAlpha=p.a;cx.fillStyle=p.c;cx.strokeStyle=p.c;
 if(p.k==='spark'){cx.globalAlpha=p.a*.25;cx.beginPath();cx.arc(p.x,p.y,p.s*3.2*d,0,6.283);cx.fill();cx.globalAlpha=p.a;cx.beginPath();cx.arc(p.x,p.y,p.s*1.2*d,0,6.283);cx.fill()}
 else if(p.k==='star'){star(p.x,p.y,p.s*2.4*d)}
 else if(p.k==='ribbon'){cx.lineWidth=2*d;cx.beginPath();for(let i=0;i<14;i++){const yy=p.y-i*2.2*d,xx=p.x+Math.sin(p.ph+i*.6+p.rot)*5*d;i?cx.lineTo(xx,yy):cx.moveTo(xx,yy)}cx.stroke()}
 cx.restore()})}
/* ---------- sound ---------- */
let actx;function tone(fs,type,gap,len,vol){if(muted||frozen!==null)return;try{actx=actx||new (window.AudioContext||window.webkitAudioContext)();const s=actx.currentTime;
 fs.forEach((f,i)=>{const o=actx.createOscillator(),g=actx.createGain(),t=s+i*gap;o.type=type;o.frequency.value=f;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(vol,t+.02);
 g.gain.exponentialRampToValueAtTime(.0001,t+len);o.connect(g).connect(actx.destination);o.start(t);o.stop(t+len+.05)})}catch(e){}}
const SOUNDS={motiv:()=>tone([659,880],'sine',.07,.5,.05),daily:()=>{tone([523,659,784],'sine',.09,.6,.05);setTimeout(()=>tone([1047,1319],'triangle',.08,1.2,.05),1000)},
 streak:()=>{tone([392,523,659],'triangle',.1,.6,.05);setTimeout(()=>tone([784,988,1175,1568],'sine',.08,1.4,.05),1000)},month:()=>{SOUNDS.daily();setTimeout(()=>tone([523,659,784,1047],'triangle',.12,1.6,.05),1700)}};
$('cel-snd').onclick=e=>{e.stopPropagation();muted=!muted;try{localStorage.setItem('mk-mute',muted?'1':'0')}catch(_){};$('cel-snd').style.opacity=muted?.45:1};$('cel-snd').style.opacity=muted?.45:1;
/* ---------- slot machine ---------- */
function buildSlot(text){const s=$('cel-slot');s.innerHTML='';[...text].forEach(ch=>{if(/\d/.test(ch)){const col=document.createElement('span');col.className='col';
 const st=document.createElement('span');st.className='strip';for(let r=0;r<3;r++)for(let k=0;k<10;k++){const d=document.createElement('span');d.textContent=k;st.appendChild(d)}
 col.appendChild(st);col.dataset.d=ch;s.appendChild(col)}else{const c=document.createElement('span');c.className='ch';c.textContent=ch===' '?' ':ch;s.appendChild(c)}})}
function slotFrame(t,start,stagger){const cols=[...document.querySelectorAll('#cel-slot .col')];cols.forEach((c,i)=>{const settle=start+300+i*stagger,d=+c.dataset.d;
 let pos;if(t<start)pos=0;else if(t<settle){pos=((t-start)/38)%10}else{pos=20+d}if(t>=settle)pos=20+d;else pos=10+pos%10;
 c.firstChild.style.transform=`translateY(${-pos*44}px)`})}
/* ---------- the frame ---------- */
let parts=null,fireworks=null;
const DPR=()=>Math.min(devicePixelRatio||1,1.5);
function setup(){const d=DPR(),W=innerWidth,H=innerHeight;cv.width=W*d;cv.height=H*d;
 const r=$('cel-top').getBoundingClientRect(),ccx=(r.left+r.width/2)*d,ccy=(r.top+r.height/2)*d;
 parts=burstAt(7,mode==='motiv'?0:110,ccx,ccy,9*d,['spark','spark','star','ribbon','star']);
 if(mode==='motiv')parts=burstAt(11,40,ccx,(r.top+r.height)*d,11*d,['star','spark','ribbon','star']);
 fireworks=[];if(mode==='month'){const rr=rng(5);[300,800,1250,1750,2300,2800,3300].forEach((at,i)=>{const x=(rr()*.8+.1)*W*d,y=(rr()*.35+.12)*H*d;
  fireworks.push({at,x,y,ps:burstAt(100+i,70,x,y,7*d,['spark','spark','star'])})})}}
function frame(t){const d=DPR(),W=cv.width,H=cv.height;cx.clearRect(0,0,W,H);
 const end=END[mode];bg.style.opacity=seg(t,0,200);
 const isM=mode==='motiv',isS=mode==='streak';
 // card entrance
 if(isM){const k=eb(seg(t,0,420));card.style.transform=`translateY(${(1-k)*110}%)`;card.style.opacity=seg(t,0,150)}
 else{const k=eb(seg(t,100,600));card.style.transform=`scale(${.85+.15*k})`;card.style.opacity=seg(t,100,300)}
 // ring + counter (daily/month)
 const ringOn=!isM&&!isS;$('cel-ring').style.display=ringOn?'':'none';$('cel-count').style.display=(ringOn||isM)?'':'none';
 if(isM){const k=eb(seg(t,150,550));$('cel-count').style.opacity=seg(t,150,250);$('cel-count').style.transform=`scale(${.4+.6*k}) rotate(${(1-k)*-20}deg)`}
 if(ringOn){const k=eo(seg(t,200,1000)),p=C.ring_from+(1-C.ring_from)*k;$('cel-ring-v').setAttribute('stroke-dashoffset',(452.4*(1-p)).toFixed(1));
  $('cel-num').textContent=nf(C.count_from+(C.count_to-C.count_from)*k);
  const pop=seg(t,1000,1250);$('cel-ring').style.opacity=1-pop;$('cel-count').style.opacity=1-pop;$('cel-ring').style.transform=`scale(${1+pop*.25})`}
 // light wave
 const w=seg(t,1000,1500);$('cel-wave').style.display=isM?'none':'';$('cel-wave').style.transform=`scale(${.6+w*2.2})`;$('cel-wave').style.opacity=w>0&&w<1?1-w:0;
 // trophy (daily/month) draws itself, then fills with gold
 $('cel-trophy').style.display=ringOn?'':'none';if(ringOn){const dr=seg(t,1050,1500),fl=seg(t,1400,1750);$('cel-tp').setAttribute('stroke-dashoffset',(1-dr).toFixed(3));
  $('cel-tfill').setAttribute('opacity',fl.toFixed(2));$('cel-tglow').setAttribute('opacity',fl.toFixed(2));$('cel-tp').setAttribute('stroke-opacity',(1-fl*.9).toFixed(2));$('cel-trophy').style.transform=`scale(${.7+.3*eb(seg(t,1000,1400))}) translateY(${Math.sin(t/500)*3*seg(t,1800,2200)}px)`;$('cel-trophy').style.opacity=seg(t,1000,1100)}
 // gift box (streak): lid flies off at 1.0 s, the gift card rises
 $('cel-gift').style.display=isS?'':'none';$('cel-giftcard').style.display=isS?'':'none';
 if(isS){const shake=t<1000?Math.sin(t/40)*seg(t,400,1000)*4:0;$('cel-gift').style.transform=`translateY(${(1-eb(seg(t,100,600)))*60+eo(seg(t,1150,1700))*46}px) rotate(${shake}deg) scale(${1-seg(t,1150,1700)*.25})`;
  const lid=seg(t,1000,1500);$('cel-lid').setAttribute('transform',`translate(${lid*90} ${-lid*160}) rotate(${lid*50} 60 48)`);
  const gc=eb(seg(t,1150,1700));$('cel-giftcard').style.transform=`translate(-50%,${40-gc*62}px) scale(${.6+.4*gc})`;$('cel-giftcard').style.opacity=seg(t,1150,1350);
  $('cel-gift').style.opacity=1-seg(t,1700,2000)*.0}
 // particles: burst at 1.0 s (emoji burst at 0.2 s for motiv)
 const bAt=isM?200:1000;if(t>=bAt)drawParts(simulate(parts,t-bAt,isM?.35*d:.26*d),d);
 // fireworks (month)
 if(fireworks)fireworks.forEach(f=>{if(t<f.at)return;const rise=seg(t,f.at-300,f.at);if(t<f.at){return}drawParts(simulate(f.ps,t-f.at,.12*d),d)});
 if(fireworks)fireworks.forEach(f=>{const r=seg(t,f.at-350,f.at);if(r>0&&r<1){cx.fillStyle='#ffe27a';cx.beginPath();cx.arc(f.x,H-(H-f.y)*r,3*d,0,6.283);cx.fill()}});
 // ambient floating glints after the main beat
 if(t>end-600&&t<end+400&&!isM){const rr=rng(9);for(let i=0;i<18;i++){const x=rr()*W,y=(rr()*H+(-(t/14)*d))%H,yy=y<0?y+H:y,a=.35+.35*Math.sin(t/400+i);cx.globalAlpha=a*seg(t,end-600,end);
  cx.fillStyle=i%2?'#fec200':'#ffffff';cx.beginPath();cx.arc(x,yy,1.6*d,0,6.283);cx.fill()}cx.globalAlpha=1}
 // name types letter by letter, then the meme line
 const nA=isM?150:1600,mA=isM?250:1750,mB=isM?700:2600;const nm=C.full_name;$('cel-name').textContent=nm.slice(0,Math.round(nm.length*seg(t,nA,nA+(isM?150:500))));
 if(isM){const P=$('cel-path'),L=P.getTotalLength(),k=eo(seg(t,250,1400)),pos=Math.max(.5,L*storyP*k),a=P.getPointAtLength(pos),b=P.getPointAtLength(Math.min(L,pos+1)),
  ang=Math.atan2(b.y-a.y,b.x-a.x)*57.3+90;$('cel-rk').setAttribute('transform',`translate(${a.x.toFixed(1)} ${a.y.toFixed(1)}) rotate(${ang.toFixed(1)})`);
  $('cel-trail').setAttribute('stroke-dasharray',L.toFixed(1));$('cel-trail').setAttribute('stroke-dashoffset',(L-pos).toFixed(1));$('cel-pct').textContent=Math.round(storyP*100*k)+'%';
  $('cel-sub').style.opacity=seg(t,700,900)}
 const shown=msgText.slice(0,Math.round(msgText.length*seg(t,mA,mB)));$('cel-msg').innerHTML=shown.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+(t<mB+300&&t>mA?'<i></i>':'');
 // bonus slot (not for motiv)
 $('cel-bonus').style.display=(isM||!C.bonus)?'none':'';if(!isM){$('cel-bonus').style.opacity=seg(t,2100,2300);slotFrame(t,2200,70)}
 // chips
 const chips=[...document.querySelectorAll('#cel-chips span')];chips.forEach((c,i)=>{const sg=seg(t,(isM?600:2800)+i*150,(isM?800:3050)+i*150),k=eb(sg);c.style.opacity=sg>0?Math.min(1,sg*3):0;c.style.transform=`scale(${.6+.4*k})`});
 // buttons
 const bk=seg(t,isM?800:3200,isM?1000:3500);$('cel-btns').style.opacity=bk;$('cel-btns').style.transform=`translateY(${(1-bk)*10}px)`;$('cel-png').style.opacity=bk;
}
function loop(now){const t=now-t0;if(t>=END[mode]+400){frame(END[mode]+400);return}frame(t);raf=requestAnimationFrame(loop)}
/* ---------- open / close ---------- */
const IC={"flame": "<svg width=\"15\" height=\"15\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path fill=\"currentColor\" d=\"M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z\"/><\/svg>", "users": "<svg viewBox=\"0 0 24 24\" width=\"15\" height=\"15\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\"/><circle cx=\"9\" cy=\"7\" r=\"4\"/><path d=\"M22 21v-2a4 4 0 0 0-3-3.87\"/><path d=\"M16 3.13a4 4 0 0 1 0 7.75\"/><\/svg>", "target": "<svg viewBox=\"0 0 24 24\" width=\"15\" height=\"15\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"10\"/><circle cx=\"12\" cy=\"12\" r=\"6\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/><\/svg>", "big": ["<span class=\"medal\"><svg viewBox=\"0 0 24 24\"><path d=\"M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z\"/><path d=\"m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z\"/><path d=\"M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0\"/><path d=\"M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5\"/><\/svg><\/span>", "<span class=\"medal v\"><svg viewBox=\"0 0 24 24\"><path d=\"M6 9H4.5a2.5 2.5 0 0 1 0-5H6\"/><path d=\"M18 9h1.5a2.5 2.5 0 0 0 0-5H18\"/><path d=\"M4 22h16\"/><path d=\"M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22\"/><path d=\"M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22\"/><path d=\"M18 2H6v7a6 6 0 0 0 12 0V2Z\"/><\/svg><\/span>", "<span class=\"medal g\"><svg viewBox=\"0 0 24 24\"><polyline points=\"22 7 13.5 15.5 8.5 10.5 2 17\"/><polyline points=\"16 7 22 7 22 13\"/><\/svg><\/span>", "<span class=\"medal\"><svg viewBox=\"0 0 24 24\"><circle cx=\"12\" cy=\"8\" r=\"6\"/><path d=\"M15.477 12.89 17 22l-5-3-5 3 1.523-9.11\"/><\/svg><\/span>", "<span class=\"medal v\"><svg viewBox=\"0 0 24 24\"><path d=\"M13 2 3 14h9l-1 8 10-12h-9l1-8z\"/><\/svg><\/span>", "<span class=\"medal g\"><svg viewBox=\"0 0 24 24\"><circle cx=\"12\" cy=\"12\" r=\"10\"/><circle cx=\"12\" cy=\"12\" r=\"6\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/><\/svg><\/span>", "<span class=\"medal\"><svg viewBox=\"0 0 24 24\"><path d=\"M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z\"/><\/svg><\/span>"], "trophy": ["M6 9H4.5a2.5 2.5 0 0 1 0-5H6", "M18 9h1.5a2.5 2.5 0 0 0 0-5H18", "M4 22h16", "M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22", "M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22", "M18 2H6v7a6 6 0 0 0 12 0V2Z"]};
function chipsFor(m){const a=[];if(C.streak)a.push(IC.flame+`${C.streak} күн қатарынан`);a.push(IC.users+`бүгін ${C.today_leads}/${C.lead_day}`);if(C.month_pct!==null)a.push(IC.target+`ай ${C.month_pct}%`);
 $('cel-chips').innerHTML=a.map(x=>`<span>${x}</span>`).join('')}
function pickMeme(){let k;do{k=Math.floor(Math.random()*C.praise.length)}while(k===last&&C.praise.length>1);last=k;return fill(C.praise[k])}
let lastFocus;
let storyP=0;const STAR0=$('cel-star').innerHTML;
function open(m,text,freezeAt){mode=m;lastFocus=document.activeElement;el.hidden=false;el.classList.remove('fly');card.style.transition='';
 card.classList.toggle('story',m==='motiv');
 const goal=C.lead_day||100,leads=C.today_leads||0;storyP=Math.max(0,Math.min(1,leads/goal));
 $('cel-goal').textContent=goal+' лид';
 $('cel-sub').textContent=leads>=goal?`Бүгінгі жоспар орындалды — ${leads} лид! Мақсатқа қондың.`:
  leads>=goal/2?`Бүгін ${leads} лид — жолдың жартысынан астам артта. Мақсатқа ${goal-leads} лид қалды.`:
  `Бүгін ${leads} лид. Ракета ұшып барады — мақсатқа ${goal-leads} лид қалды.`;
 $('cel-star').innerHTML=m==='motiv'?STAR0.replace('Бүгінгі периодтың жұлдызы','Бүгінгі ұшу'):STAR0;
 msgText=text||(m==='motiv'?pickMeme():m==='streak'?fill(C.streak_line):m==='month'?fill(C.month_line):fill(C.daily_line));
 $('cel-blabel').textContent=C.bonus_label;
 if(m==='motiv'){$('cel-num').innerHTML=IC.big[Math.floor(Math.random()*IC.big.length)];$('cel-num').style.fontSize='';$('cel-count').querySelector(':scope>span').textContent='күндік мотивация'}
 else{$('cel-num').textContent='0';$('cel-num').style.fontSize='';$('cel-count').querySelector(':scope>span').textContent='лид';$('cel-count').style.transform=''}buildSlot((C.bonus_reached||m!=='motiv'?'+':'')+nf(C.bonus)+' ₸');$('cel-gift-t').textContent=C.gift||'Кофе';chipsFor(m);
 setup();cancelAnimationFrame(raf);
 if(freezeAt!==null){frozen=freezeAt;frame(freezeAt);return}
 if(reduce){frame(END[m]);return}
 SOUNDS[m]();t0=performance.now();raf=requestAnimationFrame(loop);
 clearTimeout(open._fb);open._fb=setTimeout(()=>{if(performance.now()-t0>=END[m]&&!el.hidden){frame(Math.max(END[m],performance.now()-t0))}$('cel-go').focus()},END[m]+80)}
function close(){const pill=document.getElementById('streak');cancelAnimationFrame(raf);
 if(pill&&!reduce){const a=card.getBoundingClientRect(),b=pill.getBoundingClientRect();el.classList.add('fly');
  card.style.transform=`translate(${b.left+b.width/2-(a.left+a.width/2)}px,${b.top+b.height/2-(a.top+a.height/2)}px) scale(.08)`;card.style.opacity=0;bg.style.transition='opacity .5s';bg.style.opacity=0;
  setTimeout(()=>{el.hidden=true;bg.style.transition='';pill.classList.remove('flash');void pill.offsetWidth;pill.classList.add('flash');tone([880,1175],'sine',.06,.4,.04)},560)}
 else el.hidden=true;cx.clearRect(0,0,cv.width,cv.height);if(lastFocus)lastFocus.focus()}
el.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',close));$('cel-go').onclick=close;
addEventListener('keydown',e=>{if(!el.hidden&&e.key==='Escape')close()});
$('cel-more').onclick=()=>open('motiv',pickMeme(),null);
/* easter egg: tap the star five times */
let taps=0,tt;$('cel-star').onclick=()=>{taps++;clearTimeout(tt);tt=setTimeout(()=>taps=0,1500);tone([900+taps*80],'square',.05,.12,.03);
 if(taps>=5){taps=0;open(mode==='motiv'?'motiv':mode,fill(C.eggs[Math.floor(Math.random()*C.eggs.length)]),null)}};
/* story PNG 1080×1920 */
function storyPng(){const c=document.createElement('canvas');c.width=1080;c.height=1920;const g=c.getContext('2d');
 const gr=g.createLinearGradient(0,0,0,1920);gr.addColorStop(0,'#0f0a2a');gr.addColorStop(.42,'#2F0E51');gr.addColorStop(.76,'#7336F7');gr.addColorStop(1,'#2A78D6');g.fillStyle=gr;g.fillRect(0,0,1080,1920);
 const rr=rng(7);for(let i=0;i<90;i++){g.globalAlpha=rr()*.7+.2;g.fillStyle=i%4?'#fff':'#fec200';g.beginPath();g.arc(rr()*1080,rr()*1150,rr()*3.5+1,0,6.283);g.fill()}g.globalAlpha=1;
 const S=1080/420;g.save();g.scale(S,S*1.35);
 const P=new Path2D($('cel-path').getAttribute('d'));g.setLineDash([2,9]);g.lineCap='round';g.strokeStyle='rgba(255,255,255,.25)';g.lineWidth=3;g.stroke(P);g.setLineDash([]);
 const el2=$('cel-path'),L=el2.getTotalLength(),pos=Math.max(.5,L*storyP),a=el2.getPointAtLength(pos),b=el2.getPointAtLength(Math.min(L,pos+1));
 g.save();g.setLineDash([L]);g.lineDashOffset=L-pos;g.strokeStyle='#fec200';g.lineWidth=6;g.stroke(P);g.restore();
 g.save();g.translate(a.x,a.y);g.rotate(Math.atan2(b.y-a.y,b.x-a.x)+1.5708);g.fillStyle='#fff';g.fill(new Path2D('M0-16c8 6 9 16 4 25h-8c-5-9-4-19 4-25z'));
 g.fillStyle='#2A78D6';g.beginPath();g.arc(0,-4,3.6,0,6.283);g.fill();g.fillStyle='#f35b2f';g.fill(new Path2D('M-5 9l-7 7 5 1zM5 9l7 7-5 1z'));g.fillStyle='#fec200';g.fill(new Path2D('M-3 11q3 14 6 0z'));g.restore();
 g.restore();
 const px=330*S,py=68*S*1.35,pr=30*S,pl=g.createRadialGradient(px,py,0,px,py,pr);pl.addColorStop(0,'#ffe27a');pl.addColorStop(1,'#f35b2f');g.fillStyle=pl;g.beginPath();g.arc(px,py,pr,0,6.283);g.fill();
 g.save();g.translate(px,py);g.rotate(-.26);g.strokeStyle='rgba(255,226,122,.75)';g.lineWidth=8;g.beginPath();g.ellipse(0,0,46*S,10*S,0,0,6.283);g.stroke();g.restore();
 g.fillStyle='#fff';g.textAlign='center';g.font='800 36px Golos Text,sans-serif';g.fillText((C.lead_day||100)+' лид',330*S,122*S*1.35+10);
 g.textAlign='left';g.font='900 120px Golos Text,sans-serif';g.fillText(Math.round(storyP*100)+'%',70,1080);
 g.fillStyle='rgba(254,194,0,.2)';g.beginPath();g.roundRect(70,1150,420,64,32);g.fill();g.fillStyle='#fec200';g.font='800 30px Golos Text,sans-serif';g.fillText('★  БҮГІНГІ ҰШУ',100,1193);
 g.fillStyle='#fff';let fs=104;do{g.font=`900 ${fs}px Golos Text,sans-serif`;fs-=4}while(g.measureText(C.full_name).width>940&&fs>40);g.fillText(C.full_name,70,1340);
 g.font='800 54px Golos Text,sans-serif';let line='',y=1440;msgText.split(' ').forEach(wd=>{const t=line+wd+' ';if(g.measureText(t).width>940){g.fillText(line,70,y);line=wd+' ';y+=72}else line=t});g.fillText(line,70,y);
 g.fillStyle='rgba(255,255,255,.8)';g.font='500 40px Golos Text,sans-serif';line='';y+=90;$('cel-sub').textContent.split(' ').forEach(wd=>{const t=line+wd+' ';if(g.measureText(t).width>940){g.fillText(line,70,y);line=wd+' ';y+=56}else line=t});g.fillText(line,70,y);
 g.fillStyle='rgba(255,255,255,.75)';g.font='700 36px Golos Text,sans-serif';g.fillText('EduApp Marketing',70,1840);
 const a2=document.createElement('a');a2.download='eduapp-'+C.name+'.png';a2.href=c.toDataURL('image/png');a2.click()}
$('cel-png').onclick=async()=>{try{await document.fonts.ready}catch(e){}if(mode==='motiv'){storyPng();return}const c=document.createElement('canvas');c.width=1080;c.height=1920;const g=c.getContext('2d');
 const gr=g.createLinearGradient(0,0,1080,1920);gr.addColorStop(0,'#2F0E51');gr.addColorStop(.5,'#7336F7');gr.addColorStop(1,'#2A78D6');g.fillStyle=gr;g.fillRect(0,0,1080,1920);
 const glow=g.createRadialGradient(860,260,0,860,260,520);glow.addColorStop(0,'rgba(254,194,0,.55)');glow.addColorStop(1,'rgba(254,194,0,0)');g.fillStyle=glow;g.fillRect(0,0,1080,1920);
 const rr=rng(4);for(let i=0;i<70;i++){g.globalAlpha=rr()*.6+.2;g.fillStyle=i%3?'#fff':'#fec200';g.beginPath();g.arc(rr()*1080,rr()*1920,rr()*4+1,0,6.283);g.fill()}g.globalAlpha=1;
 g.save();g.translate(540-108,300);g.scale(9,9);g.strokeStyle='#fec200';g.lineWidth=1.6;g.lineCap=g.lineJoin='round';IC.trophy.forEach(d=>g.stroke(new Path2D(d)));g.restore();g.textAlign='center';
 g.fillStyle='rgba(255,255,255,.85)';g.font='700 40px Golos Text,sans-serif';g.fillText('БҮГІНГІ ПЕРИОДТЫҢ ЖҰЛДЫЗЫ',540,640);
 g.fillStyle='#fff';let fs=110;do{g.font=`800 ${fs}px Golos Text,sans-serif`;fs-=4}while(g.measureText(C.full_name).width>940&&fs>40);g.fillText(C.full_name,540,790);
 g.font='500 50px Golos Text,sans-serif';const words=msgText.split(' ');let line='',y=900;words.forEach(wd=>{const tst=line+wd+' ';if(g.measureText(tst).width>900){g.fillText(line,540,y);line=wd+' ';y+=68}else line=tst});g.fillText(line,540,y);
 g.fillStyle='rgba(255,255,255,.14)';g.beginPath();g.roundRect(140,y+80,800,240,40);g.fill();g.fillStyle='#fec200';g.font='800 110px Golos Text,sans-serif';g.fillText((C.bonus_reached?'+':'')+nf(C.bonus)+' ₸',540,y+230);
 g.fillStyle='rgba(255,255,255,.8)';g.font='600 38px Golos Text,sans-serif';g.fillText(C.bonus_label,540,y+290);
 g.fillStyle='#fff';g.font='700 44px Golos Text,sans-serif';g.fillText((C.streak?C.streak+' күн қатарынан  ·  ':'')+C.today_leads+' лид',540,y+420);
 g.fillStyle='rgba(255,255,255,.7)';g.font='600 36px Golos Text,sans-serif';g.fillText('EduApp Marketing',540,1840);
 const a=document.createElement('a');a.download='eduapp-'+C.name+'.png';a.href=c.toDataURL('image/png');a.click()};
window.zCelebrate=open;
/* entry points: demo (admin), automatic once a day, the motivation button */
const demo=C.demo_ok?q.get('demo'):null,fz=q.get('freeze');const freezeAt=fz===null?null:(+fz<=1?99999:+fz);
if(demo&&END[demo]){setTimeout(()=>open(demo,null,freezeAt),50);return}
const mb=document.getElementById('motiv');if(mb)mb.onclick=()=>open('motiv',pickMeme(),null);
const sp=document.getElementById('streak');if(sp)sp.onclick=()=>open(C.streak_reached?'streak':'motiv',C.streak_reached?fill(C.streak_line):fill('{name}, {days} күн қатарынан жоспар орындалды. Келесі сыйлыққа '+C.streak_left+' күн қалды.'),null);
if(q.get('nocel'))return;
let seen='';try{seen=localStorage.getItem('mk-cel')||''}catch(e){}
const auto=C.month_hit?'month':C.streak_unlocked?'streak':C.daily_hit?'daily':null;const key=C.today+'|'+auto;
if(auto&&seen!==key){setTimeout(()=>open(auto,null,null),700);try{localStorage.setItem('mk-cel',key)}catch(e){}}
})();
"""


def block(cfg: dict) -> tuple[str, str, str]:
    """(css, html, script) for the page; cfg is the data the celebration shows."""
    return CSS, HTML, "<script>" + JS.replace("__CEL__", json.dumps(cfg, ensure_ascii=False)) + "</script>"
