import { isColliding } from "./Collision.js";
import { QuadTree } from "./QuadTree.js";

export const Physics = {
  update(objects, dt, canvas) {
    objects.forEach(obj => obj.update(dt));

    const quadTrees = new Map();

    // ✅ Build separate QuadTrees per group
    objects.forEach(obj => {
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

    for (let a of objects) {
      if (!a.active || !a.collider) continue;

      // ✅ Query only groups this object can collide with
      for (let group of a.collidesWith) {
        const quadTree = quadTrees.get(group);
        if (!quadTree) continue; // No objects in that group

        const possible = quadTree.query({
          x: a.x - 5,
          y: a.y - 5,
          width: a.width + 10,
          height: a.height + 10
        });

        for (let b of possible) {
          if (a === b || !b.active || !b.collider) continue;
          if (!a.canCollideWith(b) && !b.canCollideWith(a)) continue;

          const pairKey = a._id < b._id ? `${a._id}-${b._id}` : `${b._id}-${a._id}`;
          if (checkedPairs.has(pairKey)) continue;
          checkedPairs.add(pairKey);

          if (isColliding(a, b)) {
            a.onCollision(b);
            b.onCollision(a);
          }
        }
      }
    }
  }
};
