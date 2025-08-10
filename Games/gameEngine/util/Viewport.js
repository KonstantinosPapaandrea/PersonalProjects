// File: gameEngine/util/Viewport.js

/**
 * Viewport (mini camera)
 * -----------------------------------------------------------------------------
 * Role: Map your fixed WORLD size to the current CSS canvas size with a chosen fit.
 *
 * Public API (use this):
 * - update(engine, mode="contain" | "cover")
 *     Computes { scale, offsetX, offsetY, fit } on engine.viewport.
 *
 * How it’s used:
 * - Renderer applies translate(offsetX,offsetY) then scale(scale).
 * - Input.getPointerPosInWorld() inverts the mapping for pointer → world.
 *
 * Invariants:
 * - Uses engine._cssWidth/_cssHeight (set by CanvasManager) and engine.world.
 * - Offsets are letterbox margins in CSS pixels; scale maps WORLD→CSS.
 */


export const Viewport = {
  /**
   * Recompute the viewport mapping from world→screen.
   * @param {Engine} engine - your engine instance
   * @param {"contain"|"cover"} [mode] - fit policy; defaults to existing setting
   */
  update(engine, mode = engine.viewport?.fit ?? "contain") {
    // Canvas size in CSS pixels (already stored by CanvasManager)
    const cssW = engine._cssWidth  || 0;
    const cssH = engine._cssHeight || 0;

    // Logical world size (fixed "design resolution")
    const wW = engine.world?.width  || 0;
    const wH = engine.world?.height || 0;

    // Initialize viewport object if missing
    if (!engine.viewport) engine.viewport = { scale: 1, offsetX: 0, offsetY: 0, fit: mode };

    // Early out if sizes are not yet known
    if (!cssW || !cssH || !wW || !wH) {
      engine.viewport.scale   = 1;
      engine.viewport.offsetX = 0;
      engine.viewport.offsetY = 0;
      engine.viewport.fit     = mode;
      return;
    }

    // Compute scale factor based on requested fit mode
    const scale =
      mode === "cover"
        ? Math.max(cssW / wW, cssH / wH)  // fill screen, possibly crop
        : Math.min(cssW / wW, cssH / wH); // show all, letterbox if needed

    // Center the world (letterbox offsets in CSS pixels)
    const offsetX = Math.floor((cssW - wW * scale) / 2);
    const offsetY = Math.floor((cssH - wH * scale) / 2);

    // Store results back on the engine
    engine.viewport.scale   = scale;
    engine.viewport.offsetX = offsetX;
    engine.viewport.offsetY = offsetY;
    engine.viewport.fit     = mode;
  }
};
