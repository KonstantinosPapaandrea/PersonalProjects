/**
 * GameObject – Base Class for All Game Entities
 *
 * This is the parent class for every object in the engine.
 * It provides basic properties like position, size, movement, and collision.
 *
 * Key Features:
 * ✅ Position & movement (x, y, vx, vy)
 * ✅ Collision support (`collider`, `collisionGroup`, `onCollision`)
 * ✅ Active state for removal from the game loop
 * ✅ Static objects (e.g., bricks, walls) are optimized (drawn once on a static layer)
 *
 * Typical Usage:
 *  class Ball extends GameObject { update(dt) { ... } onCollision(other) { ... } }
 */

export class GameObject {
  constructor(x, y, width, height, color = "white") {
    // ✅ Position and size
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
    this.color = color;

    // ✅ Movement (velocity)
    this.vx = 0; // horizontal speed (pixels per frame)
    this.vy = 0; // vertical speed (pixels per frame)

    // ✅ Game state flags
    this.active = true;     // if false → will be removed from the engine
    this.collider = true;   // participates in collision detection
    this.static = false;    // static objects (bricks, walls) do not move & can be drawn once

    // ✅ Collision groups
    this.collisionGroup = "default";   // The group this object belongs to
    this.collidesWith = ["default"];   // Groups this object can collide with

    // ✅ Reference to the engine (set automatically by engine.addObject)
    this.engine = null;

    // ✅ Unique ID for each object (used to avoid duplicate collision checks)
    if (!GameObject._nextId) GameObject._nextId = 1;
    this._id = GameObject._nextId++;
  }

  /**
   * update(dt)
   * Called every frame by the engine.
   * Moves the object based on its velocity (if not static).
   *
   * @param {number} dt - Delta time (frame time ratio)
   */
  update(dt) {
    if (!this.static) {
      this.x += this.vx * dt;
      this.y += this.vy * dt;
    }
  }

  /**
   * render(ctx)
   * Draws the object on the canvas (default: simple colored rectangle).
   * Subclasses can override for custom drawing.
   */
  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  /**
   * onCollision(other)
   * Called automatically by the engine when a collision is detected.
   * Override in subclasses (e.g., Ball bounce, Brick destroy).
   */
  onCollision(other) {}

  /**
   * canCollideWith(other)
   * Determines if this object should collide with another object.
   * Override to filter collision groups (e.g., balls shouldn’t collide with other balls).
   */
  canCollideWith(other) {
    return true;
  }

  /**
   * destroy()
   * Marks the object as inactive (will be removed by engine).
   * If it's static, triggers a static layer rebuild.
   */
  destroy() {
    this.active = false;
    if (this.static) this.engine._staticLayerDirty = true;
  }
}
