// File: TicTacToe/TicTacToeUI.js
import { UIElement } from "../gameEngine/UI/UIElement.js";

export class TicTacToeUI extends UIElement {
  /**
   * @param {Engine} engine    - the engine instance
   * @param {number} cellSize  - pixel size of each cell
   */
  constructor(engine, cellSize = 100) {
    super();
    this.engine   = engine;       // grab reference immediately
    this.cellSize = cellSize;
    this.board    = [
      ["","",""],
      ["","",""],
      ["","",""]
    ];
    this.current = "X";
    this.winner  = null;

    // now it's safe to bind to engine.canvas
    this.engine.canvas.addEventListener("click", this.onClick.bind(this));
  }

  onClick(e) {
    if (this.winner) return;
    const rect = this.engine.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const col = Math.floor(x / this.cellSize);
    const row = Math.floor(y / this.cellSize);
    if (row < 0 || row > 2 || col < 0 || col > 2) return;
    if (this.board[row][col] !== "") return;

    this.board[row][col] = this.current;
    if (this.checkWin(this.current)) this.winner = this.current;
    else if (this.board.flat().every(v => v !== "")) this.winner = "DRAW";
    else this.current = this.current === "X" ? "O" : "X";
  }

  checkWin(p) {
    const B = this.board;
    for (let i = 0; i < 3; i++) {
      if (B[i][0] === p && B[i][1] === p && B[i][2] === p) return true;
      if (B[0][i] === p && B[1][i] === p && B[2][i] === p) return true;
    }
    if (B[0][0] === p && B[1][1] === p && B[2][2] === p) return true;
    if (B[0][2] === p && B[1][1] === p && B[2][0] === p) return true;
    return false;
  }

  render(ctx) {
    const size = this.cellSize * 3;
    // draw grid
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 4;
    for (let i = 1; i < 3; i++) {
      ctx.beginPath();
      ctx.moveTo(i * this.cellSize, 0);
      ctx.lineTo(i * this.cellSize, size);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * this.cellSize);
      ctx.lineTo(size, i * this.cellSize);
      ctx.stroke();
    }

    // draw marks
    ctx.font = `${this.cellSize * 0.8}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        const mark = this.board[r][c];
        if (!mark) continue;
        ctx.fillStyle = mark === "X" ? "red" : "blue";
        ctx.fillText(
          mark,
          c * this.cellSize + this.cellSize / 2,
          r * this.cellSize + this.cellSize / 2
        );
      }
    }

    // draw status
    ctx.fillStyle = "black";
    ctx.font = "20px sans-serif";
    ctx.fillText(
      this.winner
        ? this.winner === "DRAW"
          ? "Draw!"
          : `${this.winner} Wins!`
        : `Turn: ${this.current}`,
      size / 2,
      size + 20
    );
  }
}
