let engine = null;

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
