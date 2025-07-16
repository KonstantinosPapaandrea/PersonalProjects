// ball.js
// =======
// Wraps a Matter.js circle as your Ball.

const { Bodies, Body, World } = Matter;

export class Ball {
  /**
   * @param {Matter.World} world
   * @param {number} x
   * @param {number} y
   * @param {number} radius
   * @param {number} vx
   * @param {number} vy
   */
  constructor(world, x, y, radius, vx, vy) {
    this.radius = radius;

    // Create the ball body: restitution/friction as before,
    // plus collisionFilter.group = -1 so balls never collide with each other.
    this.body = Bodies.circle(x, y, radius, {
      restitution:    1,
      friction:       0,
      frictionStatic: 0,
      frictionAir:    0,
      label:          'ball',
      collisionFilter: {
        group: -1
      }
    });

    World.add(world, this.body);
    Body.setVelocity(this.body, { x: vx, y: vy });
  }

  draw(ctx) {
    const { x, y } = this.body.position;
    ctx.beginPath();
    ctx.arc(x, y, this.radius, 0, Math.PI * 2);
    ctx.fillStyle = '#f3f3f3';
    ctx.fill();
  }
}
