import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";
import { Brick } from "./Brick.js";

export class Ball extends GameObject {
  constructor(x, y, radius, color = "red") {
    super(x, y, radius * 2, radius * 2, color);
    this.radius = radius;
    this.stuck = true;
    this.paddle = null;
    this.vx = 0;
    this.vy = 0;
    this.collisionGroup = "ball";
  this.collidesWith = ["brick", "paddle"]; // ✅ Only checks these groups
  }

  update(dt) {
    if (this.stuck && this.paddle) {
      this.x = this.paddle.x + this.paddle.width / 2 - this.radius;
      this.y = this.paddle.y - this.height - 2;

      if (Input.isKeyDown(" ")) {
        this.stuck = false;
        this.vx = 0;
        this.vy = -8; // ✅ Lowered initial speed for better collisions
      }
      return;
    }

    // ✅ Clamp max speed to prevent tunneling
    const MAX_SPEED = 10;
    this.vx = Math.max(-MAX_SPEED, Math.min(this.vx, MAX_SPEED));
    this.vy = Math.max(-MAX_SPEED, Math.min(this.vy, MAX_SPEED));

    // ✅ Sub-stepping: split movement into smaller steps for better collision detection
  const steps = Math.ceil(Math.abs(this.vx) + Math.abs(this.vy)) / 5; 

    const stepDt = dt / steps;

    for (let i = 0; i < steps; i++) {
      super.update(stepDt);

      // ✅ Bounce off walls within sub-steps
         const W = this.engine.world.width;
        const H = this.engine.world.height;
     if (this.x < 0) {
        this.x = 0;
        this.vx *= -1;
      }
      if (this.x + this.width > W) {
        this.x = W - this.width;
        this.vx *= -1;
      }
      if (this.y < 0) {
        this.y = 0;
        this.vy *= -1;
      }
    if (this.y + this.height > H) {
        this.destroy(); // ✅ Remove ball when out of bounds
        const anyLeft = this.engine.objects.some(
          o => o.constructor.name === "Ball" && o.active
        );
        if (!anyLeft) {
          console.log("Game Over");
          this.engine.running = false;
        }
        break;
      }
    }
  }

  canCollideWith(other) {
    return (
      other.constructor.name !== "Ball" &&
      other.constructor.name !== "PowerUp"
    );
  }

  onCollision(other) {
    if (other.constructor.name === "Paddle") {
      this.vy = -Math.abs(this.vy);
      const hitPos =
        (this.x + this.radius - (other.x + other.width / 2)) /
        (other.width / 2);
      this.vx = hitPos * 5; // ✅ Slightly increased horizontal control
    }

    if (other instanceof Brick) {
if (other.collisionGroup === "brick" || other.collisionGroup === "unbreakable") {
  // Basic vertical/horizontal response
  if (Math.abs(this.vy) > Math.abs(this.vx)) {
    this.vy *= -1;
    this.y = this.vy > 0 ? other.y + other.height : other.y - this.height;
  } else {
    this.vx *= -1;
    this.x = this.vx > 0 ? other.x + other.width : other.x - this.width;
  }
}

      // ✅ Better side detection
      const overlapX =
        this.x + this.width / 2 < other.x + other.width / 2
          ? this.x + this.width - other.x
          : other.x + other.width - this.x;

      const overlapY =
        this.y + this.height / 2 < other.y + other.height / 2
          ? this.y + this.height - other.y
          : other.y + other.height - this.y;

      if (overlapX < overlapY) {
        this.vx =
          this.x + this.width / 2 < other.x + other.width / 2
            ? -Math.abs(this.vx)
            : Math.abs(this.vx);
      } else {
        this.vy =
          this.y + this.height / 2 < other.y + other.height / 2
            ? -Math.abs(this.vy)
            : Math.abs(this.vy);
      }
    }
    
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(
      this.x + this.radius,
      this.y + this.radius,
      this.radius,
      0,
      Math.PI * 2
    );
    ctx.fill();
  }
}
