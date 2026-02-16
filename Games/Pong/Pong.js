// File: Pong.js
// -----------------------------------------------------------------------------
// Main wiring: WORLD gameplay + UI overlays (CSS space).
// -----------------------------------------------------------------------------
import { Engine }          from "../gameEngine/core/Engine.js";
import { Input }           from "../gameEngine/core/Input.js";
import { GameStateManager } from "../gameEngine/util/GameStateManager.js";

import { Ball }    from "./Ball.js";      // WORLD ball       :contentReference[oaicite:2]{index=2}
import { Paddle }  from "./Paddle.js";    // WORLD paddles    :contentReference[oaicite:3]{index=3}
import { Scoreboard } from "./ScoreBoard.js"; // UI element  :contentReference[oaicite:4]{index=4}

import { PongMainMenu }     from "./UI/PongMainMenu.js";
import { PongPauseOverlay } from "./UI/PongPauseOverlay.js";
import { PongWinBanner }    from "./UI/PongWinBanner.js";
import { ServeCountdown }   from "./UI/ServeCountdown.js";

// ----- WORLD size (design resolution) ----------------------------------------
const WORLD_W = 1280;
const WORLD_H = 720;

// ----- Boot engine & GSM -----------------------------------------------------
const engine = new Engine("gameCanvas", WORLD_W, WORLD_H);
GameStateManager.setEngine(engine);
GameStateManager.setState("init"); // start at menu

// ----- Create gameplay objects (WORLD space) ---------------------------------
const PADDLE_W = 16, PADDLE_H = 140, PADDLE_S = 20, SIDE_GAP = 28;
const BALL_R = 8, BALL_SPEED = 10;

const ball = new Ball(WORLD_W / 2, WORLD_H / 2, BALL_R, "white", BALL_SPEED);
ball.layer = "default";

const leftPaddle = new Paddle(SIDE_GAP, (WORLD_H - PADDLE_H) / 2, PADDLE_W, PADDLE_H, "white", PADDLE_S, "Player1");
leftPaddle.layer = "default";

const rightPaddle = new Paddle(WORLD_W - SIDE_GAP - PADDLE_W, (WORLD_H - PADDLE_H) / 2, PADDLE_W, PADDLE_H, "white", PADDLE_S, "Player2");
rightPaddle.layer = "default";

// Add to engine
engine.addObject(ball);
engine.addObject(leftPaddle);
engine.addObject(rightPaddle);

// ----- Scoreboard (UI) -------------------------------------------------------
const hud = new Scoreboard(ball, "Player1", "Player2", /*target*/5, /*cooldown ms*/1200);
engine.ui.add(hud);

// ----- UI: key capture for "press once" semantics ----------------------------
window.__lastKey = null;
window.addEventListener("keydown", (e) => {
  window.__lastKey = e.key;             // store last pressed key
  if (e.key === " ") {                  // SPACE to serve when allowed
    if (GameStateManager.isRunning() && hud.canServe() && ball.stuck) ball.launch();
  }
  if (e.key === "p" || e.key === "P") GameStateManager.togglePause(); // pause toggle
});

// ----- UI: main menu ---------------------------------------------------------
engine.ui.add(new PongMainMenu({
  onStart: () => {
    // Reset the round and allow serve; leave ball stuck until SPACE
    hud.lastResetTime = performance.now() - hud.cooldown; // serve immediately
  }
}));

// ----- UI: pause overlay -----------------------------------------------------
engine.ui.add(new PongPauseOverlay());

// ----- UI: post-point countdown ---------------------------------------------

// ----- UI: win banner --------------------------------------------------------
engine.ui.add(new PongWinBanner(
  () => hud.getWinnerName(),
  () => {
    // On ENTER after a point/win → reset for next serve or match
    const winner = hud.getWinnerName();
    if (winner) {
      // Hard reset the match scores
      hud.leftScore = 0; hud.rightScore = 0;
    }
    // Reset serve cooldown
    hud.lastResetTime = performance.now() - hud.cooldown;
    // Back to running (ensure menu is gone)
    GameStateManager.setState("running");
  }
));

// ----- Scoring referee (WORLD bounds) ----------------------------------------
function checkScoring() {
  const W = engine.world.width;
  if (ball.x + ball.width < 0) {
    hud.addPointToRight();                   // left out → right scores
  } else if (ball.x > W) {
    hud.addPointToLeft();                    // right out → left scores
  }
  requestAnimationFrame(checkScoring);
}
requestAnimationFrame(checkScoring);

// ----- Start engine loop -----------------------------------------------------
engine.start();
