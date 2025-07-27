import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";
import { Brick } from "./Brick.js";

export class Ball extends GameObject {
  constructor(x, y, radius, color) {
    super(x, y, radius * 2, radius * 2, color);
    this.radius = radius;
    this.stuck = true;
    this.vx = 0;
    this.vy = 0;
    this.paddle = null;
  }

  update(dt) {
    if (this.stuck && this.paddle) {
      this.x = this.paddle.x + this.paddle.width / 2 - this.radius;
      this.y = this.paddle.y - this.height - 2;

      if (Input.isDown(" ")) {
        this.stuck = false;
        this.vx = 0;
        this.vy = -10;
      }
      return;
    }

    super.update(dt);

    if (this.x < 0 || this.x + this.width > this.engine.canvas.width) this.vx *= -1;
    if (this.y < 0) this.vy *= -1;
  if (this.y + this.height > this.engine.canvas.height) {
  this.destroy(); // ✅ remove this ball

  // ✅ Check if there are any balls left
  const ballsLeft = this.engine.objects.some(obj => obj.constructor.name === "Ball");
    console.log(ballsLeft);
  if (!ballsLeft) {
    console.log("Game Over");
    this.engine.running = false;
  }
}

  }

  onCollision(other) {
    if (other.constructor.name === "Paddle") {
      this.vy = -Math.abs(this.vy);
      let hitPos = (this.x + this.radius - (other.x + other.width / 2)) / (other.width / 2);
      this.vx = hitPos * 4;
    }

    if (other instanceof Brick) {
      const overlapX = (this.x + this.width / 2 < other.x + other.width / 2)
        ? (this.x + this.width - other.x)
        : (other.x + other.width - this.x);

      const overlapY = (this.y + this.height / 2 < other.y + other.height / 2)
        ? (this.y + this.height - other.y)
        : (other.y + other.height - this.y);

      if (overlapX < overlapY) {
        this.vx = (this.x + this.width / 2 < other.x + other.width / 2)
          ? -Math.abs(this.vx)
          : Math.abs(this.vx);
      } else {
        this.vy = (this.y + this.height / 2 < other.y + other.height / 2)
          ? -Math.abs(this.vy)
          : Math.abs(this.vy);
      }
    }
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x + this.radius, this.y + this.radius, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}
