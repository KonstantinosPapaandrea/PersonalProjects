/* ============================================================
   SHARED CONSTANTS & SMALL HELPERS
   ============================================================ */
export const SLIDE_MS = 800;                    // keep in one place

/** page centre of an element (scroll-aware) */
export const pageCentre = el => {
  const r = el.getBoundingClientRect();
  return {
    x: r.left + r.width  / 2 + window.scrollX,
    y: r.top  + r.height / 2 + window.scrollY
  };
};
