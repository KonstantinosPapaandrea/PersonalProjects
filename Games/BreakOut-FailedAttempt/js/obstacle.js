// obstacle.js
// Wraps a static rectangle as your block.
// Uses global Matter (loaded via <script> in index.html).

const { Bodies, World } = Matter;

export class Obstacle {
  /**
   * @param {Matter.World} world
   * @param {number} x      top-left X
   * @param {number} y      top-left Y
   * @param {number} w      width
   * @param {number} h      height
   * @param {string} color
   * @param {boolean} breakable
   */
  constructor(world, x, y, w, h, color, breakable) {
    this.width     = w;
    this.height    = h;
    this.color     = color;
    this.breakable = breakable;
    this.active    = true;

    // Give the block restitution=1 and zero friction so the ball
    // bounces off at full speed.
    this.body = Bodies.rectangle(
      x + w/2,
      y + h/2,
      w, h,
      {
         isStatic: true,
  restitution: 1,
  friction: 0,
  frictionStatic: 0,
  label: 'block'
      }
    );
    World.add(world, this.body);
  }

  /** Draw the block on a CanvasRenderingContext2D */
  draw(ctx) {
    if (!this.active) return;
    const { x, y } = this.body.position;
    ctx.fillStyle = this.color;
    ctx.fillRect(
      x - this.width/2,
      y - this.height/2,
      this.width,
      this.height
    );
  }
}
