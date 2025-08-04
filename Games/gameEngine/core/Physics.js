// File: Physics.js
import { isColliding } from "./Collision.js";
import { QuadTree } from "./QuadTree.js";

/**
 * Basic swept AABB vs AABB time-of-impact test.
 * Returns an object { collided: boolean, toi: number, normal: {x,y} }
 * or null if no collision within the frame.
 */
function sweptAABB(moving, target, dt) {
  // Calculate relative velocity
  const vx = moving.vx;
  const vy = moving.vy;

  // Expand target by moving size (to treat moving as a point)
  const expanded = {
    x: target.x - moving.width / 2,
    y: target.y - moving.height / 2,
    width: target.width + moving.width,
    height: target.height + moving.height
  };

  // Ray from center of moving box
  const px = moving.x + moving.width / 2;
  const py = moving.y + moving.height / 2;

  // Avoid division by zero
  let txEntry, tyEntry, txExit, tyExit;
  if (vx === 0) {
    txEntry = -Infinity;
    txExit = Infinity;
  } else {
    txEntry = (expanded.x - px) / (vx * dt);
    txExit = (expanded.x + expanded.width - px) / (vx * dt);
    if (txEntry > txExit) [txEntry, txExit] = [txExit, txEntry];
  }

  if (vy === 0) {
    tyEntry = -Infinity;
    tyExit = Infinity;
  } else {
    tyEntry = (expanded.y - py) / (vy * dt);
    tyExit = (expanded.y + expanded.height - py) / (vy * dt);
    if (tyEntry > tyExit) [tyEntry, tyExit] = [tyExit, tyEntry];
  }

  const entryTime = Math.max(txEntry, tyEntry);
  const exitTime = Math.min(txExit, tyExit);

  if (entryTime > exitTime || entryTime < 0 || entryTime > 1) {
    return null; // no collision within this frame
  }

  // Determine normal
  let normal = { x: 0, y: 0 };
  if (txEntry > tyEntry) {
    normal.x = vx < 0 ? 1 : -1;
  } else {
    normal.y = vy < 0 ? 1 : -1;
  }

  return {
    collided: true,
    toi: entryTime, // time of impact (0..1)
    normal
  };
}

/**
 * Applies response for swept collision: move to impact, reflect velocity, and
 * advance the remaining time.
 */
function resolveSwept(moving, other, dt, collisionInfo) {
  const { toi, normal } = collisionInfo;

  // Move to time of impact
  moving.x += moving.vx * dt * toi;
  moving.y += moving.vy * dt * toi;

  // Simple reflection: reflect velocity across normal
  if (normal.x !== 0) moving.vx = -moving.vx;
  if (normal.y !== 0) moving.vy = -moving.vy;

  // Small epsilon pull to avoid re-colliding
  const eps = 0.001;
  moving.x += normal.x * eps;
  moving.y += normal.y * eps;

  // Call collision callbacks
  moving.onCollision(other);
  other.onCollision(moving);

  // Advance remaining time after impact
  const remaining = 1 - toi;
  moving.x += moving.vx * dt * remaining;
  moving.y += moving.vy * dt * remaining;
}

export const Physics = {
  update(objects, dt, canvas) {
      // ---- 0. Let objects do their per-frame logic (input, internal state) ----
  objects.forEach(obj => {
    if (!obj.active) return;
    if (typeof obj.update === "function") obj.update(dt);
  });

    // ---- 1. Update phase with optional substepping per object ----
    const toProcess = [...objects]; // copy to allow in-place modifications

    // Build separate QuadTrees per group for broad-phase
    const quadTrees = new Map();
    toProcess.forEach(obj => {
      if (!obj.active || !obj.collider) return;
      if (!quadTrees.has(obj.collisionGroup)) {
        quadTrees.set(
          obj.collisionGroup,
          new QuadTree({ x: 0, y: 0, width: canvas.width, height: canvas.height })
        );
      }
      quadTrees.get(obj.collisionGroup).insert(obj);
    });

    const checkedPairs = new Set();

    // Helper for collision checking between a and b
    const tryCollide = (a, b) => {
      if (!a.active || !b.active || !a.collider || !b.collider) return;
      if (!a.canCollideWith(b) && !b.canCollideWith(a)) return;
      const pairKey = a._id < b._id ? `${a._id}-${b._id}` : `${b._id}-${a._id}`;
      if (checkedPairs.has(pairKey)) return;
      checkedPairs.add(pairKey);

      // If either wants swept CCD and both are moving, try that first
      if (a.useCCD || b.useCCD) {
        // We'll treat 'a' as moving for simplicity; more complex bidirectional CCD would iterate both
        const moving = a.useCCD ? a : b;
        const other = moving === a ? b : a;
        const collisionInfo = sweptAABB(moving, other, dt);
        if (collisionInfo) {
          resolveSwept(moving, other, dt, collisionInfo);
          return;
        }
      }

      // Discrete fallback
      if (isColliding(a, b)) {
        // Basic penetration correction (nudge)
        a.onCollision(b);
        b.onCollision(a);
      }
    };

    // ---- 2. Movement + collision resolution ----
    for (let obj of toProcess) {
      if (!obj.active) continue;

      // Substepping decision
      const moveX = obj.vx * dt;
      const moveY = obj.vy * dt;
      const maxSpan = Math.max(Math.abs(moveX), Math.abs(moveY));
      const size = Math.min(obj.width, obj.height);
      const ratio = obj.maxMoveRatio ?? 0.5; // default cap
      const threshold = size * ratio;

      const steps = obj.substepEnabled && maxSpan > threshold
        ? Math.ceil(maxSpan / threshold)
        : 1;

      const subDt = dt / steps;
      for (let step = 0; step < steps; step++) {
        // Apply movement
        obj.x += obj.vx * subDt;
        obj.y += obj.vy * subDt;

        // Broad-phase: gather possible collisions based on groups
        if (!obj.collider || !obj.active) continue;

        for (let group of obj.collidesWith || []) {
          const quadTree = quadTrees.get(group);
          if (!quadTree) continue;
          const possible = quadTree.query({
            x: obj.x - 5,
            y: obj.y - 5,
            width: obj.width + 10,
            height: obj.height + 10
          });
          for (let other of possible) {
            if (obj === other) continue;
            tryCollide(obj, other);
          }
        }
      }
    }

    // Note: cleanup (removal) should be handled by caller / engine layer after physics
  }
};
