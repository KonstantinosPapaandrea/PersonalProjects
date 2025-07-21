// levels.js
// ============
// Each level is a 2D array of size ROWS×COLS:
//  0 = empty space
//  1 = breakable block
//  2 = unbreakable block

const ROWS = 20;
const COLS = 100;
const center = Math.floor(COLS / 2);
const emptyCols = [center - 1, center, center + 1];

// ─────────────────────────────────────────────────────────────────────────────
// Level 0: “T‑in‑a‑Box”
//   • A “T”–shaped empty region (rows 2–4 & a 3‑wide stem).
//   • Surrounded by an unbreakable border, with a 3‑wide opening at bottom.
// ─────────────────────────────────────────────────────────────────────────────
const tWithBorder = Array.from({ length: ROWS }, (_, r) =>
  Array.from({ length: COLS }, (_, c) => {
    // 1) Horizontal bar at rows 2–4 (interior only)
    if ((r === 2 || r === 3 || r === 4) && c > 0 && c < COLS - 1) {
      return 0;
    }
    // 2) Vertical stem (3‑wide) from row 2 downward
    if (r >= 2 && emptyCols.includes(c)) {
      return 0;
    }
    // 3) Top border always unbreakable
    if (r === 0) {
      return 2;
    }
    // 4) Bottom border unbreakable except the 3 middle columns
    if (r === ROWS - 1 && !emptyCols.includes(c)) {
      return 2;
    }
    // 5) Left/right border always unbreakable
    if (c === 0 || c === COLS - 1) {
      return 2;
    }
    // 6) Everything else is breakable
    return 1;
  })
);

// ─────────────────────────────────────────────────────────────────────────────
// Level 1: “Pyramid”
//   • A centered pyramid of breakable blocks in the top 10 rows.
//   • Outer border of unbreakable blocks on all four sides.
//   • Rest of interior is empty for the ball to fall through.
// ─────────────────────────────────────────────────────────────────────────────
const pyramidWithBorder = Array.from({ length: ROWS }, (_, r) =>
  Array.from({ length: COLS }, (_, c) => {
    // 1) Outer border (top, bottom, left, right)
    if (r === 0 || r === ROWS - 1 || c === 0 || c === COLS - 1) {
      return 2;
    }

    // 2) Pyramid of breakable blocks in rows 1–10
    const pyramidHeight = 10;  // number of rows in the pyramid
    if (r >= 1 && r <= pyramidHeight) {
      // width decreases each row:
      const level = r - 1;              // 0-based
      const width = (pyramidHeight - level) * 2 - 1;
      const start = center - Math.floor(width / 2);
      if (c >= start && c < start + width) {
        return 1;  // breakable block
      }
    }

    // 3) Everything else is empty
    return 0;
  })
);

export const levels = [
  {
    name: 'T‑in‑a‑Box (100×20)',
    layout: tWithBorder
  },
  {
    name: 'Pyramid (100×20)',
    layout: pyramidWithBorder
  }
];
