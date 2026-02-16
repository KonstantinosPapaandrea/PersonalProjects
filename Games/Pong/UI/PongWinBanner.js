// File: UI/PongWinBanner.js
// -----------------------------------------------------------------------------
// Shows winner and prompt to restart next round. CSS pixels.
// -----------------------------------------------------------------------------
import { GameStateManager } from "../../gameEngine/util/GameStateManager.js";

export class PongWinBanner {
  constructor(getWinnerName, onContinue) {
    this.engine = null;
    this.active = true;
    this.getWinnerName = getWinnerName; // () => string|null
    this.onContinue = onContinue;       // () => void
  }

  update(dt) {
    const name = this.getWinnerName ? this.getWinnerName() : null;
    if (!name) return;

    // Press ENTER to continue to next round
    if (window.__lastKey === "Enter") {
      window.__lastKey = null;
      if (this.onContinue) this.onContinue();
    }
  }

  render(ctx) {
    const name = this.getWinnerName ? this.getWinnerName() : null;
    if (!name) return;

    const W = this.engine._cssWidth;
    const H = this.engine._cssHeight;

    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "yellow";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font = "48px sans-serif";
    ctx.fillText(`${name} scores!`, W / 2, H / 2 - 10);

    ctx.font = "20px sans-serif";
    ctx.fillText("Press ENTER for next serve", W / 2, H / 2 + 30);
  }
}
