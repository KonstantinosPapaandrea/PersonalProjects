// File: Pong.js
// ────────────────────────────────────────────────────────────────────────────
// Pong main: create a fixed-size WORLD and let the Viewport map it to the
// canvas on every resize. All gameplay (ball/paddles) stays in WORLD units.
// ────────────────────────────────────────────────────────────────────────────

import { Engine } from "../gameEngine/core/Engine.js";                 // engine core
import { Ball }   from "./Ball.js";                                    // ball (world coords)
import { Paddle } from "./Paddle.js";                                  // paddle (world coords)
import { Scoreboard } from "./ScoreBoard.js";                          // overlay (CSS coords OK)
import { Input }  from "../gameEngine/core/Input.js";                  // keyboard
import { ScaleFromCenter, easeOutQuad } from "../gameEngine/Animation/Scale.js"; // optional FX

// 1) Pick a fixed "design" WORLD size. The Viewport will letterbox/scale it.
//    Do NOT use window size here; that's CSS space.
const WORLD_W = 1280;  // world width (game units)
const WORLD_H = 720;   // world height (game units)

// 2) Boot the engine with that WORLD size. CanvasManager will still size the
//    canvas to the window and DPR, and Viewport will map WORLD→CSS.
const engine = new Engine("gameCanvas", WORLD_W, WORLD_H);

// 3) WORLD-scaled gameplay constants. These never change with window size.
//    (If you want to balance the “feel”, change these numbers—not CSS.)
const PADDLE_W   = 16;    // world px
const PADDLE_H   = 140;
const PADDLE_S   = 20;   // speed in world px/s
const SIDE_GAP   = 28;    // gap from world edge
const BALL_R     = 8;
const BALL_SPEED = 10;   // world px/s

// 4) Create gameplay objects at WORLD positions (not CSS).
const ball = new Ball(WORLD_W / 2, WORLD_H / 2, BALL_R, "white", BALL_SPEED);
ball.layer = "default"; // render on gameplay layer

// Left paddle anchored to WORLD left
const leftPaddle = new Paddle(
  SIDE_GAP,                            // x in WORLD space
  (WORLD_H - PADDLE_H) / 2,            // centered in WORLD
  PADDLE_W, PADDLE_H, "white", PADDLE_S, "Player1"
);
leftPaddle.layer = "default";

// Right paddle anchored to WORLD right
const rightPaddle = new Paddle(
  WORLD_W - SIDE_GAP - PADDLE_W,       // x in WORLD space
  (WORLD_H - PADDLE_H) / 2,
  PADDLE_W, PADDLE_H, "white", PADDLE_S, "Player2"
);
rightPaddle.layer = "default";

// 5) Add to engine
engine.addObject(ball);
engine.addObject(leftPaddle);
engine.addObject(rightPaddle);

// 6) UI overlay (CSS space is fine for overlays)
const hud = new Scoreboard(ball, "Player1", "Player2");
engine.ui.add(hud);

// 7) Start engine
engine.start();

// 8) Launch ball with Space
window.addEventListener("keydown", (e) => {
  if (e.code === "Space") ball.launch();
});

// 9) World‑space “referee” that awards points when ball leaves WORLD bounds.
//    IMPORTANT: use engine.world.width (WORLD), not CSS width.
function checkScoring() {
  const W = engine.world.width; // world width (fixed)
  if (ball.x + ball.width < 0) {
    hud.addPointToRight();      // ball out on left → right scores
  } else if (ball.x > W) {
    hud.addPointToLeft();       // ball out on right → left scores
  }
  requestAnimationFrame(checkScoring);
}
requestAnimationFrame(checkScoring);

// 10) Optional intro animation on paddles (purely visual)
leftPaddle.width = 0; leftPaddle.height = 0;
ScaleFromCenter(leftPaddle, PADDLE_W, PADDLE_H, 400, easeOutQuad);

rightPaddle.width = 0; rightPaddle.height = 0;
ScaleFromCenter(rightPaddle, PADDLE_W, PADDLE_H, 400, easeOutQuad);
