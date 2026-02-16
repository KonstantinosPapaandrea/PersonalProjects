// File: gameEngine/core/Physics.js
import { isColliding } from "./Collision.js";
import { QuadTree }    from "./QuadTree.js";

/**
 * Physics
 * -----------------------------------------------------------------------------
 * Role: Updates positions and handles collisions (broad‑phase QuadTree +
 *       narrow‑phase AABB), with substepping and simple swept‑AABB CCD.
 *
 * Public API (use this):
 * - update(objects, dt, worldBounds, quadCfg?)
 *     objects      : GameObject[] with {x,y,width,height,vx,vy,...}
 *     dt           : normalized delta (1 ≈ 16.67ms @ 60fps)
 *     worldBounds  : { width, height } in WORLD units (design resolution)
 *     quadCfg      : { capacity?:number, maxLevels?:number }
 *
 * Expectations:
 * - GameObject.update(dt) handles input/AI only; **do not** change x/y here.
 * - Provide collisionGroup + collidesWith arrays to limit queries.
 * - For very fast movers: set useCCD=true (optionally with substepEnabled).
 */
export const Physics = {
  update(objects, dt, world, quadConfig = {}) {
    const { capacity = 10, maxLevels = 5 } = quadConfig;

    // 0) Let objects run their logic (no movement here)
    for (const o of objects) {
      if (o.active && typeof o.update === "function") o.update(dt);
    }

    // 1) Build QuadTrees per collisionGroup using WORLD bounds (not CSS)
    const quadTrees = new Map();
    for (const obj of objects) {
      if (!obj.active || !obj.collider) continue;
      const key = obj.collisionGroup;
      if (!quadTrees.has(key)) {
        quadTrees.set(
          key,
          new QuadTree(
            { x: 0, y: 0, width: world.width, height: world.height },
            capacity, 0, maxLevels
          )
        );
      }
      quadTrees.get(key).insert(obj);
    }

    // 2) Narrow-phase helper with pair de-dup
    const checkedPairs = new Set();
    const tryCollide = (a, b) => {
      // Early outs: inactive, disabled collider, or mutual ignore
      if (!a.active || !b.active || !a.collider || !b.collider) return;
      if (!a.canCollideWith(b) && !b.canCollideWith(a)) return;

      // Stable pair key (_id assigned by Engine.addObject)
      const key = a._id < b._id ? `${a._id}-${b._id}` : `${b._id}-${a._id}`;
      if (checkedPairs.has(key)) return;
      checkedPairs.add(key);

      // CCD first if either requests it (swept AABB)
      if (a.useCCD || b.useCCD) {
        const moving = a.useCCD ? a : b;
        const other  = moving === a ? b : a;
        const info = sweptAABB(moving, other, dt);
        if (info) { resolveSwept(moving, other, dt, info); return; }
      }

      // Discrete overlap
      if (isColliding(a, b)) { a.onCollision(b); b.onCollision(a); }
    };

    // 3) Integrate with optional substeps for fast movers
    for (const obj of objects) {
      if (!obj.active) continue;

      const moveX = obj.vx * dt, moveY = obj.vy * dt;
      const maxSpan = Math.max(Math.abs(moveX), Math.abs(moveY));
      const size    = Math.min(obj.width, obj.height);
      const ratio   = obj.maxMoveRatio ?? 0.5;
      const steps   = (obj.substepEnabled && maxSpan > size * ratio)
        ? Math.ceil(maxSpan / (size * ratio))
        : 1;

      const subDt = dt / steps;

      for (let s = 0; s < steps; s++) {
        // 3a) Integrate
        obj.x += obj.vx * subDt;
        obj.y += obj.vy * subDt;

        // 3b) Optional world-bounds handling (opt-in per object)
        //     Set obj.stayInWorld = true to enable clamping + simple bounce.
        if (obj.stayInWorld) {
          // Left/Right
          if (obj.x < 0) { obj.x = 0; obj.vx = Math.max(0, obj.vx); }
          if (obj.x + obj.width > world.width) {
            obj.x = world.width - obj.width;
            obj.vx = Math.min(0, obj.vx);
          }
          // Top/Bottom
          if (obj.y < 0) { obj.y = 0; obj.vy = Math.max(0, obj.vy); }
          if (obj.y + obj.height > world.height) {
            obj.y = world.height - obj.height;
            obj.vy = Math.min(0, obj.vy);
          }
        }

        // 3c) Broad-phase queries: only against groups this object cares about
        if (!obj.collider) continue;
        for (const group of obj.collidesWith || []) {
          const tree = quadTrees.get(group);
          if (!tree) continue;

          // Small padded AABB query around the object
          const potentials = tree.query({
            x: obj.x - 5, y: obj.y - 5, width: obj.width + 10, height: obj.height + 10
          });

          // 3d) Narrow-phase
          for (const other of potentials) {
            if (other === obj) continue;
            tryCollide(obj, other);
          }
        }
      }
    }
  }
};

/* ---------------- CCD helpers (swept AABB) ---------------- */
/**
 * sweptAABB(moving, target, dt)
 * Treats the moving box as a point by expanding the target by moving's size.
 * Returns { toi, normal:{x,y} } or null if no hit within this dt.
 */
function sweptAABB(moving, target, dt) {
  const vx = moving.vx, vy = moving.vy;

  // Expanded target bounds (so moving top-left acts like a point)
  const expanded = {
    x: target.x - moving.width,
    y: target.y - moving.height,
    width:  target.width  + moving.width,
    height: target.height + moving.height
  };

  const px = moving.x;  // current point position (top-left)
  const py = moving.y;

  // Parametric entry/exit times for x and y
  let txEntry, tyEntry, txExit, tyExit;

  if (vx === 0) { txEntry = -Infinity; txExit = Infinity; }
  else {
    txEntry = (expanded.x - px) / (vx * dt);
    txExit  = (expanded.x + expanded.width - px) / (vx * dt);
    if (txEntry > txExit) [txEntry, txExit] = [txExit, txEntry];
  }

  if (vy === 0) { tyEntry = -Infinity; tyExit = Infinity; }
  else {
    tyEntry = (expanded.y - py) / (vy * dt);
    tyExit  = (expanded.y + expanded.height - py) / (vy * dt);
    if (tyEntry > tyExit) [tyEntry, tyExit] = [tyExit, tyEntry];
  }

  const entry = Math.max(txEntry, tyEntry);
  const exit  = Math.min(txExit,  tyExit);

  if (entry > exit || entry < 0 || entry > 1) return null;

  // Collision normal points out of the target
  let nx = 0, ny = 0;
  if (txEntry > tyEntry) nx = (vx < 0) ? 1 : -1;
  else                   ny = (vy < 0) ? 1 : -1;

  return { toi: entry, normal: { x: nx, y: ny } };
}

function resolveSwept(moving, other, dt, info) {
  // Move to time-of-impact
  moving.x += moving.vx * dt * info.toi;
  moving.y += moving.vy * dt * info.toi;

  // Nudge out of the surface a tiny bit to avoid sticking
  const EPS = 0.01;
  moving.x += info.normal.x * EPS;
  moving.y += info.normal.y * EPS;

  // Let game logic decide post-collision velocity (bounce, slide, etc.)
  moving.onCollision(other);
  other.onCollision(moving);

  // Use remaining time with (possibly) updated velocity (no second CCD)
  const remaining = Math.max(0, 1 - info.toi) * dt;
  if (remaining > 0) {
    moving.x += moving.vx * remaining;
    moving.y += moving.vy * remaining;
  }
}
