/* ============================================================
   Simple 3-card wheel - previous | current | next
   ============================================================ */
(() => {
  const wheel = document.getElementById('projectWheel');
  const cards = wheel ? [...wheel.querySelectorAll('.wheel__card')] : [];
  const btnPrev = document.querySelector('.wheel-btn--prev');
  const btnNext = document.querySelector('.wheel-btn--next');

  if (!wheel || cards.length === 0 || !btnPrev || !btnNext) return;

  /* ----------------------------------------------------------------
     Layout constants - tweak to taste
     -------------------------------------------------------------- */
  const GAP = 20; // vw offset of side cards from center
  const SCALE_IN = 0.7; // side-card scale
  const SCALE_OUT = 0.5; // hidden scale
  const OP_SIDE = 0.35; // opacity of side cards

  /* ----------------------------------------------------------------
     Current index & render
     -------------------------------------------------------------- */
  let current = 0; // center card idx (0..n-1)

  function render() {
    const n = cards.length;

    cards.forEach((card, i) => {
      const diff = (i - current + n) % n;
      card.classList.remove('is-front');

      if (diff === 0) {
        card.style.transform = 'translateX(0) scale(1)';
        card.style.opacity = 1;
        card.style.zIndex = 3;
        card.classList.add('is-front');
      } else if (diff === 1) {
        card.style.transform = `translateX(${GAP}vw) scale(${SCALE_IN})`;
        card.style.opacity = OP_SIDE;
        card.style.zIndex = 2;
      } else if (diff === n - 1) {
        card.style.transform = `translateX(-${GAP}vw) scale(${SCALE_IN})`;
        card.style.opacity = OP_SIDE;
        card.style.zIndex = 2;
      } else {
        const far = diff < n / 2 ? -220 : 220;
        card.style.transform = `translateX(${far}%) scale(${SCALE_OUT})`;
        card.style.opacity = 0;
        card.style.zIndex = 1;
      }
    });
  }

  const goPrev = () => {
    current = (current - 1 + cards.length) % cards.length;
    render();
  };

  const goNext = () => {
    current = (current + 1) % cards.length;
    render();
  };

  btnPrev.addEventListener('click', goPrev);
  btnNext.addEventListener('click', goNext);

  // Mobile safety: trigger instantly on touch and avoid ghost taps.
  btnPrev.addEventListener(
    'touchstart',
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      goPrev();
    },
    { passive: false }
  );

  btnNext.addEventListener(
    'touchstart',
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      goNext();
    },
    { passive: false }
  );

  /* ----------------------------------------------------------------
     Swipe support (pointer + touch) for mobile reliability
     -------------------------------------------------------------- */
  let startX = null;
  let startY = null;
  let touchActive = false;

  wheel.addEventListener('pointerdown', (e) => {
    startX = e.clientX;
  });
  wheel.addEventListener('pointerup', (e) => {
    if (startX == null) return;
    const dx = e.clientX - startX;
    if (dx > 40) goPrev();
    else if (dx < -40) goNext();
    startX = null;
  });

  wheel.addEventListener(
    'touchstart',
    (e) => {
      if (!e.touches || e.touches.length === 0) return;
      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      touchActive = true;
    },
    { passive: true }
  );

  wheel.addEventListener(
    'touchmove',
    (e) => {
      if (!touchActive || startX == null || startY == null || !e.touches || e.touches.length === 0) return;
      const t = e.touches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      // Lock to horizontal gestures; keep vertical page scroll natural.
      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 12) {
        e.preventDefault();
      }
    },
    { passive: false }
  );

  wheel.addEventListener(
    'touchend',
    (e) => {
      if (!touchActive || startX == null) return;
      const t = e.changedTouches && e.changedTouches[0];
      if (!t) return;
      const dx = t.clientX - startX;
      if (dx > 45) goPrev();
      else if (dx < -45) goNext();
      startX = null;
      startY = null;
      touchActive = false;
    },
    { passive: true }
  );

  render();
})();
