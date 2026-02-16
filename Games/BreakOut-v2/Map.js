// File: Map.js
import { Brick } from "./Brick.js";

/**
 * Creates a brick map with different patterns and brick types.
 * Patterns: "grid", "pyramid", "checkerboard", "diamond"
 */
export function createMap(
  engine,
  pattern = "grid",
  rows = 6,
  cols = 10,
  marginTop = 50,
  marginSide = 5,
  gapX = 5,
  gapY = 5
) {
  const W = engine.world.width;
  const H = engine.world.height;
  // --- Compute brick size (guard against negative/too-small values) ---
  const totalGapX = Math.max(0, (cols - 1) * gapX);
  const availW = Math.max(0, W - 2 * marginSide - totalGapX);
  const brickWidth = Math.max(1, availW / cols);

  const totalGapY = Math.max(0, (rows - 1) * gapY);
  const maxRegionH = Math.max(0, H / 3 - totalGapY);   // keep bricks in top third
  const brickHeight = Math.max(1, maxRegionH / rows);

  const bricks = [];
  const centerCol = Math.floor(cols / 2);
  const midRow = Math.floor(rows / 2);

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      let place = true;
      switch (pattern) {
        case "pyramid": {
          // Widen by one column per side each row (top row = 1 brick at center)
          const left  = Math.max(0, centerCol - r);
          const right = Math.min(cols - 1, centerCol + r);
          place = (c >= left && c <= right);
          break;
        }
        case "diamond": {
          // Manhattan-distance diamond centered in the grid
          place = (Math.abs(r - midRow) + Math.abs(c - centerCol) <= midRow);
          break;
        }
        case "checkerboard":
          place = ((r + c) % 2 === 0);
          break;
        case "grid":
        default:
          place = true;
      }
      if (!place) continue;

      const x = marginSide + c * (brickWidth + gapX);
      const y = marginTop  + r * (brickHeight + gapY);

      // Slight variety: top rows tougher
      const breakable = Math.random() > 0.2 || r > 1;
      const color = breakable ? "green" : "grey";

      const brick = new Brick(x, y, brickWidth, brickHeight, color, breakable);
      bricks.push(brick);
      engine.addObject(brick);
    }
  }

  return bricks;
}
