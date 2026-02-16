// File: PowerUp.js
import { GameObject } from "../gameEngine/core/GameObject.js";

export class PowerUp extends GameObject {
  constructor(x, y, width = 20, height = 20, color = "orange", effect = null) {
    super(x, y, width, height, color);
    this.vy = 3;                 // Physics will move us down over time
    this.effect = effect;

    this.collisionGroup = "powerup";
    this.collidesWith   = ["paddle"]; // only collides with paddle
  }

  canCollideWith(other) { return other.constructor.name === "Paddle"; }

  update(dt) {
    // No manual motion; Physics integrates. Just handle off-screen cleanup.
    if (this.y > this.engine.world.height) this.destroy();
  }

  onCollision(other) {
    if (other.constructor.name === "Paddle" && this.effect) {
      this.effect();
      this.destroy();
    }
  }
}
