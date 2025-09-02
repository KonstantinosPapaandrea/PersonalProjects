// File: UI/PongMainMenu.js
// -----------------------------------------------------------------------------
// Full-screen start menu. Draws in CSS pixels. Press ENTER to start.
// -----------------------------------------------------------------------------
import { GameStateManager } from "../../gameEngine/util/GameStateManager.js";

export class PongMainMenu {
  constructor({ title = "PONG", subtitle = "Press ENTER to Start", onStart } = {}) {
    this.engine = null;       // set by UIManager.add()
    this.active = true;       // UIManager renders only active elements
    this.title = title;
    this.subtitle = subtitle;
    this.onStart = onStart;   // callback provided by game (starts round)
  }

  update(dt) {
    // Only react if we're on the menu state
    if (GameStateManager.is("init") && (window.__lastKey === "Enter")) {
      // Consume the "press" (optional safety)
      window.__lastKey = null;
      // Switch to running
      GameStateManager.setState("running");
      // Fire the game-provided start callback (sets up ball/round)
      if (this.onStart) this.onStart();
      // Remove this menu (either by UIManager.remove(...) or set inactive)
      this.active = false;
    }
  }

  render(ctx) {
    if (!GameStateManager.is("init")) return; // nothing to draw in other states
    // Use CSS-pixel canvas size for UI
    const W = this.engine._cssWidth;
    const H = this.engine._cssHeight;

    // Dim background
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, W, H);

    // Title
    ctx.fillStyle = "white";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font = "64px sans-serif";
    ctx.fillText(this.title, W / 2, H / 2 - 40);

    ctx.font = "24px sans-serif";
    ctx.fillText(this.subtitle, W / 2, H / 2 + 20);

    // Controls hint (bottom)
    ctx.font = "16px monospace";
    ctx.fillText("Player1: W/S   Player2: ↑/↓   Pause: P", W / 2, H - 30);
  }
}
