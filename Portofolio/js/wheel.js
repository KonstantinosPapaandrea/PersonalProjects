/* ============================================================
   3-D WHEEL CAROUSEL  – v2  (front card gets higher z-index)
   ============================================================ */
const wheel   = document.getElementById('projectWheel');
const cards   = [...wheel.querySelectorAll('.wheel__card')];
const btnPrev = wheel.parentElement.querySelector('.wheel-btn--prev');
const btnNext = wheel.parentElement.querySelector('.wheel-btn--next');

const count   = cards.length;
const cardDeg = 360 / count;
let   current = 0;

wheel.style.setProperty('--card-count', count);

/* place cards once */
cards.forEach((card, i)=>{
  card.style.setProperty('--rot', `rotateY(${i*cardDeg}deg)`);
});

/* ── helper ─────────────────────────────────────────────── */
function updateClasses(){
  cards.forEach((c,i)=>{
    const rel = ((i - current) % count + count) % count;   // 0 … n-1
    /* front-/side/back styling */
    c.style.setProperty('--visible',      rel<=1||rel>=count-1 ? 1 : .15);
    c.style.setProperty('--frontScale',   rel===0 ? 1 : .8);

    /* NEW → toggle z-index flag */
    if (rel === 0) {
      c.dataset.front = 'true';           // adds  data-front="true"
    } else {
      delete c.dataset.front;             // attribute removed → z-index back
    }
  });
}

/* ── rotate wheel ───────────────────────────────────────── */
function spin(dir){
  current = (current + dir + count) % count;
  updateClasses();
}

btnPrev.addEventListener('click', ()=>spin(-1));
btnNext.addEventListener('click', ()=>spin( 1));
updateClasses();

/* optional swipe */
let startX=null;
wheel.addEventListener('pointerdown', e=>startX=e.clientX);
wheel.addEventListener('pointerup',   e=>{
  if(startX===null) return;
  const dx = e.clientX - startX;
  if(Math.abs(dx) > 30) spin(dx>0?-1:1);
  startX=null;
});
