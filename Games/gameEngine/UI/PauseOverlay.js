import { UIElement } from "./UIElement.js";
import { GameStateManager } from "../util/GameStateManager.js";

export class PauseOverlay extends UIElement {
  render(ctx) {
    if (!GameStateManager.isPaused()) return;

    const { width, height } = this.engine.canvas;
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "white";
    ctx.font = "40px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("⏸ PAUSED", width / 2, height / 2);
  }
}
