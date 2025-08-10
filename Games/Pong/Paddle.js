// File: Paddle.js
// ────────────────────────────────────────────────────────────────────────────
// Pong paddle in WORLD coordinates. Never reads CSS size; clamps to world.
// ────────────────────────────────────────────────────────────────────────────
import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input }      from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  /**
   * @param {number} x         WORLD x (left/top in world units)
   * @param {number} y         WORLD y
   * @param {number} width     WORLD width
   * @param {number} height    WORLD height
   * @param {string} color
   * @param {number} speed     WORLD px/s
   * @param {string} name      "Player1" or "Player2" (controls)
   */
  constructor(x, y, width, height, color = "white", speed, name = "Player1") {
    super(x, y, width, height, color); // ← WORLD space
    this.speed = speed;                // ← WORLD px/s
    this.collisionGroup = "paddle";
    this.collidesWith   = ["ball"];
    this.name = name;
  }

  update(dt) {
    // Reset vertical velocity each frame
    this.vy = 0;

    // Keyboard controls (no CSS here)
    if (this.name === "Player2") {
      if (Input.isKeyDown("ArrowUp"))   this.vy = -this.speed;
      if (Input.isKeyDown("ArrowDown")) this.vy =  this.speed;
    } else {
      if (Input.isKeyDown("w") || Input.isKeyDown("W")) this.vy = -this.speed;
      if (Input.isKeyDown("s") || Input.isKeyDown("S")) this.vy =  this.speed;
    }

    // Integrate position via base class (uses vx/vy*dt)
    super.update(dt);

    // Clamp to WORLD HEIGHT (not CSS)
    if (this.engine) {
      const H = this.engine.world.height;   // ← WORLD height
      if (this.y < 0) this.y = 0;
      if (this.y + this.height > H) this.y = H - this.height;
    }
  }
}
