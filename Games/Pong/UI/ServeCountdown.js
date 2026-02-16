// File: UI/ServeCountdown.js
// -----------------------------------------------------------------------------
// 3–2–1 countdown after a point. Reads a provided "getMillisUntilServe" fn.
// -----------------------------------------------------------------------------
export class ServeCountdown {
  constructor(getMillisUntilServe) {
    this.engine = null;
    this.active = true;
    this.getMillisUntilServe = getMillisUntilServe; // () => ms (>=0) until serve allowed
  }

  update(dt) {
    // purely visual
  }

  render(ctx) {
    const remaining = this.getMillisUntilServe ? this.getMillisUntilServe() : 0;
    if (remaining <= 0) return;

    const W = this.engine._cssWidth;
    const H = this.engine._cssHeight;

    // Compute number (ceil to next second)
    const secs = Math.ceil(remaining / 1000);

    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "white";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "72px monospace";
    ctx.fillText(secs.toString(), W / 2, H / 2);
  }
}
