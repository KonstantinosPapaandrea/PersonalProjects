import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  update(dt) {
    if (Input.isDown("ArrowLeft")) this.vx = -20;
    else if (Input.isDown("ArrowRight")) this.vx = 20;
    else this.vx = 0;

    super.update(dt);

    if (this.x < 0) this.x = 0;
    if (this.x + this.width > this.engine.canvas.width) {
      this.x = this.engine.canvas.width - this.width;
    }
  }
}
