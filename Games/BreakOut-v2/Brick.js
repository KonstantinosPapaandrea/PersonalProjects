// File: Brick.js
import { GameObject } from "../gameEngine/core/GameObject.js";
import { PowerUp }    from "./PowerUp.js";

export class Brick extends GameObject {
  constructor(x, y, width, height, color = "green", breakable = true) {
    super(x, y, width, height, color);
    this.breakable      = breakable;
    this.static         = true;       // drawn to static layer
    this.collisionGroup = "brick";
    this.collidesWith   = ["ball"];   // only balls collide with me
  }

  canCollideWith(other) { return other.constructor.name === "Ball"; }

  destroy() {
    this.active = false;
    if (this.static) this.engine._staticLayerDirty = true; // trigger static rebuild

    // If no breakable bricks remain → win
    const remaining = this.engine.objects.some(o => o.static && o.active && o.breakable);
    if (!remaining) window.dispatchEvent(new CustomEvent("gameWon"));
  }

  onCollision(other) {
    if (!this.breakable) return;
    if (other.constructor.name !== "Ball") return;

    // Remove the brick
    this.destroy();

    // 20% chance to drop a power‑up (was 100% by mistake)
    if (Math.random() < 0.2) {  // ← fixed from < 1
      const pu = new PowerUp(
        this.x + this.width / 2 - 10,
        this.y + this.height,
        20, 20,
        "orange",
        () => this.spawnTripleBalls(24) // cap to avoid explosion
      );
      this.engine.addObject(pu);
    }
  }

  // Spawns two extra balls per existing ball, capped by maxBalls
  spawnTripleBalls(maxBalls = 24) {
    const balls = this.engine.objects.filter(o => o.constructor.name === "Ball" && o.active);
    let count = balls.length;
    for (const b of balls) {
      for (let i = 0; i < 2; i++) {
        if (count >= maxBalls) return;
        const nb = new b.constructor(b.x, b.y, b.radius, b.color);
        nb.vx = (Math.random() - 0.5) * 6;
        const variation = 0.1 * Math.abs(b.vy);
        nb.vy = b.vy + (Math.random() * variation * 2 - variation);
        nb.useCCD = true; nb.substepEnabled = true; nb.maxMoveRatio = 0.3;
        this.engine.addObject(nb);
        count++;
      }
    }
  }
}
