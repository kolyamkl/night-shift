// Pixel sprites drawn from character grids: one SVG path of horizontal runs per colour, crisp at any scale.

import { useMemo } from "react";

export const INK = "#0d0d0d";
export const SIGNAL = "#e2231a";
export const STONE = "#8b8a85";
export const STEEL = "#55534d";
export const BONE = "#f8f7f3";

export const COLORS: Record<string, string> = { k: INK, r: SIGNAL, o: "#ff6b61", g: STONE, s: STEEL, w: BONE, h: "#c9c7bd", m: "#dcdad1", c: "currentColor" };

export type Rows = readonly string[];

/** One path of horizontal runs per colour: [colour key, path data]. */
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

export function Sprite({ rows, scale, className, label }: { rows: Rows; scale: number; className?: string; label?: string }) {
  const { w, h, paths } = useMemo(
    () => ({ w: Math.max(...rows.map((r) => r.length)), h: rows.length, paths: runPaths(rows) }),
    [rows],
  );
  return (
    <svg
      className={className}
      width={w * scale}
      height={h * scale}
      viewBox={`0 0 ${w} ${h}`}
      shapeRendering="crispEdges"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {paths.map(([ch, d]) => (
        <path key={ch} fill={COLORS[ch]} d={d} />
      ))}
    </svg>
  );
}

export const KNIGHT_SMALL: Rows = [
  "......rr......", ".....rrr......", "....kkkkkk....", "...kggggggk...", "..kggggggggk..",
  "..kgkkkkkkgk..", "..kggggggggk..", "..kgkgkgkggk..", "..kggggggggk..", "...kkkkkkkk...",
  ".kkrrrrrrrrkk.", "kkrrrrwwrrrrkk", "kkrrrrwwrrrrkk", "kkrrrwwwwrrrkk",
];

// The victory knight is symmetric: each row is written as its left half plus the centre column, then mirrored.
const mirror = (half: string[]): Rows => half.map((h) => h + [...h.slice(0, -1)].reverse().join(""));

export const HERO = mirror([
  "...........rr", "..........rrr", "...........rr",
  ".......kkkkkk", "......kgggggg", ".....kggwgggg", ".....kggggggg", ".....kgkkkkkk",
  ".....kggggggg", ".....kggkgkgg", ".....kggggggg", "......kkkkkkk",
  "...kkkkkkkkkk", ".kkggggkrrrrr", "kgggwggkrrrrr", "kggggggkrrrrr", ".kggggkrrrrrr",
  "..kgggkkrrrrr", "...kgggkkrrrr", "....kgggkkrrr", ".....kgggkrrr", "......kkkkrrr",
  "......krrrrrr", "......kkkkkkk",
  ".....kggk....", "....kggk.....", "....kggk.....", "...kggk......", "...kggk......", "..kkggk......", ".kkkkkk......",
]);

// Drawn over the knight, by absolute row: the two-handed sword planted point down, then the gauntlets on its grip.
export const HERO_SWORD: [number, string][] = [
  [15, "...........kkk..........."], [16, "...........krk..........."], [17, "............k............"],
  [21, ".......ksssssssssk......."], [22, ".......kkkkkkkkkkk......."],
  ...[23, 24, 25, 26, 27, 28, 29, 30].map((r): [number, string] => [r, "...........sws..........."]),
  [18, ".........kkkkkkk........."], [19, "........kgggggggk........"], [20, "........kgkgkgkgk........"],
];

export const HACKER: Rows = ["..kkkkkkk..", ".kwwwwwwwk.", "kwwkkkkkwwk", "kwkrkkkrkwk", "kwkkkkkkkwk", "kwwwwwwwwwk", ".kk.....kk."];
export const HACKER_DOWN: Rows = ["..kkkkkkk..", "kwwkkkkkwwk", "kwkwkkkwkwk", "kwwkwkwkwwk", ".kkkkkkkkk."];

export const ICON_PLUS: Rows = ["..c..", "..c..", "ccccc", "..c..", "..c.."];
export const ICON_DOWNLOAD: Rows = ["...c...", "...c...", "...c...", ".ccccc.", "..ccc..", "...c...", ".......", "ccccccc"];
export const ICON_LOCK: Rows = ["..ccc..", ".c...c.", ".c...c.", "ccccccc", "ccc.ccc", "ccc.ccc", "ccccccc"];
