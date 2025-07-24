// ---- Game Initialization ----
const engine = new Engine("gameCanvas", 500, 320);

const paddle = new Paddle(200, 300, 80, 15, "blue");
const ball = new Ball(240, 200, 8, "red");
const bricks = [];

// Create a grid of bricks
for (let row = 0; row < 5; row++) {
  for (let col = 0; col < 8; col++) {
    const brick = new Brick(60 * col + 20, 30 * row + 20, 50, 20, "green");
    bricks.push(brick);
    engine.addObject(brick);
  }
}

// Add objects to the engine
engine.addObject(paddle);
engine.addObject(ball);

engine.start(); // Run the game
