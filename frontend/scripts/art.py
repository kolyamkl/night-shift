"""Generates the landing page pixel art in src/landing/art.ts.

Run from frontend/: python3 scripts/art.py   (add a path to also write an HTML preview)
"""
import json
import sys
from pathlib import Path

W, H = 78, 56
TOP = 6  # rows above the roofs for poles and pennants


def blank(w, h):
    return [["."] * w for _ in range(h)]


def put(g, x, y, ch):
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = ch


def rect(g, x0, y0, x1, y1, ch):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(g, x, y, ch)


def bricks(g, x0, y0, x1, y1):
    """Stone fill with mortar courses and staggered joints, outlined in ink."""
    rect(g, x0, y0, x1, y1, "g")
    for y in range(y0, y1 + 1):
        course = (y - y0) // 4
        if (y - y0) % 4 == 3:
            for x in range(x0, x1 + 1):
                put(g, x, y, "s")
        else:
            off = 0 if course % 2 == 0 else 3
            for x in range(x0 + off, x1 + 1, 6):
                put(g, x, y, "s")
    for y in range(y0, y1 + 1):
        put(g, x0, y, "k")
        put(g, x1, y, "k")


def roof(g, cx, top, rows, half_max):
    for r in range(rows):
        half = round(0.5 + r * (half_max - 0.5) / (rows - 1))
        for x in range(cx - half, cx + half + 1):
            put(g, x, top + r, "r")
        put(g, cx - half, top + r, "k")
        put(g, cx + half, top + r, "k")
        if r % 3 == 2:  # tile courses
            for x in range(cx - half + 1, cx + half, 2):
                put(g, x, top + r, "k")
    for x in range(cx - half_max, cx + half_max + 1):
        put(g, x, top + rows, "k")


def castle():
    g = blank(W, H)
    # towers
    for cx in (8, W - 9):
        rect(g, cx, TOP - 6, cx, TOP, "k")  # pole
        bricks(g, cx - 7, TOP + 13, cx + 7, H - 1)
        roof(g, cx, TOP, 13, 8)
        for y0 in (TOP + 18, TOP + 32):  # arrow slits
            rect(g, cx, y0, cx, y0 + 4, "k")
            put(g, cx - 1, y0 + 2, "k")
            put(g, cx + 1, y0 + 2, "k")
    # curtain wall with crenellations
    wx0, wx1, wy = 16, W - 17, TOP + 19
    bricks(g, wx0, wy, wx1, H - 1)
    for x in range(wx0, wx1 + 1):
        put(g, x, wy, "k")
    for x in range(wx0, wx1 + 1, 4):
        rect(g, x, wy - 3, x + 1, wy - 1, "g")
        put(g, x, wy - 3, "k"); put(g, x + 1, wy - 3, "k")
        put(g, x, wy - 2, "k"); put(g, x + 1, wy - 2, "g")
        put(g, x, wy - 1, "k"); put(g, x + 1, wy - 1, "g")
        put(g, x + 2, wy - 1, "k") if x + 2 <= wx1 else None
    # gate: stone arch ring around a dark opening
    gx0, gx1, gtop = 31, 46, TOP + 27
    for y in range(gtop, H):
        for x in range(gx0 - 2, gx1 + 3):
            put(g, x, y, "s")
    for y in range(gtop + 1, H):
        inset = max(0, 3 - (y - gtop - 1)) if y - gtop < 4 else 0
        for x in range(gx0 + inset, gx1 - inset + 1):
            put(g, x, y, "k")
    # banners
    for bx in (21, W - 26):
        for y in range(wy + 1, wy + 13):
            for x in range(bx, bx + 5):
                put(g, x, y, "r")
            put(g, bx - 1, y, "k"); put(g, bx + 5, y, "k")
        put(g, bx, wy + 13, "r"); put(g, bx + 1, wy + 13, "r"); put(g, bx + 3, wy + 13, "r"); put(g, bx + 4, wy + 13, "r")
        put(g, bx, wy + 14, "r"); put(g, bx + 4, wy + 14, "r")
        rect(g, bx + 1, wy + 3, bx + 3, wy + 5, "w")  # keyhole emblem: round head, flared stem
        put(g, bx + 2, wy + 4, "k")
        rect(g, bx + 2, wy + 6, bx + 2, wy + 7, "w")
        rect(g, bx + 1, wy + 8, bx + 3, wy + 8, "w")
        rect(g, bx - 1, wy + 1, bx + 5, wy + 1, "k")  # rod
    return g


DOOR = (16 // 2, H - (TOP + 28))  # each leaf is 8 wide


def door():
    w, h = DOOR
    g = blank(w, h)
    rect(g, 0, 0, w - 1, h - 1, "s")
    for x in range(0, w, 2):  # planks
        for y in range(h):
            put(g, x, y, "k" if x == 0 or x == w - 1 else "s")
    for x in range(1, w, 2):
        for y in range(h):
            put(g, x, y, "g")
    for y in (4, h // 2, h - 5):  # iron bands with studs
        for x in range(w):
            put(g, x, y, "k")
    for x in range(w):
        put(g, x, h - 1, "k")
    return g


LOCK = ["..kkkk..", ".k....k.", ".k....k.", "kkkkkkkk", "krrrrrrk", "krrwwrrk", "krrwwrrk", "krrrwrrk", "krrrrrrk", "kkkkkkkk"]
TORCH = [
    ["..r..", ".rrr.", ".rwr.", "rrwrr", ".rwr.", "..k..", ".kkk.", "..s..", "..s..", "..s.."],
    ["...r.", "..rr.", ".rrwr", ".rwr.", "rrwrr", "..k..", ".kkk.", "..s..", "..s..", "..s.."],
]
PENNANT = [["krrrr.", "krrrrr", "krrr..", "k....."], ["krrr..", "krrrrr", "krrrr.", "k....."]]
CLOUD = ["....kkkk......", "..kkwwwwkk....", ".kwwwwwwwwkkk.", "kwwwwwwwwwwwwk", ".kkkkkkkkkkkk."]
SCROLL = ["kkkkkkkk", "kwkkkkwk", "kwwwwwwk", "kwkkkwwk", "kwwwwwwk", "kkkkkkkk"]

COL = {"k": "#0d0d0d", "g": "#8b8a85", "w": "#f8f7f3", "r": "#e2231a", "s": "#55534d", "h": "#c9c7bd", "m": "#dcdad1"}

LOCK_OPEN = ["kk......", "k.k.....", "..k.....", "kkkkkkkk", "krrrrrrk", "krrwwrrk", "krrwwrrk", "krrrwrrk", "krrrrrrk", "kkkkkkkk"]
TOWER = ["..kkkk..", ".krrrrk.", "krrrrrrk", "kkkkkkkk", ".kggggk.", ".kgkkgk.", ".kggggk.", ".kgkkgk.", ".kggggk.", ".kggggk.", "kkkkkkkk"]


def gatehouse():
    """A stretch of curtain wall with an arched gate, used on the journey stage. The portcullis is a separate sprite."""
    w, h = 60, 44
    g = blank(w, h)
    bricks(g, 0, 6, w - 1, h - 1)
    for x in range(0, w):
        put(g, x, 6, "k")
    for x in range(0, w, 4):
        rect(g, x, 3, x + 1, 5, "g")
        put(g, x, 3, "k"); put(g, x + 1, 3, "k"); put(g, x, 4, "k"); put(g, x, 5, "k")
        if x + 2 < w:
            put(g, x + 2, 5, "k")
    gx0, gx1, gtop = 22, 37, 14
    for y in range(gtop, h):
        for x in range(gx0 - 2, gx1 + 3):
            put(g, x, y, "s")
    for y in range(gtop + 1, h):
        inset = max(0, 3 - (y - gtop - 1)) if y - gtop < 4 else 0
        for x in range(gx0 + inset, gx1 - inset + 1):
            put(g, x, y, "k")
    for bx in (8, w - 13):  # banners
        for y in range(7, 19):
            for x in range(bx, bx + 5):
                put(g, x, y, "r")
            put(g, bx - 1, y, "k"); put(g, bx + 5, y, "k")
        put(g, bx, 19, "r"); put(g, bx + 1, 19, "r"); put(g, bx + 3, 19, "r"); put(g, bx + 4, 19, "r")
        put(g, bx, 20, "r"); put(g, bx + 4, 20, "r")
        rect(g, bx + 1, 9, bx + 3, 11, "w"); put(g, bx + 2, 10, "k")
        rect(g, bx + 2, 12, bx + 2, 13, "w"); rect(g, bx + 1, 14, bx + 3, 14, "w")
        rect(g, bx - 1, 7, bx + 5, 7, "k")
    return g


def portcullis():
    w, h = 16, 30
    g = blank(w, h)
    for x in range(0, w, 3):
        rect(g, x, 0, x, h - 2, "k")
        put(g, x, h - 1, "k")
    for y in range(2, h - 3, 5):
        rect(g, 0, y, w - 1, y, "k")
    for x in range(0, w, 3):  # spikes
        put(g, x, h - 1, "s")
    return g


def wall_side():
    """The castle wall seen from the side, with a gate tunnel through its foot. The tunnel is see-through."""
    w, h = 24, 56
    g = blank(w, h)
    bricks(g, 0, 3, w - 1, h - 1)
    for x in range(0, w, 6):  # merlons
        rect(g, x, 0, x + 2, 2, "g")
        put(g, x, 0, "k"); put(g, x + 1, 0, "k"); put(g, x + 2, 0, "k"); put(g, x, 1, "k"); put(g, x, 2, "k"); put(g, x + 2, 1, "k")
    for x in range(w):
        put(g, x, 3, "k")
    top = 28
    for y in range(top, h):
        inset = max(0, 3 - (y - top)) if y - top < 3 else 0
        for x in range(4 + inset, 20 - inset):
            put(g, x, y, ".")
        put(g, 3 + inset, y, "k"); put(g, 20 - inset, y, "k")
    for x in range(7, 17):
        put(g, x, top - 1, "k")
    return g


def ai_tower():
    """A neutral tower for 'the AI provider': stone, slate roof, one lit window. No logo."""
    w, h = 24, 64
    g = blank(w, h)
    cx = 11
    for r in range(14):
        half = round(0.5 + r * 8.5 / 13)
        for x in range(cx - half, cx + half + 2):
            put(g, x, 6 + r, "s")
        put(g, cx - half, 6 + r, "k"); put(g, cx + half + 1, 6 + r, "k")
    rect(g, cx, 0, cx + 1, 5, "k")
    rect(g, cx - 1, 1, cx + 2, 2, "r")  # beacon
    for x in range(cx - 9, cx + 11):
        put(g, x, 20, "k")
    bricks(g, cx - 8, 21, cx + 9, h - 1)
    rect(g, cx - 2, 26, cx + 3, 33, "k")  # window frame
    rect(g, cx - 1, 27, cx + 2, 32, "w")
    rect(g, cx, 27, cx + 1, 32, "k")
    rect(g, cx - 1, 29, cx + 2, 29, "k")
    rect(g, cx - 3, h - 12, cx + 4, h - 1, "k")  # door
    rect(g, cx - 2, h - 11, cx + 3, h - 1, "s")
    return g


PIGEON = [
    ["......kk........", ".....kwgk.......", ".....kwggk......", "......kwggk.....", ".......kwggk..kk",
     "kk.....kkkgkkkwk", "kwkkkkkwwwwggggr", ".kwwwwwwwwwggkk.", "..kkkkkkkkkkk...", "................", "................"],
    ["................", "................", "................", "................", "..............kk",
     "kk.....kkkkkkkwk", "kwkkkkkwwwwggggr", ".kwwwwwkwwwggkk.", "..kkkkkwggkkk...", "......kwgk......", ".......kk......."],
]

def hills(width, height, ridge, ch):
    """A hill strip that tiles: ridge(x) gives the ridge row for each column and must wrap at `width`.
    The outline is continuous (steep steps are joined), and everything below it is filled."""
    tops = [max(0, min(height - 1, round(ridge(x)))) for x in range(width)]
    g = blank(width, height)
    for x in range(width):
        lower = max(tops[x], tops[(x - 1) % width] - 1, tops[(x + 1) % width] - 1)
        for y in range(tops[x], height):
            put(g, x, y, "k" if y <= lower else ch)
    return g


def far_ridge(x, width=160):
    import math
    t = 2 * math.pi * x / width
    return 12 - 7 * (0.6 * math.sin(2 * t + 1.3) + 0.28 * math.sin(5 * t + 2.6) + 0.12 * math.sin(9 * t + 4.1))


def near_ridge(x, width=160):
    """Low and calm across the middle half, where the hero castle stands; rolling hills on both sides."""
    import math
    d = abs(x - width / 2) / (width / 2)  # 0 at the centre, 1 at the tile edges
    rise = min(1.0, max(0.0, (d - 0.5) / 0.3))
    rise = rise * rise * (3 - 2 * rise)
    t = 2 * math.pi * x / width
    return 16 - rise * (10 + 2.5 * math.sin(3 * t + 0.7) + 0.8 * math.sin(7 * t))


def write_ts(path):
    rows = lambda grid: "[\n" + "".join(f'  "{r}",\n' for r in grid) + "]"
    out = [
        "// Landing page pixel art. Generated by scripts/art.py; edit the generator, not this file.",
        "// Colour letters follow sprites.tsx: k ink, g stone, s steel, w bone, r signal.",
        "",
        f"export const CASTLE_W = {W};",
        f"export const CASTLE_H = {H};",
        f"export const CASTLE_TOP = {TOP};",
        "",
        f"export const CASTLE = {rows(''.join(r) for r in castle())};",
        "",
        f"export const DOOR = {rows(''.join(r) for r in door())};",
        "",
    ]
    for name, grid in [("GATEHOUSE", gatehouse()), ("PORTCULLIS", portcullis()), ("AI_TOWER", ai_tower()), ("WALL_SIDE", wall_side()),
                       ("HILLS_FAR", hills(160, 40, far_ridge, "h")), ("HILLS_NEAR", hills(160, 20, near_ridge, "m"))]:
        out.append(f"export const {name} = {rows(''.join(r) for r in grid)};")
        out.append("")
    for name, value in [("LOCK", LOCK), ("LOCK_OPEN", LOCK_OPEN), ("TORCH", TORCH), ("PENNANT", PENNANT),
                        ("CLOUD", CLOUD), ("SCROLL", SCROLL), ("PIGEON", PIGEON)]:
        out.append(f"export const {name} = {json.dumps(value)};")
    Path(path).write_text("\n".join(out) + "\n")


def write_preview(path):
    P = 8
    html = ['<html><body style="margin:0;background:#ecebe5;padding:30px">',
            f'<div style="position:relative;width:{W * P}px;height:{H * P}px">']

    def draw(grid, ox, oy):
        for y, r in enumerate(grid):
            for x, ch in enumerate(r):
                if ch != ".":
                    html.append(f'<i style="position:absolute;left:{(x + ox) * P}px;top:{(y + oy) * P}px;'
                                f'width:{P}px;height:{P}px;background:{COL[ch]}"></i>')

    draw(["".join(r) for r in castle()], 0, 0)
    draw(["".join(r) for r in door()], 31, TOP + 28)
    draw(["".join(r)[::-1] for r in door()], 39, TOP + 28)
    draw(LOCK, 35, TOP + 38)
    draw(TORCH[0], 25, TOP + 35)
    draw(TORCH[1], 48, TOP + 35)
    html.append("</div>")
    for name, grid, scale in [("wall", wall_side(), 6), ("portcullis", portcullis(), 8), ("tower", ai_tower(), 6),
                              ("pigeon a", PIGEON[0], 10), ("pigeon b", PIGEON[1], 10)]:
        rows_ = ["".join(r) if not isinstance(r, str) else r for r in grid]
        html.append(f'<div style="display:inline-block;position:relative;margin:20px;width:{len(rows_[0])*scale}px;height:{len(rows_)*scale}px">')
        for y, r in enumerate(rows_):
            for x, ch in enumerate(r):
                if ch != ".":
                    html.append(f'<i style="position:absolute;left:{x*scale}px;top:{y*scale}px;width:{scale}px;height:{scale}px;background:{COL[ch]}"></i>')
        html.append("</div>")
    hl = ["".join(r) for r in hills(160, 40, far_ridge, "h")] * 1
    html.append('<div style="position:relative;width:960px;height:160px;margin:20px">')
    for y, r in enumerate(hl):
        for x, ch in enumerate(r):
            if ch != ".":
                html.append(f'<i style="position:absolute;left:{x*4}px;top:{y*4}px;width:4px;height:4px;background:{COL[ch]}"></i>')
    html.append("</div></body></html>")
    Path(path).write_text("".join(html))


if __name__ == "__main__":
    write_ts(Path(__file__).resolve().parents[1] / "src" / "landing" / "art.ts")
    if len(sys.argv) > 1:
        write_preview(sys.argv[1])
