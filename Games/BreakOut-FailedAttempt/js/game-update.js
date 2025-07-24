// game-update.js
// ================
// This function runs once per frame to update all moving parts of the game.
// `dt` (delta time) is the time in seconds since the last frame.

const { Engine, World, Body } = Matter;        // Matter.js physics engine
import { Ball }   from './ball.js';            // our Ball class
import { levels } from './levels.js';          // level layouts

export default function updateGame(dt) {
  // ────────────────────────────────────────────────────────────────────────────
  // a) Move the paddle
  //    The Paddle class reads keyboard/mouse and updates its position.
  // ────────────────────────────────────────────────────────────────────────────
  this.paddle.update(dt);

  // ────────────────────────────────────────────────────────────────────────────
  // b) Lock the first ball to the paddle until the player presses Space
  //    We keep the ball hovering just above the paddle if it hasn't been launched.
  // ────────────────────────────────────────────────────────────────────────────
  if (!this.isLaunched && this.balls[0]) {
    const ballBody = this.balls[0].body;
    const px = this.paddle.body.position.x;
    const py = this.paddle.body.position.y;
    // Place the ball right above the paddle each frame
    Body.setPosition(ballBody, {
      x: px,
      y: py - ballBody.circleRadius - 1
    });
  }

  // ────────────────────────────────────────────────────────────────────────────
  // c) Physics step
  //    Advance the Matter.js engine by dt*1000 milliseconds.
  // ────────────────────────────────────────────────────────────────────────────
  Engine.update(this.engine, dt * 1000);

  // ────────────────────────────────────────────────────────────────────────────
  // d) Renormalize ball speeds
  //    Solve tiny speed losses by resetting each ball to its recorded ideal speed.
  // ────────────────────────────────────────────────────────────────────────────
  this.balls.forEach(ball => {
    const v   = ball.body.velocity;         // current velocity {x, y}
    const cur = Math.hypot(v.x, v.y);       // current speed magnitude
    // only if we've recorded an ideal speed
    if (ball.speed > 0 && cur > 0) {
      const factor = ball.speed / cur;      // scale factor to restore speed
      Body.setVelocity(ball.body, {
        x: v.x * factor,
        y: v.y * factor
      });
    }
  });

  // ────────────────────────────────────────────────────────────────────────────
  // e) Remove balls that fell off the bottom
  //    If a ball's bottom goes past the canvas height, delete it.
  // ────────────────────────────────────────────────────────────────────────────
  for (let i = this.balls.length - 1; i >= 0; i--) {
    const b = this.balls[i].body;
    if (b.position.y - b.circleRadius > this.canvas.height) {
      World.remove(this.world, b); // remove from physics world
      this.balls.splice(i, 1);     // remove from our array
    }
  }
  // If no balls remain, spawn a new one (locked) and wait for serve
  if (this.balls.length === 0) {
    this._spawnBall();
    this.isLaunched = false;
  }

  // ────────────────────────────────────────────────────────────────────────────
  // f) Update & catch power‑ups
  //    1) Move each power‑up downward.
  //    2) Remove if it falls off screen.
  //    3) If caught by paddle, apply effect (e.g. x2 power‑up).
  // ────────────────────────────────────────────────────────────────────────────
  this.powerups = this.powerups.filter(pu => {
    pu.update(dt);  // advance vertical position by vy * dt

    // 1) Off-screen? drop it.
    if (pu.y - pu.radius > this.canvas.height) {
      return false;
    }

    // 2) Check paddle catch
    const px    = this.paddle.body.position.x;
    const py    = this.paddle.body.position.y;
    const halfW = this.paddle.width  / 2;
    const halfH = this.paddle.height / 2;

    const caught =
      pu.y + pu.radius >= py - halfH && // bottom of pu reaches top of paddle
      pu.x >= px - halfW &&             // pu x within left edge
      pu.x <= px + halfW;               // pu x within right edge

    if (caught) {
      if (pu.type === 'x2') {
        // Duplicate balls up to the max limit
        let slots   = this.maxBalls - this.balls.length;
        const existing = this.balls.slice(); // copy of current balls

        for (let i = 0; i < existing.length && slots > 0; i++) {
          const orig     = existing[i];
          const { x, y } = orig.body.position;
          const { x: vx0, y: vy0 } = orig.body.velocity;

          // Determine speed & angle of original ball
          const speed     = orig.speed || Math.hypot(vx0, vy0);
          const baseAngle = Math.atan2(vy0, vx0);
          // Add a small random tilt ±0.3 rad
          const tilt      = (Math.random() * 2 - 1) * 0.3;
          const angle     = baseAngle + tilt;

          // Compute new velocity components
          const vx = speed * Math.cos(angle);
          const vy = speed * Math.sin(angle);

          // Spawn the clone with the same speed & random tilt
          const clone = new Ball(this.world, x, y, orig.radius, vx, vy);
          clone.speed = speed;  // record its ideal speed
          this.balls.push(clone);
          slots--;
        }
      }
      return false; // remove this power‑up from the array
    }

    // 3) Otherwise keep it
    return true;
  });

  // ────────────────────────────────────────────────────────────────────────────
  // g) Level progression
  //    If no breakable obstacles remain, advance to the next level layout.
  // ────────────────────────────────────────────────────────────────────────────
  const anyLeft = this.obstacles.some(o => o.breakable && o.active);
  if (!anyLeft) {
    this.currentLevel = (this.currentLevel + 1) % levels.length;
    this._loadLevel(this.currentLevel);
  }
}
