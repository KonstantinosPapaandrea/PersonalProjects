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
    this.static = false; // ✅ Mark for static objects like bricks

    this.engine = null;
    if (!GameObject._nextId) GameObject._nextId = 1;
    this._id = GameObject._nextId++;
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
    return true; // override in subclasses
  }

  destroy() {
    this.active = false;
  }
}
