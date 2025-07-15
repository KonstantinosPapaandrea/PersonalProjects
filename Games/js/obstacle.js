// obstacle.js
export class Obstacle {
    /**
     * @param {number} x 
     * @param {number} y 
     * @param {number} width 
     * @param {number} height 
     * @param {string} color 
     * @param {boolean} breakable 
     */
    constructor(x, y, width, height, color = '#e74c3c', breakable = true) {
      this.x         = x;
      this.y         = y;
      this.width     = width;
      this.height    = height;
      this.color     = color;
      this.breakable = breakable;
      this.active    = true;
    }
  
    draw(ctx) {
      if (!this.active) return;
      ctx.fillStyle = this.color;
      ctx.fillRect(this.x, this.y, this.width, this.height);
    }
  }
  