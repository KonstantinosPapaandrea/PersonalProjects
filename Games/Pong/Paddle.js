// Paddle.js (Pong-style paddle)
import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input } from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  constructor(x, y, width, height, color = "white", speed,name) {
    super(x, y, width, height, color);
    this.speed = speed;
    this.collisionGroup = "paddle";
    this.collidesWith = ["ball"];
    this.name=name;
  }

  update(dt) {
// inside update(dt) or similar per-frame logic
this.vy = 0; // reset first

if (this.name === "Player2") {
  if (Input.isDown("ArrowUp")) this.vy = -this.speed;
  else if (Input.isDown("ArrowDown")) this.vy = this.speed;
} else {
  if (Input.isDown("w") || Input.isDown("W")) this.vy = -this.speed;
  else if (Input.isDown("s") || Input.isDown("S")) this.vy = this.speed;
}
   
    super.update(dt);

    // Clamp to canvas
    if (this.engine) {
      if (this.y < 0) this.y = 0;
      if (this.y + this.height > this.engine.canvas.height)
        this.y = this.engine.canvas.height - this.height;
    }
  }
}
