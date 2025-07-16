// game.js
import { levels }    from './levels.js';
import { Ball }      from './ball.js';
import { Paddle }    from './paddle.js';
import { Obstacle }  from './obstacle.js';
import { PowerUp }   from './powerup.js';

export class Game {
  constructor(startLevel = 0) {
    // level & canvas
    this.currentLevel = startLevel;
    this.canvas = document.getElementById('gameCanvas');
    this.ctx    = this.canvas.getContext('2d');

    // single ball initially, will live in this.balls[]
    const initialBall = new Ball(
      this.canvas.width/2,
      this.canvas.height/2,
      15,    // radius
      1000,   // vx
      -1000   // vy (upwards)
    );
    this.balls = [ initialBall ];

    // paddle
    this.paddle = new Paddle(
      250,   // width
      20,    // height
      1000,   // speed px/s
      this.canvas
    );

    // power‑ups
    this.powerups = [];

    // handle resize → rebuild level
    window.addEventListener('resize', () => this._onResize());
    this._onResize();

    // start loop
    this.lastTimestamp = 0;
  }

  _onResize() {
    this.canvas.width  = window.innerWidth;
    this.canvas.height = window.innerHeight;
    // reposition paddle bottom
    this.paddle.y = this.canvas.height - this.paddle.height - 10;
    this.paddle.x = Math.min(this.paddle.x, this.canvas.width - this.paddle.width);
    // load/reload obstacles & reset ball(s)
    this._loadLevel(this.currentLevel);
  }

  _loadLevel(index) {
    const map    = levels[index];
    const layout = map.layout;
    const rows   = layout.length;
    const cols   = layout[0]?.length || 0;
    const pad    = 10;
    const blockW = (this.canvas.width  - (cols + 1) * pad) / cols;
    const blockH = blockW;

    // reset balls to single initial ball
    this.balls = [ this.balls[0] ];
    // reset that ball just above paddle
    this.resetBall();

    // center paddle
    this.paddle.x = (this.canvas.width - this.paddle.width) / 2;

    // build obstacles
    this.obstacles = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const code = layout[r][c];
        if (code === 0) continue;
        const isBreakable = code === 1;
        const color = isBreakable ? '#e74c3c' : '#7f8c8d';
        const x = pad + c * (blockW + pad);
        const y = pad + r * (blockH + pad);
        this.obstacles.push(
          new Obstacle(x, y, blockW, blockH, color, isBreakable)
        );
      }
    }
  }

  resetBall() {
    // place above paddle center
    const b = this.balls[0];
    b.x = this.paddle.x + this.paddle.width/2;
    b.y = this.paddle.y - b.radius - 10;
    // upward at random angle ±30°
    const speed = Math.hypot(b.vx, b.vy) || 400;
    const angle = -Math.PI/2 + (Math.random()*Math.PI/3 - Math.PI/6);
    b.vx = speed * Math.cos(angle);
    b.vy = speed * Math.sin(angle);
  }

  update(dt) {
    // 1) paddle
    this.paddle.update(dt);

    // 2) each ball: sub‑stepped movement & collisions
    for (let bi = 0; bi < this.balls.length; bi++) {
      const ball = this.balls[bi];
      // compute safe step
      const speed  = Math.hypot(ball.vx, ball.vy);
      let   minB   = Infinity;
      if (this.obstacles.length) {
        const o = this.obstacles[0];
        minB = Math.min(o.width, o.height);
      }
      const safeStep = speed>0 ? minB/speed : 1/60;
      const MAX_STEP = Math.min(safeStep, 1/60);

      let rem = dt;
      while (rem > 0) {
        const step = Math.min(rem, MAX_STEP);
        rem -= step;

        // move
        ball.x += ball.vx * step;
        ball.y += ball.vy * step;

        // wall bounces
        if (ball.x - ball.radius < 0) { ball.x = ball.radius; ball.vx *= -1; }
        if (ball.x + ball.radius > this.canvas.width) {
          ball.x = this.canvas.width - ball.radius; ball.vx *= -1;
        }
        if (ball.y - ball.radius < 0) { ball.y = ball.radius; ball.vy *= -1; }

        // paddle
        if (
          ball.y + ball.radius >= this.paddle.y &&
          ball.x >= this.paddle.x &&
          ball.x <= this.paddle.x + this.paddle.width
        ) {
          ball.vy *= -1;
          ball.y  = this.paddle.y - ball.radius;
        }

        // obstacles
        for (const obs of this.obstacles) {
          if (!obs.active) continue;
          const cx = Math.max(obs.x, Math.min(ball.x, obs.x+obs.width));
          const cy = Math.max(obs.y, Math.min(ball.y, obs.y+obs.height));
          const dx = ball.x - cx, dy = ball.y - cy;
          if (dx*dx+dy*dy < ball.radius*ball.radius) {
            // break block
            if (obs.breakable) {
              obs.active = false;
              // 20% chance to spawn x2 powerup
              if (Math.random() < 0.2) {
                this.powerups.push(
                  new PowerUp(cx, cy, 'x2')
                );
              }
            }
            // bounce
            ball.vy *= -1;
            // nudge
            ball.y += (ball.vy>0 ? + (obs.height + 2*ball.radius) : - (obs.height + 2*ball.radius));
            break;
          }
        }
      }

      // out‐of‐bounds?
      if (ball.y - ball.radius > this.canvas.height) {
        // remove this ball
        this.balls.splice(bi, 1);
        bi--;
      }
    }

    // if all balls lost → reset single ball
    if (this.balls.length === 0) {
      this.balls.push(this.balls[0] = new Ball(0,0,15,400,-400));
      this.resetBall();
    }

    // 3) power‑ups fall & catch
    for (let i = 0; i < this.powerups.length; i++) {
      const pu = this.powerups[i];
      pu.update(dt);
      // off bottom?
      if (pu.y - pu.radius > this.canvas.height) {
        this.powerups.splice(i--, 1);
        continue;
      }
      // catch by paddle?
      if (
        pu.y + pu.radius >= this.paddle.y &&
        pu.x >= this.paddle.x &&
        pu.x <= this.paddle.x + this.paddle.width
      ) {
        // activate x2
        if (pu.type === 'x2') {
          // duplicate every existing ball
          const clones = this.balls.map(b => 
            new Ball(b.x, b.y, b.radius, -b.vx, b.vy)
          );
          this.balls.push(...clones);
        }
        this.powerups.splice(i--, 1);
      }
    }

    // 4) level clear?
    const anyLeft = this.obstacles.some(o=>o.breakable&&o.active);
    if (!anyLeft) {
      this.currentLevel = (this.currentLevel+1)%levels.length;
      this._loadLevel(this.currentLevel);
    }
  }

  draw() {
    this.ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
    this.balls.forEach(b=>b.draw(this.ctx));
    this.paddle.draw(this.ctx);
    this.obstacles.forEach(o=>o.draw(this.ctx));
    this.powerups.forEach(p=>p.draw(this.ctx));
  }

  loop(ts) {
    const dt = (ts - this.lastTimestamp)/1000;
    this.lastTimestamp = ts;
    this.update(dt);
    this.draw();
    requestAnimationFrame(t=>this.loop(t));
  }

  start() {
    requestAnimationFrame(t=>this.loop(t));
  }
}
