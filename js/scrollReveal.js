document.addEventListener('DOMContentLoaded', () => {
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
      rootMargin: '0px 0px 50% 0px'
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

  initReveal();
});
