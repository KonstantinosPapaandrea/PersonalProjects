/* ──────────────────────────────────────────────────────────
   Minimal 30-line type-writer that loops through roles
   (no external libs – keeps bundle tiny)
────────────────────────────────────────────────────────── */
(() => {
  const roles = [
    'Developer',
    'Game Designer',
    'Tech Tinkerer'
  ];

  const span   = document.getElementById('roleTyper');
  const speed  = 80;     // ms / character
  const pause  = 1600;   // pause after a word
  let roleIdx  = 0, charIdx = 0, deleting = false;

  const tick = () => {
    const current = roles[roleIdx];
    if (!deleting) {
      // typing
      span.textContent = current.slice(0, ++charIdx);
      if (charIdx === current.length) {
        deleting = true;
        setTimeout(tick, pause);
        return;
      }
    } else {
      // deleting
      span.textContent = current.slice(0, --charIdx);
      if (charIdx === 0) {
        deleting = false;
        roleIdx  = (roleIdx + 1) % roles.length;
      }
    }
    setTimeout(tick, deleting ? speed/2 : speed);
  };

  tick();   // fire on load
})();
