// game-draw.js
// =============
// Responsible for all the drawing/rendering each frame.
// It clears the canvas, then draws balls (with optional velocity arrows),
// the paddle, all obstacles, and any active power‑ups.

import { drawArrow } from './utils.js';  // helper to draw arrows

export default function drawGame() {
  // 1) Clear the entire canvas before drawing the new frame
  //    This prevents “ghosting” of previous frames.
  this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

  // 2) Draw each ball and its velocity arrow
  //    - b.draw(...) renders the ball circle
  //    - We then overlay a yellow arrow showing its current velocity vector
  this.balls.forEach(b => {
    // a) Draw the ball itself
    b.draw(this.ctx);

    // b) Compute arrow start (ball center) and direction/length
    const { x, y }         = b.body.position;   // current center of ball
    const { x: vx, y: vy } = b.body.velocity;   // current velocity vector
    const speed = Math.hypot(vx, vy);           // magnitude of velocity

    // Only draw arrow if the ball is moving
    /*if (speed > 0) {
      const arrowScale = 10;    // pixels of arrow per px/s of speed
      const minLen     = 30;    // minimum arrow length so it’s always visible
      const baseLen    = speed * arrowScale;
      const len        = Math.max(baseLen, minLen);  // enforce min length

      // Normalize velocity to get direction unit vector
      const ux = vx / speed;
      const uy = vy / speed;

      // Compute arrow endpoint = start + direction * length
      const toX = x + ux * len;
      const toY = y + uy * len;

      // Draw the arrow in yellow, 2px thick
      this.ctx.strokeStyle = 'yellow';
      this.ctx.lineWidth   = 2;
      drawArrow(this.ctx, x, y, toX, toY);
    }*/
  });

  // 3) Draw the paddle
  //    The Paddle class knows how to render itself given the 2D context.
  this.paddle.draw(this.ctx);

  // 4) Draw all obstacles (blocks)
  //    Some are breakable (red), some unbreakable (gray).
  this.obstacles.forEach(o => o.draw(this.ctx));

  // 5) Draw active power‑ups
  //    These are little falling circles (e.g. the x2 power‑up).
  this.powerups.forEach(p => p.draw(this.ctx));
}
