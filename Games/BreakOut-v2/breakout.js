// ==============================
// BREAKOUT GAME (Responsive Scaling)
// ==============================

import { Engine } from "../gameEngine/core/Engine.js";
import { GameObject } from "../gameEngine/core/GameObject.js";
// ---- 1. Virtual Resolution ----
const VIRTUAL_WIDTH = 500;
const VIRTUAL_HEIGHT = 320;

let scaleX = window.innerWidth / VIRTUAL_WIDTH;
let scaleY = window.innerHeight / VIRTUAL_HEIGHT;

// ---- 2. Scale Helper ----
function scaled(x, y, width, height) {
  return {
    x: x * scaleX,
    y: y * scaleY,
    width: width * scaleX,
    height: height * scaleY
  };
}

// ---- 3. Initialize Engine ----
const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);

// ---- 4. Create Paddle ----
let p = scaled(200, 300, 80, 15);
const paddle = new Paddle(p.x, p.y, p.width, p.height, "blue");

// ---- 5. Create Ball ----
let b = scaled(240, 200, 8, 8); 
const ball = new Ball(b.x, b.y, b.width / 2, "red"); // Ball takes radius = width/2
// ---- 3. Brick Layout Settings ----
const ROWS = 10;
const COLS = 30;
const GAP_X = 2;       // horizontal gap between bricks
const GAP_Y = 2;       // vertical gap between bricks
const MARGIN_TOP = 20; // top margin
const MARGIN_SIDE = 20; // left & right margin

// Calculate brick size dynamically
const totalGapX = (COLS - 1) * GAP_X;
const totalWidthAvailable = VIRTUAL_WIDTH - (2 * MARGIN_SIDE) - totalGapX;
const BRICK_WIDTH = totalWidthAvailable / COLS;

// Dynamic brick height (occupies 1/3 of top screen)
const totalGapY = (ROWS - 1) * GAP_Y;
const totalHeightAvailable = VIRTUAL_HEIGHT / 3;
const BRICK_HEIGHT = (totalHeightAvailable - totalGapY) / ROWS;
const bricks = [];
for (let row = 0; row < ROWS; row++) {
  for (let col = 0; col < COLS; col++) {
    const x = MARGIN_SIDE + col * (BRICK_WIDTH + GAP_X);
    const y = MARGIN_TOP + row * (BRICK_HEIGHT + GAP_Y);

    let br = scaled(x, y, BRICK_WIDTH, BRICK_HEIGHT);
    const brick = new Brick(br.x, br.y, br.width, br.height, "green");
    bricks.push(brick);
    engine.addObject(brick);
  }
}

// ---- 7. Add Objects to Engine ----
engine.addObject(paddle);
engine.addObject(ball);

// ---- 8. Handle Window Resize (Optional) ----
engine.onResize = (newWidth, newHeight) => {
  scaleX = newWidth / VIRTUAL_WIDTH;
  scaleY = newHeight / VIRTUAL_HEIGHT;

  // Keep paddle & ball in correct place if you resize
  paddle.x = 200 * scaleX;
  paddle.y = 300 * scaleY;

  if (ball.stuck) {
    ball.x = paddle.x + paddle.width / 2 - ball.radius;
    ball.y = paddle.y - ball.height - 2;
  }
};

// ---- 9. Start the Game ----
engine.start();
