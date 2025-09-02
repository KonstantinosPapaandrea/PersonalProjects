/* ============================================================
   WATER-DROP CONTROLLER – slides from .target-pic to .target-pic
   ============================================================ */
import { SLIDE_MS, pageCentre } from './utils.js';

/* ---------- DOM refs ---------- */
const drop   = document.getElementById('global-drop');
const panels = document.querySelectorAll('[data-drop]');

/* ---------- make one sentinel per section ---------- */
panels.forEach(panel=>{
  const s = Object.assign(document.createElement('div'),
                          { className:'io-sentinel' });
  Object.assign(s.style,{
    position:'absolute', top:'50%', left:0, right:0,
    height:'1px', pointerEvents:'none'
  });
  panel.style.position = 'relative';
  panel.appendChild(s);
});

/* ---------- CSS transition (left, top, scale) ---------- */
drop.style.transition =
  `left ${SLIDE_MS}ms cubic-bezier(.6,.2,.3,1),
   top  ${SLIDE_MS}ms cubic-bezier(.6,.2,.3,1),
   transform ${SLIDE_MS}ms cubic-bezier(.6,.2,.3,1)`;

/* ---------- scale presets ---------- */
const SCALE = { center:1.5, left:1, right:1, bottom:2  ,top:1.5};

/* ---------- sizing helpers ---------- */
const NATURAL = { w: drop.offsetWidth, h: drop.offsetHeight };
const halfSizeAt = scale => ({ w:(NATURAL.w*scale)/2, h:(NATURAL.h*scale)/2 });

function moveAndScale(px, py, scale){
  drop.style.transform = `scale(${scale})`;
  const { w, h } = halfSizeAt(scale);
  drop.style.left = px - w + 'px';
  drop.style.top  = py - h + 'px';
}

/* keep absolute under <body> so it can move across sections */
function floatUnderBody(){
  if (drop.parentElement !== document.body){
    const r = drop.getBoundingClientRect();
    drop.style.left = r.left + window.scrollX + 'px';
    drop.style.top  = r.top  + window.scrollY + 'px';
    document.body.appendChild(drop);
  }
}
// helper to re-position the drop under the current panel
function refreshDropPosition() {
  if (!currentPanel) return;
  const pic = currentPanel.querySelector('.target-pic');
  if (!pic) return;

  // read the current scale
  const m = drop.style.transform.match(/scale\(([^)]+)\)/);
  const scale = m ? parseFloat(m[1]) : 1;

  // find the live centre
  const { x, y } = pageCentre(pic);
  moveAndScale(x, y, scale);
}


/* ---------- main IO logic ---------- */
let currentPanel = null;

const io = new IntersectionObserver(entries=>{
  entries.forEach(e=>{
    if(!e.isIntersecting) return;

    const panel = e.target.parentElement;
    if(panel === currentPanel) return;
    currentPanel = panel;

    const pic = panel.querySelector('.target-pic');
    if(!pic){ console.warn('No .target-pic in', panel); return; }

    floatUnderBody();

    const targetScale = SCALE[panel.dataset.drop] ?? 1;
    const { x,y }     = pageCentre(pic);

    moveAndScale(x, y, targetScale);
  });
},{threshold:0.5});

document.querySelectorAll('.io-sentinel').forEach(s => io.observe(s));

/* ---------- first placement ---------- */
(() => {
  /* 👉  re-measure now – the SVG is fully parsed at this point */
  NATURAL.w = drop.offsetWidth;
  NATURAL.h = drop.offsetHeight;

  const first = panels[0];
  const pic   = first.querySelector('.target-pic');
  if (!pic) return;

  const { x, y } = pageCentre(pic);
  moveAndScale(x, y, SCALE[first.dataset.drop] ?? 1);
})();

/* ---------- keep centre correct on resize ---------- */
let rAF;

// on resize you already have:
window.addEventListener('resize', () => {
  cancelAnimationFrame(rAF);
  rAF = requestAnimationFrame(refreshDropPosition);
});

// **add this** on scroll (and on any other event that can move things)
window.addEventListener('scroll', () => {
  cancelAnimationFrame(rAF);
  rAF = requestAnimationFrame(refreshDropPosition);
});