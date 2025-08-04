/**
 * Animates numeric properties over time.
 * Returns a controller object you can keep if you want to cancel early.
 *
 * @param {object} target         Object to mutate.
 * @param {object} from           Starting values (e.g., { width: 10, height: 10 }).
 * @param {object} to             Ending values (same keys as from).
 * @param {number} duration       Duration in milliseconds.
 * @param {function} [easing]     Easing function t→[0,1], default linear.
 * @param {function} [onUpdate]   Optional callback each frame with progress 0..1.
 * @param {function} [onComplete] Called when animation finishes.
 * @returns {{cancel: function}}  Controller with cancel().
 */
export function Scale(target, from, to, duration, easing = t => t, onUpdate, onComplete) {
  const start = performance.now();
  let cancelled = false;

  // Initialize
  for (const key in from) {
    target[key] = from[key];
  }

  function step(now) {
    if (cancelled) return;
    const elapsed = now - start;
    let t = Math.min(1, elapsed / duration);
    const eased = easing(t);

    for (const key in from) {
      target[key] = from[key] + (to[key] - from[key]) * eased;
    }

    if (onUpdate) onUpdate(eased);

    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      if (onComplete) onComplete();
    }
  }

  requestAnimationFrame(step);

  return {
    cancel() {
      cancelled = true;
    }
  };

}

/**
 * Animate size from current width/height to target while keeping center fixed.
 * @param {object} obj - GameObject with x,y,width,height
 * @param {number} toW
 * @param {number} toH
 * @param {number} duration - ms
 * @param {function} easing
 * @param {function} onComplete
 * @returns {{cancel: function}}
 */
export function ScaleFromCenter(obj, toW, toH, duration, easing = t => t, onComplete) {
  const fromW = obj.width;
  const fromH = obj.height;

  // compute initial center
  const centerX = obj.x + fromW / 2;
  const centerY = obj.y + fromH / 2;

  return Scale(
    obj,
    { width: fromW, height: fromH },
    { width: toW, height: toH },
    duration,
    easing,
    (progress) => {
      // adjust position so center stays
      obj.x = centerX - obj.width / 2;
      obj.y = centerY - obj.height / 2;
    },
    () => {
      if (onComplete) onComplete();
    }
  );
}

export const easeOutQuad = t => 1 - (1 - t) * (1 - t);
export const easeInOutCubic = t =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
