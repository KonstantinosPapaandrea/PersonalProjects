import { Engine }           from "../gameEngine/core/Engine.js";
import { Paddle }           from "./Paddle.js";
import { Ball }             from "./Ball.js";
import { createMap }        from "./Map.js";
import { PowerUp }          from "./PowerUp.js";
import { GameStateManager } from "../gameEngine/util/GameStateManager.js";
import { Input }            from "../gameEngine/core/Input.js";
import { Renderer } from "../gameEngine/core/Renderer.js";  // ← add this

// ─── GAME‑SPECIFIC STATE ────────────────────────────────────────────
let winner = false;
window.addEventListener("gameWon", () => {
  winner = true;
});

// ─── LEVEL CONFIG ────────────────────────────────────────────────────
const levels = [
  { pattern: "diamond",      rows: 6, cols: 10 },
  { pattern: "pyramid",      rows: 7, cols: 11 },
  { pattern: "checkerboard", rows: 6, cols: 12 },
];
let currentLevel = 0;

// ─── ENGINE & STATE SETUP ───────────────────────────────────────────
const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);
GameStateManager.setEngine(engine);
GameStateManager.setState("init");  // show main menu first

// ─── HELPER: LOAD A LEVEL ────────────────────────────────────────────

function loadLevel(index) {
  // 1) remove all game objects (bricks, balls, paddle), but leave UI intact:
  engine.objects = [];

  // 2) reset win flag
  winner = false;

  // 3) generate bricks
  const cfg = levels[index];
  createMap(engine, cfg.pattern, cfg.rows, cfg.cols);

  // 4) reset paddle & ball (you already have these created once)
  paddle.x = (engine.world.width - paddle.width) / 2;
  paddle.y = engine.world.height - paddle.height - 30;
  paddle.vx = paddle.vy = 0;
  paddle.active = true;

  ball.stuck = true;
  ball.x = engine.world.width / 2 - ball.radius;
  ball.y = paddle.y - ball.height - 2;
  ball.vx = ball.vy = 0;
  ball.active = true;

  engine.addObject(paddle);
  engine.addObject(ball);

  // 5) rebuild the static brick layer **via Renderer**, not engine
  Renderer.buildStaticLayers(engine);
}

// ─── CREATE PADDLE & BALL ONCE ───────────────────────────────────────
const paddleWidth  = engine.world.width / 7;
const paddleHeight = 20;
const paddle = new Paddle(
  (engine.world.width - paddleWidth) / 2,
  engine.world.height - paddleHeight - 30,
  paddleWidth,
  paddleHeight,
  "blue"
);

const ball = new Ball(240, 200, 7, "red");
ball.paddle = paddle;

// ─── UI OVERLAYS ─────────────────────────────────────────────────────
// Main Menu
const mainMenu = {
  update() {
    if (GameStateManager.state === "init" && Input.isKeyDown("Enter")) {
      GameStateManager.setState("running");
      engine.ui.remove(mainMenu);
      loadLevel(currentLevel);
    }
  },
  render(ctx) {
    if (GameStateManager.state !== "init") return;
    const W = engine._cssWidth, H = engine._cssHeight;
    ctx.fillStyle = "#222"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "white"; ctx.font = "56px sans-serif"; ctx.textAlign = "center";
    ctx.fillText("BREAKOUT", W/2, H/2 - 40);
    ctx.font = "24px sans-serif"; ctx.fillText("Press ENTER to Start", W/2, H/2 + 20);
  }
};
engine.ui.add(mainMenu);

// Pause Overlay
engine.ui.add({
  update() {},
  render(ctx) {
    if (!GameStateManager.isPaused()) return;
    const W = engine.world.width, H = engine.world.height;
    ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fillRect(0,0,W,H);
    ctx.fillStyle = "white"; ctx.font = "40px sans-serif"; ctx.textAlign = "center";
    ctx.fillText("⏸ PAUSED", W/2, H/2);
  }
});

// Winner Banner
engine.ui.add({
  update() {},
  render(ctx) {
    if (!winner) return;
    const W = engine.world.width, H = engine.world.height;
    ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(0,0,W,H);
    ctx.fillStyle = "yellow"; ctx.font = "60px Arial"; ctx.textAlign = "center";
    ctx.fillText("🏆 YOU WIN!", W/2, H/2);
  }
});

// ─── HOTKEYS ─────────────────────────────────────────────────────────
window.addEventListener("keydown", e => {
  if (e.key === "p") GameStateManager.togglePause();
  if (e.key === "r") window.location.reload();
  if (e.key === "n" && GameStateManager.state === "running") {
    // next level
    currentLevel = (currentLevel + 1) % levels.length;
    loadLevel(currentLevel);
  }
});

// ─── START GAME LOOP ─────────────────────────────────────────────────
engine.start();
console.log("Game started");