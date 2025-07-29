/**
 * UIManager – Generic on‑top UI layer
 *
 * Collects lightweight “UI elements” (pause screens, overlays, HUDs, banners)
 * and drives their update & render calls after the main game world.
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
