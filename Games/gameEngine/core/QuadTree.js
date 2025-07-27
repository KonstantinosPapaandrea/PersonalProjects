export class QuadTree {
  constructor(boundary, capacity = 10, level = 0, maxLevels = 5) {
    this.boundary = boundary; // {x, y, width, height}
    this.capacity = capacity;
    this.level = level;
    this.maxLevels = maxLevels;
    this.objects = [];
    this.divided = false;
  }

  subdivide() {
    const { x, y, width, height } = this.boundary;
    const hw = width / 2;
    const hh = height / 2;

    this.nw = new QuadTree({ x, y, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.ne = new QuadTree({ x: x + hw, y, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.sw = new QuadTree({ x, y: y + hh, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);
    this.se = new QuadTree({ x: x + hw, y: y + hh, width: hw, height: hh }, this.capacity, this.level + 1, this.maxLevels);

    this.divided = true;
  }

  insert(obj) {
    // ✅ Changed: Insert if intersects (not strict contain)
    if (!this.intersects(this.boundary, { x: obj.x, y: obj.y, width: obj.width, height: obj.height }))
      return false;

    if (this.objects.length < this.capacity || this.level >= this.maxLevels) {
      this.objects.push(obj);
      return true;
    }

    if (!this.divided) this.subdivide();

    return (
      this.nw.insert(obj) || this.ne.insert(obj) ||
      this.sw.insert(obj) || this.se.insert(obj)
    );
  }

  query(range, found = []) {
    if (!this.intersects(this.boundary, range)) return found;

    for (let obj of this.objects) {
      if (this.intersects(range, { x: obj.x, y: obj.y, width: obj.width, height: obj.height })) {
        found.push(obj);
      }
    }

    if (this.divided) {
      this.nw.query(range, found);
      this.ne.query(range, found);
      this.sw.query(range, found);
      this.se.query(range, found);
    }

    return found;
  }

  // ✅ Use intersection for everything now
  intersects(a, b) {
    return !(
      b.x > a.x + a.width ||
      b.x + b.width < a.x ||
      b.y > a.y + a.height ||
      b.y + b.height < a.y
    );
  }

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
