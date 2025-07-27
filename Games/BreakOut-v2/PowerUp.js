import { GameObject } from "../gameEngine/core/GameObject.js";

export class PowerUp extends GameObject {
  constructor(x, y, width = 20, height = 20, color = "orange", effect = null) {
    super(x, y, width, height, color);
    this.vy = 3; // falls down slowly
    this.effect = effect; // function executed when collected
  }

  update(dt) {
    super.update(dt);

    // Remove if it falls out of the screen
    if (this.y > this.engine.canvas.height) {
      this.destroy();
    }
  }

  onCollision(other) {
    if (other.constructor.name === "Paddle" && this.effect) {
      this.effect(); // ✅ Trigger power-up effect
      this.destroy();
    }
  }
}
