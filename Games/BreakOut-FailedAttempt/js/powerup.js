// powerup.js
// A falling power‑up that the paddle can catch.

export class PowerUp {
  /**
   * @param {number} x
   * @param {number} y
   * @param {string} type  e.g. 'x2'
   */
  constructor(x, y, type = 'x2') {
    this.x      = x;
    this.y      = y;
    this.radius = 50;
    this.type   = type;
    this.vy     = 200;  // px/s fall speed
    this.active = true;
  }

  /** Fall straight down */
  update(dt) {
    this.y += this.vy * dt;
  }

  /** Draw on a CanvasRenderingContext2D */
  draw(ctx) {
    if (!this.active) return;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fillStyle = 'gold';
    ctx.fill();
    ctx.closePath();
    ctx.fillStyle = 'black';
    ctx.font = '50px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(this.type, this.x, this.y + 4);
  }
}
