/* ============================================================
   SIMPLE SCROLL-REVEAL (fade / slide-up once)
   ============================================================ */
const els = document.querySelectorAll('[data-reveal]');

const io = new IntersectionObserver((entries, obs)=>{
  entries.forEach(entry=>{
    if(!entry.isIntersecting) return;
    entry.target.classList.add('is-visible');
    obs.unobserve(entry.target);      // comment out to replay each time
  });
},{
  threshold : 0,
  rootMargin: '0px 0px -30% 0px'
});

els.forEach(el => io.observe(el));

/* optional sanity re-observe after all assets in cache load */
window.addEventListener('load', ()=> {
  requestAnimationFrame(()=>els.forEach(el=>{
    io.unobserve(el); io.observe(el);
  }));
});
