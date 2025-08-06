// File: CanvasManager.js
import { Renderer } from "./Renderer.js";

/**
 * CanvasManager – Manages high-DPI (retina) rendering
 * - Backing store size = CSS size * devicePixelRatio
 * - CSS size stays at logical pixels (window.innerWidth/innerHeight)
 * - Contexts are scaled so 1 unit = 1 CSS pixel
 */
export const CanvasManager = {
  /**
   * Resize both the main canvas and (if it exists) the staticCanvas
   * to full device-pixel resolution, then scale contexts appropriately.
   *
   * @param {Engine} engine
   * @param {number} cssWidth   Logical width in CSS pixels
   * @param {number} cssHeight  Logical height in CSS pixels
   */
  setSize(engine, cssWidth, cssHeight) {
    const dpr = window.devicePixelRatio || 1;

    // Store CSS size on engine for reference
    engine._cssWidth  = cssWidth;
    engine._cssHeight = cssHeight;

    // 1) Backing store
    engine.canvas.width  = Math.floor(cssWidth  * dpr);
    engine.canvas.height = Math.floor(cssHeight * dpr);

    // 2) CSS size
    engine.canvas.style.width  = `${cssWidth}px`;
    engine.canvas.style.height = `${cssHeight}px`;

    // 3) Scale the main context
    const ctx = engine.ctx;
    ctx.resetTransform();          // clear any previous scaling
    ctx.scale(dpr, dpr);

    // 4) If staticCanvas exists, resize & scale it too
    if (engine.staticCanvas && engine.staticCtx) {
      engine.staticCanvas.width  = engine.canvas.width;
      engine.staticCanvas.height = engine.canvas.height;

      const sctx = engine.staticCtx;
      sctx.resetTransform();
      sctx.scale(dpr, dpr);
    }
  },

  /**
   * For high-DPI resizing: always updates backing + CSS sizes on window resize.
   * @param {Engine} engine
   */
  handleDisplayResize(engine) {
    const resizeHandler = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      this.setSize(engine, w, h);
      // Rebuild the static layer at the new size
      Renderer.buildStaticLayer(engine);
    };

    window.addEventListener("resize", resizeHandler);
    resizeHandler(); // initial call
    engine._resizeHandler = resizeHandler;
  },

  /**
   * If you ever need to stop listening (e.g. on teardown), call this.
   */
  removeResizeListener(engine) {
    if (engine._resizeHandler) {
      window.removeEventListener("resize", engine._resizeHandler);
      delete engine._resizeHandler;
    }
  }
};
