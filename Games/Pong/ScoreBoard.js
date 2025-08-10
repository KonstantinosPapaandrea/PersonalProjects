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

// File: Scoreboard.js

  /* …ctor, addPointToLeft/Right, _scoreReset, update stay the same… */

  render(ctx) {
    // Padding from the top edge
    const padding = 10;

    // We want to draw text in CSS pixels, not device pixels.
    // ctx.canvas.width is backing-store size (CSS size × DPR).
    // clientWidth is the CSS-pixel width you see on screen.
    const visibleWidth = ctx.canvas.clientWidth;

    // Semi-transparent black behind the score
    ctx.fillStyle = "rgba(0,0,0,0)";
    ctx.fillRect(0, 0, visibleWidth, 40);  // draw a background bar

    // White text in monospace, centered
    ctx.fillStyle = "white";
    ctx.font = "24px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Draw left player’s name and score at 25% of visible width
    ctx.fillText(
      `${this.leftName}: ${this.leftScore}`,  // text to render
      visibleWidth * 0.25,                     // x-position
      padding + 20                             // y-position (half of 40px bar)
    );

    // Draw right player’s name and score at 75% of visible width
    ctx.fillText(
      `${this.rightName}: ${this.rightScore}`, // text to render
      visibleWidth * 0.75,                     // x-position
      padding + 20                             // y-position
    );
  }
}


