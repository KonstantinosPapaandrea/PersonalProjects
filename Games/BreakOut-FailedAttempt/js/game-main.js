// game-main.js
// =============
// This is the “glue” file that puts all the pieces together and starts the game.
// It sets up the physics engine, the canvas, loads levels, and kicks off the main loop.

const { Engine, World } = Matter;      // Matter.js physics engine core
import { drawArrow }     from './utils.js';
import { levels }        from './levels.js';
import { Ball }          from './ball.js';
import { Paddle }        from './paddle.js';
import { Obstacle }      from './obstacle.js';
import { PowerUp }       from './powerup.js';

// Import our modularized game functions
import { onResize, onLoadLevel } from './game-init.js';
import { spawnBall }             from './game-spawn.js';
import { handleCollisions }      from './game-collisions.js';
import updateGame                from './game-update.js';
import drawGame                  from './game-draw.js';

export class Game {
  /**
   * Create a new Game.
   * @param {string} canvasId   – the ID attribute of the <canvas> in your HTML.
   * @param {number} startLevel – which level index to load first (0-based).
   */
  constructor(canvasId, startLevel = 1) {
    // 1) Physics engine setup
    //    - Engine.create() gives us the world and solver
    //    - We turn off gravity (we want the ball to float)
    this.engine = Engine.create();
    this.world  = this.engine.world;
    this.world.gravity.x = 0;
    this.world.gravity.y = 0;

    //    - Increase solver iterations to reduce tunneling and improve collision accuracy
    this.engine.positionIterations   =30;
    this.engine.velocityIterations   = 30;
    this.engine.constraintIterations = 4;

    // 2) Canvas setup
    //    - Grab the <canvas> element by its ID
    //    - Get the 2D drawing context
    this.canvas = document.getElementById(canvasId);
    this.ctx    = this.canvas.getContext('2d');

    // 3) Initial game state variables
    this.currentLevel = 1; // which level we’re on
    this.paddle       = null;       // will hold our Paddle instance
    this.balls        = [];         // array of Ball instances
    this.powerups     = [];         // array of PowerUp instances
    this.obstacles    = [];         // array of Obstacle instances
    this.isLaunched   = false;      // has the ball been served?
    this.maxBalls     = 1000;       // cap on simultaneous balls

    // 4) Collision wiring
    //    - Set up all the collision callbacks (ball↔paddle, ball↔block, etc.)
    handleCollisions(this);

    // 5) Window resize & initial level load
    //    - Whenever the browser window changes size, rebuild the canvas and reload the level
    window.addEventListener('resize', () => onResize(this));
    //    - Call it once now to do the initial sizing and load
    onResize(this);

    // 6) Prepare for the main loop
    //    - Record the current time so we can calculate delta-time
    this.lastStamp = performance.now();
  }

  // ────────────────────────────────────────────────────────────────────────────
  // bound main loop
  // ────────────────────────────────────────────────────────────────────────────
  // We use an arrow function so that `this` inside always points to our Game instance.
  loop = (timestamp) => {
    // a) Compute how much time passed since last frame (in seconds)
let dt = (timestamp - this.lastStamp) / 1000;
 const MAX_DT = 1 / 30;
  if (dt > MAX_DT) dt = MAX_DT;

if (dt > 0.03) {
  console.warn(`Large dt: ${dt.toFixed(3)}s`);
}
// also log solver iterations on startup
console.log(
  `iters: pos=${this.engine.positionIterations}` +
  ` vel=${this.engine.velocityIterations}`
);    this.lastStamp = timestamp;

    // b) Update game state (move paddle, balls, powerups, etc.)
    this.update(dt);

    // c) Draw everything to the canvas
    this.draw();

    // d) Schedule the next frame
    requestAnimationFrame(this.loop);
  };

  /**
   * Start the game loop.
   * Call this after creating your Game instance.
   */
  start() {
    requestAnimationFrame(this.loop);
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Attach modular functions to Game.prototype
// This lets us keep code in separate files but still call them as methods:
// e.g. `this._spawnBall()`, `this._loadLevel()`, `this.update()`, `this.draw()`
// ────────────────────────────────────────────────────────────────────────────
Game.prototype._spawnBall = spawnBall;         // adds the spawnBall function as a method
Game.prototype._onResize  = onResize;          // onResize resizes canvas & reloads level
Game.prototype._loadLevel = onLoadLevel;       // onLoadLevel builds walls, paddle, blocks
Game.prototype.update     = updateGame;         // updateGame contains all per-frame logic
Game.prototype.draw       = drawGame;           // drawGame contains all rendering logic
