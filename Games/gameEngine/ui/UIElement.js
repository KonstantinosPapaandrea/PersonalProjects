/**
 * UIElement – Base class for anything drawn by UIManager.
 * 
 * Subclasses should override:
 *  - update(dt)   // optional game‑logic per frame
 *  - render(ctx)  // must draw itself
 */
export class UIElement {
  constructor() {
    this.engine = null;   // set by UIManager.add()
    this.active = true;
  }

  update(dt) {
    // override in subclass
  }

  render(ctx) {
    // override in subclass
  }
}
