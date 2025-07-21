// main.js
import { Game } from './game-main.js';

window.addEventListener('DOMContentLoaded', () => {
  const game = new Game('gameCanvas', 0);
  game.start();
});
