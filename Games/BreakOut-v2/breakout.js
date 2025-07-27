import { Engine } from "../gameEngine/core/Engine.js";
import { Paddle } from "./Paddle.js";
import { Ball } from "./Ball.js";
import { createMap } from "./Map.js";
import { PowerUp } from "./PowerUp.js"; // ✅ new


const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);
engine.handleResize(true); // ✅ scale objects when window resizes

const paddleWidth = window.innerWidth/7;
const paddleHeight = 20;

// ✅ Always place paddle at bottom, 30px above the bottom edge
const paddle = new Paddle(
  (engine.canvas.width - paddleWidth) / 2,   // centered horizontally
  engine.canvas.height - paddleHeight - 30, // 30px margin from bottom
  paddleWidth,
  paddleHeight,
  "blue"
);

const ball = new Ball(240, 200, 15, "red");
ball.paddle = paddle;

// ✅ Generate a responsive map

const bricks = createMap(
  engine,
  20,   // rows
  100,  // columns
  50,  // marginTop
  5,  // marginSide
  10,  // gapX (horizontal spacing)
  10    // gapY (vertical spacing)
);
engine.addObject(paddle);
engine.addObject(ball);

engine.start();
