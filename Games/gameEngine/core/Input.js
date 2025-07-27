/**
 * Input Manager – Keyboard Handling
 *
 * This simple utility tracks which keys are currently pressed.
 * 
 * How it works:
 * 1. `init()` attaches event listeners for keydown and keyup.
 * 2. `keys` is a dictionary (object) where keys are stored as true/false.
 * 3. `isDown(key)` checks if a specific key is currently pressed.
 *
 * Example:
 *  if (Input.isDown("ArrowLeft")) { ... }  // Move left while holding left arrow
 */

export const Input = {
  // ✅ Stores key states: e.g., { "ArrowLeft": true, "ArrowRight": false }
  keys: {},

  // ✅ Initializes event listeners to track key presses
  init() {
    // When a key is pressed → set its state to true
    window.addEventListener("keydown", e => (this.keys[e.key] = true));

    // When a key is released → set its state to false
    window.addEventListener("keyup", e => (this.keys[e.key] = false));
  },

  // ✅ Check if a specific key is currently pressed
  isDown(key) {
    return this.keys[key] === true;
  }
};
