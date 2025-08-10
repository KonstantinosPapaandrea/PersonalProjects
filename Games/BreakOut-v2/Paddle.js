import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  constructor(x, y, width, height, color = "blue") {
    super(x, y, width, height, color);

    this.collisionGroup = "paddle";
    this.collidesWith = ["ball","powerup"];
  }

  update(dt) {
    if (Input.isKeyDown("ArrowLeft")) this.vx = -20;
    else if (Input.isKeyDown("ArrowRight")) this.vx = 20;
    else this.vx = 0;

    super.update(dt);
    const W = this.engine.world.width;   // ← world units
    if (this.x < 0) this.x = 0;
    if (this.x + this.width > W) this.x = W - this.width;
  }
  
}
