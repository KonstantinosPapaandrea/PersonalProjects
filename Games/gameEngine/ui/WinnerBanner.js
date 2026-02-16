// File: gameEngine/UI/WinnerBanner.js

// Base UI class in the same UI folder
import { UIElement } from "./UIElement.js";

/**
 * WinnerBanner
 * -----------------------------------------------------------------------------
 * Shows a full-screen "YOU WIN!" overlay when `checkFn()` returns true.
 * Drawn in **screen space** (CSS pixels).
 */
export class WinnerBanner extends UIElement {
  constructor(checkFn, text = "🏆 YOU WIN!") {
    super();                     // set {engine:null, active:true}
    this.checkWin = checkFn;     // function: () => boolean
    this.text     = text;        // customizable banner text
  }

  render(ctx) {
    // Only show when the supplied condition is met
    if (!this.checkWin()) return;

    // CSS size (no viewport transform on UI)
    const width  = this.engine._cssWidth;
    const height = this.engine._cssHeight;

    // Dim background
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(0, 0, width, height);

    // Banner text
    ctx.fillStyle = "yellow";
    ctx.font = "60px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(this.text, width / 2, height / 2);
  }
}
