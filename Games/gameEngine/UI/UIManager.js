// UIManager.js — patch to treat undefined `active` as true

export class UIManager {
  constructor(engine) {
    this.engine = engine;      // back-ref to engine
    this.uiElements = [];      // ordered list
  }

  add(element) {
    element.engine = this.engine;       // let UI read sizes/state
    // If element.active is undefined, default it to true so plain objects work.
    if (element.active === undefined) element.active = true;   // <-- added
    this.uiElements.push(element);
  }

  remove(element) {
    this.uiElements = this.uiElements.filter(e => e !== element);
  }

  clear() { this.uiElements.length = 0; }

  update(dt) {
    for (const el of this.uiElements) {
      // Skip only when explicitly deactivated; undefined counts as active.
      if (!el || el.active === false) continue;                // <-- changed
      if (typeof el.update === "function") el.update(dt);
    }
  }

  render(ctx) {
    for (const el of this.uiElements) {
      // Skip only when explicitly deactivated; undefined counts as active.
      if (!el || el.active === false) continue;                // <-- changed
      if (typeof el.render === "function") el.render(ctx);
    }
  }
}
