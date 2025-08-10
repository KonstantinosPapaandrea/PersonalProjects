// File: gameEngine/core/Renderer.js

/**
 * Renderer
 * -----------------------------------------------------------------------------
 * Role: Draw ordered render layers; cache static layers to offscreen canvases.
 *
 * Public API (use these):
 * - buildStaticLayers(engine) → pre‑render static objects per layer (DPR + viewport aware).
 * - draw(engine)              → draw one frame (auto rebuilds statics if needed).
 *
 * Collaborators:
 * - CanvasManager (DPR scaling of main ctx).
 * - Viewport      (offsetX/offsetY/scale applied to both statics and dynamics).
 * - Engine.layerOrder & Engine.objects.
 *
 * Helpers / Internals:
 * - engine.staticCanvases/staticCtxs: per‑layer offscreens.
 * - engine._staticMeta: detects when DPR/canvas size/viewport changed.
 *
 * Invariants:
 * - Static offscreen ctx = DPR scale × viewport transform.
 * - Main ctx is already DPR‑scaled; we only apply viewport on dynamic draws.
 * - UI layer (if used) is drawn in screen space (skip viewport).
 */

export const Renderer = {
  /**
   * (Re)build static layer caches.
   * Each layer with `o.static === true` is drawn into its own offscreen canvas.
   * The offscreen ctx is transformed so you can render using WORLD units:
   *   [DPR scale] × [viewport translate/scale].
   */
  buildStaticLayers(engine) {
    // Reset caches
    engine.staticCanvases.clear();
    engine.staticCtxs.clear();

    // Compute the DPR the main canvas uses
    const dpr = engine._cssWidth ? (engine.canvas.width / engine._cssWidth) : 1;
    const vp  = engine.viewport; // {scale, offsetX, offsetY}

    for (const layer of engine.layerOrder) {
      // Gather static objects in this layer
      const statics = engine.objects.filter(o => o.static && o.active && o.layer === layer);
      if (statics.length === 0) continue;

      // Create offscreen canvas at BACKING size (device pixels)
      const off = document.createElement("canvas");
      off.width  = engine.canvas.width;
      off.height = engine.canvas.height;

      // Prepare its context
      const ctx = off.getContext("2d");
      try { ctx.resetTransform(); } catch { ctx.setTransform(1,0,0,1,0,0); }

      // 1 unit == 1 CSS px
      ctx.scale(dpr, dpr);
      ctx.imageSmoothingEnabled = true;

      // Apply viewport: translate letterbox, then scale world→screen
      ctx.translate(vp.offsetX, vp.offsetY);
      ctx.scale(vp.scale, vp.scale);

      // Draw all statics in WORLD coordinates
      for (const o of statics) o.render(ctx);

      // Cache
      engine.staticCanvases.set(layer, off);
      engine.staticCtxs.set(layer, ctx);
    }

    // Remember what we built against (to detect when to rebuild)
    engine._staticMeta = {
      dpr,
      w: engine.canvas.width,
      h: engine.canvas.height,
      vpScale: engine.viewport.scale,
      vpOffX:  engine.viewport.offsetX,
      vpOffY:  engine.viewport.offsetY,
    };
  },

  /**
   * Draw one frame:
   *   - Rebuild statics if needed (size/DPR/viewport change).
   *   - Clear main canvas using CSS size (ctx already DPR-scaled).
   *   - For each layer:
   *       1) Blit static bitmap to EXACT CSS size (avoids double-scale).
   *       2) Draw dynamic objects under SAME viewport transform.
   *          (Skip viewport transform for a dedicated 'ui' layer, if you use one.)
   */
  draw(engine) {
    const ctx = engine.ctx;

    // Auto-rebuild statics if anything fundamental changed
    const currentDpr = engine._cssWidth ? (engine.canvas.width / engine._cssWidth) : 1;
    const m = engine._staticMeta;
    if (!m ||
        m.dpr     !== currentDpr ||
        m.w       !== engine.canvas.width ||
        m.h       !== engine.canvas.height ||
        m.vpScale !== engine.viewport.scale ||
        m.vpOffX  !== engine.viewport.offsetX ||
        m.vpOffY  !== engine.viewport.offsetY) {
      this.buildStaticLayers(engine);
    }

    // Clear in CSS-pixel space (main ctx already scaled by DPR)
    ctx.clearRect(0, 0, engine._cssWidth, engine._cssHeight);

    // Draw each layer in order
    for (const layer of engine.layerOrder) {
      // (1) Blit cached statics, if any, scaled to CSS size
      const off = engine.staticCanvases.get(layer);
      if (off) {
        ctx.drawImage(off, 0, 0, engine._cssWidth, engine._cssHeight);
      }

      // (2) Draw dynamic objects
      const vp = engine.viewport;

      // For regular gameplay layers, apply viewport transform.
      // If you have a special 'ui' layer that draws in screen space, skip it.
      const needsViewport = layer !== "ui";

      ctx.save();
      if (needsViewport) {
        // Main ctx is already DPR-scaled by CanvasManager,
        // so we only apply the viewport mapping here.
        ctx.translate(vp.offsetX, vp.offsetY);
        ctx.scale(vp.scale, vp.scale);
      }

      for (const o of engine.objects) {
        if (!o.static && o.active && o.layer === layer) {
          o.render(ctx); // o.render uses WORLD units if 'needsViewport' is true; CSS px if on 'ui'
        }
      }
      ctx.restore();
    }

    // // Optional: draw a red border to verify CSS bounds visually
    // ctx.strokeStyle = "red";
    // ctx.lineWidth = 1;
    // ctx.strokeRect(0.5, 0.5, engine._cssWidth - 1, engine._cssHeight - 1);
  }
};
