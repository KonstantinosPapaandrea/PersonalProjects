// File: Scoreboard.js (or define inline in Pong.js)
export class Scoreboard {
  constructor(ball, leftPaddleName = "Player1", rightPaddleName = "Player2") {
    this.leftScore = 0;
    this.rightScore = 0;
    this.ball = ball; // for reset hook
    this.leftName = leftPaddleName;
    this.rightName = rightPaddleName;
    this.lastResetTime = 0;
    this.cooldown = 500; // ms before allowing relaunch after score
  }

  addPointToLeft() {
    this.leftScore++;
    this._scoreReset();
  }
  addPointToRight() {
    this.rightScore++;
    this._scoreReset();
  }

  _scoreReset() {
    // reset ball and delay auto-launch
    this.ball.reset();
    this.lastResetTime = performance.now();
  }

  update(dt) {
    // auto-launch after short delay
    if (this.ball.stuck && performance.now() - this.lastResetTime > this.cooldown) {
      // could auto-launch or wait for space
      // this.ball.launch(); // uncomment to auto-start
    }
  }

  render(ctx) {
    const padding = 10;
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.font = "24px monospace";
    ctx.textAlign = "center";

    const w = ctx.canvas.width;
    // Left
    ctx.fillStyle = "white";
    ctx.fillText(`${this.leftName}: ${this.leftScore}`, w * 0.25, 30);
    // Right
    ctx.fillText(`${this.rightName}: ${this.rightScore}`, w * 0.75, 30);
  }
}
