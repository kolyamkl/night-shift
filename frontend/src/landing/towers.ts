// The hero castle's towers can be knocked about: each press takes a few stone cells off the tower near the press,
// and after COLLAPSE_AT presses the roof (pole, cone and brim) comes down; then the tower is rebuilt from CASTLE.
// Pure grid functions; HeroScene draws the falling pieces.

export type Side = "left" | "right";
export type Cell = { x: number; y: number; ch: string };

// Columns of each tower in CASTLE (78 x 56), including its outline.
export const TOWERS: Record<Side, { x0: number; x1: number }> = {
  left: { x0: 0, x1: 16 },
  right: { x0: 61, x1: 77 },
};
export const ROOF_BOTTOM = 19; // rows 0 to 19: the pole, the red cone and the brim
export const COLLAPSE_AT = 12;
const REACH = 3; // a press counts while the tower has stone within this many rows of it

const inTower = (side: Side, x: number) => x >= TOWERS[side].x0 && x <= TOWERS[side].x1;
const filled = (grid: readonly string[], x: number, y: number) => {
  const ch = grid[y]?.[x];
  return ch !== undefined && ch !== ".";
};

/** Which tower a stone cell belongs to; null for the wall, the gate, the sky or a cell already knocked out. */
export function towerAt(x: number, y: number, grid: readonly string[]): Side | null {
  if (!filled(grid, x, y)) return null;
  if (inTower("left", x)) return "left";
  if (inTower("right", x)) return "right";
  return null;
}

/** Like towerAt, but any press over a tower counts while that tower still has stone on the rows around it, so
 * pressing the same spot keeps eating into the tower after the first stones are gone. */
export function towerNear(x: number, y: number, grid: readonly string[]): Side | null {
  const side = inTower("left", x) ? "left" : inTower("right", x) ? "right" : null;
  if (!side) return null;
  for (let yy = y - REACH; yy <= y + REACH; yy++)
    for (let xx = TOWERS[side].x0; xx <= TOWERS[side].x1; xx++) if (filled(grid, xx, yy)) return side;
  return null;
}

/** Up to n stone cells off one face of a tower: the face nearer the press, on the rows around it, outermost first.
 * Repeated presses so bite into the tower from that side until it cannot hold its roof. `rand` roughens the edge. */
export function knockOut(grid: readonly string[], side: Side, x: number, y: number, n: number, rand: () => number = Math.random): Cell[] {
  const { x0, x1 } = TOWERS[side];
  const fromLeft = x <= (x0 + x1) / 2;
  const found: { cell: Cell; score: number }[] = [];
  for (let yy = y - 2; yy <= y + 2; yy++) {
    const row: number[] = [];
    for (let xx = x0; xx <= x1; xx++) if (filled(grid, xx, yy)) row.push(xx);
    if (!row.length) continue;
    const edge = fromLeft ? row[0] : row[row.length - 1];
    for (const xx of row) {
      const depth = fromLeft ? xx - edge : edge - xx;
      if (depth > 2) continue;
      found.push({ cell: { x: xx, y: yy, ch: grid[yy][xx] }, score: depth + Math.abs(yy - y) * 0.6 + rand() * 0.7 });
    }
  }
  return found.sort((a, b) => a.score - b.score).slice(0, n).map((f) => f.cell);
}

export function remove(grid: readonly string[], cells: readonly Cell[]): string[] {
  const rows = grid.map((r) => [...r]);
  for (const c of cells) if (rows[c.y]) rows[c.y][c.x] = ".";
  return rows.map((r) => r.join(""));
}

/** The tower's roof as it stands now. */
export function roofCells(grid: readonly string[], side: Side): Cell[] {
  const out: Cell[] = [];
  for (let y = 0; y <= ROOF_BOTTOM; y++)
    for (let x = TOWERS[side].x0; x <= TOWERS[side].x1; x++) if (filled(grid, x, y)) out.push({ x, y, ch: grid[y][x] });
  return out;
}

/** Put one tower back from `original` for every row from `fromRow` down. */
export function restoreRows(grid: readonly string[], original: readonly string[], side: Side, fromRow: number): string[] {
  const { x0, x1 } = TOWERS[side];
  return grid.map((row, y) => (y < fromRow ? row : row.slice(0, x0) + original[y].slice(x0, x1 + 1) + row.slice(x1 + 1)));
}
