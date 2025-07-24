// ==============================
// ENGINE CORE
// ==============================

// ---- GameObject Base Class ----
// This is the parent class that ALL objects
// will inherit from. It handles position, size, velocity, and basic rendering.

class GameObject {
  constructor(x, y, width, height, color = "white") {
    this.x = x; //x-coords
    this.y = y; //y-coords
    this.width = width; //width
    this.height = height; //height
    this.color = color; //color
    this.vx = 0; //horizontal velocity
    this.vy = 0; //vertical velocity
    this.active = true; // useful for removing objects later
  }

  update(dt) {
    // Move the object based on velocity and delta time
    this.x += this.vx * dt;
    this.y += this.vy * dt;
  }

  render(ctx) {
    // Default render method: draw a filled rectangle
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }
    destroy() {
    //  Call this when you want to remove the object from the game
    this.active = false;
  }
}

// ---- Input Manager ----
// Handles all keyboard input in one place.
// Future games can reuse it for WASD, arrows, space, etc.
const Input = {
  keys: {}, // Stores pressed keys as true/false
  init() {
    // Track when keys are pressed
    window.addEventListener("keydown", e => (this.keys[e.key] = true));
    // Track when keys are released
    window.addEventListener("keyup", e => (this.keys[e.key] = false));
  },
  isDown(key) {
    // Helper to check if a specific key is pressed
    return this.keys[key] === true;
  }
};
// ---- Collision Helper (AABB) ----
// AABB = Axis-Aligned Bounding Box collision detection.
// Checks if two rectangles overlap.
function isColliding(a, b) {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}

// ---- Engine Core ----
// Handles the main game loop, updates, and rendering for all objects.

class Engine {
  constructor(canvasId, width, height) {
    this.canvas = document.getElementById(canvasId);  // Reference to <canvas>
    this.ctx = this.canvas.getContext("2d");          // Drawing context (2D)
    this.canvas.width = width;
    this.canvas.height = height;
    this.lastTime = 0;     // Tracks last frame timestamp (for delta time calculation)
    this.objects = [];     // Stores all GameObjects in the scene
    this.running = false;  // Controls if the game loop is running
  }

  addObject(obj) {
    // Add any object (Ball, Paddle, Brick) to be managed by the engine
    this.objects.push(obj);
  }

  start() {
    // Start the engine loop
    this.running = true;
    Input.init();           // Initialize keyboard input
    requestAnimationFrame(this.loop.bind(this));
  }

  loop(timestamp) {
    if (!this.running) return;

    // ---- Delta Time Calculation ----
    // dt ~ 1 when running at 60fps. Multiplying velocities by dt makes movement
    // framerate-independent.
    let dt = (timestamp - this.lastTime) / 16.67;
    this.lastTime = timestamp;

    // ---- Update ----
    this.objects.forEach(obj => obj.update(dt));
  //  Remove destroyed objects
  this.objects = this.objects.filter(obj => obj.active);
    // ---- Render ----
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height); // Clear canvas
    this.objects.forEach(obj => obj.render(this.ctx));

    // ---- Next Frame ----
    requestAnimationFrame(this.loop.bind(this));
  }
}
