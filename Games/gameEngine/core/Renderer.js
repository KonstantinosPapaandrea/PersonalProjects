/**
 * Renderer – Handles all drawing operations.
 *
 * Responsibilities:
 * ✅ Builds and updates the static layer (off-screen canvas for static objects).
 * ✅ Draws the static layer + dynamic objects every frame.
 *
 * Why Static Layer?
 * Static objects (e.g., bricks, walls) rarely change, so we draw them once
 * on a separate off-screen canvas (`staticCanvas`) to improve performance.
 */

export const Renderer = {
  /**
   * buildStaticLayer(engine)
   * Draws all static objects onto an off-screen canvas once.
   * Called on:
   *  - Engine start
   *  - Window resize
   *  - When static objects are destroyed or added
   */
  buildStaticLayer(engine) {
    // ✅ Create a new off-screen canvas matching the main canvas size
    engine.staticCanvas = document.createElement("canvas");
    engine.staticCanvas.width = engine.canvas.width;
    engine.staticCanvas.height = engine.canvas.height;
    engine.staticCtx = engine.staticCanvas.getContext("2d");

    // ✅ Clear and redraw only static objects
    engine.staticCtx.clearRect(0, 0, engine.canvas.width, engine.canvas.height);
    engine.objects
      .filter(o => o.static && o.active) // Only active static objects
      .forEach(o => o.render(engine.staticCtx));
  },

  /**
   * draw(engine)
   * Clears the screen and draws:
   * 1. The static layer (as one pre-rendered image)
   * 2. All dynamic objects (balls, paddle, power-ups)
   */
  draw(engine) {
    // ✅ Clear the main canvas
    engine.ctx.clearRect(0, 0, engine.canvas.width, engine.canvas.height);

    // ✅ Draw the pre-rendered static layer (cheap & fast)
    engine.ctx.drawImage(engine.staticCanvas, 0, 0);

    // ✅ Draw all active dynamic objects
    engine.objects
      .filter(o => !o.static) // Static ones are already drawn on staticCanvas
      .forEach(o => o.render(engine.ctx));
  }
};
