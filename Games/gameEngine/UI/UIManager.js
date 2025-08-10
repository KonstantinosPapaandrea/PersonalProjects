/**
 * UIManager
 * -----------------------------------------------------------------------------
 * Role: Collects lightweight UI elements and draws them after the game world.
 *
 * Public API (use these):
 * - new UIManager(engine)
 * - add(element) / remove(element)  // element gets element.engine = engine
 * - update(dt)                      // forwards to elements
 * - render(ctx)                     // forwards to elements (screen space)
 *
 * Expectations:
 * - UI elements draw in CSS pixel space (no viewport transform).
 * - Use engine._cssWidth/_cssHeight when you need screen size.
 */

export class UIManager {
  constructor(engine) {
    this.engine = engine;
    this.uiElements = [];
  }

  /** Add a UI element (must implement update(dt) and/or render(ctx)) */
  add(element) {
    element.engine = this.engine;
    this.uiElements.push(element);
  }

  /** Remove a UI element */
  remove(element) {
    this.uiElements = this.uiElements.filter(e => e !== element);
  }

  /** Call update on all UI elements */
  update(dt) {
    for (let el of this.uiElements) {
      if (typeof el.update === "function") el.update(dt);
    }
  }

  /** Draw all UI elements on top of the game */
  render(ctx) {
    for (let el of this.uiElements) {
      if (typeof el.render === "function") el.render(ctx);
    }
  }
}
