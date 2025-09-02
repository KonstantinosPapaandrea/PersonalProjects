// File: ScoreBoard.js
// -----------------------------------------------------------------------------
// UI element for scores. Draws in CSS pixels; keeps round state helpers.
// -----------------------------------------------------------------------------
export class Scoreboard {
  constructor(ball, leftPaddleName = "Player1", rightPaddleName = "Player2", targetScore = 5, cooldownMs = 800) {
    this.engine = null;               // injected by UIManager.add()
    this.active = true;               // render by default

    this.leftScore  = 0;
    this.rightScore = 0;
    this.leftName   = leftPaddleName;
    this.rightName  = rightPaddleName;

    this.targetScore = targetScore;   // points to win the match
    this.cooldown    = cooldownMs;    // ms after a point before serve allowed
    this.lastResetTime = 0;           // timestamp of last score

    this.ball = ball;                 // reference to game ball (to reset/launch)
  }

  // ----- scoring API ----------------------------------------------------------
  addPointToLeft()  { this.leftScore++;  this._scoreReset(); }
  addPointToRight() { this.rightScore++; this._scoreReset(); }

  _scoreReset() {
    // Reset the ball to center and mark when we can serve again
    this.ball.reset();
    this.lastResetTime = performance.now();
  }

  // Winner detection (string or null)
  getWinnerName() {
    if (this.leftScore  >= this.targetScore) return this.leftName;
    if (this.rightScore >= this.targetScore) return this.rightName;
    return null;
  }

  // Milliseconds left until serve is allowed (for countdown overlay)
  getMillisUntilServe() {
    const elapsed = performance.now() - this.lastResetTime;
    return Math.max(0, this.cooldown - elapsed);
  }

  // Convenience “can serve now?”
  canServe() { return this.getMillisUntilServe() <= 0; }

  update(dt) {
    // Auto-launch after cooldown (optional; keep manual launch if you prefer)
    // if (this.ball.stuck && this.canServe()) this.ball.launch();
  }

  render(ctx) {
    // Draw along the top in CSS pixels
    const W = this.engine?._cssWidth  ?? ctx.canvas.clientWidth;
    const H = this.engine?._cssHeight ?? ctx.canvas.clientHeight;

    // Background strip
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(0, 0, W, 48);

    // Text
    ctx.fillStyle = "white";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font = "20px monospace";
    ctx.fillText(`${this.leftName}: ${this.leftScore}`,  W * 0.25, 24);
    ctx.fillText(`${this.rightName}: ${this.rightScore}`, W * 0.75, 24);

    // Serve hint (center)
    const winner = this.getWinnerName();
    if (!winner) {
      ctx.font = "14px monospace";
      const serveHint = this.canServe() ? "Press SPACE to serve" : `Serve in ${Math.ceil(this.getMillisUntilServe()/1000)}…`;
      ctx.fillText(serveHint, W * 0.5, 24);
    }
  }
}
