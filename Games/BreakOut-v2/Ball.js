// File: Ball.js
import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input }      from "../gameEngine/core/Input.js";
import { Brick }      from "./Brick.js";

export class Ball extends GameObject {
  constructor(x, y, radius, color = "red") {
    // Store as a box for Physics/AABB; width/height are diameter
    super(x, y, radius * 2, radius * 2, color);

    // --- Ball properties ------------------------------------------------------
    this.radius = radius;
    this.stuck  = true;     // starts attached above the paddle
    this.paddle = null;     // paddle reference (set from game)
    this.vx = 0; this.vy = 0;

    // --- Physics / collision grouping ----------------------------------------
    this.collisionGroup = "ball";
    this.collidesWith   = ["brick", "paddle"]; // checks only these groups

    // Use engine Physics substepping/CCD; we only predict wall hits here
    this.useCCD         = true;   // request swept AABB for high-speed safety
    this.substepEnabled = true;   // Physics can substep us if needed
    this.maxMoveRatio   = 0.3;    // be a bit stricter than default for small ball
    this.stayInWorld    = false;  // we bounce ourselves; Physics clamp is for paddles
  }

  update(dt) {
    // --- 1) Handle "stuck to paddle" launch ----------------------------------
    if (this.stuck && this.paddle) {
      // Follow paddle horizontally
      this.x = this.paddle.x + this.paddle.width / 2 - this.radius;
      this.y = this.paddle.y - this.height - 2;

      // Launch with Space (keep using Input.isKeyDown per your game)
      if (Input.isKeyDown(" ")) {
        this.stuck = false;
        this.vx = 0;
        this.vy = -8; // start upward
      }
      return; // don't predict walls while stuck
    }

    // --- 2) Predictive wall checks (before Physics integrates this frame) ----
    // We DO NOT move here; Physics integrates after update().
    const W = this.engine.world.width;
    const H = this.engine.world.height;

    // Clamp maximum speed to keep CCD robust and gameplay sane
    const MAX_SPEED = 10;
    this.vx = Math.max(-MAX_SPEED, Math.min(this.vx, MAX_SPEED));
    this.vy = Math.max(-MAX_SPEED, Math.min(this.vy, MAX_SPEED));

    // Predict next position for this frame (Physics will apply exactly this)
    const nextX = this.x + this.vx * dt;
    const nextY = this.y + this.vy * dt;

    // Left/right walls: invert vx if we would cross this frame
    if (nextX < 0) {
      this.vx = Math.abs(this.vx);            // reflect to the right
    } else if (nextX + this.width > W) {
      this.vx = -Math.abs(this.vx);           // reflect to the left
    }

    // Top wall: invert vy if we would cross this frame
    if (nextY < 0) {
      this.vy = Math.abs(this.vy);            // reflect downward
    }

    // Bottom: if we would leave the world, mark for removal after Physics moves
    if (nextY + this.height > H) {
      // Let Physics move us this frame; on the very next update we’ll be > H
      // and we can kill the ball cleanly. Or do it now:
      this.active = false;                     // mark inactive
      // If this was the last ball → stop the game (use GSM in your flow)
      const anyLeft = this.engine.objects.some(o => o.constructor?.name === "Ball" && o.active);
      if (!anyLeft) {
        console.log("Game Over");
        // Consider using GameStateManager.setState("init") or a proper game-over
      }
    }
  }

  // Broad filter keeps noise down (Physics still checks collidesWith)
  canCollideWith(other) {
    return other.constructor.name !== "Ball" && other.constructor.name !== "PowerUp";
  }

  onCollision(other) {
    // --- Paddle bounce --------------------------------------------------------
    if (other.constructor.name === "Paddle") {
      // Always bounce upward
      this.vy = -Math.abs(this.vy);

      // Horizontal control based on hit position relative to paddle center
      const hitPos = (this.x + this.radius - (other.x + other.width / 2)) / (other.width / 2);
      this.vx = hitPos * 5; // tweak for feel
    }

    // --- Brick bounce + brick removal ----------------------------------------
    if (other instanceof Brick) {
      // Basic response: flip axis of greater penetration
      const overlapX = (this.x + this.width  / 2 < other.x + other.width  / 2)
        ? this.x + this.width  - other.x
        : other.x + other.width - this.x;
      const overlapY = (this.y + this.height / 2 < other.y + other.height / 2)
        ? this.y + this.height - other.y
        : other.y + other.height - this.y;

      if (overlapX < overlapY) {
        this.vx = (this.x + this.width / 2 < other.x + other.width / 2)
          ? -Math.abs(this.vx) : Math.abs(this.vx);
      } else {
        this.vy = (this.y + this.height / 2 < other.y + other.height / 2)
          ? -Math.abs(this.vy) : Math.abs(this.vy);
      }
      // Brick handles its own destroy/power‑up logic in Brick.onCollision
    }
  }

  render(ctx) {
    // Draw a circle in world space; Renderer has already applied viewport
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x + this.radius, this.y + this.radius, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}
