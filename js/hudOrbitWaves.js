const canvas = document.querySelector('.hero-orbit-canvas');
const hero = document.querySelector('.hero');
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (!canvas || !hero || reduceMotion) {
  if (canvas && reduceMotion) canvas.style.opacity = '0.45';
} else {
  const ctx = canvas.getContext('2d');
  const rings = 20;
  let raf = 0;
  let t = 0;

  const resize = () => {
    const rect = hero.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const pointAt = (cx, cy, rx, ry, ampX, ampY, freq, phase, a) => {
      const radialSine = Math.sin(freq * a + t + phase);
      const verticalSine = Math.sin(freq * 0.9 * a + t * 1.8 + phase * 0.55);
      const bob = Math.sin(t * 1.25 + phase) * ampY * 0.55;
      const mx = ampX * radialSine;
      const x = cx + (rx + mx) * Math.cos(a);
      const y = cy + ry * Math.sin(a) + verticalSine * ampY + bob;
      return { x, y };
  };

  const drawRing = (cx, cy, rx, ry, ampX, ampY, freq, phase, width, color, baseAlpha) => {
    const steps = 260;
    for (let i = 0; i < steps; i += 1) {
      const a1 = (i / steps) * Math.PI * 2;
      const a2 = ((i + 1) / steps) * Math.PI * 2;
      const p1 = pointAt(cx, cy, rx, ry, ampX, ampY, freq, phase, a1);
      const p2 = pointAt(cx, cy, rx, ry, ampX, ampY, freq, phase, a2);

      // Top/back of the orbit fades out, bottom/front stays stronger.
      const mid = (a1 + a2) * 0.5;
      const depth = (Math.sin(mid) + 1) * 0.5;
      const depthAlpha = baseAlpha * Math.pow(depth, 1.35);
      const depthWidth = width * (0.82 + depth * 0.28);

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineWidth = depthWidth;
      ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${depthAlpha.toFixed(4)})`;
      ctx.stroke();
    }
  };

  const draw = () => {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const cx = w / 2;
    const cy = h / 2;

    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.globalCompositeOperation = 'screen';

    for (let i = 0; i < rings; i += 1) {
      const depth = i / (rings - 1);
      const rx = w * (0.44 + depth * 0.19);
      const ry = h * (0.33 + depth * 0.18);
      const ampX = 2 + depth * 5.5;
      const ampY = 7 + depth * 15;
      const freq = 5.2 + depth * 4.8;
      const phase = i * 0.45;
      const alpha = 0.2 + depth * 0.3;
      const width = 0.7 + depth * 1.15;
      const color = i % 3 === 0
        ? { r: 0, g: 232, b: 255 }
        : i % 3 === 1
          ? { r: 74, g: 173, b: 255 }
          : { r: 37, g: 119, b: 255 };
      drawRing(cx, cy, rx, ry, ampX, ampY, freq, phase, width, color, alpha);
    }

    ctx.restore();
    t += 0.018;
    raf = requestAnimationFrame(draw);
  };

  resize();
  draw();

  const ro = new ResizeObserver(() => resize());
  ro.observe(hero);
  window.addEventListener('resize', resize);
  window.addEventListener('beforeunload', () => {
    cancelAnimationFrame(raf);
    ro.disconnect();
  });
}
