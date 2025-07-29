import { UIElement } from ".UIElement.js";

export class WinnerBanner extends UIElement {
  constructor(checkFn) {
    super();
    this.checkWin = checkFn;  // a function that returns true when you want to show
  }

  render(ctx) {
    if (!this.checkWin()) return;

    const { width, height } = this.engine.canvas;
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "yellow";
    ctx.font = "60px Arial";
    ctx.textAlign = "center";
    ctx.fillText("🏆 YOU WIN!", width / 2, height / 2);
  }
}
