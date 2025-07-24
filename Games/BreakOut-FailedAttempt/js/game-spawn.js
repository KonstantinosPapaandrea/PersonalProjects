// game‑spawn.js

import { Ball } from './ball.js';

/**
 * Spawns one Ball directly above the paddle, with zero velocity.
 * Must be installed as a method: Game.prototype._spawnBall = spawnBall;
 */
export function spawnBall() {
  // `this` is the Game instance
  const px = this.paddle.body.position.x;
  const py = this.paddle.body.position.y;
  const r  = 15;

  // create & add
  const ball = new Ball(this.world, px, py - r - 1, r, 0, 0);
  this.balls.push(ball);

  // note: ball.speed stays 0 until the user serves
}
