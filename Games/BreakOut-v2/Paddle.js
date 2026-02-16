// File: Paddle.js
import { GameObject } from "../gameEngine/core/GameObject.js";
import { Input }      from "../gameEngine/core/Input.js";

export class Paddle extends GameObject {
  constructor(x, y, width, height, color = "blue") {
    super(x, y, width, height, color);

    // Grouping for Physics queries
    this.collisionGroup = "paddle";
    this.collidesWith   = ["ball", "powerup"];

    // Let Physics clamp us inside the world bounds (no bounce for paddles)
    this.stayInWorld = true;   // Physics will clamp x/y and zero bad velocity
  }

  update(dt) {
    // Respond to input; Physics will integrate after this
    if (Input.isKeyDown("ArrowLeft"))      this.vx = -20;
    else if (Input.isKeyDown("ArrowRight")) this.vx =  20;
    else                                    this.vx =   0;

    // Do NOT move or clamp here; Physics will handle both.
  }
}
