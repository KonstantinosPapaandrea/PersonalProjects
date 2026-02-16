/* ============================================================
   Simple 3-card wheel – previous | current | next
   ============================================================ */
   (() => {
    const wheel   = document.getElementById('projectWheel');
    const cards   = [...wheel.querySelectorAll('.wheel__card')];
    const btnPrev = document.querySelector('.wheel-btn--prev');
    const btnNext = document.querySelector('.wheel-btn--next');
  
    /* ----------------------------------------------------------------
       Layout constants – tweak to taste
       -------------------------------------------------------------- */
    const GAP      = 20;   // px offset of side cards from centre
    const SCALE_IN = 0.70; // side-card scale
    const SCALE_OUT= 0.50; // hidden scale
    const OP_SIDE  = 0.35; // opacity of side cards
  
    /* ----------------------------------------------------------------
       Current index & render
       -------------------------------------------------------------- */
    let current = 0;               // centre card idx (0…n-1)
  
    function render () {
      const n = cards.length;
  
      cards.forEach((card, i) => {
        /* distance from current card in the cyclic list: -2…+2 */
        const diff = (i - current + n) % n;
  
        /* reset helper classes */
        card.classList.remove('is-front');
  
        /* centre card (diff 0) -------------------------------- */
        if (diff === 0) {
          card.style.transform = `translateX(0) scale(1)`;
          card.style.opacity   = 1;
          card.style.zIndex    = 3;
          card.classList.add('is-front');
        }
        /* right neighbour (diff 1 or -(n-1)) ------------------- */
        else if (diff === 1 || diff === -(n-1)) {
          card.style.transform = `translateX(${GAP}vw) scale(${SCALE_IN})`;
          card.style.opacity   = OP_SIDE;
          card.style.zIndex    = 2;
        }
        /* left neighbour (diff n-1 or -1) ---------------------- */
        else if (diff === n-1 || diff === -1) {
          card.style.transform = `translateX(-${GAP}vw) scale(${SCALE_IN})`;
          card.style.opacity   = OP_SIDE;
          card.style.zIndex    = 2;
        } 
        /* everything else – hide ------------------------------- */
        else {
          const far = diff < n/2 ? -220 : 220;  // park off-screen
          card.style.transform = `translateX(${far}%) scale(${SCALE_OUT})`;
          card.style.opacity   = 0;
          card.style.zIndex    = 1;
        }
      });
    }
  
    /* ----------------------------------------------------------------
       Button wiring
       -------------------------------------------------------------- */
    btnPrev.addEventListener('click', () => {
      current = (current - 1 + cards.length) % cards.length;
      render();
    });
  
    btnNext.addEventListener('click', () => {
      current = (current + 1) % cards.length;
      render();
    });
  
    /* ----------------------------------------------------------------
       Touch-friendly swipe (optional but nice)
       -------------------------------------------------------------- */
    let startX = null;
    wheel.addEventListener('pointerdown', e => startX = e.clientX);
    wheel.addEventListener('pointerup',   e => {
      if (startX == null) return;
      const dx = e.clientX - startX;
      if      (dx > 40) btnPrev.click();   // swipe → right  = previous
      else if (dx < -40)btnNext.click();   // swipe ← left   = next
      startX = null;
    });
  
    /* first paint */
    render();
  })();
  