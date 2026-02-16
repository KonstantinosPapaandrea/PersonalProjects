// File: gameEngine/core/Collision.js

/**
 * isColliding(a, b)
 * -----------------------------------------------------------------------------
 * Purpose: Fast AABB vs AABB overlap test (axis-aligned rectangles).
 * Returns: true if the rectangles overlap, false otherwise.
 * Used by: Physics discrete collision path and broad-phase filtering.
 */
export function isColliding(a, b) {
  return (
    a.x < b.x + b.width  &&   // A's left is left of B's right
    a.x + a.width > b.x  &&   // A's right is right of B's left
    a.y < b.y + b.height &&   // A's top is above B's bottom
    a.y + a.height > b.y      // A's bottom is below B's top
  );
}
