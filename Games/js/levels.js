// levels.js

/**
 * 0 = empty
 * 1 = breakable
 * 2 = unbreakable
 */
export const levels = [
    {
      name: 'Level 1 – Wide Wall',
      layout: [
        // two rows of unbreakable blocks
        Array(50).fill(2),
        Array(50).fill(2),
        // four rows of breakable blocks
        Array(50).fill(1),
        Array(50).fill(1),
        Array(50).fill(1),
        Array(50).fill(1),
        // four empty rows for “natural” space at bottom
        Array(50).fill(0),
        Array(50).fill(0),
        Array(50).fill(0),
        Array(50).fill(0),
      ]
    },
    {
      name: 'Level 2 – Pyramid',
      layout: [
        // tip of the pyramid: unbreakable in the center
        [0,0,0,0,2,2,2,2,2,2,2,2,0,0],
        // next two rows of breakable expanding outward
        [0,0,1,1,1,1,1,1,1,1,1,1,1,0],
        [0,1,1,1,1,1,1,1,1,1,1,1,1,1],
        // full row of breakable at the base
        Array(14).fill(1),
        // four empty rows below for space
        Array(14).fill(0),
        Array(14).fill(0),
        Array(14).fill(0),
        Array(14).fill(0),
        Array(14).fill(0),
        Array(14).fill(0),
      ]
    },
    // you can add more levels here!
  ];
  