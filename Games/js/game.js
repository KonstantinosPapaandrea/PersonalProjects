// game.js
// Main game logic, using global Matter.js (loaded via <script> in index.html)

const { Engine, World, Bodies, Body, Events } = Matter;
import { drawArrow } from './utils.js';
import { levels }    from './levels.js';
import { Ball }      from './ball.js';
import { Paddle }    from './paddle.js';
import { Obstacle }  from './obstacle.js';
import { PowerUp }   from './powerup.js';

export class Game {
  // bound game loop, so `this` remains correct when passed to requestAnimationFrame
  loop = (timestamp) => {
    const dt = (timestamp - this.lastStamp) / 1000;
    this.lastStamp = timestamp;
    this.update(dt);
    this.draw();
    requestAnimationFrame(this.loop);
  };

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
    // increase solver accuracy
    this.engine.positionIterations   = 10;
    this.engine.velocityIterations   = 10;
    this.engine.constraintIterations = 4;

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
    this.isLaunched   = false;   // track serve state
    this.maxBalls     = 50;      // cap on simultaneous live balls

    // 4) handle collisions
    Events.on(this.engine, 'collisionStart', event => {
      for (const pair of event.pairs) {
        const A = pair.bodyA, B = pair.bodyB;
        const n = pair.collision.normal;

        // Ball ↔ Paddle
        if (A.label === 'ball' && B.label === 'paddle') {
          this._bounceOffPaddle(A, B);
          continue;
        }
        if (B.label === 'ball' && A.label === 'paddle') {
          this._bounceOffPaddle(B, A);
          continue;
        }

        // Ball ↔ Block
        if (A.label === 'ball' && B.label === 'block') {
          this._reflectBall(A, n);
          this._onBlockHit(B);
          continue;
        }
        if (B.label === 'ball' && A.label === 'block') {
          this._reflectBall(B, { x: -n.x, y: -n.y });
          this._onBlockHit(A);
          continue;
        }
      }
    });

    // 5) Spacebar to serve, only before launch
    window.addEventListener('keydown', e => {
      if (e.code === 'Space' && !this.isLaunched && this.balls[0]) {
        const b = this.balls[0].body;
        const speed = 20;
        Body.setVelocity(b, { x: 0, y: -speed });
        this.isLaunched = true;
      }
    });

    // 6) initial layout & start loop
    this._onResize();
    this.lastStamp = performance.now();
  }

  /** handle window resizes: rebuild paddle & reload level */
  _onResize() {
    this.canvas.width  = window.innerWidth;
    this.canvas.height = window.innerHeight;

    // recreate paddle at bottom
    if (this.paddle && this.paddle.body) {
      World.remove(this.world, this.paddle.body);
    }
    this.paddle = new Paddle(this.world, 500, 20, 800, this.canvas);

    // load current level (clears blocks, ball, etc.)
    this._loadLevel(this.currentLevel);
  }

  /** populate world: walls, paddle, ball(s), obstacles */
  _loadLevel(idx) {
    World.clear(this.world, false);
    World.add(this.world, this.paddle.body);

    // invisible walls (top, left, right)
    const w = this.canvas.width, h = this.canvas.height;
    World.add(this.world, [
      Bodies.rectangle(w/2, -10,   w, 20, { isStatic:true }),
      Bodies.rectangle(-10, h/2,   20,  h, { isStatic:true }),
      Bodies.rectangle(w+10, h/2,  20,  h, { isStatic:true })
    ]);

    // reset serve state & spawn ball on paddle
    this.isLaunched = false;
    this.balls = [];
    this._spawnBall();

    // build obstacles grid
    const layout = levels[idx].layout;
    const rows   = layout.length, cols = layout[0].length, pad = 3;
    const blockW = (w - (cols + 1) * pad) / cols;
    const blockH = blockW;

    this.obstacles = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const code = layout[r][c];
        if (!code) continue;
        const color     = code === 1 ? '#e74c3c' : '#7f8c8d';
        const breakable = code === 1;
        const obs = new Obstacle(
          this.world,
          pad + c * (blockW + pad),
          pad + r * (blockH + pad),
          blockW, blockH,
          color,
          breakable
        );
        this.obstacles.push(obs);
      }
    }
  }

  /** spawn the initial ball just above the paddle, with zero velocity */
  _spawnBall() {
    const px = this.paddle.body.position.x;
    const py = this.paddle.body.position.y;
    const r  = 15;
    const ball = new Ball(this.world, px, py - r - 1, r, 0, 0);
    this.balls.push(ball);
  }

  /**
   * Custom bounce off paddle:
   * - horizontal vel based on hit offset
   * - preserves speed
   */
  _bounceOffPaddle(ballBody, paddleBody) {
    // measure offset [-1..1]
    const halfW = this.paddle.width / 2;
    let normX = (ballBody.position.x - paddleBody.position.x) / halfW;
    normX = Math.max(-1, Math.min(1, normX));

    // map offset to ±60° from vertical
    const maxAngle = Math.PI / 3;
    const angle    = normX * maxAngle;

    // preserve pre‑bounce speed
    const v0 = ballBody.velocity;
    const speed = Math.hypot(v0.x, v0.y) || 20;

    const vx = speed * Math.sin(angle);
    const vy = -speed * Math.cos(angle);
    Body.setVelocity(ballBody, { x: vx, y: vy });

    // nudge out of overlap
    Body.setPosition(ballBody, {
      x: ballBody.position.x,
      y: paddleBody.position.y - (this.paddle.height/2 + ballBody.circleRadius + 1)
    });

    this.isLaunched = true;
  }

  /**
   * Perfect reflection about normal + speed renormalization
   */
  _reflectBall(ballBody, normal) {
    const v0 = ballBody.velocity;
    const speed0 = Math.hypot(v0.x, v0.y);

    // reflect v0 → v1
    const dot = v0.x * normal.x + v0.y * normal.y;
    let vx1 = v0.x - 2 * dot * normal.x;
    let vy1 = v0.y - 2 * dot * normal.y;

    // renormalize to original speed
    const speed1 = Math.hypot(vx1, vy1);
    if (speed1 > 0) {
      const factor = speed0 / speed1;
      vx1 *= factor;
      vy1 *= factor;
    }

    Body.setVelocity(ballBody, { x: vx1, y: vy1 });

    // minimal nudge out
    const push = ballBody.circleRadius + 0.5;
    Body.translate(ballBody, {
      x: normal.x * push,
      y: normal.y * push
    });
  }

  /** remove breakable blocks & maybe spawn power‑up */
  _onBlockHit(body) {
    const obs = this.obstacles.find(o => o.body === body);
    if (!obs || !obs.breakable) return;
    World.remove(this.world, body);
    obs.active = false;
    // 5% drop chance
    if (Math.random() < 0.05) {
      const { x, y } = body.position;
      this.powerups.push(new PowerUp(x, y, 'x2'));
    }
  }

  /** per-frame update */
  update(dt) {
    // 1) paddle moves
    this.paddle.update(dt);

    // 2) lock ball to paddle until launch
    if (!this.isLaunched && this.balls[0]) {
      const b = this.balls[0].body;
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      Body.setPosition(b, { x: px, y: py - b.circleRadius - 1 });
    }

    // 3) step physics
    Engine.update(this.engine, dt * 1000);

    // 4) remove fallen balls
    for (let i = this.balls.length - 1; i >= 0; i--) {
      const b = this.balls[i].body;
      if (b.position.y - b.circleRadius > this.canvas.height) {
        World.remove(this.world, b);
        this.balls.splice(i, 1);
      }
    }
    // if none left, respawn & relock
    if (this.balls.length === 0) {
      this._spawnBall();
      this.isLaunched = false;
    }

    // 5) power‑ups: fall & catch
    this.powerups = this.powerups.filter(pu => {
      pu.update(dt);
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      const halfW = this.paddle.width/2;
      const halfH = this.paddle.height/2;

      const caught =
        pu.y + pu.radius >= py - halfH &&
        pu.x >= px - halfW &&
        pu.x <= px + halfW;

      if (caught) {
        if (pu.type === 'x2') {
          const slots = this.maxBalls - this.balls.length;
          if (slots > 0) {
            const existing = this.balls.slice();
            const clones = [];
            for (let i = 0; i < existing.length && clones.length < slots; i++) {
              const orig = existing[i];
              const { x, y } = orig.body.position;
              const { x: vx0, y: vy0 } = orig.body.velocity;
              const speed     = Math.hypot(vx0, vy0);
              const baseAngle = Math.atan2(vy0, vx0);
              const tilt      = (Math.random()*2 - 1)*0.3;
              const angle     = baseAngle + tilt;
              const vx        = speed * Math.cos(angle);
              const vy        = speed * Math.sin(angle);
              const clone     = new Ball(this.world, x, y, orig.radius, 0, 0);
              Body.setVelocity(clone.body, { x: vx, y: vy });
              clones.push(clone);
            }
            this.balls.push(...clones);
          }
        }
        return false; // remove this power‑up
      }
      return pu.y - pu.radius < this.canvas.height;
    });

    // 6) next level?
    if (!this.obstacles.some(o => o.breakable && o.active)) {
      this.currentLevel = (this.currentLevel + 1) % levels.length;
      this._loadLevel(this.currentLevel);
    }
  }

  /** draw all objects */
  draw() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // balls + velocity arrows
    this.balls.forEach(b => {
      b.draw(this.ctx);
      const { x, y } = b.body.position;
      const { x: vx, y: vy } = b.body.velocity;
      const arrowScale = 3;
      const toX = x + vx * arrowScale;
      const toY = y + vy * arrowScale;
      this.ctx.strokeStyle = 'yellow';
      this.ctx.lineWidth   = 2;
      drawArrow(this.ctx, x, y, toX, toY);
    });

    // paddle
    this.paddle.draw(this.ctx);

    // obstacles
    this.obstacles.forEach(o => o.draw(this.ctx));

    // power-ups
    this.powerups.forEach(p => p.draw(this.ctx));
  }

  /** start the game loop */
  start() {
    this.lastStamp = performance.now();
    requestAnimationFrame(this.loop);
  }
}
