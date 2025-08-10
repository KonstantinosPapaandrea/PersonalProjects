// File: gameEngine/core/Engine.js

import { Input }         from "./Input.js";             // input events/state
import { Renderer }      from "./Renderer.js";          // drawing
import { Physics }       from "./Physics.js";           // movement + collisions
import { CanvasManager } from "./CanvasManager.js";     // sizing + DPR
import { Viewport }      from "../util/Viewport.js";    // world→screen mapping

// Optional (if you use them already)
import { GameStateManager } from "../util/GameStateManager.js";
import { UIManager }        from "../UI/UIManager.js";
/**
 * Engine
 * -----------------------------------------------------------------------------
 * Role: Orchestrates the game loop; owns canvas, objects, and subsystems.
 *
 * Public API (use these):
 * - new Engine(canvasId, worldW=window.innerWidth, worldH=window.innerHeight)
 * - addObject(obj) / removeObject(obj)
 * - start() / stop() / destroy()
 * - (optional) requestStaticRebuild()  // rebuild static caches next frame
 *
 * Collaborators:
 * - CanvasManager → sizing/DPR, resize listener.
 * - Viewport      → world→screen mapping from your fixed world size.
 * - Physics       → integrates motion + collisions in WORLD units.
 * - Renderer      → draws world & UI (and caches statics).
 * - Input, UIManager, GameStateManager (optional).
 *
 * Helpers / Internals:
 * - this.objects: array of GameObject (engine assigns stable _id for de‑dup).
 * - this.viewport: { scale, offsetX, offsetY, fit } recomputed on resize.
 * - this.layerOrder: ["background","default","foreground","ui"] (customize).
 * - this.staticCanvases/staticCtxs/_staticMeta: static cache infrastructure.
 *
 * Time step:
 * - dt is a smoothed ratio where 1 ≈ 16.67ms @ 60fps; clamp big spikes.
 * - While paused: still renders & updates UI with dt=0.
 */


export class Engine {
  /**
   * @param {string} canvasId           - id of the <canvas> element
   * @param {number} worldWidth         - logical world width (default: window.innerWidth)
   * @param {number} worldHeight        - logical world height (default: window.innerHeight)
   */
  constructor(canvasId, worldWidth = window.innerWidth, worldHeight = window.innerHeight) {
    // --- Canvas + 2D context --------------------------------------------------
    this.canvas = document.getElementById(canvasId);
    this.ctx    = this.canvas.getContext("2d");

    // Apply initial size (CSS + backing + DPR scaling)
    CanvasManager.setSize(this, window.innerWidth, window.innerHeight);

    // --- World & viewport -----------------------------------------------------
    // Fixed design resolution (all gameplay runs in these world units)
    this.world   = { width: worldWidth, height: worldHeight };

    // Viewport state; updated on resize to map world→screen
    this.viewport = { scale: 1, offsetX: 0, offsetY: 0, fit: "contain" };
    Viewport.update(this, this.viewport.fit);

    // --- Objects & loop state -------------------------------------------------
    this.objects = [];         // list of all game objects
    this.running = false;      // main loop flag
    this._nextId = 1;          // unique id (for collision pair de-dup)

    // --- Managers (optional but common) --------------------------------------
    this.ui = typeof UIManager === "function" ? new UIManager(this) : { update(){}, render(){} };
    GameStateManager?.setEngine?.(this);

    // --- Physics broad-phase config ------------------------------------------
    this.quadTreeCapacity  = 10;
    this.quadTreeMaxLevels = 5;

    this._staticRebuildRequested = false;


    // --- Rendering layers & static caches ------------------------------------
    this.layerOrder     = ["background", "default", "foreground", "ui"];
    this.staticCanvases = new Map();  // layer → offscreen canvas
    this.staticCtxs     = new Map();  // layer → offscreen ctx
    this._staticMeta    = null;       // info about last static build

    // --- Resize handling ------------------------------------------------------
    CanvasManager.handleDisplayResize(this); // runs once immediately
  }
  requestStaticRebuild() { this._staticRebuildRequested = true; }


  /** Add a new object; provide engine back-ref and stable id. */
  addObject(obj) {
    obj.engine = this;
    obj._id    = this._nextId++;
    this.objects.push(obj);
  }

  /** Remove an object (safe if not present). */
  removeObject(obj) {
    this.objects = this.objects.filter(o => o !== obj);
  }

  /** Start input + build statics + kick the main loop. */
  start() {
    this.lastTime = performance.now();
    this.running  = true;
    Input.init();
    Renderer.buildStaticLayers(this); // initial static cache
    requestAnimationFrame(this.loop.bind(this));
  }

  /** Stop the loop (non-destructive). */
  stop() { this.running = false; }

  /** Clean teardown for scene/app changes. */
  destroy() {
    this.stop();
    Input.destroy();
    CanvasManager.removeResizeListener(this);
    this.staticCanvases.clear();
    this.staticCtxs.clear();
    this.objects.length = 0;
  }

  /** Main game loop (requestAnimationFrame). */
  loop(timestamp) {
    if (!this.running) return;

    // --- Frame timing (smoothed dt in 60-fps units) --------------------------
    const elapsedMs = timestamp - this.lastTime;
    let rawDt = elapsedMs / 16.67;           // 1 == ~16.67ms
    rawDt = Math.min(rawDt, 2.0);            // clamp runaway frames
    this.dt = (this.dt !== undefined) ? (this.dt * 0.9 + rawDt * 0.1) : rawDt;
    this.lastTime = timestamp;
    const dt = this.dt;

    // --- Pause handling (still draw UI while paused) -------------------------
    if (GameStateManager?.isPaused?.()) {
      Renderer.draw(this);
      this.ui.update(0);
      this.ui.render(this.ctx);
      return requestAnimationFrame(this.loop.bind(this));
    }

    if (this._staticRebuildRequested) {
  Renderer.buildStaticLayers(this);
  this._staticRebuildRequested = false;
}
    // --- Simulation in WORLD units -------------------------------------------
    Physics.update(
      this.objects,
      dt,
      // IMPORTANT: pass WORLD bounds, not CSS size
      { width: this.world.width, height: this.world.height },
      { capacity: this.quadTreeCapacity, maxLevels: this.quadTreeMaxLevels }
    );

    // GC inactive & rebuild statics if static count changed
    const oldStaticCount = this.objects.filter(o => o.static).length;
    this.objects = this.objects.filter(o => o.active);
    if (oldStaticCount !== this.objects.filter(o => o.static).length) {
      Renderer.buildStaticLayers(this);
    }

    // --- Draw world + UI ------------------------------------------------------
    Renderer.draw(this);
    this.ui.update(dt);
    this.ui.render(this.ctx);

    requestAnimationFrame(this.loop.bind(this));
  }
}
