// js/hamburger.js
(function () {
  const header = document.querySelector('.site-header');
  const btn    = document.querySelector('.nav-toggle');
  const nav    = document.getElementById('primary-nav'); // matches HTML above

  if (!header || !btn || !nav) return;

  function setOpen(isOpen) {
    header.classList.toggle('is-open', isOpen);
    btn.setAttribute('aria-expanded', String(isOpen));
    nav.dataset.open = isOpen ? 'true' : 'false'; // drives CSS [data-open="true"]
    // optional scroll lock
    document.documentElement.classList.toggle('nav-open', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  }

  btn.addEventListener('click', () => {
    const isOpen = nav.dataset.open !== 'true';
    setOpen(isOpen);
  });

  // Close when a link is clicked
  nav.addEventListener('click', (e) => {
    if (e.target.closest('a')) setOpen(false);
  });

  // Close on Escape
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setOpen(false);
  });

  // Close if we resize to desktop
  const mql = window.matchMedia('(min-width: 768px)');
  mql.addEventListener('change', () => mql.matches && setOpen(false));
})();
