// game-collisions.js
// ==================
// Improved collision logic to handle simultaneous hits (corners) properly.

const { World, Body, Events } = Matter;
import { PowerUp } from './powerup.js';

export function handleCollisions(game) {
  Events.on(game.engine, 'collisionStart', event => {
    // Map from ballBody to an object { paddleBody?, blockBodies: [], normals: [] }
    const hitMap = new Map();

    // 1) Collect all collisions in this tick
    for (const pair of event.pairs) {
      const { bodyA: A, bodyB: B, collision } = pair;
      const n = collision.normal;
      let ball, paddle, block, normal;

      // Ball ↔ Paddle?
      if (A.label === 'ball' && B.label === 'paddle') {
        ball = A; paddle = B; normal = n;
      } else if (B.label === 'ball' && A.label === 'paddle') {
        ball = B; paddle = A; normal = n;
      }
      // Ball ↔ Block?
      else if (A.label === 'ball' && B.label === 'block') {
        ball = A; block = B; normal = n;
      } else if (B.label === 'ball' && A.label === 'block') {
        ball = B; block = A;
        // flip normal so it always points out of the block into the ball
        normal = { x: -n.x, y: -n.y };
      } else {
        continue;  // not a collision we care about
      }

      // Initialize entry if needed
      if (!hitMap.has(ball)) {
        hitMap.set(ball, { paddleBody: null, blockBodies: [], normals: [] });
      }
      const data = hitMap.get(ball);

      if (paddle) {
        data.paddleBody = paddle;
      }
      if (block) {
        data.blockBodies.push(block);
        data.normals.push(normal);
      }
    }

    // 2) Process each ball exactly once
    for (const [ballBody, data] of hitMap.entries()) {
      // a) If there was a paddle hit, do that first
      if (data.paddleBody) {
        bounceOffPaddle(game, ballBody, data.paddleBody);
      }

      // b) If there were block hits, combine normals and reflect
      if (data.blockBodies.length > 0) {
        // Sum normals
        let sumX = 0, sumY = 0;
        for (const n of data.normals) {
          sumX += n.x;
          sumY += n.y;
        }
        // Normalize the sum to get a unit vector
        const mag = Math.hypot(sumX, sumY) || 1;
        const combinedNormal = { x: sumX / mag, y: sumY / mag };

        // Reflect once using the combined normal
        reflectBall(game, ballBody, combinedNormal);

        // Break each block that was hit
        for (const blockBody of data.blockBodies) {
          onBlockHit(game, blockBody);
        }
      }
    }
  });
}

function bounceOffPaddle(game, ballBody, paddleBody) {
  const halfW = game.paddle.width / 2;
  let offset = (ballBody.position.x - paddleBody.position.x) / halfW;
  offset = Math.max(-1, Math.min(1, offset));
  const angle = offset * (Math.PI / 3);

  const v0    = ballBody.velocity;
  const speed = ballBody.speed || Math.hypot(v0.x, v0.y) || 20;
  const vx    = speed * Math.sin(angle);
  const vy    = -speed * Math.cos(angle);

  Body.setVelocity(ballBody, { x: vx, y: vy });
  Body.setPosition(ballBody, {
    x: ballBody.position.x,
    y: paddleBody.position.y - (game.paddle.height/2 + ballBody.circleRadius + 1)
  });

  ballBody.speed  = speed;
  game.isLaunched = true;
}

function reflectBall(game, ballBody, normal) {
  const v0     = ballBody.velocity;
  const speed0 = ballBody.speed || Math.hypot(v0.x, v0.y);

  // reflect = v0 – 2*(v0·n)*n
  const dot = v0.x*normal.x + v0.y*normal.y;
  let vx1 = v0.x - 2*dot*normal.x;
  let vy1 = v0.y - 2*dot*normal.y;

  // renormalize magnitude back to speed0
  const speed1 = Math.hypot(vx1, vy1);
  if (speed1 > 0) {
    const factor = speed0 / speed1;
    vx1 *= factor;
    vy1 *= factor;
  }

  Body.setVelocity(ballBody, { x: vx1, y: vy1 });

  // nudge out to avoid sticking
  const push = ballBody.circleRadius + 0.5;
  Body.translate(ballBody, {
    x: normal.x * push,
    y: normal.y * push
  });

  ballBody.speed = speed0;
}

function onBlockHit(game, body) {
  const obs = game.obstacles.find(o => o.body === body);
  if (!obs || !obs.breakable) return;

  World.remove(game.world, body);
  obs.active = false;

  if (Math.random() < 0.05) {
    const { x, y } = body.position;
    game.powerups.push(new PowerUp(x, y, 'x2'));
  }
}
