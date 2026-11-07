"""Custom charts, no chart library: «Канва» (one big breathing line, no grid, glass tooltip) and «Бенто» widgets
(monolith columns, dot calendar, week pills, split capsule, ring). The HTML/SVG comes from the server; one small
script (JS below, included once per page) draws the canvas line and adds the hover cards.
"""
import html
import json
import math

E = html.escape


def nf(n) -> str:
    return "—" if n is None else f"{round(n):,}".replace(",", " ")


CSS = """<style>
.zc-lbl{font-size:0.875rem;font-weight:500;color:var(--muted)}
.zc-num{font-weight:700;letter-spacing:-.035em;line-height:1;font-variant-numeric:tabular-nums lining-nums}
.zc-unit{font-weight:800;letter-spacing:-.02em;color:var(--faint);margin-left:3px;font-size:.45em}
.zc-dl{display:inline-flex;align-items:center;gap:3px;font-size:0.75rem;font-weight:800}.zc-dl.up{color:var(--green)}.zc-dl.dn{color:var(--red)}
.zc-cap{font-size:0.75rem;line-height:1.45;color:var(--faint);font-weight:600;letter-spacing:.005em}
/* canvas */
.zcv{position:relative;background:var(--surface);border-radius:var(--r);padding:22px 22px 14px;border:1px solid var(--border);margin-top:18px}
.zcv-top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}
.zcv .zc-num{font-size:2.5rem;margin-top:6px}.zcv-meta{display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap}
.zcv-tabs{display:flex;gap:2px;padding:3px;border-radius:999px;background:var(--surface2);flex-wrap:wrap}
.zcv-tabs button{border:0;background:transparent;font:600 0.8125rem Golos Text,sans-serif;font-variant-numeric:tabular-nums;color:var(--muted);padding:8px 14px;border-radius:999px;cursor:pointer;min-height:34px}
.zcv-tabs button.on{background:var(--board);color:var(--bink);box-shadow:none}
.zcv-plot{position:relative;margin:16px -24px 0;height:250px;touch-action:pan-y;cursor:crosshair}
.zcv-plot svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.zcv-x{display:flex;justify-content:space-between;padding:8px 0 0;font-size:0.6875rem;font-weight:700;color:var(--faint)}
.zcv-ann{position:absolute;transform:translate(-50%,-135%);font-size:0.6875rem;font-weight:800;color:var(--muted);white-space:nowrap;pointer-events:none}
.zcv-ann.max{color:var(--accent)}.zcv-ann:not(.max){transform:translate(-100%,-170%)}.zcv-ann i{font-style:normal;opacity:.55;font-weight:700;margin-left:4px}
.zcv-cross{position:absolute;top:0;bottom:0;width:0;border-left:1px dashed color-mix(in srgb,var(--accent) 50%,transparent);opacity:0;transition:opacity .2s;pointer-events:none}
.zcv-knob{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:var(--surface);border:3px solid var(--accent);box-shadow:0 0 0 6px color-mix(in srgb,var(--accent) 14%,transparent);opacity:0;transition:opacity .2s;pointer-events:none}
.zc-tip{position:absolute;top:0;min-width:160px;padding:11px 13px;border-radius:16px;pointer-events:none;opacity:0;transform:translate(-50%,-8px);transition:opacity .2s,transform .25s cubic-bezier(.2,.8,.2,1);
background:color-mix(in srgb,var(--surface) 74%,transparent);backdrop-filter:blur(14px) saturate(160%);-webkit-backdrop-filter:blur(14px) saturate(160%);
border:1px solid color-mix(in srgb,var(--surface) 90%,transparent);box-shadow:0 18px 40px -12px rgba(47,14,81,.3);z-index:5}
.zc-tip .d{font-size:0.75rem;font-weight:500;color:var(--faint)}
.zc-tip .v{font-size:1.375rem;font-weight:700;letter-spacing:-.03em;margin:2px 0}
.zc-tip .r{display:flex;justify-content:space-between;gap:12px;font-size:0.75rem;font-weight:700;color:var(--muted)}
.zcv.on .zcv-cross,.zcv.on .zcv-knob{opacity:1}.zcv.on .zc-tip{opacity:1;transform:translate(-50%,0)}
.zcv-ln{stroke-dasharray:var(--L);stroke-dashoffset:var(--L);animation:zcdr 1.3s cubic-bezier(.65,0,.35,1) forwards}
.zcv-ar{opacity:0;animation:zcfi .9s .45s forwards}@keyframes zcdr{to{stroke-dashoffset:0}}@keyframes zcfi{to{opacity:1}}
.zcv-mob{display:none}
@media (max-width:700px){.zcv{padding:18px 18px 12px;border-radius:var(--r)}.zcv .zc-num{font-size:2.125rem}.zcv-plot{height:190px;margin:12px -18px 0}
 .zcv-mob{display:grid;gap:10px;margin-top:12px}
 .zct{display:grid;grid-template-columns:1fr 92px;align-items:center;gap:12px;padding:14px 16px;border-radius:var(--r);background:var(--surface);border:1px solid var(--border)}
 .zct .zc-num{font-size:1.625rem;margin:3px 0}.zct svg{width:92px;height:40px}}
/* bento */
.zb{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;margin-top:18px}
.zbc{position:relative;overflow:hidden;border-radius:var(--r);padding:20px;background:var(--surface);border:1px solid var(--border);display:flex;flex-direction:column;min-height:190px;min-width:0}
.zbc .zc-num{font-size:2.125rem;margin-top:8px}
.zbc.s3{grid-column:span 3}.zbc.s4{grid-column:span 4}.zbc.s5{grid-column:span 5}.zbc.s6{grid-column:span 6}.zbc.s7{grid-column:span 7}.zbc.s12{grid-column:span 12}
.zb-foot{margin-top:auto}
.zb-cols{display:flex;align-items:flex-end;gap:4px;flex:1;min-height:120px;max-height:280px;margin-top:18px}
.zb-cols i{position:relative;flex:1;min-width:3px;border-radius:7px 7px 4px 4px;background:rgba(255,255,255,.11);height:var(--h);transform-origin:bottom;animation:zbup .9s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--k)*22ms)}
.zb-cols i b{position:absolute;inset:auto 0 0 0;height:var(--s);max-height:100%;border-radius:inherit;background:var(--accent)}
.zb-cols i.ok b{background:var(--green)}
.zb-cols i.now b{background:var(--gilt)}
.zb-cols i.fut{background:transparent;box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.12)}
@keyframes zbup{from{transform:scaleY(0)}}
.zb-dots{display:grid;grid-template-columns:repeat(var(--n,16),minmax(0,1fr));gap:6px;margin-top:auto}
.zb-dots i{aspect-ratio:1;border-radius:8px;background:var(--surface2);transition:transform .15s}
.zb-dots i[data-l="1"]{background:#DCD0FB}.zb-dots i[data-l="2"]{background:#B394F7}.zb-dots i[data-l="3"]{background:#8D5CF5}.zb-dots i[data-l="4"]{background:#7336F7}
:root[data-theme=dark] .zb-dots i[data-l="1"]{background:#3A2B66}:root[data-theme=dark] .zb-dots i[data-l="2"]{background:#5A3DA8}
.zb-dots i.now{box-shadow:0 0 0 2px var(--surface),0 0 0 4px var(--yellow)}.zb-dots i.fut{background:transparent;box-shadow:inset 0 0 0 1.5px var(--border)}
@media (hover:hover){.zb-dots i:hover{transform:scale(1.14)}}
.zb-wk{display:flex;align-items:flex-end;gap:8px;height:96px;margin-top:auto}
.zb-wk div{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;height:100%;justify-content:flex-end}
.zb-wk i{width:100%;max-width:22px;border-radius:999px;background:color-mix(in srgb,var(--accent) 16%,var(--surface));height:var(--h);min-height:6px}
.zb-wk .now i{background:var(--accent)}.zb-wk .fut i{background:transparent;box-shadow:inset 0 0 0 1.5px var(--border)}
.zb-wk span{font-size:0.6875rem;font-weight:800;color:var(--faint);letter-spacing:.04em}
.zb-split{display:flex;height:32px;gap:3px;margin-top:auto}.zb-split i{height:100%;border-radius:10px;min-width:6px}
.zb-split .a{background:var(--accent)}.zb-split .o{background:color-mix(in srgb,var(--accent) 18%,var(--surface))}
.zb-leg{display:flex;justify-content:space-between;gap:8px;margin-top:10px;font-size:0.75rem;font-weight:800;flex-wrap:wrap}
.zb-leg span{display:flex;align-items:center;gap:6px}.zb-leg em{width:8px;height:8px;border-radius:3px}
.zb-ring{display:flex;align-items:center;gap:16px;margin-top:auto}.zb-ring svg{width:88px;height:88px;flex:none}
.zb-ring .ra{stroke-dasharray:var(--c);stroke-dashoffset:var(--c);animation:zbrg 1.3s .2s cubic-bezier(.65,0,.35,1) forwards}
@keyframes zbrg{to{stroke-dashoffset:var(--o)}}
.zbc.dark{color:#fff;background:var(--hero)}.zbc.dark .zb-cols{max-height:none}.zbc.dark .zc-lbl,.zbc.dark .zc-cap,.zbc.dark .zc-unit{color:rgba(255,255,255,.78)}
.zb-tip{position:fixed;z-index:80;pointer-events:none;padding:8px 11px;border-radius:12px;font-size:0.75rem;font-weight:800;color:var(--text);opacity:0;transform:translate(-50%,calc(-100% - 10px));transition:opacity .15s;
background:color-mix(in srgb,var(--surface) 78%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--surface);box-shadow:0 14px 30px -10px rgba(47,14,81,.3)}
.zb-tip.on{opacity:1}.zt-on{outline:2px solid var(--accent);outline-offset:2px;border-radius:inherit}.zb-cols i.zt-on,.bt-hours .zt-on i{outline:2px solid #FEC200}.zb-tip span{color:var(--faint);font-weight:700;margin-right:6px}
.zb-pager{display:none;justify-content:center;gap:6px;margin-top:6px}.zb-pager i{width:6px;height:6px;border-radius:9px;background:color-mix(in srgb,var(--accent) 25%,var(--surface))}.zb-pager i.on{width:18px;background:var(--accent)}
@media (max-width:1000px){.zbc.s3,.zbc.s4{grid-column:span 6}.zbc.s5,.zbc.s7{grid-column:span 12}}
@media (max-width:700px){.zb{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:12px;margin:18px -16px 0;padding:4px 16px 14px;scrollbar-width:none}
 .zb::-webkit-scrollbar{display:none}.zbc{flex:0 0 84%;scroll-snap-align:center;min-height:250px}.zb-pager{display:flex}.zbc .zc-num{font-size:2.25rem}}
.zf{display:grid;gap:14px}.zf-r{display:grid;gap:7px}.zf-h{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.zf-h span{font-size:0.8125rem;font-weight:700;color:var(--muted)}.zf-h b{font-size:1.5rem;font-weight:700;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.zf-b{height:14px;border-radius:999px;background:var(--surface2);overflow:hidden}.zf-b i{display:block;height:100%;border-radius:inherit;width:var(--w);background:var(--accent);transform-origin:left;animation:zfx 1s cubic-bezier(.2,.8,.2,1) both}
.zf-r:last-child .zf-b i{background:var(--green)}
.zf-c{justify-self:start;display:inline-flex;align-items:center;gap:4px;margin:-4px 0 -4px 10px;padding:3px 9px;border-radius:999px;font-size:0.6875rem;font-weight:800;color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent)}
@keyframes zfx{from{transform:scaleX(0)}}
@media (prefers-reduced-transparency:reduce){.zc-tip,.zb-tip{background:var(--surface);backdrop-filter:none;-webkit-backdrop-filter:none}}@media (prefers-contrast:more){.zc-tip,.zb-tip{background:var(--surface);backdrop-filter:none;-webkit-backdrop-filter:none;border:2px solid var(--text)}.zbc.dark .zc-lbl,.zbc.dark .zc-cap,.zbc.dark .zc-unit{color:#fff}.zcv-cross{border-left-color:var(--text)}}
@media (prefers-reduced-motion:reduce){.zf-b i{animation:none}.zcv-ln,.zcv-ar,.zb-cols i,.zb-ring .ra{animation:none!important;stroke-dashoffset:var(--o,0);opacity:1}}
</style>"""

JS = r"""<script>(function(){if(!document.getElementById("zbtip")){var t=document.createElement("div");t.className="zb-tip";t.id="zbtip";document.body.appendChild(t)}
var nf=function(n){return n==null?'—':Math.round(n).toLocaleString('ru-RU').replace(/ /g,' ')};
function smooth(p){var d='M'+p[0][0]+','+p[0][1];for(var i=0;i<p.length-1;i++){var a=p[i-1]||p[i],b=p[i],c=p[i+1],e=p[i+2]||c;
 d+=' C'+(b[0]+(c[0]-a[0])/6).toFixed(1)+','+(b[1]+(c[1]-a[1])/6).toFixed(1)+' '+(c[0]-(e[0]-b[0])/6).toFixed(1)+','+(c[1]-(e[1]-b[1])/6).toFixed(1)+' '+c[0].toFixed(1)+','+c[1].toFixed(1)}return d}
document.querySelectorAll('.zcv').forEach(function(cv){if(cv.dataset.zc)return;cv.dataset.zc=1;
 var C=JSON.parse(cv.querySelector('script[type="application/json"]').textContent),key=0,P=[],plot=cv.querySelector('.zcv-plot'),svg=plot.querySelector('svg');
 var tip=cv.querySelector('.zc-tip'),cross=cv.querySelector('.zcv-cross'),knob=cv.querySelector('.zcv-knob');
 function draw(){var s=C.s[key],n=s.cur.length;if(!n)return;var W=plot.clientWidth,H=plot.clientHeight,top=30,bot=8,
  vals=s.cur.concat((s.prev||[]).filter(function(v){return v!=null})),mx=Math.max.apply(0,vals)||1,lo=Math.min.apply(0,vals),mn=s.fromMin?lo-(mx-lo)*.25:Math.min(0,lo),PX=Math.min(34,W*.04);
  var x=function(i){return PX+(n<2?0:i/(n-1))*(W-2*PX)},y=function(v){return top+(1-(v-mn)/((mx+(mx-mn)*.04-mn)||1))*(H-top-bot)};
  P=s.cur.map(function(v,i){return[x(i),y(v||0)]});var line=smooth(P),area=line+' L'+P[n-1][0]+','+H+' L'+P[0][0]+','+H+' Z',hi=s.cur.indexOf(Math.max.apply(0,s.cur));
  var prev=(s.prev&&s.prev.length===n&&s.prev.every(function(v){return v!=null}))?'<path d="'+smooth(s.prev.map(function(v,i){return[x(i),y(v)]}))+'" fill="none" stroke="var(--faint)" stroke-opacity=".55" stroke-width="1.5" stroke-dasharray="1 6" stroke-linecap="round"/>':'';
  var id='z'+Math.random().toString(36).slice(2,7);svg.setAttribute('viewBox','0 0 '+W+' '+H);
  svg.innerHTML='<defs><linearGradient id="'+id+'a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".08"/><stop offset="1" stop-color="var(--accent)" stop-opacity=".08"/></linearGradient></defs>'
  +'<path class="zcv-ar" d="'+area+'" fill="url(#'+id+'a)"/>'+prev+'<path class="zcv-ln" d="'+line+'" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round"/>'
  +'<circle cx="'+P[hi][0]+'" cy="'+P[hi][1]+'" r="4" fill="var(--accent)"/><circle cx="'+P[n-1][0]+'" cy="'+P[n-1][1]+'" r="4.5" fill="var(--surface)" stroke="var(--accent)" stroke-width="2.5"/>';
  var ln=svg.querySelector('.zcv-ln');ln.style.setProperty('--L',ln.getTotalLength());
  plot.querySelectorAll('.zcv-ann').forEach(function(a){a.remove()});
  var ann=[[hi,'max','ең көп']];if(hi!==n-1)ann.push([n-1,'',C.lastLabel||'соңғы']);
  ann.forEach(function(t){var a=document.createElement('div');a.className='zcv-ann '+t[1];a.style.left=Math.min(Math.max(P[t[0]][0],46),W-46)+'px';a.style.top=P[t[0]][1]+'px';
   a.innerHTML=nf(s.cur[t[0]])+(s.unit||'')+'<i>'+t[2]+'</i>';plot.appendChild(a)});
  cv.querySelector('.zcv-big').innerHTML=nf(s.total)+'<span class="zc-unit">'+(s.unitBig||'')+'</span>';
  var dl=cv.querySelector('.zc-dl');if(s.delta==null){dl.textContent=''}else{dl.className='zc-dl '+(s.delta>=0?'up':'dn');dl.textContent=(s.delta>=0?'▲ ':'▼ ')+Math.abs(s.delta)+'%'}
  cv.querySelector('.zcv-lbl').textContent=s.label;
  var L=C.labels;cv.querySelector('.zcv-x').innerHTML='<span>'+L[0]+'</span><span>'+L[Math.floor((n-1)/2)]+'</span><span>'+L[n-1]+'</span>'}
 function hover(e){var r=plot.getBoundingClientRect(),s=C.s[key],n=s.cur.length,px=Math.min(34,r.width*.04),cx=(e.touches?e.touches[0].clientX:e.clientX)-r.left,
  i=Math.max(0,Math.min(n-1,Math.round((cx-px)/(r.width-2*px)*(n-1)))),p=P[i];if(!p)return;cv.classList.add('on');
  cross.style.left=p[0]+'px';knob.style.left=p[0]+'px';knob.style.top=p[1]+'px';tip.style.left=Math.min(Math.max(p[0],92),r.width-92)+'px';tip.style.top=Math.max(-10,p[1]-118)+'px';
  var pv=s.prev&&s.prev[i],dd=(pv!=null&&pv)?Math.round((s.cur[i]-pv)/pv*100):null;
  tip.innerHTML='<div class="d">'+C.labels[i]+'</div><div class="v">'+nf(s.cur[i])+(s.unit||'')+'</div>'+(pv!=null?'<div class="r"><span>'+(C.prevLabel||'алдыңғы кезең')+'</span><b>'+nf(pv)+(dd!=null?' <span style="color:'+(dd>=0?'var(--green)':'var(--red)')+'">'+(dd>=0?'▲':'▼')+Math.abs(dd)+'%</span>':'')+'</b></div>':'')}
 plot.addEventListener('mousemove',hover);plot.addEventListener('touchstart',hover,{passive:true});plot.addEventListener('touchmove',hover,{passive:true});
 /* apple-design «Direct manipulation»: on a phone the value follows the finger and goes away when the finger lifts */
 plot.addEventListener('mouseleave',function(){cv.classList.remove('on')});
 ['touchend','touchcancel'].forEach(function(t){plot.addEventListener(t,function(){cv.classList.remove('on')},{passive:true})});
 cv.querySelectorAll('.zcv-tabs button').forEach(function(b,i){b.onclick=function(){cv.querySelectorAll('.zcv-tabs button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');key=i;draw()}});
 var mob=cv.querySelector('.zcv-mob');if(mob)mob.innerHTML=C.s.slice(1).map(function(s){var v=s.cur.slice(-14),w=92,h=40,mx=Math.max.apply(0,v),mn=Math.min.apply(0,v),
  p=v.map(function(a,i){return[i/Math.max(1,v.length-1)*(w-6)+3,h-5-(a-mn)/((mx-mn)||1)*(h-10)]});
  return '<div class="zct"><div><div class="zc-lbl">'+s.label+'</div><div class="zc-num">'+nf(s.total)+'<span class="zc-unit">'+(s.unitBig||'')+'</span></div>'
  +(s.delta==null?'':'<span class="zc-dl '+(s.delta>=0?'up':'dn')+'">'+(s.delta>=0?'▲ ':'▼ ')+Math.abs(s.delta)+'%</span>')+'</div>'
  +'<svg viewBox="0 0 92 40"><path d="'+smooth(p)+'" fill="none" stroke="#7336F7" stroke-width="2.2" stroke-linecap="round"/><circle cx="'+p[p.length-1][0]+'" cy="'+p[p.length-1][1]+'" r="3" fill="#7336F7"/></svg></div>'}).join('');
 draw();var rt;addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(draw,150)});document.addEventListener('themechange',draw)});
var tp=document.getElementById('zbtip');document.querySelectorAll('[data-tip]').forEach(function(el){if(el.dataset.zt)return;el.dataset.zt=1;
 el.addEventListener('mouseenter',function(){tp.innerHTML=el.dataset.tip;tp.classList.add('on')});
 el.addEventListener('mousemove',function(e){tp.style.left=e.clientX+'px';tp.style.top=e.clientY+'px'});el.addEventListener('mouseleave',function(){tp.classList.remove('on')})});
/* touch (apple-design «Response»): show the value on finger-down, above the finger, highlight the touched mark; hide on the next tap or after a moment */
var ztm,zcur;function zhide(){tp.classList.remove('on');if(zcur)zcur.classList.remove('zt-on');zcur=null}
document.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse')return;var el=e.target.closest&&e.target.closest('[data-tip]');
 if(!el||!el.dataset.tip){zhide();return}clearTimeout(ztm);if(zcur)zcur.classList.remove('zt-on');zcur=el;el.classList.add('zt-on');
 var r=el.getBoundingClientRect();tp.innerHTML=el.dataset.tip;tp.style.left=Math.min(Math.max(r.left+r.width/2,90),innerWidth-90)+'px';
 tp.style.top=Math.max(r.top-6,60)+'px';tp.classList.add('on');ztm=setTimeout(zhide,2400)},{passive:true});
addEventListener('scroll',zhide,{passive:true});
document.querySelectorAll('.zb').forEach(function(b){var pg=b.nextElementSibling;if(!pg||!pg.classList.contains('zb-pager')||b.dataset.zp)return;b.dataset.zp=1;
 for(var j=0;j<b.children.length;j++)pg.appendChild(document.createElement('i'));
 function f(){var w=(b.children[0]||{}).offsetWidth+12||1,k=Math.round(b.scrollLeft/w);[].forEach.call(pg.children,function(x,i){x.classList.toggle('on',i===k)})}
 b.addEventListener('scroll',f,{passive:true});f()});
})();</script>"""


def delta(cur, prev):
    return None if not prev or cur is None else round((cur - prev) / prev * 100)


def canvas(title: str, series: list, labels: list, prev_label="алдыңғы кезең", last_label="бүгін") -> str:
    """series: [{label, cur:[...], prev:[...]|None, total, delta, unit (per point, e.g. ' ₸'), unitBig}] — tabs in that order."""
    data = {"s": series, "labels": labels, "prevLabel": prev_label, "lastLabel": last_label}
    first = series[0]
    tabs = "".join(f'<button type="button"{" class=on" if i == 0 else ""}>{E(s["tab"])}</button>' for i, s in enumerate(series)) if len(series) > 1 else ""
    d = first.get("delta")
    return (f'<section class="zcv cardin" aria-label="{E(title)}"><script type="application/json">{json.dumps(data, ensure_ascii=False)}</script>'
            f'<div class="zcv-top"><div><div class="zc-lbl zcv-lbl">{E(first["label"])}</div>'
            f'<div class="zc-num zcv-big">{nf(first["total"])}<span class="zc-unit">{E(first.get("unitBig") or "")}</span></div>'
            f'<div class="zcv-meta"><span class="zc-dl {"up" if (d or 0) >= 0 else "dn"}">{"" if d is None else ("▲ " if d >= 0 else "▼ ") + str(abs(d)) + "%"}</span>'
            f'{f"<span class=zc-cap>{E(prev_label)} салыстырғанда</span>" if prev_label else ""}</div></div>'
            f'{f"<div class=zcv-tabs role=tablist>{tabs}</div>" if tabs else ""}</div>'
            f'<div class="zcv-plot"><svg aria-hidden="true"></svg><div class="zcv-cross"></div><div class="zcv-knob"></div><div class="zc-tip"></div></div>'
            f'<div class="zcv-x"></div><div class="zcv-mob"></div></section>')


def card(size: str, label: str, num_html: str, viz: str, sub: str = "", dark=False, i=0) -> str:
    return (f'<article class="zbc {size}{" dark" if dark else ""} cardin" style="--i:{i}"><div class="zc-lbl">{E(label)}</div>'
            f'<div class="zc-num">{num_html}</div>{f"<div class=zc-cap>{sub}</div>" if sub else ""}{viz}</article>')


def num(value, unit="") -> str:
    return f'{nf(value)}<span class="zc-unit">{E(unit)}</span>' if unit else nf(value)


def cols(days: list) -> str:
    """Monolith columns: capsule = the day's plan, fill = what was done. days: [{label, value, plan, now, future, tip}]"""
    top = max([d.get("plan") or 0 for d in days] + [d.get("value") or 0 for d in days]) or 1
    out = []
    for k, d in enumerate(days):
        plan, v = d.get("plan") or top, d.get("value") or 0
        cls = "fut" if d.get("future") else "now" if d.get("now") else "ok" if plan and v >= plan else ""
        out.append(f'<i class="{cls}" style="--h:{plan / top * 100:.1f}%;--s:{min(v / plan, 1.0) * 100 if plan else 0:.1f}%;--k:{k}" data-tip="{E(d.get("tip", ""))}"><b></b></i>')
    return f'<div class="zb-cols">{"".join(out)}</div>'


def dots(days: list, per_row: int = 16) -> str:
    """Dot calendar. days: [{level 0-4, now, future, tip}]"""
    cells = "".join(f'<i data-l="{d.get("level", 0)}" class="{"fut" if d.get("future") else "now" if d.get("now") else ""}" data-tip="{E(d.get("tip", ""))}"></i>'
                    for d in days)
    return f'<div class="zb-dots" style="--n:{per_row}">{cells}</div>'


def week(days: list) -> str:
    top = max([d.get("value") or 0 for d in days]) or 1
    return '<div class="zb-wk">' + "".join(
        f'<div class="{"fut" if d.get("future") else "now" if d.get("now") else ""}" data-tip="{E(d.get("tip", ""))}"><i style="--h:{(d.get("value") or 0) / top * 100:.0f}%"></i><span>{E(d["label"])}</span></div>'
        for d in days) + "</div>"


def split(a: int, b: int, la: str, lb: str) -> str:
    t = (a + b) or 1
    return (f'<div class="zb-split"><i class="a" style="width:{a / t * 100:.1f}%" data-tip="{E(la)}: {nf(a)}"></i><i class="o" style="width:{b / t * 100:.1f}%" data-tip="{E(lb)}: {nf(b)}"></i></div>'
            f'<div class="zb-leg"><span><em style="background:var(--accent)"></em>{E(la)} {nf(a)}</span><span><em style="background:color-mix(in srgb,var(--accent) 18%,var(--surface))"></em>{E(lb)} {nf(b)}</span></div>')


def ring(pct, big: str, sub: str) -> str:
    r = 34
    c = 2 * math.pi * r
    p = max(0, min(100, pct or 0))
    return (f'<div class="zb-ring"><svg viewBox="0 0 88 88"><circle cx="44" cy="44" r="{r}" fill="none" stroke="var(--surface2)" stroke-width="10"/>'
            f'<circle class="ra" cx="44" cy="44" r="{r}" fill="none" stroke="{"var(--green)" if p >= 100 else "var(--accent)"}" stroke-width="10" stroke-linecap="round" '
            f'transform="rotate(-90 44 44)" style="--c:{c:.1f};--o:{c * (1 - p / 100):.1f}"/></svg>'
            f'<div><div class="zc-num" style="font-size:2.25rem">{big}</div><div class="zc-cap">{sub}</div></div></div>')


def bento(cards: list) -> str:
    return f'<section class="zb">{"".join(cards)}</section><div class="zb-pager"></div>'


def funnel(steps: list, soft: bool = False) -> str:
    """Steps [(label, value)]: a capsule per step (width = share of the first step) and the step-to-step conversion between them.
    soft: square-root widths, for funnels whose first step is hundreds of times bigger than the last (views → sales)."""
    top = max([v for _, v in steps] + [1])
    scale = (lambda v: math.sqrt(v / top) * 100) if soft else (lambda v: v / top * 100)
    out = []
    for i, (label, v) in enumerate(steps):
        if i:
            pv = steps[i - 1][1]
            out.append(f'<span class="zf-c">↓ {round(v / pv * 100) if pv else 0}%</span>')
        out.append(f'<div class="zf-r"><div class="zf-h"><span>{E(label)}</span><b>{nf(v)}</b></div>'
                   f'<div class="zf-b"><i style="--w:{max(2, scale(v)):.1f}%"></i></div></div>')
    return f'<div class="zf">{"".join(out)}</div>'
