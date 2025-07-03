// main.js

document.addEventListener('DOMContentLoaded', () => {
    // 1) Create & preload the explosion audio
    const boom = new Audio('/sounds/8-bit-explosion_F.wav');
    boom.preload = 'auto';
    let boomUnlocked = false;
  
    // 2) On first user interaction, prime the audio
    function unlockBoom() {
      // try playing silently to get permission
      boom.muted = true;
      boom.play()
        .then(() => {
          boom.pause();
          boom.currentTime = 0;
          boom.muted = false;
          boomUnlocked = true;
          console.log('Boom SFX unlocked');
        })
        .catch(console.error)
        .finally(() => {
          window.removeEventListener('click', unlockBoom);
        });
    }
    window.addEventListener('click', unlockBoom, { once: true });
  
    function playBoom() {
      if (!boomUnlocked) return;
      boom.currentTime = 0;
      boom.play().catch(console.error);
    }
  
    // 3) Particle explosion helper
    function explodeWord(wordEl) {
      const w   = wordEl.offsetWidth;
      const h   = wordEl.offsetHeight;
      const dir = wordEl.getAttribute('data-reveal-from');
      const isVert = dir === 'top' || dir === 'bottom';
  
      const count = 12;
      for (let i = 0; i < count; i++) {
        const p = document.createElement('span');
        p.className = 'particle';
  
        // spread start along perpendicular axis
        let baseX, baseY;
        if (isVert) {
          baseX = Math.random() * w;
          baseY = dir === 'bottom' ? 0 : h;
        } else {
          baseX = dir === 'left' ? w : 0;
          baseY = Math.random() * h;
        }
        p.style.left = `${baseX}px`;
        p.style.top  = `${baseY}px`;
  
        // explosion vector opposite entry
        const dist = 20 + Math.random() * 20;
        let dx = 0, dy = 0;
        switch (dir) {
          case 'left':   dx = +dist; break;
          case 'right':  dx = -dist; break;
          case 'top':    dy = +dist; break;
          case 'bottom': dy = -dist; break;
        }
  
        // random color & timing
        const hue = Math.floor(Math.random() * 360);
        const dur = 0.4 + Math.random() * 0.4;
        const del = -Math.random() * dur;
  
        p.style.setProperty('--dx',       `${dx}px`);
        p.style.setProperty('--dy',       `${dy}px`);
        p.style.setProperty('--color',    `hsl(${hue},100%,65%)`);
        p.style.setProperty('--duration', `${dur}s`);
        p.style.setProperty('--delay',    `${del}s`);
  
        wordEl.appendChild(p);
        p.addEventListener('animationend', () => p.remove(), { once: true });
      }
    }
  
    // 4) Hook each word’s reveal end to trigger sound + particles
    const words = document.querySelectorAll('.welcome h1 > span');
    words.forEach((word, idx) => {
      const onEnd = e => {
        if (e.target !== word) return;
        if (e.animationName && !e.animationName.startsWith('slide-in')) return;
        if (e.type === 'transitionend' && e.propertyName !== 'transform') return;
  
        console.log(
          `Word ${idx+1} (“${word.textContent.trim()}”) animationend:`,
          e.animationName || '(transition)'
        );
        playBoom();
        explodeWord(word);
      };
  
      word.addEventListener('animationend',  onEnd, { once: true });
      word.addEventListener('transitionend', onEnd, { once: true });
    });
  });
  