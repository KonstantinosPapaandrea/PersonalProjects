// main.js

document.addEventListener('DOMContentLoaded', () => {
  // 1) Overlay “Play” logic
  const overlay = document.getElementById('intro-overlay');
  const playBtn = document.getElementById('intro-play-btn');

  // prevent scrolling until play
  document.body.style.overflow = 'hidden';

  playBtn.addEventListener('click', () => {
    // fade out & remove overlay
    overlay.style.transition = 'opacity 0.4s ease';
    overlay.style.opacity    = '0';
    overlay.addEventListener('transitionend', () => {
      overlay.remove();
      document.body.style.overflow = '';
      // only now initialize scroll‐reveal
      initReveal();
    }, { once: true });
  });

  // 2) Scroll-reveal setup, invoked only after Play
  function initReveal() {
    const els = document.querySelectorAll('[data-reveal]');

    const io = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px 30% 0px'
    });

    els.forEach(el => io.observe(el));

    // optional: re-observe after load to catch cached assets
    window.addEventListener('load', () => {
      requestAnimationFrame(() => {
        els.forEach(el => {
          io.unobserve(el);
          io.observe(el);
        });
      });
    });
  }
});
