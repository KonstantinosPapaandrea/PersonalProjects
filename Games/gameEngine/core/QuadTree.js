/**
 * QuadTree – Spatial Partitioning for Collision Optimization
 *
 * A QuadTree recursively divides the game area into 4 smaller rectangles (nodes)
 * to group nearby objects together. Instead of checking every object against all others,
 * we only check objects inside the same or neighboring nodes.
 *
 * How it works:
 * 1. Insert objects into the QuadTree.
 *    - If a node exceeds its capacity, it subdivides into 4 child nodes.
 * 2. Query objects by providing a range (e.g., the area around a ball).
 *    - Returns only objects that might collide with the queried object.
 *
 * Benefits:
 * ✅ Reduces collision checks from O(n²) to ~O(n log n)
 * ✅ Essential for games with many objects (e.g., lots of bricks or bullets)
 */

export class QuadTree {
  constructor(boundary, capacity = 10, level = 0, maxLevels = 5) {
    // The rectangular area this QuadTree covers
    // Example: {x:0, y:0, width:800, height:600}
    this.boundary = boundary;

    // Max objects before splitting into 4 sub-trees
    this.capacity = capacity;

    // Depth level in the tree (root = 0)
    this.level = level;

    // Limit depth to avoid infinite subdivision
    this.maxLevels = maxLevels;

    // Objects currently stored in this node (only if not subdivided yet)
    this.objects = [];

    // Whether this node is subdivided into 4 child QuadTrees
    this.divided = false;
  }

  // ✅ Split the current QuadTree into 4 child nodes
  subdivide() {
    const { x, y, width, height } = this.boundary;
    const hw = width / 2;  // half width
    const hh = height / 2; // half height

    // 4 children: NW, NE, SW, SE
    this.nw = new QuadTree({ x, y, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.ne = new QuadTree({ x: x + hw, y, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.sw = new QuadTree({ x, y: y + hh, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.se = new QuadTree({ x: x + hw, y: y + hh, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);

    this.divided = true;
  }

  // ✅ Insert an object into the tree
  insert(obj) {
    // Ignore objects outside this boundary
    if (!this.intersects(this.boundary, obj)) return false;

    // If there is space in this node OR max depth reached → store it here
    if (this.objects.length < this.capacity || this.level >= this.maxLevels) {
      this.objects.push(obj);
      return true;
    }

    // Otherwise, subdivide and pass the object to the appropriate children
    if (!this.divided) this.subdivide();

    // Insert into children (only one child will return true)
    return (
      this.nw.insert(obj) ||
      this.ne.insert(obj) ||
      this.sw.insert(obj) ||
      this.se.insert(obj)
    );
  }

  // ✅ Query all objects in a given range (e.g., for collision checks)
  query(range, found = []) {
    // If range doesn't overlap this boundary → skip
    if (!this.intersects(this.boundary, range)) return found;

    // Check objects stored in this node
    for (let obj of this.objects) {
      if (this.intersects(range, obj)) {
        found.push(obj);
      }
    }

    // Recursively check children if subdivided
    if (this.divided) {
      this.nw.query(range, found);
      this.ne.query(range, found);
      this.sw.query(range, found);
      this.se.query(range, found);
    }

    return found;
  }

  // ✅ Axis-Aligned Bounding Box (AABB) intersection test
  intersects(a, b) {
    return !(
      b.x > a.x + a.width ||
      b.x + b.width < a.x ||
      b.y > a.y + a.height ||
      b.y + b.height < a.y
    );
  }

  // ✅ Clear all objects (e.g., between frames)
  clear() {
    this.objects = [];
    if (this.divided) {
      this.nw.clear();
      this.ne.clear();
      this.sw.clear();
      this.se.clear();
      this.divided = false;
    }
  }
}
