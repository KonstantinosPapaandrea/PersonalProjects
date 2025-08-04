// File: Ball.js
import { GameObject } from "../gameEngine/core/GameObject.js";

export class Ball extends GameObject {
  /**
   * @param {number} x
   * @param {number} y
   * @param {number} radius
   * @param {string} color
   * @param {number} speed - base speed magnitude
   */
  constructor(x, y, radius, color = "red", speed = 200) {
    super(x, y, radius * 2, radius * 2, color);
    this.radius = radius;
    this.stuck = true; // waiting to launch
    this.baseSpeed = speed;

    // start with zero velocity
    this.vx = 0;
    this.vy = 0;

    this.collisionGroup = "ball";
    this.collidesWith = ["paddle"];
  }

  launch() {
    if (!this.stuck) return;
    this.stuck = false;

    const angle = (Math.random() * 0.6 - 0.3); // vertical variation
    const dir = Math.random() < 0.5 ? 1 : -1; // left or right
    this.vx = Math.cos(angle) * this.baseSpeed * dir;
    this.vy = Math.sin(angle) * this.baseSpeed;
  }

  reset() {
    this.stuck = true;
    this.vx = 0;
    this.vy = 0;

    if (this.engine) {
      this.x = this.engine.canvas.width / 2 - this.radius;
      this.y = this.engine.canvas.height / 2 - this.radius;
    }
  }

  onCollision(other) {
    if (other.collisionGroup === "paddle") {
      // Preserve speed magnitude
      const speed = Math.hypot(this.vx, this.vy) || this.baseSpeed;

      // Compute normalized hit position along paddle's vertical axis (-1 top, +1 bottom)
      const relativeIntersectY =
        (this.y + this.radius) - (other.y + other.height / 2);
      const normalized = Math.max(
        -1,
        Math.min(1, relativeIntersectY / (other.height / 2))
      );

      // Max deflection angle from horizontal
      const maxBounceAngle = Math.PI / 3; // 60 degrees
      const bounceAngle = normalized * maxBounceAngle;

      // Determine direction away from paddle horizontally
      const direction = other.x < this.x ? 1 : -1;

      // New velocities
      this.vx = Math.cos(bounceAngle) * speed * direction;
      this.vy = Math.sin(bounceAngle) * speed;

      // Nudge out of overlap
      if (other.x < this.x) {
        this.x = other.x + other.width + 0.1;
      } else {
        this.x = other.x - this.width - 0.1;
      }
    }
  }

  update(dt) {
    if (this.stuck) {
      // stay centered if stuck
      if (this.engine) {
        this.x = this.engine.canvas.width / 2 - this.radius;
        this.y = this.engine.canvas.height / 2 - this.radius;
      }
      return;
    }

    super.update(dt);

    // bounce top/bottom
    if (this.y < 0) {
      this.y = 0;
      this.vy = Math.abs(this.vy);
    }
    if (this.y + this.height > this.engine.canvas.height) {
      this.y = this.engine.canvas.height - this.height;
      this.vy = -Math.abs(this.vy);
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
