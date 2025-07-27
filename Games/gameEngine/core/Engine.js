import { Input } from "./Input.js";
import { Renderer } from "./Renderer.js";
import { Physics } from "./Physics.js";
import { CanvasManager } from "./CanvasManager.js";

/**
 * Engine – The Heart of the Game Loop
 *
 * Responsibilities:
 * ✅ Manages the canvas and object list.
 * ✅ Updates all objects each frame (via Physics).
 * ✅ Renders static and dynamic objects (via Renderer).
 * ✅ Handles resizing and delta time calculations.
 *
 * How It Works:
 * 1. Call `start()` → Initializes input & starts requestAnimationFrame loop.
 * 2. Each frame:
 *    - Calculate delta time (dt)
 *    - Update object positions and handle collisions
 *    - Remove inactive objects
 *    - Redraw static + dynamic objects
 */

export class Engine {
  constructor(canvasId, width = window.innerWidth, height = window.innerHeight) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext("2d");
    CanvasManager.setSize(this, width, height);

    this.lastTime = 0;
    this.objects = [];
    this.running = false;
    this._nextId = 1;

    CanvasManager.handleResize(this);
  }

  // ✅ Adds an object to the engine and assigns a unique ID
  addObject(obj) {
    obj.engine = this;
    if (!obj._id) obj._id = this._nextId++;
    this.objects.push(obj);
  }

  // ✅ Starts the game loop
  start() {
    this.running = true;
    Input.init();
    Renderer.buildStaticLayer(this);
    requestAnimationFrame(this.loop.bind(this));
  }

  // ✅ The main game loop (runs every frame)
  loop(timestamp) {
    if (!this.running) return;

    // ---- Delta Time Calculation ----
    const dt = (timestamp - this.lastTime) / 16.67; // ~1 at 60fps
    this.lastTime = timestamp;

    // ---- Update Physics ----
    Physics.update(this.objects, dt, this.canvas);

    // ---- Remove Inactive Objects ----
    const oldStaticCount = this.objects.filter(o => o.static).length;
    this.objects = this.objects.filter(o => o.active);

    // ✅ Rebuild static layer if static objects changed
    if (oldStaticCount !== this.objects.filter(o => o.static).length) {
      Renderer.buildStaticLayer(this);
    }

    // ---- Render Frame ----
    Renderer.draw(this);

    // ---- Request Next Frame ----
    requestAnimationFrame(this.loop.bind(this));
  }
}
