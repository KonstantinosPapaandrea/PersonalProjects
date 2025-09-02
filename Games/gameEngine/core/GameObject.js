// File: gameEngine/core/GameObject.js
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

    // Collision broad/narrow-phase defaults
    this.collisionGroup = this.collisionGroup ?? "default";
    this.collidesWith   = this.collidesWith   ?? [];

    // Motion quality (substeps & CCD)
    this.useCCD         = this.useCCD         ?? false;
    this.substepEnabled = this.substepEnabled ?? true;
    this.maxMoveRatio   = this.maxMoveRatio   ?? 0.5; // substep threshold

    // World bounds handling (Physics will honor this if true)
    this.stayInWorld    = this.stayInWorld    ?? false;
  }

  update(dt) { /* input/AI/timers/animations only; Physics moves you */ }

  render(ctx) {
    ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.width, this.height);
  }

  onCollision(other) { /* override for collision response */ }

  canCollideWith(other) { return true; }

  destroy() { this.active = false; }
}
