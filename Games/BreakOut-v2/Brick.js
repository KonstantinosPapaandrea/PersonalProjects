import { GameObject } from "../gameEngine/core/GameObject.js";
import { PowerUp }    from "./PowerUp.js";

export class Brick extends GameObject {
  /**
   * @param {number} x 
   * @param {number} y 
   * @param {number} width 
   * @param {number} height 
   * @param {string} color 
   * @param {boolean} breakable 
   */
  constructor(x, y, width, height, color = "green", breakable = true) {
    super(x, y, width, height, color);
    this.breakable     = breakable;
    this.static        = true;            // drawn to static layer
    this.collisionGroup = "brick";
    this.collidesWith  = ["ball"];        // only balls collide
  }

  canCollideWith(other) {
    return other.constructor.name === "Ball";
  }

  /**
   * Marks this brick inactive, rebuilds static layer if needed,
   * and when no breakable bricks remain dispatches `gameWon`.
   */
  destroy() {
    this.active = false;
    if (this.static) this.engine._staticLayerDirty = true;

    // Check whether any breakable bricks are left
    const remaining = this.engine.objects.some(
      o => o.static && o.active && o.breakable
    );

    if (!remaining) {
      // 🚀 Notify the game that the player has won
      window.dispatchEvent(new CustomEvent("gameWon"));
    }
  }

  /**
   * Called by the engine when a collision with another object occurs.
   */
  onCollision(other) {
    if (!this.breakable) return;
    if (other.constructor.name !== "Ball") return;

    // Remove this brick
    this.destroy();

    // 20% chance to drop a power-up
    if (Math.random() < 1) {
      const pu = new PowerUp(
        this.x + this.width / 2 - 10,
        this.y + this.height,
        20, 20,
        "orange",
        () => this.spawnTripleBalls(500)
      );
      this.engine.addObject(pu);
    }
  }

  /**
   * Spawns two extra balls per existing ball, up to maxBalls.
   */
  spawnTripleBalls(maxBalls = 500) {
    const balls = this.engine.objects.filter(
      o => o.constructor.name === "Ball" && o.active
    );
    let count = balls.length;

    balls.forEach(b => {
      for (let i = 0; i < 2; i++) {
        if (count >= maxBalls) return;
        const nb = new b.constructor(b.x, b.y, b.radius, b.color);

        // Random horizontal speed
        nb.vx = (Math.random() - 0.5) * 6;

        // Keep same vertical direction with slight variation
        const variation = 0.1 * Math.abs(b.vy);
        nb.vy = b.vy + (Math.random() * variation * 2 - variation);

        this.engine.addObject(nb);
        count++;
      }
    });
  }
}
