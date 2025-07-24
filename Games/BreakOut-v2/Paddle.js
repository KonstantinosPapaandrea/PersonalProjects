// ---- Paddle Class ----
// Simple horizontal movement based on arrow keys.

class Paddle extends GameObject {
  update(dt) {
    // Control with Arrow keys
    if (Input.isDown("ArrowLeft")) this.vx = -5;
    else if (Input.isDown("ArrowRight")) this.vx = 5;
    else this.vx = 0;

    super.update(dt);

    // Stay inside canvas bounds
    if (this.x < 0) this.x = 0;
    if (this.x + this.width > engine.canvas.width)
      this.x = engine.canvas.width - this.width;
  }
}
