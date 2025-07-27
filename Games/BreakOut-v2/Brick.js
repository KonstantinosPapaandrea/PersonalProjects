import { GameObject } from "../gameEngine/core/GameObject.js";
import { PowerUp } from "./PowerUp.js";

export class Brick extends GameObject {
  constructor(x, y, width, height, color = "green", breakable = true) {
    super(x, y, width, height, color);
    this.breakable = breakable;
    this.static = true; // ✅ For QuadTree optimization
  }

  canCollideWith(other) {
    return other.constructor.name === "Ball";
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
            this.spawnTripleBalls(200); // ✅ MAX BALL LIMIT = 30
          }
        );
        this.engine.addObject(powerUp);
      }
    }
  }

  spawnTripleBalls(maxBalls = 500) {
    const activeBalls = this.engine.objects.filter(
      obj => obj.constructor.name === "Ball" && obj.active
    );

    activeBalls.forEach(ball => {
      for (let i = 0; i < 2; i++) {
        const currentBallCount = this.engine.objects.filter(
          obj => obj.constructor.name === "Ball" && obj.active
        ).length;

        if (currentBallCount >= maxBalls) return;

        const newBall = new ball.constructor(
          ball.x,
          ball.y,
          ball.radius,
          ball.color
        );
        newBall.vx = (Math.random() - 0.5) * 6;
        newBall.vy = -Math.abs(ball.vy || -4);
        this.engine.addObject(newBall);
      }
    });
  }
}
