// game-init.js
// =============
// This module handles resizing the canvas to fit the window
// and (re)loading an entire level: paddle, walls, ball, and blocks.

const { World, Bodies } = Matter;       // Matter.js world helper & body factory
import { Paddle }   from './paddle.js';  // our Paddle class
import { Ball }     from './ball.js';    // our Ball class
import { Obstacle } from './obstacle.js';// our Obstacle class
import { levels }   from './levels.js';  // array of level layouts

/**
 * Called whenever the browser window is resized (or at game start).
 * - Resizes the <canvas>
 * - Recreates the paddle at the bottom
 * - Reloads the current level’s layout
 */
export function onResize(game) {
  // 1) Resize canvas to fill the window
  game.canvas.width  = window.innerWidth;
  game.canvas.height = window.innerHeight;

  // 2) Remove the old paddle from the physics world (if any)
  if (game.paddle && game.paddle.body) {
    World.remove(game.world, game.paddle.body);
  }

  // 3) Create a new Paddle instance at the bottom center
  //    Params: (world, width, height, speed, canvas)
  game.paddle = new Paddle(game.world, 500, 20, 800, game.canvas);

  // 4) Now (re)load the current level’s blocks, ball, and walls
  onLoadLevel(game, game.currentLevel);
}

/**
 * Clears out all existing bodies and populates:
 *  1) The paddle
 *  2) Invisible boundary walls (top, left, right)
 *  3) A single ball, locked until served
 *  4) A grid of Obstacles based on the level layout
 */
export function onLoadLevel(game, index) {
  // 1) Clear all bodies (paddle, walls, balls, obstacles), keep engine state
  World.clear(game.world, false);

  // 2) Add the paddle body back into the world
  World.add(game.world, game.paddle.body);

  // 3) Add invisible static walls to contain the ball
  const w = game.canvas.width, h = game.canvas.height;
  World.add(game.world, [
    // Top wall (wide, thin)
    Bodies.rectangle(w/2, -10,   w,   20, { isStatic: true, restitution: 1, friction: 0 }),
    // Left wall (tall, thin)
    Bodies.rectangle(-10, h/2,   20,  h,  { isStatic: true, restitution: 1, friction: 0 }),
    // Right wall (tall, thin)
    Bodies.rectangle(w+10, h/2,  20,  h,  { isStatic: true, restitution: 1, friction: 0 })
  ]);

  // 4) Reset serve state and spawn the first ball
  game.isLaunched = false;
  game.balls = [];
  game._spawnBall();  // places one Ball atop the paddle

  // 5) Build the obstacle grid from our levels array
  const layout = levels[index].layout;
  const rows   = layout.length;
  const cols   = layout[0].length;
  const pad    = 3;                          // space between blocks
  const blockW = (w - (cols + 1) * pad) / cols; // compute width so they fill the canvas
  const blockH = blockW;                     // make them square

  game.obstacles = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const code = layout[r][c];
      if (code === 0) continue;              // 0 = empty space, skip

      // Determine color and whether it breaks
      const color     = code === 1 ? '#e74c3c' : '#7f8c8d';
      const breakable = code === 1;

      // Calculate x,y position for this block
      const x = pad + c * (blockW + pad);
      const y = pad + r * (blockH + pad);

      // Create the Obstacle and add it to the array
      const obs = new Obstacle(
        game.world,
        x, y,
        blockW, blockH,
        color,
        breakable
      );
      game.obstacles.push(obs);
    }
  }
}
