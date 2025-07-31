import { Engine }      from "../gameEngine/core/Engine.js";
import { TicTacToeUI } from "./TicTacToeUI.js";

// 3 cells ×100px + 40px for status
const VIRTUAL_W = 300;
const VIRTUAL_H = 340;
const engine = new Engine("gameCanvas", VIRTUAL_W, VIRTUAL_H, { useVirtualResolution: false });

// Add the TicTacToe UI, passing the engine
engine.ui.add(new TicTacToeUI(engine, 100));

// Start the engine
engine.start();
