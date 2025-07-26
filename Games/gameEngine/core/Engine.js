import { Input } from "./Input.js";
import { isColliding } from "./Collision.js";

export class Engine {
  constructor(canvasId, width = window.innerWidth, height = window.innerHeight) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext("2d");
    this.setSize(width, height);

    this.lastTime = 0;
    this.objects = [];
    this.running = false;

    this.handleResize();
  }

  setSize(width, height) {
    this.canvas.width = width;
    this.canvas.height = height;
  }

  handleResize() {
    window.addEventListener("resize", () => {
      this.setSize(window.innerWidth, window.innerHeight);
      if (this.onResize) this.onResize(this.canvas.width, this.canvas.height);
    });
  }

  addObject(obj) {
    this.objects.push(obj);
  }

  start() {
    this.running = true;
    Input.init();
    requestAnimationFrame(this.loop.bind(this));
  }

  loop(timestamp) {
    if (!this.running) return;

    const dt = (timestamp - this.lastTime) / 16.67;
    this.lastTime = timestamp;

    // ---- Update ----
    this.objects.forEach(obj => obj.update(dt));

    // ---- Collision Detection ----
    for (let i = 0; i < this.objects.length; i++) {
      for (let j = i + 1; j < this.objects.length; j++) {
        const a = this.objects[i];
        const b = this.objects[j];

        if (!a.active || !b.active || !a.collider || !b.collider) continue;

        if (isColliding(a, b)) {
          a.onCollision(b);
          b.onCollision(a);
        }
      }
    }

    // ---- Remove Destroyed Objects ----
    this.objects = this.objects.filter(obj => obj.active);

    // ---- Render ----
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.objects.forEach(obj => obj.render(this.ctx));

    requestAnimationFrame(this.loop.bind(this));
  }
}
