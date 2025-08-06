// === File: Engine.js ===
import { Input } from "./Input.js";
import { Renderer } from "./Renderer.js";
import { Physics } from "./Physics.js";
import { CanvasManager } from "./CanvasManager.js";
import { GameStateManager } from "../util/GameStateManager.js";
import { UIManager } from "../UI/UIManager.js";

export class Engine {
  constructor(canvasId, width = window.innerWidth, height = window.innerHeight) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext("2d");
    CanvasManager.setSize(this, width, height);

    this.lastTime = 0;
    this.objects = [];
    this.running = false;
    this._nextId = 1;
    this.ui = new UIManager(this);

    GameStateManager.setEngine(this); // ✅ fix: needed for pause resume
    CanvasManager.handleDisplayResize(this); // ✅ now includes initial sizing
  }

  addObject(obj) {
    obj.engine = this;
    if (!obj._id) obj._id = this._nextId++;
    this.objects.push(obj);
  }

  removeObject(obj) {
    this.objects = this.objects.filter(o => o !== obj);
  }

  start() {
    this.running = true;
    Input.init();
    Renderer.buildStaticLayer(this);
    requestAnimationFrame(this.loop.bind(this));
  }

  loop(timestamp) {
    if (!this.running) return;

    const dt = Math.min((timestamp - this.lastTime) / 16.67, 2.0); // cap dt to avoid jumps
    this.lastTime = timestamp;

    if (GameStateManager.isPaused()) {
      Renderer.draw(this);
      this.ui.update(0);
      this.ui.render(this.ctx);
      return requestAnimationFrame(this.loop.bind(this));
    }

    Physics.update(this.objects, dt, this.canvas);

    const oldStaticCount = this.objects.filter(o => o.static).length;
    this.objects = this.objects.filter(o => o.active);
    if (oldStaticCount !== this.objects.filter(o => o.static).length) {
      Renderer.buildStaticLayer(this);
    }

    Renderer.draw(this);
    this.ui.update(dt);
    this.ui.render(this.ctx);

    requestAnimationFrame(this.loop.bind(this));
  }
}