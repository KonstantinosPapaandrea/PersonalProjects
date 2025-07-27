import { Input } from "./Input.js";
import { isColliding } from "./Collision.js";
import { QuadTree } from "./QuadTree.js";

export class Engine {
  constructor(canvasId, width = window.innerWidth, height = window.innerHeight) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext("2d");
    this.setSize(width, height);

    this.lastTime = 0;
    this.objects = [];
    this.running = false;
    this._nextId = 1;

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
    obj.engine = this;
    if (!obj._id) obj._id = this._nextId++;
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

    // ---- QuadTree Broad-phase ----
    const quadTree = new QuadTree({ x: 0, y: 0, width: this.canvas.width, height: this.canvas.height });

    this.objects.forEach(obj => {
      if (obj.active && obj.collider) quadTree.insert(obj);
    });

    const checkedPairs = new Set();

    for (let a of this.objects) {
      if (!a.active || !a.collider) continue;

      const range = { x: a.x - 5, y: a.y - 5, width: a.width + 10, height: a.height + 10 };
      const possible = quadTree.query(range);

      for (let b of possible) {
        if (a === b || !b.active || !b.collider) continue;
        if (a.static && b.static) continue;
        if (!a.canCollideWith(b) && !b.canCollideWith(a)) continue;

        const pairKey = a._id < b._id ? `${a._id}-${b._id}` : `${b._id}-${a._id}`;
        if (checkedPairs.has(pairKey)) continue;
        checkedPairs.add(pairKey);

        if (isColliding(a, b)) {
          a.onCollision(b);
          b.onCollision(a);
        }
      }
    }

    // ---- Cleanup ----
    this.objects = this.objects.filter(obj => obj.active);

    // ---- Render ----
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.objects.forEach(obj => obj.render(this.ctx));

    requestAnimationFrame(this.loop.bind(this));
  }
}
