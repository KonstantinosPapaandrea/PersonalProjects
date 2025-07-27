/**
 * isColliding – Simple AABB Collision Detection
 *
 * Checks if two rectangles (axis-aligned bounding boxes) are overlapping.
 * Works for all rectangular game objects (bricks, paddle, balls approximated as squares).
 *
 * How It Works:
 * ✅ Compares the edges of two objects:
 *    - Left edge of A is left of right edge of B
 *    - Right edge of A is right of left edge of B
 *    - Top edge of A is above bottom edge of B
 *    - Bottom edge of A is below top edge of B
 *
 * Returns:
 * ✅ true if rectangles overlap, false otherwise
 */

export function isColliding(a, b) {
  return (
    a.x < b.x + b.width &&      // A's left edge is left of B's right edge
    a.x + a.width > b.x &&      // A's right edge is right of B's left edge
    a.y < b.y + b.height &&     // A's top edge is above B's bottom edge
    a.y + a.height > b.y        // A's bottom edge is below B's top edge
  );
}
