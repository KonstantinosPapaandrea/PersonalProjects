// === File: Input.js ===
export const Input = {
  keys: {},

  init() {
    window.addEventListener("keydown", e => {
      this.keys[e.key] = true;
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "].includes(e.key)) {
        e.preventDefault();
      }
    });

    window.addEventListener("keyup", e => (this.keys[e.key] = false));
  },

  isDown(key) {
    return this.keys[key] === true;
  }
};
