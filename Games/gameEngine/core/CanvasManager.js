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
  setSize(engine, cssWidth, cssHeight) {
    const dpr = window.devicePixelRatio || 1;

    // Track CSS size on engine so other systems (Renderer/Viewport) can use it
    engine._cssWidth  = cssWidth;
    engine._cssHeight = cssHeight;

    // Backing store = CSS size × DPR (integers for crispness)
    engine.canvas.width  = Math.floor(cssWidth  * dpr);
    engine.canvas.height = Math.floor(cssHeight * dpr);

    // CSS layout size (logical pixels)
    engine.canvas.style.width  = cssWidth  + "px";
    engine.canvas.style.height = cssHeight + "px";

    // Scale the main ctx so "1 draw unit == 1 CSS pixel"
    try { engine.ctx.resetTransform(); } catch { engine.ctx.setTransform(1,0,0,1,0,0); }
    engine.ctx.scale(dpr, dpr);
    engine.ctx.imageSmoothingEnabled = true;

    // Invalidate static caches (size/DPR changed → must rebuild)
    engine.staticCanvases?.clear?.();
    engine.staticCtxs?.clear?.();
    engine._staticMeta = null; // Renderer will rebuild next draw
  },

  setDisplaySize(engine, cssWidth, cssHeight) {
    engine._cssWidth  = cssWidth;
    engine._cssHeight = cssHeight;
    engine.canvas.style.width  = cssWidth  + "px";
    engine.canvas.style.height = cssHeight + "px";
    // Note: backing store unchanged; DPR scaling stays the same
  },

  handleDisplayResize(engine) {
    const resizeHandler = () => {
      // 1) Compute CSS size from window (customize as needed)
      const cssW = Math.floor(window.innerWidth);
      const cssH = Math.floor(window.innerHeight);

      // 2) Apply sizes + DPR
      this.setSize(engine, cssW, cssH);

      // 3) Recompute viewport mapping using the engine's chosen fit
      //    (IMPORTANT: pass engine.viewport.fit so mapping is consistent)
      Viewport.update(engine, engine.viewport?.fit);

      // 4) Rebuild static layer caches (size/DPR/viewport changed)
      Renderer.buildStaticLayers(engine);
    };

    window.addEventListener("resize", resizeHandler);
    engine._resizeHandler = resizeHandler;
    resizeHandler(); // run once
  },

  removeResizeListener(engine) {
    if (engine._resizeHandler) {
      window.removeEventListener("resize", engine._resizeHandler);
      engine._resizeHandler = null;
    }
  },
};

