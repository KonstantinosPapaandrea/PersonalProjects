// 1) Scroll‐progress bar
window.addEventListener("scroll", () => {
  const scrollPercent =
    (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
  document.querySelector('.progress-bar-filled').style.width = scrollPercent + '%';
});

document.addEventListener('DOMContentLoaded', () => {
  // 2) Grab all your “Next” buttons and the corresponding sections
  const nextBtns    = document.querySelectorAll('.next-btn');
  const sections    = document.querySelectorAll('.section');
  const navLinks    = document.querySelectorAll('.main-nav a');
  let passedSections = []; // Which sections have actually been clicked

  // 3) "Level Up!" pop‐up
  function showLevelUp() {
    const msg = document.createElement('div');
    msg.className = 'level-up';
    msg.textContent = 'Level Up!';
    document.body.appendChild(msg);
    setTimeout(() => msg.remove(), 1500);
  }

  // 4) Enable a “Next” button by index
  function enableNextLink(idx) {
    if (idx < nextBtns.length) {
      nextBtns[idx].disabled        = false;
      nextBtns[idx].style.pointerEvents = 'auto';
      nextBtns[idx].style.opacity       = '1';
    }
  }

  function enableNavLinkById(id) {
    const link = document.querySelector(`.main-nav a[href="#${id}"]`);
    if (!link) return;
    link.classList.remove('nav-link--disabled');
    link.removeAttribute('aria-disabled');
  }
  

  // 6) Wire up each Next button
  nextBtns.forEach((btn, index) => {
    btn.addEventListener('click', () => {
      const sec = sections[index];
      const id  = sec.id;

      // If already clicked, do nothing
      if (passedSections.includes(sec)) {
        console.log(`Section "${id}" already leveled up.`);
        return;
      }

      // Mark this section as passed
      passedSections.push(sec);
      console.log('Passed:', passedSections.map(s => s.id));

      // Show the animation
      showLevelUp();

      // Enable the header link for *this* section
      enableNavLinkById(id);

      // Also enable the *next* section’s Next‐button
      enableNextLink(index + 1);
    });
  });
});
