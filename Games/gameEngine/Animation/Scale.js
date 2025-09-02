// File: gameEngine/util/Scale.js

// Import pause state so animations stop while the game is paused
import { GameStateManager } from "../util/GameStateManager.js";

/**
 * Scale
 * -----------------------------------------------------------------------------
 * Animates numeric properties on `target` from `from` to `to` over `duration`.
 * - Uses an internal clock that **pauses** when GameStateManager.isPaused() is true.
 * - Returns a controller with cancel().
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
  // Initialize current values from `from` snapshot
  for (const key in from) {
    target[key] = from[key];
  }

  let cancelled = false;                  // external cancel flag
  let elapsed   = 0;                      // ms accumulated while NOT paused
  let lastTime  = performance.now();      // last tick time to compute deltas

  function step(now) {
    if (cancelled) return;                // stop immediately if cancelled

    // Pause-aware time accumulation: skip advancing while paused
    if (!GameStateManager.isPaused()) {
      elapsed += (now - lastTime);        // accumulate ONLY when running
    }
    lastTime = now;                        // always update lastTime

    // Compute normalized progress in [0,1]
    const t = Math.min(1, elapsed / duration);
    const eased = easing(t);

    // Interpolate each numeric property
    for (const key in from) {
      target[key] = from[key] + (to[key] - from[key]) * eased;
    }

    // Notify caller of progress
    if (onUpdate) onUpdate(eased);

    // Continue or finish
    if (t < 1) {
      requestAnimationFrame(step);        // schedule next frame
    } else {
      if (onComplete) onComplete();       // fire completion callback
    }
  }

  // Kick off the animation
  requestAnimationFrame(step);

  // Return a simple controller to let callers cancel mid-flight
  return {
    cancel() { cancelled = true; }
  };
}

/**
 * ScaleFromCenter
 * -----------------------------------------------------------------------------
 * Animate width/height from current to target while keeping object's center fixed.
 * - Works nicely with UI or world sprites when you want a "pulse" effect.
 *
 * @param {object} obj - GameObject-like {x,y,width,height}
 * @param {number} toW - target width in same units as obj.width
 * @param {number} toH - target height in same units as obj.height
 * @param {number} duration - ms
 * @param {function} easing - easing(t) → [0..1] (default linear)
 * @param {function} onComplete - callback when finished
 * @returns {{cancel: function}}
 */
export function ScaleFromCenter(obj, toW, toH, duration, easing = t => t, onComplete) {
  const fromW = obj.width;                 // capture start width
  const fromH = obj.height;                // capture start height

  // Compute initial center in the same space as draw calls
  const centerX = obj.x + fromW / 2;
  const centerY = obj.y + fromH / 2;

  // Delegate to Scale, but adjust position each frame to lock the center
  return Scale(
    obj,
    { width: fromW, height: fromH },       // from
    { width: toW,  height: toH  },         // to
    duration,
    easing,
    () => {
      // Recompute position so the object's center stays fixed
      obj.x = centerX - obj.width  / 2;
      obj.y = centerY - obj.height / 2;
    },
    onComplete
  );
}

// A couple of handy easings for quick use
export const easeOutQuad   = t => 1 - (1 - t) * (1 - t);
export const easeInOutCubic = t => (t < 0.5)
  ? 4 * t * t * t
  : 1 - Math.pow(-2 * t + 2, 3) / 2;
