import { Brick } from "./Brick.js";

/**
 * Creates a brick map with different patterns and brick types.
 * @param {Engine} engine
 * @param {string} pattern - "grid", "pyramid", "checkerboard", "diamond"
 * @param {number} rows
 * @param {number} cols
 * @param {number} marginTop
 * @param {number} marginSide
 * @param {number} gapX
 * @param {number} gapY
 */
export function createMap(
  engine,
  pattern = "grid",
  rows = 20,
  cols = 100,
  marginTop = 50,
  marginSide = 5,
  gapX = 5,
  gapY = 5
) {
  const canvasWidth = engine.canvas.width;
  const canvasHeight = engine.canvas.height;

  const totalGapX = (cols - 1) * gapX;
  const totalWidthAvailable = canvasWidth - (2 * marginSide) - totalGapX;
  const brickWidth = totalWidthAvailable / cols;

  const totalGapY = (rows - 1) * gapY;
  const maxBrickHeight = canvasHeight / 3;
  const brickHeight = (maxBrickHeight - totalGapY) / rows;

  const bricks = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      // ✅ Calculate position
      const x = marginSide + col * (brickWidth + gapX);
      const y = marginTop + row * (brickHeight + gapY);

      // ✅ Pattern logic
      let placeBrick = true;
      switch (pattern) {
        case "pyramid":
          if (col < (cols / 2 - row / 2) || col > (cols / 2 + row / 2)) placeBrick = false;
          break;

        case "checkerboard":
          if ((row + col) % 2 !== 0) placeBrick = false;
          break;

        case "diamond":
          const mid = rows / 2;
          if (Math.abs(col - cols / 2) > Math.abs(mid - row)) placeBrick = false;
          break;

        case "grid":
        default:
          placeBrick = true;
      }

      if (!placeBrick) continue;

      // ✅ Brick Type (randomized for fun)
      const breakable = Math.random() > 0.2 || row > 1; // top rows harder
      const color = breakable ? "green" : "grey";

      const brick = new Brick(x, y, brickWidth, brickHeight, color, breakable);
      bricks.push(brick);
      engine.addObject(brick);
    }
  }

  return bricks;
}
