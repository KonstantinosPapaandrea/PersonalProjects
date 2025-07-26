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
    this.collider = true; // ✅ participates in collisions
  }

  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  onCollision(other) {
    // ✅ Override in subclasses (e.g., Ball vs Brick)
  }

  destroy() {
    this.active = false;
  }
}
