// paddle.js
// Wraps a static rectangle as your paddle.
// Uses global Matter (loaded via <script> in index.html).

// Pull in the parts of Matter.js we need from the global `Matter` object
const { Bodies, Body, World } = Matter;

export class Paddle {
  /**
   * @param {Matter.World} world
   * @param {number} width
   * @param {number} height
   * @param {number} speed      px per second
   * @param {HTMLCanvasElement} canvas
   */
  constructor(world, width, height, speed, canvas) {
    this.width  = width;
    this.height = height;
    this.speed  = speed;
    this.canvas = canvas;

    // Create a static rectangle body.  We add restitution=1 so it bounces,
    // and zero friction so the ball doesn't lose speed on contact.
    this.body = Bodies.rectangle(
      canvas.width / 2,
      canvas.height - height / 2 - 10,
      width,
      height,
      {
        isStatic: true,
        label: 'paddle',
        restitution: 1,    // perfect bounce
        friction: 0,       // no surface drag
        frictionStatic: 0
      }
    );
    World.add(world, this.body);

    // Track left/right arrow input
    this.moveLeft  = false;
    this.moveRight = false;
    window.addEventListener('keydown', e => {
      if (e.code === 'ArrowLeft')  this.moveLeft  = true;
      if (e.code === 'ArrowRight') this.moveRight = true;
    });
    window.addEventListener('keyup', e => {
      if (e.code === 'ArrowLeft')  this.moveLeft  = false;
      if (e.code === 'ArrowRight') this.moveRight = false;
    });
  }

  /**
   * Reposition the paddle each frame based on input.
   * @param {number} dt  seconds since last frame
   */
  update(dt) {
    let dx = 0;
    if (this.moveLeft)  dx = -this.speed * dt;
    if (this.moveRight) dx =  this.speed * dt;

    const pos = this.body.position;
    const halfW = this.width / 2;
    // Clamp new X within [halfW, canvas.width - halfW]
    const nx = Math.max(
      halfW,
      Math.min(this.canvas.width - halfW, pos.x + dx)
    );
    Body.setPosition(this.body, { x: nx, y: pos.y });
  }

  /**
   * Draw the paddle on a CanvasRenderingContext2D.
   * @param {CanvasRenderingContext2D} ctx
   */
  draw(ctx) {
    const { x, y } = this.body.position;
    ctx.fillStyle = '#2ecc71';
    ctx.fillRect(
      x - this.width / 2,
      y - this.height / 2,
      this.width,
      this.height
    );
  }
}
