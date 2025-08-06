// File: Pong.js
import { Scoreboard } from "./Scoreboard.js";

import { Engine } from "../gameEngine/core/Engine.js";
import { Ball } from "./Ball.js";
import { Paddle } from "./Paddle.js";
import { Input } from "../gameEngine/core/Input.js";
import { ScaleFromCenter, easeOutQuad } from "../gameEngine/Animation/Scale.js";

const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);

// 2) use logical (CSS) size instead of raw window.*
const middleWidth  = engine._cssWidth  / 2;  // ← CHANGED
const middleHeight = engine._cssHeight / 2;  // ← CHANGED

// rest of your constants unchanged...
const ballRadius = 5;
const startSpeed = 5;
const paddleWidth = 5;
const paddleHeight = 100;
const paddleSideMargin = 20;
const paddleSpeed = 5;

// create objects
const ball = new Ball(middleWidth, middleHeight, ballRadius, "white", startSpeed);
// enable improved collision handling if desired
ball.useCCD = true;
ball.substepEnabled = true;
ball.maxMoveRatio = 0.3;


const paddle1 = new Paddle(
  paddleSideMargin,
  middleHeight - paddleHeight / 2,
  paddleWidth,
  paddleHeight,
  "white",
  paddleSpeed,
  "Player1"
);

const paddle2 = new Paddle(
  engine._cssWidth - paddleSideMargin - paddleWidth, // ← CHANGED
  middleHeight - paddleHeight / 2,
  paddleWidth,
  paddleHeight,
  "white",
  paddleSpeed,
  "Player2"
);

// Pong.js — after engine.start():

// keep paddles stuck to left/right on any resize
window.addEventListener("resize", () => {
  // engine._cssWidth is updated by CanvasManager.handleDisplayResize
  paddle1.x =   paddleSideMargin;
  paddle2.x =   engine._cssWidth
              - paddleSideMargin
              - paddleWidth;
});

// you may also want to re-center the ball if it's stuck:
window.addEventListener("resize", () => {
  if (ball.stuck) ball.reset();
});

// add to engine
engine.addObject(ball);
engine.addObject(paddle1);
engine.addObject(paddle2);
const scoreboard = new Scoreboard(ball, "Player1", "Player2");
engine.ui.add(scoreboard);

// start engine
engine.start();

// launch on space
window.addEventListener("keydown", (e) => {
  if (e.code === "Space") {
    ball.launch();
  }
});

function checkOutOfBounds() {
  if (ball.x + ball.width < 0) {
    scoreboard.addPointToRight(); // right player scores
    console.log("Player 2 scores!");
  } else if (ball.x > engine.canvas.width) {
    scoreboard.addPointToLeft();
    console.log("Player 1 scores!");
  }
  requestAnimationFrame(checkOutOfBounds);
}

requestAnimationFrame(checkOutOfBounds);

// animate paddles from center (grow effect)
paddle.width = 0;
paddle.height = 0;
ScaleFromCenter(
  paddle,
  paddleWidth,
  paddleHeight,
  500,
  easeOutQuad,
  () => {
    console.log("Paddle1 size animation complete");
  }
);

paddle2.width = 0;
paddle2.height = 0;
ScaleFromCenter(
  paddle2,
  paddleWidth,
  paddleHeight,
  500,
  easeOutQuad,
  () => {
    console.log("Paddle2 size animation complete");
  }
);
