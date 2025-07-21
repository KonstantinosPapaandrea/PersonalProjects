// game.js
// ========
// Main game logic, using global Matter.js (loaded via <script> in index.html)

const { Engine, World, Bodies, Body, Events } = Matter;
import { drawArrow } from './utils.js';
import { levels }    from './levels.js';
import { Ball }      from './ball.js';
import { Paddle }    from './paddle.js';
import { Obstacle }  from './obstacle.js';
import { PowerUp }   from './powerup.js';

export class Game {
  // ────────────────────────────────────────────────────────────────────────────
  // 1) MAIN LOOP (bound arrow so `this` stays correct)
  // ────────────────────────────────────────────────────────────────────────────
  loop = (timestamp) => {
    const dt = (timestamp - this.lastStamp) / 1000;
    this.lastStamp = timestamp;

    this.update(dt);
    this.draw();

    requestAnimationFrame(this.loop);
  };

  // ────────────────────────────────────────────────────────────────────────────
  // 2) CONSTRUCTOR & INITIAL SETUP
  // ────────────────────────────────────────────────────────────────────────────
  /**
   * @param {string} canvasId   ID of your <canvas> element
   * @param {number} startLevel index into levels[] to begin
   */
  constructor(canvasId, startLevel = 0) {
    // 2a) Physics engine setup
    this.engine = Engine.create();
    this.world  = this.engine.world;
    this.world.gravity.x = 0;
    this.world.gravity.y = 0;
    this.engine.positionIterations   = 10; // improve collision quality
    this.engine.velocityIterations   = 10;
    this.engine.constraintIterations = 4;

    // 2b) Canvas & resize handler
    this.canvas = document.getElementById(canvasId);
    this.ctx    = this.canvas.getContext('2d');
    window.addEventListener('resize', () => this._onResize());

    // 2c) Game state variables
    this.currentLevel = startLevel; // which level index we’re on
    this.paddle       = null;       // Paddle instance
    this.balls        = [];         // Array of Ball instances
    this.powerups     = [];         // Array of PowerUp instances
    this.obstacles    = [];         // Array of Obstacle instances
    this.isLaunched   = false;      // Has the ball been served?
    this.maxBalls     = 1000;       // Hard cap on simultaneous balls

    // 2d) Collision event wiring
    Events.on(this.engine, 'collisionStart', event => {
      for (const pair of event.pairs) {
        const A = pair.bodyA, B = pair.bodyB;
        const n = pair.collision.normal;

        // Ball ↔ Paddle
        if (A.label==='ball' && B.label==='paddle') {
          this._bounceOffPaddle(A, B);
          continue;
        }
        if (B.label==='ball' && A.label==='paddle') {
          this._bounceOffPaddle(B, A);
          continue;
        }

        // Ball ↔ Block
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

    // 2e) Keyboard: Space to serve the ball
    window.addEventListener('keydown', e => {
      if (e.code==='Space' && !this.isLaunched && this.balls[0]) {
        const ball  = this.balls[0];
        const speed = 20; // starting upward speed
        Body.setVelocity(ball.body, { x: 0, y: -speed });
        ball.speed = speed;      // record its “ideal” speed
        this.isLaunched = true;
      }
    });

    // 2f) Kick off by sizing canvas & loading level
    this._onResize();
    this.lastStamp = performance.now();
  }


  // ────────────────────────────────────────────────────────────────────────────
  // 3) RESIZE & LEVEL LOADING
  // ────────────────────────────────────────────────────────────────────────────
  /** Called on window resize: resets canvas size, paddle & reloads current level */
  _onResize() {
    // resize
    this.canvas.width  = window.innerWidth;
    this.canvas.height = window.innerHeight;

    // rebuild paddle at bottom
    if (this.paddle && this.paddle.body) {
      World.remove(this.world, this.paddle.body);
    }
    this.paddle = new Paddle(this.world, 500, 20, 800, this.canvas);

    // load the level layout & objects
    this._loadLevel(this.currentLevel);
  }

  /**
   * Clears the world (except engine defaults), adds walls/paddle,
   * spawns one ball and lays out obstacles.
   */
  _loadLevel(idx) {
    World.clear(this.world, false);
    World.add(this.world, this.paddle.body);

    // invisible boundaries (top/left/right)
    const w = this.canvas.width, h = this.canvas.height;
    World.add(this.world, [
      Bodies.rectangle(w/2, -10,   w, 20, { isStatic:true, restitution:1, friction:0 }),
      Bodies.rectangle(-10, h/2,   20,  h, { isStatic:true, restitution:1, friction:0 }),
      Bodies.rectangle(w+10, h/2,  20,  h, { isStatic:true, restitution:1, friction:0 })
    ]);

    // reset serve and balls
    this.isLaunched = false;
    this.balls = [];
    this._spawnBall();

    // obstacle grid from levels[idx].layout
    const layout = levels[idx].layout;
    const rows   = layout.length, cols = layout[0].length;
    const pad    = 3;
    const blockW = (w - (cols+1)*pad) / cols;
    const blockH = blockW;

    this.obstacles = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const code = layout[r][c];
        if (!code) continue;
        const color     = code===1 ? '#e74c3c' : '#7f8c8d';
        const breakable = code===1;
        const obs = new Obstacle(
          this.world,
          pad + c*(blockW+pad),
          pad + r*(blockH+pad),
          blockW, blockH,
          color,
          breakable
        );
        this.obstacles.push(obs);
      }
    }
  }

  /** Creates one Ball instance directly above the paddle with zero velocity */
  _spawnBall() {
    const px = this.paddle.body.position.x;
    const py = this.paddle.body.position.y;
    const r  = 15;
    const ball = new Ball(this.world, px, py - r - 1, r, 0, 0);
    this.balls.push(ball);
    // ball.speed remains 0 until the user presses Space
  }


  // ────────────────────────────────────────────────────────────────────────────
  // 4) COLLISION RESPONSE HELPERS
  // ────────────────────────────────────────────────────────────────────────────
  /**
   * Paddle bounce:  
   *  • Horizontal velocity based on hit position  
   *  • Preserves the ball’s recorded speed  
   */
  _bounceOffPaddle(ballBody, paddleBody) {
    // compute normalized hit offset in [–1..1]
    const halfW = this.paddle.width / 2;
    let normX = (ballBody.position.x - paddleBody.position.x) / halfW;
    normX = Math.max(-1, Math.min(1, normX));

    // map offset to ±60° from straight up
    const angle = normX * (Math.PI / 3);

    // determine speed to preserve
    const v0     = ballBody.velocity;
    const speed  = ballBody.speed || Math.hypot(v0.x, v0.y) || 20;
    const vx = speed * Math.sin(angle);
    const vy = -speed * Math.cos(angle);

    // apply new velocity + reposition above paddle
    Body.setVelocity(ballBody, { x: vx, y: vy });
    Body.setPosition(ballBody, {
      x: ballBody.position.x,
      y: paddleBody.position.y - (this.paddle.height/2 + ballBody.circleRadius + 1)
    });

    // record speed for future renormalization
    ballBody.speed    = speed;
    this.isLaunched   = true;
  }

  /**
   * Block bounce: perfect reflection about collision normal + renormalize speed
   */
  _reflectBall(ballBody, normal) {
    const v0     = ballBody.velocity;
    const speed0 = ballBody.speed || Math.hypot(v0.x, v0.y);

    // reflect: v1 = v0 – 2 * (v0·n) * n
    const dot = v0.x*normal.x + v0.y*normal.y;
    let vx1 = v0.x - 2*dot*normal.x;
    let vy1 = v0.y - 2*dot*normal.y;

    // renormalize magnitude back to speed0
    const speed1 = Math.hypot(vx1, vy1);
    if (speed1 > 0) {
      const factor = speed0 / speed1;
      vx1 *= factor; vy1 *= factor;
    }

    Body.setVelocity(ballBody, { x: vx1, y: vy1 });

    // nudge out to avoid sticking
    const push = ballBody.circleRadius + 0.5;
    Body.translate(ballBody, {
      x: normal.x*push,
      y: normal.y*push
    });

    ballBody.speed = speed0;
  }

  /** Breaks a block and spawns a power‑up with 5% chance */
  _onBlockHit(body) {
    const obs = this.obstacles.find(o => o.body===body);
    if (!obs || !obs.breakable) return;
    World.remove(this.world, body);
    obs.active = false;

    // small chance to drop x2 power‑up
    if (Math.random() < 0.05) {
      const { x, y } = body.position;
      this.powerups.push(new PowerUp(x, y, 'x2'));
    }
  }


  // ────────────────────────────────────────────────────────────────────────────
  // 5) UPDATE – one per frame
  // ────────────────────────────────────────────────────────────────────────────
  update(dt) {
    // 5a) Paddle follows input
    this.paddle.update(dt);

    // 5b) Lock ball atop paddle until user serves
    if (!this.isLaunched && this.balls[0]) {
      const b  = this.balls[0].body;
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      Body.setPosition(b, { x: px, y: py - b.circleRadius - 1 });
    }

    // 5c) Advance physics simulation
    Engine.update(this.engine, dt * 1000);

    // 5d) Renormalize each ball’s velocity to its recorded speed
    this.balls.forEach(ball => {
      const v   = ball.body.velocity;
      const cur = Math.hypot(v.x, v.y);
      if (ball.speed > 0 && cur > 0) {
        const f = ball.speed / cur;
        Body.setVelocity(ball.body, { x: v.x*f, y: v.y*f });
      }
    });

    // 5e) Remove balls that fell off bottom
    for (let i = this.balls.length - 1; i >= 0; i--) {
      const b = this.balls[i].body;
      if (b.position.y - b.circleRadius > this.canvas.height) {
        World.remove(this.world, b);
        this.balls.splice(i, 1);
      }
    }
    if (this.balls.length === 0) {
      this._spawnBall();
      this.isLaunched = false;
    }

    // 5f) Update power‑ups (falling & catching)
    this.powerups = this.powerups.filter(pu => {
      pu.update(dt);

      // caught by paddle?
      const px = this.paddle.body.position.x;
      const py = this.paddle.body.position.y;
      const halfW = this.paddle.width/2;
      const halfH = this.paddle.height/2;

      if (
        pu.y + pu.radius >= py - halfH &&
        pu.x >= px - halfW &&
        pu.x <= px + halfW
      ) {
        // x2 power‑up: clone balls up to maxBalls
        if (pu.type==='x2') {
          const slots = this.maxBalls - this.balls.length;
          if (slots > 0) {
            const existing = this.balls.slice();
            const clones   = [];
            for (let j=0; j<existing.length && clones.length<slots; j++) {
              const orig = existing[j];
              const { x, y } = orig.body.position;
              const { x: vx0, y: vy0 } = orig.body.velocity;
              const speed     = orig.body.speed || Math.hypot(vx0, vy0);
              const baseAngle = Math.atan2(vy0, vx0);
              const tilt      = (Math.random()*2 - 1)*0.3;
              const angle     = baseAngle + tilt;
              const vx = speed * Math.cos(angle);
              const vy = speed * Math.sin(angle);
              const clone = new Ball(this.world, x, y, orig.radius, 0, 0);
              Body.setVelocity(clone.body, { x:vx, y:vy });
              clone.speed = speed;
              clones.push(clone);
            }
            this.balls.push(...clones);
          }
        }
        return false; // remove caught power‑up
      }
      return pu.y - pu.radius < this.canvas.height;
    });

    // 5g) Advance to next level if all breakable blocks are gone
    if (!this.obstacles.some(o => o.breakable && o.active)) {
      this.currentLevel = (this.currentLevel + 1) % levels.length;
      this._loadLevel(this.currentLevel);
    }
  }


  // ────────────────────────────────────────────────────────────────────────────
  // 6) DRAW – one per frame
  // ────────────────────────────────────────────────────────────────────────────
  draw() {
    // clear canvas
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // 6a) Balls + velocity arrows for debugging
    this.balls.forEach(b => {
      b.draw(this.ctx);
      const { x, y } = b.body.position;
      const { x: vx, y: vy } = b.body.velocity;
      const speed = Math.hypot(vx, vy);
      if (speed > 0) {
        const arrowScale = 10;  // length multiplier
        const minLen     = 30;  // ensure visibility at low speed
        const baseLen    = speed * arrowScale;
        const len        = Math.max(baseLen, minLen);
        const ux = vx/speed, uy = vy/speed;
        const toX = x + ux*len, toY = y + uy*len;
        this.ctx.strokeStyle = 'yellow';
        this.ctx.lineWidth   = 2;
        drawArrow(this.ctx, x, y, toX, toY);
      }
    });

    // 6b) Paddle
    this.paddle.draw(this.ctx);

    // 6c) Obstacles
    this.obstacles.forEach(o => o.draw(this.ctx));

    // 6d) Power‑ups
    this.powerups.forEach(p => p.draw(this.ctx));
  }


  // ────────────────────────────────────────────────────────────────────────────
  // 7) START the game
  // ────────────────────────────────────────────────────────────────────────────
  start() {
    this.lastStamp = performance.now();
    requestAnimationFrame(this.loop);
  }
}
