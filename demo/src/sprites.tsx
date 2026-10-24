// Pixel sprites from the app (frontend/src/sprites.tsx, copied so a render never breaks on app edits),
// plus a document page for the opening.

export type Rows = readonly string[];

export const COLORS: Record<string, string> = {
  k: "#0d0d0d", r: "#e2231a", o: "#ff6b61", g: "#8b8a85", s: "#55534d", w: "#f8f7f3", h: "#c9c7bd", m: "#dcdad1",
};

export function runPaths(rows: Rows): [string, string][] {
  const byColor: Record<string, string[]> = {};
  rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      let n = 1;
      while (x + n < row.length && row[x + n] === ch) n++;
      if (ch !== ".") (byColor[ch] ??= []).push(`M${x} ${y}h${n}v1h-${n}z`);
      x += n;
    }
  });
  return Object.entries(byColor).map(([ch, d]) => [ch, d.join("")]);
}

export function Sprite({ rows, scale, style, tint }: { rows: Rows; scale: number; style?: React.CSSProperties; tint?: Record<string, string> }) {
  const w = Math.max(...rows.map((r) => r.length));
  return (
    <svg width={w * scale} height={rows.length * scale} viewBox={`0 0 ${w} ${rows.length}`} shapeRendering="crispEdges" style={{ display: "block", ...style }}>
      {runPaths(rows).map(([ch, d]) => (
        <path key={ch} fill={tint?.[ch] ?? COLORS[ch]} d={d} />
      ))}
    </svg>
  );
}

/** Every filled pixel of a sprite, for building it up one pixel at a time. */
export function pixelsOf(rows: Rows) {
  const out: { x: number; y: number; c: string }[] = [];
  rows.forEach((row, y) => [...row].forEach((ch, x) => ch !== "." && out.push({ x, y, c: COLORS[ch] })));
  return out;
}

export const KNIGHT_SMALL: Rows = [
  "......rr......", ".....rrr......", "....kkkkkk....", "...kggggggk...", "..kggggggggk..",
  "..kgkkkkkkgk..", "..kggggggggk..", "..kgkgkgkggk..", "..kggggggggk..", "...kkkkkkkk...",
  ".kkrrrrrrrrkk.", "kkrrrrwwrrrrkk", "kkrrrrwwrrrrkk", "kkrrrwwwwrrrkk",
];

const mirror = (half: string[]): string[] => half.map((h) => h + [...h.slice(0, -1)].reverse().join(""));

const HERO_BODY = mirror([
  "...........rr", "..........rrr", "...........rr",
  ".......kkkkkk", "......kgggggg", ".....kggwgggg", ".....kggggggg", ".....kgkkkkkk",
  ".....kggggggg", ".....kggkgkgg", ".....kggggggg", "......kkkkkkk",
  "...kkkkkkkkkk", ".kkggggkrrrrr", "kgggwggkrrrrr", "kggggggkrrrrr", ".kggggkrrrrrr",
  "..kgggkkrrrrr", "...kgggkkrrrr", "....kgggkkrrr", ".....kgggkrrr", "......kkkkrrr",
  "......krrrrrr", "......kkkkkkk",
  ".....kggk....", "....kggk.....", "....kggk.....", "...kggk......", "...kggk......", "..kkggk......", ".kkkkkk......",
]);

const HERO_SWORD: [number, string][] = [
  [15, "...........kkk..........."], [16, "...........krk..........."], [17, "............k............"],
  [21, ".......ksssssssssk......."], [22, ".......kkkkkkkkkkk......."],
  ...[23, 24, 25, 26, 27, 28, 29, 30].map((r): [number, string] => [r, "...........sws..........."]),
  [18, ".........kkkkkkk........."], [19, "........kgggggggk........"], [20, "........kgkgkgkgk........"],
];

/** The victory knight with his sword planted, as one grid. */
export const HERO: Rows = (() => {
  const rows = HERO_BODY.map((r) => [...r]);
  for (const [y, over] of HERO_SWORD) [...over].forEach((ch, x) => { if (ch !== ".") rows[y][x] = ch; });
  return rows.map((r) => r.join(""));
})();

export const HACKER: Rows = ["..kkkkkkk..", ".kwwwwwwwk.", "kwwkkkkkwwk", "kwkrkkkrkwk", "kwkkkkkkkwk", "kwwwwwwwwwk", ".kk.....kk."];

// A page with a folded corner and lines of text.
export const DOC: Rows = [
  "kkkkkkkkk...", "kwwwwwwwkk..", "kwkkkkwwkwk.", "kwwwwwwwkkkk", "kwkkkkkkkwwk", "kwwwwwwwwwwk",
  "kwkkkkkkkkwk", "kwwwwwwwwwwk", "kwkkkkkwwwwk", "kwwwwwwwwwwk", "kwkkkkkkkkwk", "kwwwwwwwwwwk",
  "kwkkkkkkwwwk", "kwwwwwwwwwwk", "kwwwwwwwwwwk", "kkkkkkkkkkkk",
];
