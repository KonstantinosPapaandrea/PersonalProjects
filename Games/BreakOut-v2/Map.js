import { Brick } from "./Brick.js";

/**
 * Creates a responsive brick map based on the current engine canvas size.
 * @param {Engine} engine - The game engine instance.
 * @param {number} rows - Number of brick rows.
 * @param {number} cols - Number of brick columns.
 * @param {number} marginTop - Space from the top.
 * @param {number} marginSide - Space from left & right.
 * @returns {Brick[]} Array of bricks added to the engine.
 */
export function createMap(engine, rows = 6, cols = 10, marginTop = 50, marginSide = 30) {
  const canvasWidth = engine.canvas.width;
  const canvasHeight = engine.canvas.height;

  // ---- Calculate brick sizes dynamically ----
  const totalGapX = (cols - 1) * 4; // 4px gap between bricks
  const totalWidthAvailable = canvasWidth - (2 * marginSide) - totalGapX;
  const brickWidth = totalWidthAvailable / cols;

  const totalGapY = (rows - 1) * 4; // vertical gap
  const maxBrickHeight = canvasHeight / 3; // use 1/3 of screen for bricks
  const brickHeight = (maxBrickHeight - totalGapY) / rows;

  const bricks = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const x = marginSide + col * (brickWidth + 4);
      const y = marginTop + row * (brickHeight + 4);

      // Example: make top row unbreakable
      const breakable = row !== 0;
      const color = breakable ? "green" : "grey";

      const brick = new Brick(x, y, brickWidth, brickHeight, color, breakable);
      bricks.push(brick);
      engine.addObject(brick);
    }
  }

  return bricks;
}
