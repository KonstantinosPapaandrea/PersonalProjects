// ==============================
// BREAKOUT GAME IMPLEMENTATION
// ==============================

// ---- Ball Class ----
// Extends GameObject and overrides update/render for circular shape and collisions.

class Ball extends GameObject {
  constructor(x, y, radius, color) {
    super(x, y, radius * 2, radius * 2, color);  // Still uses GameObject width/height
    this.radius = radius;
    this.vx = 3;    // Ball starts moving diagonally
    this.vy = -3;
  }

  update(dt) {
    super.update(dt);  // Moves based on velocity

    // ---- Wall Collisions ----
    if (this.x < 0 || this.x + this.width > engine.canvas.width) {
      this.vx *= -1; // Bounce horizontally
    }
    if (this.y < 0) {
      this.vy *= -1; // Bounce from top wall
    }
    if (this.y + this.height > engine.canvas.height) {
      console.log("Game Over");
      engine.running = false; // Stop the engine
    }

    // ---- Paddle Collision ----
    if (isColliding(this, paddle)) {
      this.vy = -Math.abs(this.vy); // Always bounce upwards
    }

    // ---- Brick Collisions ----
    bricks.forEach((brick, i) => {
      if (brick.active && isColliding(this, brick)) {
        brick.destroy();
        this.vy *= -1;       // Bounce vertically
      }
    });
  }

  render(ctx) {
    // Draw a circle instead of a rectangle
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x + this.radius, this.y + this.radius, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}
