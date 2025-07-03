document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('intro-overlay');
    const playBtn = document.getElementById('intro-play-btn');
  
    // block scrolling until play:
    document.body.style.overflow = 'hidden';
  
    playBtn.addEventListener('click', () => {
      // fade‐out overlay
      overlay.style.transition = 'opacity 0.4s ease';
      overlay.style.opacity    = '0';
      overlay.addEventListener('transitionend', () => {
        overlay.remove();
        // re‐enable scroll
        document.body.style.overflow = '';
        // now that the user has “played,” kick off all reveals:
        initReveal();
      }, { once: true });
    });
  });
  