// paddle.js

export class Paddle {
    /**
     * @param {number} width
     * @param {number} height
     * @param {number} speed  // pixels per second
     * @param {CanvasRenderingContext2D} ctx
     */
    constructor(width, height, speed, canvas) {
      this.width = width;
      this.height = height;
      this.speed = speed;
      this.canvas = canvas;
  
      // Start centred on the bottom
      this.x = (canvas.width - width) / 2;
      this.y = canvas.height - height - 10;
  
      // Input state
      this.movingLeft = false;
      this.movingRight = false;
  
      // Listen for arrow keys
      window.addEventListener('keydown', e => {
        if (e.code === 'ArrowLeft')  this.movingLeft  = true;
        if (e.code === 'ArrowRight') this.movingRight = true;
      });
      window.addEventListener('keyup', e => {
        if (e.code === 'ArrowLeft')  this.movingLeft  = false;
        if (e.code === 'ArrowRight') this.movingRight = false;
      });
    }
  
    update(dt) {
      if (this.movingLeft)  this.x -= this.speed * dt;
      if (this.movingRight) this.x += this.speed * dt;
  
      // Clamp inside canvas
      this.x = Math.max(0, Math.min(this.canvas.width - this.width, this.x));
    }
  
    draw(ctx) {
      ctx.fillStyle = '#2ecc71';
      ctx.fillRect(this.x, this.y, this.width, this.height);
    }
  }
  