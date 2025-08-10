// File: gameEngine/core/GameObject.js
/**
 * GameObject (base)
 * -----------------------------------------------------------------------------
 * Role: Minimal base for anything that updates/renders. Physics reads/writes
 *       x/y via velocities; rendering is separate.
 *
 * Public API (use/override these):
 * - constructor(x,y,w,h,color?)
 * - update(dt)       // game logic (no movement here)
 * - render(ctx)      // default: filled rect; override for sprites/text
 * - onCollision(other)
 * - canCollideWith(other) → optional guard (default true)
 * - destroy()        // mark inactive; Engine GCs
 *
 * Common fields:
 * - x,y,width,height,color,vx,vy,active,collider,static,layer
 * - collisionGroup (string), collidesWith (string[]), useCCD, substepEnabled
 * - maxMoveRatio (substep threshold), engine (set by Engine), _id (Engine)
 */

export class GameObject {
  constructor(x, y, width, height, color = "white") {
    // Transform & visuals
    this.x = x; this.y = y;
    this.width = width; this.height = height;
    this.color = color;

    // Motion (Physics reads these)
    this.vx = 0; this.vy = 0;

    // Lifecycle / collision flags
    this.active   = true;
    this.collider = true;
    this.static   = false;        // true → pre-rendered to static layer
    this.layer    = "default";    // draw layer
    this.engine   = null;         // back-ref set by Engine.addObject
    this._id      = undefined;    // set by Engine for pair de-dup

    // Safe defaults for collision system
    this.collisionGroup = this.collisionGroup ?? "default";
    this.collidesWith   = this.collidesWith   ?? [];
    this.useCCD         = this.useCCD         ?? false;
    this.substepEnabled = this.substepEnabled ?? true;
    this.maxMoveRatio   = this.maxMoveRatio   ?? 0.5; // substep threshold
  }

  /**
   * update(dt)
   * -----------------------------------------------------------------------------
   * Purpose:
   *   For input/AI/timers/animations. **Do not move** here; Physics integrates.
   */
  update(dt) { /* no-op by default */ }

  /**
   * render(ctx)
   * -----------------------------------------------------------------------------
   * Default: draw a filled rect. Override for sprites, text, etc.
   */
  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  /** onCollision(other): override in subclasses for responses. */
  onCollision(other) {}

  /**
   * canCollideWith(other)
   * -----------------------------------------------------------------------------
   * Optional guard. Return true if this object wants to collide with `other`.
   * (You also filter by `collidesWith` during broad-phase queries.)
   */
  canCollideWith(other) { return true; }

  /** Mark for removal; Engine will GC it after this frame. */
  destroy() { this.active = false; }
}
