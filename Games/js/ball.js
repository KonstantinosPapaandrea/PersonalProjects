// ball.js
// =======
const { Bodies, Body, World } = Matter;

export class Ball {
  constructor(world, x, y, radius, vx, vy) {
    this.radius = radius;
    this.body = Bodies.circle(x, y, radius, {
      restitution:    1,
      friction:       0,
      frictionStatic: 0,
      frictionAir:    0,
      label:          'ball',
      collisionFilter:{ group: -1 }
    });
    World.add(world, this.body);

    // 1) set initial velocity
    Body.setVelocity(this.body, { x: vx, y: vy });
    // 2) remember its “ideal” speed
    this.speed = Math.hypot(vx, vy);
  }

  draw(ctx) {
    const { x, y } = this.body.position;
    ctx.beginPath();
    ctx.arc(x, y, this.radius, 0, Math.PI*2);
    ctx.fillStyle = '#3498db';
    ctx.fill();
  }
}
