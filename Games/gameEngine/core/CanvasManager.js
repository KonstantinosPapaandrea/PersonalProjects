// File: gameEngine/core/CanvasManager.js

/**
 * CanvasManager – Manages backing-store size vs. CSS display size.
 *
 * setSize: sets the canvas.width/height (world coordinates).
 * setDisplaySize: sets canvas.style.width/height (on-screen display).
 * handleDisplayResize: automatically updates CSS on window resize.
 */
export const CanvasManager = {
  
  /**
   * Set the canvas backing store size (logical world size).
   * @param {Engine} engine
   * @param {number} width
   * @param {number} height
   */
  setSize(engine, width, height) {
    engine.canvas.width = width;
    engine.canvas.height = height;
  },

  /**
   * Set the canvas on-screen display size (CSS pixels).
   * @param {Engine} engine
   * @param {number} displayWidth
   * @param {number} displayHeight
   */
  setDisplaySize(engine, displayWidth, displayHeight) {
    engine.canvas.style.width = `${displayWidth}px`;
    engine.canvas.style.height = `${displayHeight}px`;
    // ensure fill and no extra space
    engine.canvas.style.display = "block";
    engine.canvas.style.margin = "0";
  },

  /**
   * Attach a listener to resize the display size on window resize.
   * @param {Engine} engine
   */
  handleDisplayResize(engine) {
    window.addEventListener("resize", () => {
      this.setDisplaySize(engine, window.innerWidth, window.innerHeight);
    });
  }
};
