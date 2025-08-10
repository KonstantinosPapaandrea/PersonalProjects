// File: gameEngine/core/CanvasManager.js

import { Renderer } from "./Renderer.js";           // to rebuild statics after resize
import { Viewport } from "../util/Viewport.js";     // to recompute world→screen mapping
/**
 * CanvasManager
 * -----------------------------------------------------------------------------
 * Role: Owns canvas sizing for crisp rendering on high‑DPI screens.
 *
 * Public API (use these):
 * - setSize(engine, cssW, cssH)       → Set CSS size and backing store (DPR‑aware).
 * - setDisplaySize(engine, cssW, cssH)→ Change CSS size only (rare).
 * - handleDisplayResize(engine)       → Attach resize listener and run once.
 * - removeResizeListener(engine)      → Detach listener on teardown.
 *
 * Collaborators:
 * - Viewport.update(engine)  → recompute world→screen mapping after size change.
 * - Renderer.buildStaticLayers(engine) → rebuild cached static layers post‑resize.
 *
 * Helpers / Internals:
 * - Tracks engine._cssWidth/_cssHeight and invalidates engine._staticMeta to
 *   force static rebuild on next draw.
 *
 * Invariants:
 * - Main ctx is scaled so “1 draw unit == 1 CSS pixel.”
 * - Backing store = CSS size × devicePixelRatio (rounded).
 */


export const CanvasManager = {
  /**
   * Set backing store and CSS size; scale main context by DPR.
   */
  setSize(engine, cssWidth, cssHeight) {
    // Store CSS size on engine for world/renderer logic
    const dpr = window.devicePixelRatio || 1;
    engine._cssWidth  = cssWidth;
    engine._cssHeight = cssHeight;

    // Backing store in device pixels (round to integers)
    engine.canvas.width  = Math.floor(cssWidth  * dpr);
    engine.canvas.height = Math.floor(cssHeight * dpr);

    // CSS layout size (logical pixels)
    engine.canvas.style.width  = cssWidth  + "px";
    engine.canvas.style.height = cssHeight + "px";

    // Scale the main context so 1 unit == 1 CSS pixel
    try { engine.ctx.resetTransform(); } catch { engine.ctx.setTransform(1,0,0,1,0,0); }
    engine.ctx.scale(dpr, dpr);
    engine.ctx.imageSmoothingEnabled = true;

    // Invalidate static caches (they depend on size/DPR/viewport)
    if (engine.staticCanvases) engine.staticCanvases.clear();
    if (engine.staticCtxs)     engine.staticCtxs.clear();
    engine._staticMeta = null; // force rebuild on next draw
  },

  /**
   * Only change the CSS (on-screen) size; rarely useful.
   */
  setDisplaySize(engine, cssWidth, cssHeight) {
    engine._cssWidth  = cssWidth;
    engine._cssHeight = cssHeight;
    engine.canvas.style.width  = cssWidth  + "px";
    engine.canvas.style.height = cssHeight + "px";
    // Note: no backing/DPR changes here
  },

  /**
   * Attach window resize listener; recompute size, viewport and statics.
   */
  handleDisplayResize(engine) {
    const resizeHandler = () => {
      // Compute new CSS size from the window (you can customize this)
      const cssW = Math.floor(window.innerWidth);
      const cssH = Math.floor(window.innerHeight);

      // 1) Apply new sizes + DPR
      this.setSize(engine, cssW, cssH);

      // 2) Recompute viewport mapping (world→screen)
      Viewport.update(engine);

      // 3) Rebuild static layer caches for new size/DPR/viewport
      Renderer.buildStaticLayers(engine);
    };

    // Attach and run once
    window.addEventListener("resize", resizeHandler);
    engine._resizeHandler = resizeHandler;
    resizeHandler();
  },

  /**
   * Detach the resize listener (call from Engine.destroy()).
   */
  removeResizeListener(engine) {
    if (engine._resizeHandler) {
      window.removeEventListener("resize", engine._resizeHandler);
      engine._resizeHandler = null;
    }
  },
};
