import { UIElement } from "../core/UIElement.js";
import { Input }     from "../core/Input.js";
import { GameStateManager } from "../util/GameStateManager.js";

export class MainMenu extends UIElement {
  constructor(onStart,name) {
    super();
    this.onStart = onStart;
    this.name=name;
  }

  update() {
    if (GameStateManager.is("init") && Input.isDown("Enter")) {
      this.onStart();
    }
  }

  render(ctx) {
    if (!GameStateManager.is("init")) return;
    const { width, height } = this.engine.canvas;
    ctx.fillStyle = "#222";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "white";
    ctx.font = "56px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(this.name, width / 2, height / 2 - 40);
    ctx.font = "24px sans-serif";
    ctx.fillText("Press ENTER to Start", width / 2, height / 2 + 20);
  }
}
