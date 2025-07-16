// powerup.js

export class PowerUp {
    /**
     * @param {number} x         – spawn X (center)
     * @param {number} y         – spawn Y (center)
     * @param {string} type      – e.g. 'x2'
     */
    constructor(x, y, type = 'x2') {
      this.x      = x;
      this.y      = y;
      this.radius = 10;
      this.type   = type;
      this.vy     = 200;   // fall speed px/s
      this.active = true;
    }
  
    /** fall straight down */
    update(dt) {
      this.y += this.vy * dt;
    }
  
    /** draw a golden circle with label */
    draw(ctx) {
      if (!this.active) return;
      // circle
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = 'gold';
      ctx.fill();
      ctx.closePath();
      // label
      ctx.fillStyle = 'black';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(this.type, this.x, this.y + 4);
    }
  }
  