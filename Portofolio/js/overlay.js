document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('intro-overlay');
  const playBtn = document.getElementById('intro-play-btn');

  // block scroll until play
  document.body.style.overflow = 'hidden';

  function initReveal() {
    const els = document.querySelectorAll('[data-reveal]');
    const io  = new IntersectionObserver((entries, obs) => {
      /* …your existing reveal logic… */
    }, { threshold:0.1, rootMargin:'0px 0px 30% 0px' });
    els.forEach(el => io.observe(el));
    /* …optional reobserve code… */
  }

  playBtn.addEventListener('click', () => {
    document.body.style.overflow = '';  // enable scroll immediately
    initReveal();                      // start reveals immediately
    overlay.style.transition = 'opacity 0.4s ease';
    overlay.style.opacity    = '0';
    overlay.addEventListener('transitionend', () => overlay.remove(), { once: true });
  });
});
