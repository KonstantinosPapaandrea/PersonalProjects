// levels.js
// ===========
// 0 = empty, 1 = breakable, 2 = unbreakable

const ROWS = 20;
const COLS = 100;
const center = Math.floor(COLS / 2);
const emptyCols = [center - 1, center, center + 1];

// Build a “T”–shaped empty region:
//  • A full horizontal bar (empty) at row 2, across all interior columns.
//  • A 3‑column‑wide vertical stem at the center columns from row 2 down.
// Surround that interior with an unbreakable border — except leave open the 3 middle columns at the bottom.
const tWithBorder = Array.from({ length: ROWS }, (_, r) =>
  Array.from({ length: COLS }, (_, c) => {
    // 1) Horizontal bar at row 2 (interior only)
    if ((r === 2 || r===3 || r===4) && c > 0 && c < COLS - 1) {
      return 0;
    }

    // 2) Vertical stem (3‑wide) from row 2 downward
    if (r >= 2 && emptyCols.includes(c)) {
      return 0;
    }
    // 3) Outer border — top row always unbreakable
    if (r === 0) {
      return 2;
    }
    // 4) Outer border — bottom row unbreakable except the 3‑wide stem opening
    if (r === ROWS - 1 && !emptyCols.includes(c)) {
      return 2;
    }
    // 5) Outer left/right columns always unbreakable
    if (c === 0 || c === COLS - 1) {
      return 2;
    }
    // 6) Everything else is breakable
    return 1;
  })
);

export const levels = [
  {
    name: 'T‑in‑a‑Box (100×20)',
    layout: tWithBorder
  }
];
