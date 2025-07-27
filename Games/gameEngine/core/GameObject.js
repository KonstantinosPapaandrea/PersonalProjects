export class GameObject {
  constructor(x, y, width, height, color = "white") {
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
    this.color = color;
    this.vx = 0;
    this.vy = 0;
    this.active = true;
    this.collider = true;
    this.engine = null;

    this.static = false; // ✅ If true, object never moves (e.g., bricks, walls)
  }

  update(dt) {
    if (!this.static) {
      this.x += this.vx * dt;
      this.y += this.vy * dt;
    }
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  onCollision(other) {}
  canCollideWith(other) {
    return true;
  }

  destroy() {
    this.active = false;
  }
}
