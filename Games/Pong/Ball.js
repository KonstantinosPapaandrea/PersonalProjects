// File: Ball.js
// ────────────────────────────────────────────────────────────────────────────
// Pong ball in WORLD coordinates. All logic uses engine.world.*.
// ────────────────────────────────────────────────────────────────────────────
import { GameObject } from "../gameEngine/core/GameObject.js";

export class Ball extends GameObject {
  /**
   * @param {number} x      WORLD center x
   * @param {number} y      WORLD center y
   * @param {number} radius WORLD px
   * @param {string} color
   * @param {number} speed  WORLD px/s (base magnitude)
   */
  constructor(x, y, radius, color = "white", speed = 200) {
    // GameObject stores top-left + size; we store a radius too
    super(x - radius, y - radius, radius * 2, radius * 2, color);
    this.radius    = radius;
    this.baseSpeed = speed;
    this.vx = 0; this.vy = 0;
    this.stuck = true; // waiting to launch
    this.collisionGroup = "ball";
    this.collidesWith   = ["paddle"];
  }

  // Re-center to WORLD middle and stop
  reset() {
    this.stuck = true;
    this.vx = 0; this.vy = 0;
    if (this.engine) {
      const W = this.engine.world.width;
      const H = this.engine.world.height;
      this.x = W / 2 - this.radius;
      this.y = H / 2 - this.radius;
    }
  }

  // Launch with slight random angle, speed in WORLD px/s
  launch() {
    if (!this.stuck) return;
    this.stuck = false;
    const angle = (Math.random() * 0.6 - 0.3);   // ±~17°
    const dir   = Math.random() < 0.5 ? 1 : -1;  // left/right
    this.vx = Math.cos(angle) * this.baseSpeed * dir;
    this.vy = Math.sin(angle) * this.baseSpeed;
  }

  onCollision(other) {
    if (other.collisionGroup !== "paddle") return;

    // Preserve current speed magnitude; compute new bounce based on hit offset
    const speed = Math.hypot(this.vx, this.vy) || this.baseSpeed;

    // Relative impact point along paddle height: -1 top … +1 bottom
    const relY = (this.y + this.radius) - (other.y + other.height / 2);
    const norm = Math.max(-1, Math.min(1, relY / (other.height / 2)));

    // Up to 60° deflection
    const maxAngle = Math.PI / 3;
    const bounce   = norm * maxAngle;

    // Horizontal direction away from the paddle
    const dir = other.x < this.x ? 1 : -1;

    // New velocity (WORLD px/s)
    this.vx = Math.cos(bounce) * speed * dir;
    this.vy = Math.sin(bounce) * speed;

    // Nudge out to avoid sticking
    if (other.x < this.x) this.x = other.x + other.width + 0.1;
    else                  this.x = other.x - this.width - 0.1;
  }

  update(dt) {
    // Keep centered while stuck
    if (this.stuck) {
      if (this.engine) {
        const W = this.engine.world.width;
        const H = this.engine.world.height;
        this.x = W / 2 - this.radius;
        this.y = H / 2 - this.radius;
      }
      return;
    }

    // Integrate (uses vx/vy set in WORLD px/s)
    super.update(dt);

    // Bounce top/bottom using WORLD height
    if (!this.engine) return;
    const H = this.engine.world.height;
    if (this.y < 0) {
      this.y = 0; this.vy = Math.abs(this.vy);
    }
    if (this.y + this.height > H) {
      this.y = H - this.height; this.vy = -Math.abs(this.vy);
    }
  }

  render(ctx) {
    // Render as a circle; Renderer already applied the viewport (WORLD→CSS)
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x + this.radius, this.y + this.radius, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}
