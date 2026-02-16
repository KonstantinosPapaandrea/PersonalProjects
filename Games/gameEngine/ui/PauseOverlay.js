// File: gameEngine/UI/PauseOverlay.js

// Base UI element in the same UI folder
import { UIElement } from "./UIElement.js";
// Pause state checker
import { GameStateManager } from "../util/GameStateManager.js";

/**
 * PauseOverlay
 * -----------------------------------------------------------------------------
 * Dim the screen and show a "PAUSED" label.
 * Drawn in **screen space** (CSS pixels).
 */
export class PauseOverlay extends UIElement {
  render(ctx) {
    // Only when paused
    if (!GameStateManager.isPaused()) return;

    // CSS size (no viewport transform on UI)
    const width  = this.engine._cssWidth;
    const height = this.engine._cssHeight;

    // Dim background
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(0, 0, width, height);

    // Label
    ctx.fillStyle = "white";
    ctx.font = "40px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("⏸ PAUSED", width / 2, height / 2);
  }
}
