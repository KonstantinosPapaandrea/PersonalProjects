// File: gameEngine/core/Input.js

/**
 * Input
 * -----------------------------------------------------------------------------
 * Role: Centralized keyboard + pointer state with helpers to read positions
 *       in CSS (screen) space or WORLD space (via Viewport).
 *
 * Public API (use these):
 * - init() / destroy()
 * - isKeyDown(key) / isDown(key)         // alias for convenience
 * - isPointerDown()
 * - getPointerPos()                       // {x,y} in window/client coords
 * - getPointerPosInCanvas(canvas)         // {x,y} in CSS coords (top‑left=0,0)
 * - getPointerPosInWorld(engine)          // {x,y} in WORLD units (viewport‑aware)
 *
 * Helpers / Internals:
 * - Keyboard handlers, mouse/touch handlers (private _on* functions).
 * - pointerPos tracked in client coordinates; conversions handle DPR & viewport.
 */


export class Input {
  // --- Internal state ---------------------------------------------------------
  static keys = new Set();                  // keys currently down
  static pointerPos = { x: 0, y: 0 };       // last known window coords
  static pointerDown = false;               // mouse/touch down?

  // --- Lifecycle --------------------------------------------------------------
  static init() {
    // Keyboard
    window.addEventListener("keydown", Input._onKeyDown);
    window.addEventListener("keyup",   Input._onKeyUp);

    // Mouse
    window.addEventListener("mousedown", Input._onPointerDown);
    window.addEventListener("mouseup",   Input._onPointerUp);
    window.addEventListener("mousemove", Input._onPointerMove);

    // Touch
    window.addEventListener("touchstart", Input._onTouchStart, { passive: false });
    window.addEventListener("touchend",   Input._onTouchEnd,   { passive: false });
    window.addEventListener("touchmove",  Input._onTouchMove,  { passive: false });
  }

  static destroy() {
    window.removeEventListener("keydown",    Input._onKeyDown);
    window.removeEventListener("keyup",      Input._onKeyUp);
    window.removeEventListener("mousedown",  Input._onPointerDown);
    window.removeEventListener("mouseup",    Input._onPointerUp);
    window.removeEventListener("mousemove",  Input._onPointerMove);
    window.removeEventListener("touchstart", Input._onTouchStart);
    window.removeEventListener("touchend",   Input._onTouchEnd);
    window.removeEventListener("touchmove",  Input._onTouchMove);
  }

  // --- Public queries ---------------------------------------------------------
  static isKeyDown(key) { return Input.keys.has(key); } // canonical
  static isDown(key)    { return Input.isKeyDown(key); } // back‑compat alias

  static isPointerDown() { return Input.pointerDown; }
  static getPointerPos() { return { ...Input.pointerPos }; }

  /**
   * Convert window/client pointer coords → canvas CSS coords (top-left = 0,0).
   * Use when drawing UI or when you need CSS‑pixel positions.
   */
  static getPointerPosInCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    return { x: Input.pointerPos.x - rect.left, y: Input.pointerPos.y - rect.top };
  }

  /**
   * Convert pointer to WORLD coordinates (through the current viewport).
   * Use this in gameplay (drag paddles, aim, etc.).
   */
  static getPointerPosInWorld(engine) {
    const p  = Input.getPointerPosInCanvas(engine.canvas);  // CSS pixels
    const vp = engine.viewport;                              // {scale,offsetX,offsetY}
    return { x: (p.x - vp.offsetX) / vp.scale, y: (p.y - vp.offsetY) / vp.scale };
  }

  // --- Private handlers -------------------------------------------------------
  static _onKeyDown(e) {
    Input.keys.add(e.key);
    if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(e.key)) e.preventDefault();
  }
  static _onKeyUp(e) {
    Input.keys.delete(e.key);
    if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(e.key)) e.preventDefault();
  }

  static _onPointerDown(e) { Input.pointerDown = true;  Input.pointerPos = { x: e.clientX, y: e.clientY }; e.preventDefault(); }
  static _onPointerUp(e)   { Input.pointerDown = false; Input.pointerPos = { x: e.clientX, y: e.clientY }; e.preventDefault(); }
  static _onPointerMove(e) { Input.pointerPos = { x: e.clientX, y: e.clientY }; /* no preventDefault here */ }

  static _onTouchStart(e) { const t = e.changedTouches[0]; Input.pointerDown = true;  Input.pointerPos = { x: t.clientX, y: t.clientY }; e.preventDefault(); }
  static _onTouchEnd(e)   { const t = e.changedTouches[0]; Input.pointerDown = false; Input.pointerPos = { x: t.clientX, y: t.clientY }; e.preventDefault(); }
  static _onTouchMove(e)  { const t = e.changedTouches[0]; Input.pointerPos = { x: t.clientX, y: t.clientY }; e.preventDefault(); }
}

