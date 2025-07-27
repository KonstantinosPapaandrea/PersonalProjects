import { Engine } from "../gameEngine/core/Engine.js";
import { Paddle } from "./Paddle.js";
import { Ball } from "./Ball.js";
import { createMap } from "./Map.js";
import { PowerUp } from "./PowerUp.js"; // ✅ new

// ✅ Declare winner state BEFORE WinnerBanner
let winner = false;
window.addEventListener("gameWon", () => {
  winner = true;
});
// ✅ Simple UI object to display "WINNER!"
class WinnerBanner {
  constructor() {
    this.static = false;   // dynamic, so it's redrawn every frame
    this.active = true;    // always active
    this.collider = false; // no collisions
  }

  update() {
    // No logic, just checks the winner flag in render
  }

  render(ctx) {
    if (!winner) return; // only draw after winning

    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.fillRect(0, 0, engine.canvas.width, engine.canvas.height);

    ctx.fillStyle = "yellow";
    ctx.font = "bold 60px Arial";
    ctx.textAlign = "center";
    ctx.fillText("🏆 WINNER!", engine.canvas.width / 2, engine.canvas.height / 2);
  }
}

// ✅ Engine initialization
const engine = new Engine("gameCanvas", window.innerWidth, window.innerHeight);

// ✅ Create paddle
const paddleWidth = window.innerWidth / 7;
const paddleHeight = 20;
const paddle = new Paddle(
  (engine.canvas.width - paddleWidth) / 2,    // centered
  engine.canvas.height - paddleHeight - 30,  // 30px above bottom
  paddleWidth,
  paddleHeight,
  "blue"
);

// ✅ Create ball
const ball = new Ball(240, 200, 7, "red");
ball.paddle = paddle;

// ✅ Create map
createMap(engine, "diamond",1,1);

// ✅ Add objects to engine
engine.addObject(new WinnerBanner());
engine.addObject(paddle);
engine.addObject(ball);

// ✅ Start game
engine.start();
