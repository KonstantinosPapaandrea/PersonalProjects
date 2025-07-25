// ==============================
// ENGINE v0.2 – With Collision System
// ==============================

// ---- GameObject Base Class ----
class GameObject {
  constructor(x, y, width, height, color = "white") {
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
    this.color = color;
    this.vx = 0;
    this.vy = 0;
    this.active = true;
    this.collider = true; // ✅ participates in collisions
  }

  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
  }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  onCollision(other) {
    // ✅ To be overridden by subclasses
  }

  destroy() {
    this.active = false;
  }
}

// ---- Input Manager ----
const Input = {
  keys: {},
  init() {
    window.addEventListener("keydown", e => (this.keys[e.key] = true));
    window.addEventListener("keyup", e => (this.keys[e.key] = false));
  },
  isDown(key) {
    return this.keys[key] === true;
  }
};

// ---- Collision Helper (AABB)
function isColliding(a, b) {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}

// ---- Engine Core ----
class Engine {
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

    // ✅ Auto-remove destroyed objects
    this.objects = this.objects.filter(obj => obj.active);

    // ---- Render ----
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.objects.forEach(obj => obj.render(this.ctx));

    requestAnimationFrame(this.loop.bind(this));
  }
}
