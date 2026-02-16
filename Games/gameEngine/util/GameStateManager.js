// File: gameEngine/util/GameStateManager.js

let engine = null;  // back-ref to the engine so we can fix dt on resume

/**
 * GameStateManager
 * -----------------------------------------------------------------------------
 * Tiny global state controller (e.g., "init" | "running" | "paused").
 * Pausing keeps the loop running (Engine already draws UI with dt=0).
 */
export const GameStateManager = {
  state: "running",      // default state
  onChange: null,        // optional callback: (newState) => void

  /** Inject engine so we can adjust timing on resume */
  setEngine(e) { engine = e; },

  /** Set any state string; calls onChange if provided */
  setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      if (this.onChange) this.onChange(newState);
      // Removed console.log spam; add your own debug hook if needed.
    }
  },

  /** Toggle paused ↔ running with dt spike protection on resume */
  togglePause() {
    if (this.state === "paused") {
      // → RESUME
      console.log("Resuming game");
      this.setState("running");
      if (engine) {
        // Prevent a huge dt in the next frame after being paused
        engine.lastTime = performance.now();
      }
      // Do NOT call requestAnimationFrame here; Engine.loop already schedules.
    } else {
      // → PAUSE
      this.setState("paused");
  
      console.log("Game paused");}
  },

  /** Convenience checks */
  isPaused()  { return this.state === "paused";  },
  isRunning() { return this.state === "running"; },
  is(name)    { return this.state === name;      },

  /** Reset back to running (e.g., after menus) with dt spike protection */
  reset() {
    this.setState("running");
    if (engine) engine.lastTime = performance.now();
  }
};
