class Ball extends GameObject {
  constructor(x, y, radius, color) {
    super(x, y, radius * 2, radius * 2, color);
    this.radius = radius;
    this.stuck = true;
    this.vx = 0;
    this.vy = 0;
  }

  update(dt) {
    if (this.stuck) {
      this.x = paddle.x + paddle.width / 2 - this.radius;
      this.y = paddle.y - this.height - 2;

      if (Input.isDown(" ")) {
        this.stuck = false;
        this.vx = 0;
        this.vy = -20;
      }
      return;
    }

    super.update(dt);

    if (this.x < 0 || this.x + this.width > engine.canvas.width) this.vx *= -1;
    if (this.y < 0) this.vy *= -1;
    if (this.y + this.height > engine.canvas.height) {
      console.log("Game Over");
      engine.running = false;
    }
  }

  onCollision(other) {
    if (other instanceof Paddle) {
      this.vy = -Math.abs(this.vy);
      let hitPos = (this.x + this.radius - (other.x + other.width / 2)) / (other.width / 2);
      this.vx = hitPos * 4;
    }

    if (other instanceof Brick) {
      other.destroy();

      // ✅ Proper side detection
      const overlapX = (this.x + this.width / 2 < other.x + other.width / 2)
        ? (this.x + this.width - other.x)
        : (other.x + other.width - this.x);

      const overlapY = (this.y + this.height / 2 < other.y + other.height / 2)
        ? (this.y + this.height - other.y)
        : (other.y + other.height - this.y);

   if (overlapX < overlapY) {
  // Hitting from the sides → flip horizontally, keep vertical direction
  this.vx = (this.x + this.width / 2 < other.x + other.width / 2)
    ? -Math.abs(this.vx) // coming from left → go left
    : Math.abs(this.vx); // coming from right → go right
} else {
  // Hitting top/bottom → flip vertically, keep horizontal direction
  this.vy = (this.y + this.height / 2 < other.y + other.height / 2)
    ? -Math.abs(this.vy) // coming from top → go up
    : Math.abs(this.vy); // coming from bottom → go down
}

      console.log(this.vx," ",this.vy);
    }
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x + this.radius, this.y + this.radius, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}
