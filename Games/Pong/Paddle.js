import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  constructor(x, y, width, height, color = "white", speed = 200) {
    super(x, y, width, height, color);
    this.speed = speed; // units per second

    this.collisionGroup = "paddle";
    this.collidesWith = ["ball"];
  }

  handleMovement(dt) {
    // Reset velocity each frame; no accumulation
    this.vx = 0;
    this.vy = 0;

    if (Input.isDown("ArrowUp")) {
      this.vy = -this.speed; // moving up
    } else if (Input.isDown("ArrowDown")) {
      this.vy = this.speed; // moving down
    }
  }

  update(dt) {
    // Process input first
    this.handleMovement(dt);

    // Apply movement (super uses vx/vy * dt)
    super.update(dt);

    // Optional: clamp to canvas bounds if you have access to engine
    if (this.engine) {
      if (this.y < 0) this.y = 0;
      if (this.y + this.height > this.engine.canvas.height)
        this.y = this.engine.canvas.height - this.height;
    }
  }
}
