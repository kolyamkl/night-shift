import { describe, expect, it } from "vitest";
import { CASTLE } from "./art";
import { COLLAPSE_AT, knockOut, remove, restoreRows, roofCells, towerAt, towerNear } from "./towers";

describe("towerAt", () => {
  it("finds the left and right towers and nothing on the wall, the gate or the sky", () => {
    expect(towerAt(5, 30, CASTLE)).toBe("left");
    expect(towerAt(70, 30, CASTLE)).toBe("right");
    expect(towerAt(25, 40, CASTLE)).toBeNull(); // wall
    expect(towerAt(39, 45, CASTLE)).toBeNull(); // gate
    expect(towerAt(30, 2, CASTLE)).toBeNull(); // sky between the towers
    expect(towerAt(0, 2, CASTLE)).toBeNull(); // empty cell beside the left pole
  });
});

describe("knockOut", () => {
  it("takes up to n stone cells off the tower face nearest the press, on the rows around it", () => {
    const cells = knockOut(CASTLE, "left", 3, 30, 5, () => 0.5);
    expect(cells.length).toBe(5);
    for (const c of cells) {
      expect(CASTLE[c.y][c.x]).not.toBe(".");
      expect(Math.abs(c.y - 30)).toBeLessThanOrEqual(2);
      const edge = CASTLE[c.y].search(/[^.]/); // the left tower's outer face on that row
      expect(c.x - edge).toBeLessThanOrEqual(2);
    }
  });

  it("eats into the far face when the press is nearer that side", () => {
    const cells = knockOut(CASTLE, "right", 75, 40, 4, () => 0.5);
    for (const c of cells) expect(c.x).toBeGreaterThanOrEqual(74);
  });

  it("returns nothing once the stone around the press is gone", () => {
    let grid = CASTLE;
    for (let i = 0; i < 12; i++) grid = remove(grid, knockOut(grid, "left", 3, 30, 5, () => 0.5));
    const left = knockOut(grid, "left", 3, 30, 5, () => 0.5);
    for (const c of left) expect(grid[c.y][c.x]).not.toBe(".");
  });
});

describe("remove and restoreRows", () => {
  it("empties the cells, then puts a tower back from a row down", () => {
    const cells = knockOut(CASTLE, "right", 70, 40, 5, () => 0.5);
    const broken = remove(CASTLE, cells);
    for (const c of cells) expect(broken[c.y][c.x]).toBe(".");
    expect(restoreRows(broken, CASTLE, "right", 0)).toEqual(CASTLE);
    const half = restoreRows(broken, CASTLE, "right", 45);
    for (const c of cells) expect(half[c.y][c.x]).toBe(c.y >= 45 ? CASTLE[c.y][c.x] : ".");
  });
});

describe("roofCells", () => {
  it("is the pole, cone and brim of one tower", () => {
    const roof = roofCells(CASTLE, "left");
    expect(roof.length).toBeGreaterThan(50);
    expect(roof.every((c) => c.y <= 19 && c.x <= 16)).toBe(true);
    expect(COLLAPSE_AT).toBeGreaterThanOrEqual(10);
  });
});

describe("towerNear", () => {
  it("still finds the tower when the press lands in a hole it already has", () => {
    const dug = [69, 70, 71].flatMap((x) => [39, 40, 41].map((y) => ({ x, y, ch: CASTLE[y][x] })));
    const hole = remove(CASTLE, dug);
    expect(hole[40][70]).toBe(".");
    expect(towerNear(70, 40, hole)).toBe("right");
    expect(knockOut(hole, "right", 70, 40, 5, () => 0.5).length).toBeGreaterThan(0);
    expect(towerNear(30, 2, hole)).toBeNull();
  });
});
