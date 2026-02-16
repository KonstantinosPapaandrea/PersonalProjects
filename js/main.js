/* ============================================================
   MAIN ENTRY — imports side-effect modules only
   ============================================================ */
import './utils.js';        // (if you want globals here)
import './waterDrop.js';
import './scrollReveal.js';
import './wheel.js'; 
import './skills.js';
//import './typewriter.js';
import './explode.js';
import './hudOrbitWaves.js';

const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('.main-nav');
const siteHeader = document.querySelector('.site-header');
const heroSection = document.getElementById('hero');

if (siteHeader) {
  siteHeader.classList.add('is-visible');
}

if (siteHeader && heroSection) {
  const headerObserver = new IntersectionObserver(
    entries => {
      const heroVisible = entries[0]?.isIntersecting;
      siteHeader.classList.toggle('is-visible', Boolean(heroVisible));
    },
    { threshold: 0.18 }
  );

  headerObserver.observe(heroSection);
}

if (navToggle && mainNav) {
  const setNavState = isOpen => {
    navToggle.setAttribute('aria-expanded', String(isOpen));
    mainNav.setAttribute('data-open', String(isOpen));
    document.body.style.overflow = isOpen ? 'hidden' : '';
  };

  navToggle.addEventListener('click', () => {
    const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
    setNavState(!isOpen);
  });

  mainNav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => setNavState(false));
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 767) setNavState(false);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setNavState(false);
  });

  setNavState(false);
}

const heroStartBtn = document.getElementById('hero-start-btn');

if (heroStartBtn) {
  heroStartBtn.addEventListener('click', () => {
    heroStartBtn.classList.add('is-pressed');
    setTimeout(() => heroStartBtn.classList.remove('is-pressed'), 140);
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    if (event.defaultPrevented) return;
    if (event.target instanceof HTMLElement && /INPUT|TEXTAREA|SELECT|BUTTON/.test(event.target.tagName)) return;

    const inHeroView = window.scrollY < window.innerHeight * 0.6;
    if (!inHeroView) return;

    event.preventDefault();
    heroStartBtn.click();
  });
}
/* future: import other features here  */
