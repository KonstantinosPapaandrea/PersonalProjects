let engine = null;
/**
 * GameStateManager
 * -----------------------------------------------------------------------------
 * Role: Tiny global state controller (e.g., "running" | "paused" | "init").
 *
 * Public API (use these):
 * - setEngine(engine)   // enables pause→resume timestamp fix
 * - setState(name)      // change to any string state; triggers onChange
 * - togglePause()       // pause/unpause; resumes loop smoothly
 * - isPaused() / is(name) / isRunning()
 * - reset()             // set state back to "running"
 *
 * Helpers / Internals:
 * - onChange callback (optional) invoked on transitions.
 * - When resuming, resets engine.lastTime to avoid a dt spike.
 */

export const GameStateManager = {
  state: "running",
  onChange: null,

  setEngine(e) {
    engine = e;
  },

  setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      if (this.onChange) this.onChange(newState);
      console.log(this.state);
    }
  },

  togglePause() {
    if (this.state === "paused") {
      this.setState("running");
      if (engine) {
        engine.lastTime = performance.now(); // ✅ Fix timestamp jump
        requestAnimationFrame(engine.loop.bind(engine));
      }
    } else {
      this.setState("paused");
    }
  },

  isPaused() {
    return this.state === "paused";
  },
  is(state) {
    return this.state === state;
  },
  isRunning() {
    return this.state === "running";
  },

  reset() {
    this.setState("running");
  }
};
