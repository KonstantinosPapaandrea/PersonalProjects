// game.js
// Main game logic, using global Matter.js (loaded via <script> in index.html)

const { Engine, World, Bodies, Body, Events } = Matter;

import { levels }   from './levels.js';
import { Ball }     from './ball.js';
import { Paddle }   from './paddle.js';
import { Obstacle } from './obstacle.js';
import { PowerUp }  from './powerup.js';

export class Game {
  /**
   * @param {string} canvasId   – ID of your <canvas>
   * @param {number} startLevel – index into levels[]
   */
  constructor(canvasId, startLevel = 0) {
    // 1) setup physics engine & disable gravity
    
    this.engine = Engine.create();
    this.world  = this.engine.world;
    this.world.gravity.x = 0;
    this.world.gravity.y = 0;
// more solver iterations → less tunneling & jitter
this.engine.positionIterations   = 10;  // default is 6
this.engine.velocityIterations   = 10;  // default is 4
this.engine.constraintIterations = 4;   // default is 2

    // 2) setup canvas & resize handler
    this.canvas = document.getElementById(canvasId);
    this.ctx    = this.canvas.getContext('2d');
    window.addEventListener('resize', () => this._onResize());

    // 3) game state
    this.currentLevel = startLevel;
    this.paddle       = null;
    this.balls        = [];
    this.powerups     = [];
    this.obstacles    = [];
    this.isLaunched   = false;  // <- track whether the ball has been served
    this.maxBalls = 500;  
    // 4) handle collisions
    Events.on(this.engine, 'collisionStart', event => {
      for (let pair of event.pairs) {
        const A = pair.bodyA, B = pair.bodyB, n = pair.collision.normal;

        // ball ↔ paddle
        if (A.label==='ball' && B.label==='paddle') {
          this._bounceOffPaddle(A, B);
          continue;
        }
        if (B.label==='ball' && A.label==='paddle') {
          this._bounceOffPaddle(B, A);
          continue;
        }

        // ball ↔ block
        if (A.label==='ball' && B.label==='block') {
          this._reflectBall(A, n);
          this._onBlockHit(B);
          continue;
        }
        if (B.label==='ball' && A.label==='block') {
          this._reflectBall(B, { x:-n.x, y:-n.y });
          this._onBlockHit(A);
          continue;
        }
      }
    });

    // 5) listen for Space to launch, only before serve
    window.addEventListener('keydown', e => {
      if (e.code === 'Space' && !this.isLaunched && this.balls[0]) {
        // give the ball its starting upward velocity
        const b = this.balls[0].body;
        const speed = 1;
        Body.setVelocity(b, { x: 0, y: -speed });
        this.isLaunched = true;
      }
    });

    // 6) initial layout & start loop
    this._onResize();
    this.lastStamp = performance.now();
  }

  /** handle window resizes: rebuild paddle, reload level */
  _onResize() {
    this.canvas.width  = window.innerWidth;
    this.canvas.height = window.innerHeight;

    // recreate paddle at bottom
    if (this.paddle && this.paddle.body) {
      World.remove(this.world, this.paddle.body);
    }
    this.paddle = new Paddle(this.world, 500, 20, 1200, this.canvas);

    // load current level (clears blocks, ball, etc.)
    this._loadLevel(this.currentLevel);
  }

  /** populate world: walls, paddle, ball(s), obstacles */
  _loadLevel(idx) {
    World.clear(this.world, false);
    World.add(this.world, this.paddle.body);

    // invisible walls top/left/right
    const w = this.canvas.width, h = this.canvas.height;
    World.add(this.world, [
      Bodies.rectangle(w/2, -10,   w, 20,  { isStatic:true }),
      Bodies.rectangle(-10, h/2,   20,  h,  { isStatic:true }),
      Bodies.rectangle(w+10, h/2,  20,  h,  { isStatic:true })
    ]);

    // reset serve state
    this.isLaunched = false;

    // spawn ball on paddle, no velocity
    this.balls = [];
    this._spawnBall();

    // build obstacles from layout
    const layout = levels[idx].layout;
    const rows   = layout.length, cols = layout[0].length, pad = 3;
    const blockW = (w - (cols+1)*pad) / cols;
    const blockH = blockW;
    this.obstacles = [];
    for (let r=0; r<rows; r++) {
      for (let c=0; c<cols; c++) {
        const code = layout[r][c];
        if (!code) continue;
        const color = code===1 ? '#e74c3c' : '#7f8c8d';
        const obs = new Obstacle(
          this.world,
          pad + c*(blockW+pad),
          pad + r*(blockH+pad),
          blockW, blockH,
          color,
          code===1
        );
        this.obstacles.push(obs);
      }
    }
  }

  /** spawn the initial ball just above the paddle, with zero velocity */
  _spawnBall() {
    const px = this.paddle.body.position.x;
    const py = this.paddle.body.position.y;
    const r  = 20;
    const ball = new Ball(this.world, px, py - r - 1, r, 0, 0);
    this.balls.push(ball);
  }

  /**
   * Reflect a ball's velocity about the normal, preserving speed,
   * and nudge it out to avoid penetration.
   */
  _reflectBall(ballBody, normal) {
  // 1) original velocity & speed
  const v0 = ballBody.velocity;
  const speed0 = Math.hypot(v0.x, v0.y);

  // 2) reflect: v1 = v0 – 2*(v0·n)*n
  const dot = v0.x * normal.x + v0.y * normal.y;
  let vx1 = v0.x - 2 * dot * normal.x;
  let vy1 = v0.y - 2 * dot * normal.y;

  // 3) renormalize magnitude
  const speed1 = Math.hypot(vx1, vy1);
  if (speed1 > 0) {
    const factor = speed0 / speed1;
    vx1 *= factor;
    vy1 *= factor;
  }

  // 4) set it
  Body.setVelocity(ballBody, { x: vx1, y: vy1 });

  // minimal nudge out to avoid re‑penetration
  const push = ballBody.circleRadius + 0.5;
  Body.translate(ballBody, {
    x: normal.x * push,
    y: normal.y * push
  });
}

  /** remove blocks, spawn power‑ups */
  _onBlockHit(body) {
    const obs = this.obstacles.find(o=>o.body===body);
    if (!obs || !obs.breakable) return;
    World.remove(this.world, body);
    obs.active = false;
    if (Math.random() < 0.05) {
      const { x,y } = body.position;
      this.powerups.push(new PowerUp(x,y,'x2'));
    }
  }

  /** per-frame update */
  update(dt) {
    // 1) paddle movement
    this.paddle.update(dt);

    // 2) if not launched, lock ball to paddle
    if (!this.isLaunched && this.balls[0]) {
      const b = this.balls[0].body;
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      Body.setPosition(b, { x: px, y: py - b.circleRadius - 1 });
    }

    // 3) physics step
    Engine.update(this.engine, dt*1000);

    // 4) remove balls that fell off
    for (let i=this.balls.length-1; i>=0; i--) {
      const b = this.balls[i].body;
      if (b.position.y - b.circleRadius > this.canvas.height) {
        World.remove(this.world, b);
        this.balls.splice(i,1);
      }
    }
    // if all lost, respawn & relaunch lock
    if (this.balls.length === 0) {
      this._spawnBall();
      this.isLaunched = false;
    }

    // 5) update & catch power‑ups
    this.powerups = this.powerups.filter(pu => {
      pu.update(dt);
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      const halfW = this.paddle.width/2, halfH = this.paddle.height/2;
      if (
        pu.y + pu.radius >= py - halfH &&
        pu.x >= px - halfW &&
        pu.x <= px + halfW
      ) {
       if (pu.type === 'x2') {
  // how many more balls we’re allowed
  const slots = this.maxBalls - this.balls.length;
  if (slots > 0) {
    // snapshot of existing balls to clone
    const existing = this.balls.slice();
    const clones = [];
    for (let i = 0; i < existing.length && clones.length < slots; i++) {
      const orig = existing[i];
      const { x, y } = orig.body.position;
      const { x: vx0, y: vy0 } = orig.body.velocity;
      const speed     = Math.hypot(vx0, vy0);
      const baseAngle = Math.atan2(vy0, vx0);
      const tilt      = (Math.random() * 2 - 1) * 0.3;
      const angle     = baseAngle + tilt;
      const vx        = speed * Math.cos(angle);
      const vy        = speed * Math.sin(angle);

      // spawn clone at same spot, then set its velocity
      const clone = new Ball(this.world, x, y, orig.radius, 0, 0);
      Body.setVelocity(clone.body, { x: vx, y: vy });
      clones.push(clone);
    }
    this.balls.push(...clones);
  }
  return false;  // remove this power‑up
}

        return false;
      }
      return pu.y - pu.radius < this.canvas.height;
    });

    // 6) next level?
    if (!this.obstacles.some(o=>o.breakable&&o.active)) {
      this.currentLevel = (this.currentLevel+1) % levels.length;
      this._loadLevel(this.currentLevel);
    }
  }

  /** draw all objects */
  draw() {
    this.ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
    this.balls      .forEach(b => b.draw(this.ctx));
    this.paddle    .draw(this.ctx);
    this.obstacles .forEach(o => o.draw(this.ctx));
    this.powerups  .forEach(p => p.draw(this.ctx));
  }

  /** main loop */
  loop = timestamp => {
    const dt = (timestamp - this.lastStamp)/1000;
    this.lastStamp = timestamp;
    this.update(dt);
    this.draw();
    requestAnimationFrame(this.loop);
  }

  /** start the game */
  start() {
    this.lastStamp = performance.now();
    this.loop(this.lastStamp);
  }
// game.js
// …inside your Game class…

/**
 * Perfectly reflect v about normal n, then renormalize to original speed.
 */


/**
 * Bounce off paddle with angle control, then renormalize.
 */
_bounceOffPaddle(ballBody, paddleBody) {
  // original velocity & speed
  const v0 = ballBody.velocity;
  const speed0 = Math.hypot(v0.x, v0.y) || 25;

  // compute hit offset ∈ [-1..1]
  const halfW = this.paddle.width / 2;
  let normX = (ballBody.position.x - paddleBody.position.x) / halfW;
  normX = Math.max(-1, Math.min(1, normX));

  // map to angle ±60° from vertical
  const angle = normX * (Math.PI / 3);
  let vx1 = speed0 * Math.sin(angle);
  let vy1 = -speed0 * Math.cos(angle);

  // renormalize (usually unnecessary here, but for consistency)
  const speed1 = Math.hypot(vx1, vy1);
  if (speed1 > 0) {
    const factor = speed0 / speed1;
    vx1 *= factor;
    vy1 *= factor;
  }

  // apply
  Body.setVelocity(ballBody, { x: vx1, y: vy1 });

  // nudge up out of the paddle
  Body.setPosition(ballBody, {
    x: ballBody.position.x,
    y: paddleBody.position.y - (this.paddle.height / 2 + ballBody.circleRadius + 1)
  });

  this.isLaunched = true;
}


}
