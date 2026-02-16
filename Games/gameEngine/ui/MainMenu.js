// File: gameEngine/UI/MainMenu.js

// Import the base UI element class from the same UI folder
import { UIElement } from "./UIElement.js";          // ✅ keep all UI bits together
// Input for key polling (Enter to start)
import { Input }     from "../core/Input.js";
// Simple global state for "init" → "running"
import { GameStateManager } from "../util/GameStateManager.js";

/**
 * MainMenu
 * -----------------------------------------------------------------------------
 * Draws a start screen and listens for Enter to begin the game.
 * Renders in **screen space** (CSS pixels), so we use engine._cssWidth/_cssHeight.
 */
export class MainMenu extends UIElement {
  constructor(onStart, name) {
    super();               // set {engine:null, active:true}
    this.onStart = onStart; // callback to start the game when Enter is pressed
    this.name    = name;    // title shown on the menu
    // Optional: you could add a "pressed" flag to require an up→down transition
  }

  update() {
    // Only react in the "init" state. Keep logic tiny here.
    if (GameStateManager.is("init") && Input.isDown("Enter")) {
      // NOTE: If you want a true "press once" behavior, gate it with a small
      // debounce or track previous key state; for now we accept a held Enter.
      this.onStart();
    }
  }

  render(ctx) {
    // Only draw the menu in the "init" state
    if (!GameStateManager.is("init")) return;

    // Use CSS size because UIManager renders in screen space (no viewport transform)
    const width  = this.engine._cssWidth;   // logical (CSS) width
    const height = this.engine._cssHeight;  // logical (CSS) height

    // Background panel
    ctx.fillStyle = "#222";
    ctx.fillRect(0, 0, width, height);

    // Title
    ctx.fillStyle = "white";
    ctx.font = "56px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(this.name, width / 2, height / 2 - 40);

    // Prompt
    ctx.font = "24px sans-serif";
    ctx.fillText("Press ENTER to Start", width / 2, height / 2 + 20);
  }
}
