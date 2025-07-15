// ball.js
export class Ball {
    constructor(x, y, radius, vx, vy) {
      this.initial = { x, y, vx, vy };
      this.x = x;
      this.y = y;
      this.radius = radius;
      this.vx = vx;
      this.vy = vy;
    }
  
    update(dt, canvasWidth, canvasHeight) {
      this.x += this.vx * dt;
      this.y += this.vy * dt;
  
      // Bounce off left/right
      if (this.x + this.radius > canvasWidth || this.x - this.radius < 0) {
        this.vx *= -1;
        this.x = Math.max(this.radius, Math.min(canvasWidth - this.radius, this.x));
      }
      // Bounce off top
      if (this.y - this.radius < 0) {
        this.vy *= -1;
        this.y = this.radius;
      }
      // **Note:** We no longer bounce off bottom here—Game handles misses.
    }
  
    draw(ctx) {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = '#3498db';
      ctx.fill();
      ctx.closePath();
    }
  
    /** Reset position & velocity back to initial values */
    reset() {
      this.x  = this.initial.x;
      this.y  = this.initial.y;
      this.vx = this.initial.vx * (Math.random() > 0.5 ? 1 : -1); // randomize direction
      this.vy = this.initial.vy * -1; // always start moving upward
    }
  }
  