// game-collisions.js
// ==================
// Handles all collision logic for the game, with debug instrumentation
// to log and visualize contact normals & depths, and robust corner‐hit handling.

const { World, Body, Events } = Matter;
import { PowerUp } from './powerup.js';

/**
 * Install collision handlers on the Matter.js engine.
 * @param {Game} game – Your main Game instance
 */
export function handleCollisions(game) {
  // Prepare a place to store debug contacts each tick
  game.debugContacts = [];

  // Listen for the very start of any collision between bodies
  Events.on(game.engine, 'collisionStart', event => {
    // We'll group collisions by ball so each ball is handled once per tick
    const hitMap = new Map();

    // 1) Gather all collisions for this physics tick
    for (const pair of event.pairs) {
      const A = pair.bodyA;
      const B = pair.bodyB;
      const col = pair.collision;
      const normal = { x: col.normal.x, y: col.normal.y };
      
      // --- Debug logging & storage ---
      console.log(
        `⚡ collision ${A.label}↔${B.label}` +
        ` depth=${col.depth.toFixed(2)}` +
        ` normal=(${normal.x.toFixed(2)},${normal.y.toFixed(2)})`
      );
      // Store the first support point and normal for on‐screen drawing
      if (col.supports && col.supports[0]) {
        const s = col.supports[0];
        game.debugContacts.push({
          x: s.x, y: s.y,
          nx: normal.x, ny: normal.y,
          depth: col.depth
        });
      }

      // --- Identify ball vs paddle/block ---
      let ballBody = null;
      let paddleBody = null;
      let blockBody = null;

      // Ball ↔ Paddle?
      if (A.label === 'ball' && B.label === 'paddle') {
        ballBody = A; paddleBody = B;
      } else if (B.label === 'ball' && A.label === 'paddle') {
        ballBody = B; paddleBody = A;
      }
      // Ball ↔ Block?
      else if (A.label === 'ball' && B.label === 'block') {
        ballBody = A; blockBody = B;
      } else if (B.label === 'ball' && A.label === 'block') {
        ballBody = B; blockBody = A;
        // Flip the normal so it always points from block → ball
        normal.x = -normal.x;
        normal.y = -normal.y;
      } else {
        // Irrelevant collision
        continue;
      }

      // Initialize the map entry for this ball if needed
      if (!hitMap.has(ballBody)) {
        hitMap.set(ballBody, {
          paddleBody: null,
          blockBodies: [],
          normals: []
        });
      }
      const data = hitMap.get(ballBody);

      // Record paddle or block hits & their normals
      if (paddleBody) {
        data.paddleBody = paddleBody;
      }
      if (blockBody) {
        data.blockBodies.push(blockBody);
        data.normals.push(normal);
      }
    }

    // 2) Process each ball's collisions exactly once
    for (const [ballBody, data] of hitMap.entries()) {
      // a) Bounce off the paddle if hit
      if (data.paddleBody) {
        bounceOffPaddle(game, ballBody, data.paddleBody);
      }

      // b) If hit one or more blocks, combine normals & reflect
      if (data.blockBodies.length > 0) {
        // Sum all normals to get combined direction
        let sumX = 0, sumY = 0;
        for (const n of data.normals) {
          sumX += n.x;
          sumY += n.y;
        }
        // Normalize to unit vector
        const mag = Math.hypot(sumX, sumY) || 1;
        const combinedNormal = { x: sumX / mag, y: sumY / mag };

        // Reflect the ball once using that combined normal
        reflectBall(game, ballBody, combinedNormal);

        // Break each block that was hit
        for (const block of data.blockBodies) {
          onBlockHit(game, block);
        }
      }
    }
  });
}

/**
 * Bounce the ball off the paddle with an angle based on hit offset.
 */
function bounceOffPaddle(game, ballBody, paddleBody) {
  // 1) Compute horizontal hit offset in [-1..1]
  const halfW = game.paddle.width / 2;
  let offset = (ballBody.position.x - paddleBody.position.x) / halfW;
  offset = Math.max(-1, Math.min(1, offset));

  // 2) Map offset to an angle ±60° from vertical
  const angle = offset * (Math.PI / 3);

  // 3) Preserve the recorded speed (or current if none recorded)
  const v0    = ballBody.velocity;
  const speed = ballBody.speed || Math.hypot(v0.x, v0.y) || 20;

  // 4) Compute new velocity components
  const vx = speed * Math.sin(angle);
  const vy = -speed * Math.cos(angle);

  // 5) Apply velocity and reposition ball just above paddle
  Body.setVelocity(ballBody, { x: vx, y: vy });
  Body.setPosition(ballBody, {
    x: ballBody.position.x,
    y: paddleBody.position.y - (game.paddle.height/2 + ballBody.circleRadius + 1)
  });

  // 6) Record speed and mark launched
  ballBody.speed  = speed;
  game.isLaunched = true;
}

/**
 * Reflect the ball’s velocity around a normal, then renormalize to preserve speed.
 */
function reflectBall(game, ballBody, normal) {
  // 1) Current velocity & ideal speed
  const v0     = ballBody.velocity;
  const speed0 = ballBody.speed || Math.hypot(v0.x, v0.y);

  // 2) Reflect formula: v1 = v0 – 2*(v0·n)*n
  const dot = v0.x * normal.x + v0.y * normal.y;
  let vx1   = v0.x - 2 * dot * normal.x;
  let vy1   = v0.y - 2 * dot * normal.y;

  // 3) Renormalize magnitude back to speed0
  const speed1 = Math.hypot(vx1, vy1);
  if (speed1 > 0) {
    const factor = speed0 / speed1;
    vx1 *= factor;
    vy1 *= factor;
  }

  // 4) Apply new velocity
  Body.setVelocity(ballBody, { x: vx1, y: vy1 });

  // 5) Nudge the ball out to avoid getting stuck in the block
  const push = ballBody.circleRadius + 0.5;
  Body.translate(ballBody, {
    x: normal.x * push,
    y: normal.y * push
  });

  // 6) Restore recorded speed for future renormalizations
  ballBody.speed = speed0;
}

/**
 * Break a block when hit and possibly spawn a power‑up.
 */
function onBlockHit(game, body) {
  const obs = game.obstacles.find(o => o.body === body);
  if (!obs || !obs.breakable) return;

  // Remove from physics world & mark inactive
  World.remove(game.world, body);
  obs.active = false;

  // 5% chance to drop an x2 power‑up at the block's center
  if (Math.random() < 0.05) {
    const { x, y } = body.position;
    game.powerups.push(new PowerUp(x, y, 'x2'));
  }
}
