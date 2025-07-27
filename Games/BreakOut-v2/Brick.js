import { GameObject } from "../gameEngine/core/GameObject.js";
import { PowerUp } from "./PowerUp.js";

export class Brick extends GameObject {
  constructor(x, y, width, height, color = "green", breakable = true) {
    super(x, y, width, height, color);
    this.breakable = breakable;
    this.static = true; // ✅ For QuadTree optimization
    this.collisionGroup = "brick";
  this.collidesWith = ["ball"]; // ✅ Only cares about balls
  }

  canCollideWith(other) {
    return other.constructor.name === "Ball";
  }
destroy() {
  this.active = false;
  if (this.static) this.engine._staticLayerDirty = true;

  const remaining = this.engine.objects.some(
    o => o.static && o.active && o.breakable
  );
if (!remaining) {
  window.dispatchEvent(new CustomEvent("gameWon"));
}
}


  onCollision(other) {
    if (!this.breakable) return;
    if (other.constructor.name === "Ball") {
      this.destroy();

      // ✅ 20% chance to drop a power-up
      if (Math.random() < 1) {
        const powerUp = new PowerUp(
          this.x + this.width / 2 - 10,
          this.y + this.height,
          20,
          20,
          "orange",
          () => {
            this.spawnTripleBalls(500); // ✅ MAX BALL LIMIT = 30
          }
        );
        this.engine.addObject(powerUp);
      }
    }
  }

  spawnTripleBalls(maxBalls = 200) {
   let balls = this.engine.objects.filter(o => o.constructor.name === "Ball" && o.active);
  let ballCount = balls.length;

  balls.forEach(b => {
  for (let i = 0; i < 2; i++) {
    if (ballCount >= maxBalls) return;

    const nb = new b.constructor(b.x, b.y, b.radius, b.color);

    // ✅ Random horizontal speed (-3 to 3)
    nb.vx = (Math.random() - 0.5) * 6;

    // ✅ Keep same vertical direction, add ±10% variation
    const variation = 0.1 * Math.abs(b.vy); // 10% of original speed
    nb.vy = b.vy + (Math.random() * variation * 2 - variation);

    this.engine.addObject(nb);
    ballCount++;
  }
});
}
}
