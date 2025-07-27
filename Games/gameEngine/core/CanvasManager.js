import { Renderer } from "./Renderer.js";

/**
 * CanvasManager – Handles canvas size & window resizing.
 *
 * Responsibilities:
 * ✅ Sets initial canvas size.
 * ✅ Automatically updates canvas size on window resize.
 * ✅ Rebuilds static layer when resized.
 */

export const CanvasManager = {
  /**
   * setSize(engine, width, height)
   * Updates the canvas size to the given dimensions.
   */
  setSize(engine, width, height) {
    engine.canvas.width = width;
    engine.canvas.height = height;
  },

  /**
   * handleResize(engine)
   * Attaches a resize listener to keep the canvas full-screen
   * and rebuild the static layer when the window changes size.
   */
  handleResize(engine) {
    window.addEventListener("resize", () => {
      this.setSize(engine, window.innerWidth, window.innerHeight);
      Renderer.buildStaticLayer(engine);

      // Optional callback for custom game logic (e.g., reposition paddle)
      if (engine.onResize) engine.onResize(engine.canvas.width, engine.canvas.height);
    });
  }
};
