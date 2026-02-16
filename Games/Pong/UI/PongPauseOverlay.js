// File: UI/PongPauseOverlay.js
// -----------------------------------------------------------------------------
// Dim overlay while paused. Draws in CSS pixels, uses GameStateManager.
// -----------------------------------------------------------------------------
import { GameStateManager } from "../../gameEngine/util/GameStateManager.js";

export class PongPauseOverlay {
  constructor() {
    this.engine = null;
    this.active = true;
  }

  update(dt) {
    // no-op; purely visual overlay
  }

  render(ctx) {
    if (!GameStateManager.isPaused()) return;

    const W = this.engine._cssWidth;
    const H = this.engine._cssHeight;

    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "white";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "40px sans-serif";
    ctx.fillText("⏸ PAUSED", W / 2, H / 2);
  }
}
