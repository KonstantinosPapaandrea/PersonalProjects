class WinnerBanner {
  constructor() {
    this.static = false;
    this.active = true;
    this.collider = false;
  }

  update() {
    if (!winner) return;
  }

  render(ctx) {
    if (!winner) return;

    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.fillRect(0, 0, engine.canvas.width, engine.canvas.height);

    ctx.fillStyle = "yellow";
    ctx.font = "bold 60px Arial";
    ctx.textAlign = "center";
    ctx.fillText("🏆 WINNER!", engine.canvas.width / 2, engine.canvas.height / 2);
  }
}

// ✅ Add the banner to engine objects once at the start
const winnerBanner = new WinnerBanner();
engine.addObject(winnerBanner);
