// File: gameEngine/core/QuadTree.js

/**
 * QuadTree
 * -----------------------------------------------------------------------------
 * Role: Spatial partition so collision checks drop from O(n^2) to ~O(n log n).
 *
 * Public API (use these):
 * - new QuadTree(boundary, capacity=10, level=0, maxLevels=5)
 * - insert(obj)     → store an object with AABB (x,y,width,height)
 * - query(range)    → collect objects intersecting 'range'
 * - clear()         → wipe objects and children
 *
 * Helpers / Internals:
 * - subdivide()     → nw/ne/sw/se children once capacity is exceeded.
 * - _fits(rect,obj) → only descends if the object fully fits the child.
 * - intersects(a,b) → fast AABB overlap helper.
 *
 * Invariants:
 * - Objects that span multiple children stay at the current node.
 * - Query short‑circuits if the search rect misses this node’s boundary.
 */

export class QuadTree {
  constructor(boundary, capacity = 10, level = 0, maxLevels = 5) {
    this.boundary  = boundary;       // {x,y,width,height}
    this.capacity  = capacity;       // max objects before subdividing
    this.level     = level;          // depth of this node
    this.maxLevels = maxLevels;      // limit recursion
    this.objects   = [];             // objects stored at this node
    this.divided   = false;          // whether children exist
  }

  /** Split into 4 children (nw, ne, sw, se). */
  subdivide() {
    const { x, y, width, height } = this.boundary;
    const hw = width  / 2;
    const hh = height / 2;

    this.nw = new QuadTree({ x: x,       y: y,       width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.ne = new QuadTree({ x: x + hw,  y: y,       width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.sw = new QuadTree({ x: x,       y: y + hh,  width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.se = new QuadTree({ x: x + hw,  y: y + hh,  width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);

    this.divided = true;
  }

  /** Axis-aligned rectangle overlap test. */
  intersects(a, b) {
    return !(b.x > a.x + a.width ||
             b.x + b.width < a.x ||
             b.y > a.y + a.height ||
             b.y + b.height < a.y);
  }

  /** Does 'obj' fit fully within 'rect'? */
  _fits(rect, obj) {
    return (
      obj.x >= rect.x &&
      obj.y >= rect.y &&
      obj.x + obj.width  <= rect.x + rect.width &&
      obj.y + obj.height <= rect.y + rect.height
    );
  }

  /**
   * Insert an object. If at capacity and under max depth, subdivide and try to
   * descend into a child that **fully contains** the object; otherwise keep at
   * this node so queries from multiple children can still hit it.
   */
  insert(obj) {
    // ignore objects completely outside this node
    if (!this.intersects(this.boundary, obj)) return false;

    // store here if capacity ok or we're at max depth
    if (this.objects.length < this.capacity || this.level >= this.maxLevels) {
      this.objects.push(obj);
      return true;
    }

    // otherwise, subdivide if needed and try children
    if (!this.divided) this.subdivide();

    if      (this._fits(this.nw.boundary, obj)) return this.nw.insert(obj);
    else if (this._fits(this.ne.boundary, obj)) return this.ne.insert(obj);
    else if (this._fits(this.sw.boundary, obj)) return this.sw.insert(obj);
    else if (this._fits(this.se.boundary, obj)) return this.se.insert(obj);

    // doesn’t fit in a single child → keep at this node
    this.objects.push(obj);
    return true;
  }

  /** Collect all objects intersecting 'range'. */
  query(range, found = []) {
    if (!this.intersects(this.boundary, range)) return found;

    for (const obj of this.objects) {
      if (this.intersects(range, obj)) found.push(obj);
    }

    if (this.divided) {
      this.nw.query(range, found);
      this.ne.query(range, found);
      this.sw.query(range, found);
      this.se.query(range, found);
    }
    return found;
  }

  /** Remove everything (use between frames if you reuse trees). */
  clear() {
    this.objects.length = 0;
    if (this.divided) {
      this.nw.clear(); this.ne.clear();
      this.sw.clear(); this.se.clear();
      this.divided = false;
    }
  }
}
