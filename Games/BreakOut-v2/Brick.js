import { GameObject } from "../gameEngine/core/GameObject.js";
import { PowerUp } from "./PowerUp.js";

export class Brick extends GameObject {
  constructor(x, y, width, height, color = "green", breakable = true) {
    super(x, y, width, height, color);
    this.breakable = breakable;
  }

  onCollision(other) {
    if (!this.breakable) return;

    if (other.constructor.name === "Ball") {
      this.destroy();

      // ✅ 20% chance to spawn a power-up
      if (Math.random() < 0.2) {
        const powerUp = new PowerUp(
          this.x + this.width / 2 - 10, // center
          this.y + this.height,
          20,
          20,
          "orange",
          () => {
            this.spawnTripleBall(500);
          }
        );
        this.engine.addObject(powerUp);
      }
    }
  }

spawnTripleBall(maxBalls = 30) {
  // ✅ Get all active balls
  const activeBalls = this.engine.objects.filter(
    obj => obj.constructor.name === "Ball" && obj.active
  );

  const currentBallCount = activeBalls.length;

  // ✅ If already at max, do nothing
  if (currentBallCount >= maxBalls) return;

  activeBalls.forEach(ball => {
    for (let i = 0; i < 2; i++) {
      // ✅ Check before spawning each ball
      if (this.engine.objects.filter(o => o.constructor.name === "Ball" && o.active).length >= maxBalls) {
        return;
      }

      const newBall = new ball.constructor(
        ball.x,
        ball.y,
        ball.radius,
        ball.color
      );
      newBall.vx = (Math.random() - 0.5) * 6; // random horizontal direction
      newBall.vy = ball.vy;
      this.engine.addObject(newBall);
    }
  });
}


}
