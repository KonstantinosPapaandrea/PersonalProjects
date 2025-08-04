// File: Pong.js
import { Scoreboard } from "./Scoreboard.js";

import { Engine } from "../gameEngine/core/Engine.js";
import { Ball } from "./Ball.js";
import { Paddle } from "./Paddle.js";
import { Input } from "../gameEngine/core/Input.js";
import { ScaleFromCenter, easeOutQuad } from "../gameEngine/Animation/Scale.js";

const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);

// ensure input is initialized (engine.start does it)
const middleHeight = window.innerHeight / 2;
const middleWidth = window.innerWidth / 2;

const ballRadius = 5;
const startSpeed = 5; // sensible speed

const paddleWidth = 5;
const paddleHeight = 100;
const paddleSideMarginSpace = 20;
const paddleSpeed = 5; // units per second

// create objects
const ball = new Ball(middleWidth, middleHeight, ballRadius, "white", startSpeed);
// enable improved collision handling if desired
ball.useCCD = true;
ball.substepEnabled = true;
ball.maxMoveRatio = 0.3;

const paddle = new Paddle(
  paddleSideMarginSpace,
  middleHeight - paddleHeight / 2,
  paddleWidth,
  paddleHeight,
  "white",
  paddleSpeed,
  "Player1"
);
const paddle2 = new Paddle(
  window.innerWidth - paddleSideMarginSpace - paddleWidth,
  middleHeight - paddleHeight / 2,
  paddleWidth,
  paddleHeight,
  "white",
  paddleSpeed,
  "Player2"
);

// add to engine
engine.addObject(ball);
engine.addObject(paddle);
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
