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

    // store base speed and give initial direction (up-right)
    this.baseSpeed = speed;
    this.vx = speed ;
    this.vy = 0;

    this.collisionGroup = "ball";
    this.collidesWith = ["paddle", "brick"];
  }

 onCollision(other) {
  if (other.collisionGroup === "paddle") {
    // Total speed magnitude preserved
    const speed = Math.hypot(this.vx, this.vy);

    // Compute hit position along the paddle (vertical), normalized to [-1,1]
    const relativeIntersectY =
      (this.y + this.radius) - (other.y + other.height / 2);
    const normalized = relativeIntersectY / (other.height / 2);
    const clamped = Math.max(-1, Math.min(1, normalized));

    // Max deflection angle away from pure horizontal (in radians)
    const maxBounceAngle = Math.PI / 3; // 60 degrees

    // Angle relative to horizontal: positive means downwards
    const bounceAngle = clamped * maxBounceAngle;

    // Determine new velocities: reflect horizontally, apply vertical variation
    const direction = other.x < this.x ? 1 : -1; // if paddle is left, ball should go right
    this.vx = Math.cos(bounceAngle) * speed * direction;
    this.vy = Math.sin(bounceAngle) * speed;
  }
}


  update(dt) {
  super.update(dt);

  // ---- bottom ----
  if (this.y + this.height > this.engine.canvas.height) {
    this.y = this.engine.canvas.height - this.height;
    this.vy *= -1;
  }

  // ---- top ----
  if (this.y < 0) {
    this.y = 0;
    this.vy *= -1;
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
