"""Draws the README pictures in docs/readme/ from the landing page's own sprites and fonts.

The castle, knight, towers and hills come from src/landing/art.ts and src/sprites.tsx; text is set in Pixelify Sans,
Silkscreen and Source Serif 4 and turned into paths, because an SVG shown as an image on GitHub cannot load fonts.
Motion is SMIL, which GitHub plays inside <img>.

Run from frontend/:  uv run --no-project --with fonttools --with brotli python scripts/readme_art.py
"""

import json
import re
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "docs" / "readme"

INK, SIGNAL, SIGNAL_DEEP, SIGNAL_SOFT = "#0d0d0d", "#e2231a", "#b3170f", "#ff6b61"
QUIET, STONE, HAZE, MIST, BONE, PAPER = "#55534d", "#8b8a85", "#c9c7bd", "#dcdad1", "#ecebe5", "#f8f7f3"
COLORS = {"k": INK, "r": SIGNAL, "o": SIGNAL_SOFT, "g": STONE, "s": QUIET, "w": PAPER, "h": HAZE, "m": MIST}


# ---------- sprites ----------

def load_art() -> dict:
    src = (ROOT / "src/landing/art.ts").read_text() + (ROOT / "src/sprites.tsx").read_text()
    art = {}
    for m in re.finditer(r"export const (\w+)(?::\s*[\w\[\], ]+)?\s*=\s*(\[.*?\])\s*(?:as const)?;", src, re.S):
        try:
            art[m.group(1)] = json.loads(re.sub(r",\s*\]", "]", m.group(2)))
        except json.JSONDecodeError:
            pass
    return art


ART = load_art()


def run_paths(rows) -> dict[str, str]:
    """One path of horizontal runs per colour key, as in sprites.tsx."""
    out: dict[str, list[str]] = {}
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch, n = row[x], 1
            while x + n < len(row) and row[x + n] == ch:
                n += 1
            if ch != ".":
                out.setdefault(ch, []).append(f"M{x} {y}h{n}v1h-{n}z")
            x += n
    return {ch: "".join(d) for ch, d in out.items()}


def sprite(rows, x, y, s, colors=None, extra="", inner="") -> str:
    colors = {**COLORS, **(colors or {})}
    paths = "".join(f'<path fill="{colors[ch]}" d="{d}"/>' for ch, d in run_paths(rows).items())
    return f'<g transform="translate({x} {y}) scale({s})"{extra}>{paths}{inner}</g>'


def mirror(rows):
    return ["".join(reversed(r)) for r in rows]


def size(rows):
    return max(len(r) for r in rows), len(rows)


def flicker(frames, x, y, s, dur=0.8, late=False) -> str:
    """Two sprite frames swapped in steps, like the landing's torches and pennants."""
    begin = f"{dur / 2:.2f}s" if late else "0s"
    a = f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" calcMode="discrete" dur="{dur}s" begin="{begin}" repeatCount="indefinite"/>'
    b = f'<animate attributeName="opacity" values="0;1" keyTimes="0;0.5" calcMode="discrete" dur="{dur}s" begin="{begin}" repeatCount="indefinite"/>'
    return sprite(frames[0], x, y, s, inner=a) + sprite(frames[1], x, y, s, extra=' opacity="0"', inner=b)


def hills(rows, y, cell, width, edge, fill, opacity=1.0, offset=0) -> str:
    w, _ = size(rows)
    paths = run_paths(rows)
    tile = "".join(f'<path fill="{edge if ch == "k" else fill}" d="{d}"/>' for ch, d in paths.items())
    n = int(width / (w * cell)) + 2
    tiles = "".join(f'<g transform="translate({offset + i * w * cell} {y}) scale({cell})">{tile}</g>' for i in range(-1, n))
    return f'<g opacity="{opacity}">{tiles}</g>'


# ---------- text as paths ----------

class Face:
    def __init__(self, key, path, wght=None):
        font = TTFont(ROOT / "node_modules" / path)
        if wght is not None and "fvar" in font:
            font = instancer.instantiateVariableFont(font, {"wght": wght})
        self.key, self.font = key, font
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.hmtx = font["hmtx"]
        self.used: dict[str, str] = {}

    def glyph(self, ch):
        name = self.cmap.get(ord(ch)) or self.cmap[ord("?")]
        gid = f"{self.key}{ord(ch):x}"
        if gid not in self.used:
            pen = SVGPathPen(self.glyphs, lambda v: str(round(v)))
            self.glyphs[name].draw(pen)
            self.used[gid] = pen.getCommands()
        return gid, self.hmtx[name][0]

    def width(self, s, px, track=0.0):
        return sum(self.hmtx[self.cmap.get(ord(c)) or self.cmap[ord("?")]][0] for c in s) * px / self.upm + track * px * max(len(s) - 1, 0)


FACES = {
    "display": Face("d", "@fontsource-variable/pixelify-sans/files/pixelify-sans-latin-wght-normal.woff2", 700),
    "pixel": Face("p", "@fontsource-variable/pixelify-sans/files/pixelify-sans-latin-wght-normal.woff2", 500),
    "label": Face("l", "@fontsource/silkscreen/files/silkscreen-latin-400-normal.woff2"),
    "serif": Face("s", "@fontsource-variable/source-serif-4/files/source-serif-4-latin-wght-normal.woff2", 400),
    "serifb": Face("b", "@fontsource-variable/source-serif-4/files/source-serif-4-latin-wght-normal.woff2", 650),
}


def text(s, x, y, px, face="pixel", fill=INK, anchor="start", track=0.0, extra="") -> str:
    """A line of text drawn with <use> glyphs; y is the baseline."""
    f = FACES[face]
    w = f.width(s, px, track)
    x0 = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)
    k = px / f.upm
    uses, cx = [], 0.0
    for ch in s:
        gid, adv = f.glyph(ch)
        if ch != " ":
            uses.append(f'<use href="#{gid}" x="{round(cx)}"/>')
        cx += adv + track * f.upm
    return f'<g fill="{fill}" transform="translate({x0:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})"{extra}>{"".join(uses)}</g>'


def width(s, px, face="pixel", track=0.0):
    return FACES[face].width(s, px, track)


def defs() -> str:
    return "<defs>" + "".join(f'<path id="{gid}" d="{d}"/>' for f in FACES.values() for gid, d in f.used.items()) + "</defs>"


def reset_glyphs():
    for f in FACES.values():
        f.used = {}


# ---------- pixel frames and pieces ----------

def frame(x, y, w, h, fill=PAPER, edge=INK, t=4, shadow=False) -> str:
    """A notched pixel frame: four sides with the corners left empty, as the landing's .px-frame."""
    out = []
    if shadow:  # the same notched shape, 4px down and right
        out.append(f'<path fill="{INK}" d="M{x + t + 4} {y + 4}h{w - 2 * t}v{h}h-{w - 2 * t}zM{x + 4} {y + t + 4}h{w}v{h - 2 * t}h-{w}z"/>')
    out.append(f'<rect x="{x + t}" y="{y + t}" width="{w - 2 * t}" height="{h - 2 * t}" fill="{fill}"/>')
    out.append(f'<path fill="{edge}" d="M{x + t} {y}h{w - 2 * t}v{t}h-{w - 2 * t}zM{x + t} {y + h - t}h{w - 2 * t}v{t}h-{w - 2 * t}z'
               f'M{x} {y + t}h{t}v{h - 2 * t}h-{t}zM{x + w - t} {y + t}h{t}v{h - 2 * t}h-{t}z"/>')
    return "".join(out)


def svg(w, h, body, title, desc="") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="t d" shape-rendering="crispEdges"><title id="t">{title}</title><desc id="d">{desc}</desc>'
            f"{defs()}{body}</svg>")


def write(name, content):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(content)
    print(f"{name}: {len(content) / 1024:.0f} KB")


# ---------- hero ----------

def hero():
    reset_glyphs()
    W, H, G = 1200, 530, 486
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>']
    # clouds drift right to left
    for cx, cy, s, dur in ((620, 36, 5, 70), (960, 104, 4, 95), (1110, 28, 3, 120)):
        b.append(f'<g>{sprite(ART["CLOUD"], 0, 0, s)}<animateTransform attributeName="transform" type="translate" '
                 f'values="{cx} {cy};{cx - 180} {cy};{cx} {cy}" dur="{dur}s" repeatCount="indefinite"/></g>')
    # hills fade in from the right, so the words on the left sit on clean paper
    b.append(f'<defs><linearGradient id="fade" x1="0" x2="1"><stop offset="0.36" stop-color="#fff" stop-opacity="0"/>'
             f'<stop offset="0.52" stop-color="#fff"/></linearGradient><mask id="hills"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask></defs>')
    b.append(f'<g mask="url(#hills)">{hills(ART["HILLS_FAR"], G - 230, 6, W, STONE, HAZE, 0.7, -140)}'
             f'{hills(ART["HILLS_NEAR"], G - 110, 6, W, INK, MIST, 1, -420)}</g>')
    b.append(f'<rect y="{G}" width="{W}" height="{H - G}" fill="{MIST}"/><rect y="{G}" width="{W}" height="4" fill="{INK}"/>')

    # the castle, its pennants, torches and a glowing gate
    p, cw, ch = 5, *size(ART["CASTLE"])
    cx, cy = 770, G - ch * p
    b.append(sprite(ART["CASTLE"], cx, cy, p))
    b.append(flicker(ART["PENNANT"], cx + 8 * p, cy, p, 0.9))
    b.append(flicker(ART["PENNANT"], cx + (cw - 9) * p, cy, p, 0.9, late=True))
    b.append(flicker(ART["TORCH"], cx + 25 * p, cy + 41 * p, p, 0.6))
    b.append(flicker(ART["TORCH"], cx + 48 * p, cy + 41 * p, p, 0.6, late=True))
    dx, dy = cx + 31 * p, cy + 34 * p
    b.append(sprite(ART["DOOR"], dx, dy, p) + sprite(mirror(ART["DOOR"]), dx + 8 * p, dy, p))
    b.append(f'<rect x="{dx + 8 * p - 3}" y="{dy + 6 * p}" width="6" height="{14 * p}" fill="{SIGNAL_SOFT}">'
             f'<animate attributeName="opacity" values="0.25;0.9;0.25" dur="1.8s" repeatCount="indefinite"/></rect>')

    # a document that comes out of the gate redacted: every value flashes red, a black bar wipes over it, a tag drops
    dxo, dyo, dw, dh = 494, 276, 268, 196
    rows = [("Tenant", "Raj Patel", "PERSON_1"), ("Address", "41 Elm Road", "ADDRESS_1"),
            ("Sort code", "20-45-77", "SORT_CODE_1"), ("Account", "31926819", "ACCOUNT_1")]
    doc = [frame(0, 0, dw, dh, shadow=True), text("tenancy.pdf", 18, 34, 13, "label", QUIET)]
    T = 8.0
    for i, (label, value, tag) in enumerate(rows):
        y = 70 + i * 34
        doc.append(text(label + ":", 18, y, 17, "serif", INK))
        vx = 18 + width(label + ": ", 17, "serif")
        vw = width(value, 17, "serifb") + 8
        t0, t1 = (0.12 + i * 0.12), (0.12 + i * 0.12 + 0.08)
        doc.append(f'<g>{text(value, vx, y, 17, "serifb", SIGNAL_DEEP)}'
                   f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;{t1:.2f};{t1 + 0.01:.2f};0.97;1" dur="{T}s" repeatCount="indefinite"/></g>')
        doc.append(f'<rect x="{vx - 4}" y="{y - 17}" height="23" width="0" fill="{INK}">'
                   f'<animate attributeName="width" values="0;0;{vw};{vw};0" keyTimes="0;{t0:.2f};{t1:.2f};0.97;1" dur="{T}s" repeatCount="indefinite"/></rect>')
        doc.append(f'<g opacity="0">{text(tag, vx + 2, y - 1, 11, "label", SIGNAL_SOFT)}'
                   f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{t1:.2f};{t1 + 0.02:.2f};0.97;1" dur="{T}s" repeatCount="indefinite"/></g>')
    stamp = (f'<g opacity="0" transform="translate({dw - 128} {dh - 52}) rotate(-8)">{frame(0, 0, 118, 34, BONE, SIGNAL)}'
             f'{text("PROTECTED", 59, 23, 13, "label", SIGNAL, "middle")}'
             f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.66;0.68;0.97;1" dur="{T}s" repeatCount="indefinite"/></g>')
    b.append(f'<g transform="translate({dxo} {dyo}) rotate(-3)">{"".join(doc)}{stamp}</g>')

    # words
    b.append(f'<g>{frame(48, 52, 318, 34, INK, INK)}{text("MUBIT NIGHT SHIFT · LONDON 2026", 207, 75, 12, "label", BONE, "middle")}</g>')
    b.append(text("MuGuard", 44, 196, 112, "display", INK))
    b.append(text("Your documents stay", 48, 258, 38, "display", INK))
    b.append(text("inside the walls.", 48, 302, 38, "display", INK))
    for i, line in enumerate(("Hides names, account numbers and IDs", "before a document goes to an AI, then",
                              "puts the real values back in the answer.")):
        b.append(text(line, 50, 356 + i * 30, 21, "pixel", QUIET))
    write("hero.svg", svg(W, H, "".join(b), "MuGuard: your documents stay inside the walls",
                          "A pixel castle on a hill; a tenancy agreement leaves the gate and each personal value is blacked out with a red placeholder tag."))


# ---------- shared motion helpers ----------

def keyed(points, T, hold=0.0):
    """SMIL keyTimes/values from (progress, value) points; the value holds before the first and after the last point.
    Progress runs over the first (1 - hold) of the loop; the rest holds the end frame."""
    span = 1 - hold
    ks, vs = [0.0], [points[0][1]]
    for k, v in points:
        k = round(k * span, 4)
        if k <= ks[-1]:
            k = ks[-1] + 0.0001
        ks.append(k)
        vs.append(v)
    ks.append(1.0)
    vs.append(points[-1][1])
    return f'keyTimes="{";".join(f"{k:.4f}" for k in ks)}" values="{";".join(str(v) for v in vs)}" dur="{T}s" repeatCount="indefinite"'


def move(points, T, hold=0.0):
    return f'<animateTransform attributeName="transform" type="translate" {keyed(points, T, hold)}/>'


def fade(points, T, hold=0.0):
    return f'<animate attributeName="opacity" {keyed(points, T, hold)}/>'


def wrap(s, px, face, maxw):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and width(trial, px, face) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def chip(label, x, y, px=11):
    w = width(label, px, "label") + 14
    return f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{px + 10}" fill="{INK}"/>' + text(label, x + 7, y + px + 4, px, "label", SIGNAL_SOFT)


def stage_label(label, x, y):
    w = width(label.upper(), 11, "label") + 16
    return f'<rect x="{x}" y="{y}" width="{w:.0f}" height="22" fill="{BONE}"/>' + text(label.upper(), x + 8, y + 15, 11, "label", QUIET)


def backdrop(W, G, H, cell=6):
    return (hills(ART["HILLS_FAR"], G - 240, cell, W, STONE, HAZE, 0.7, -60) + hills(ART["HILLS_NEAR"], G - 120, cell, W, INK, MIST, 1, -300)
            + f'<rect y="{G}" width="{W}" height="{H - G}" fill="{MIST}"/><rect y="{G}" width="{W}" height="4" fill="{INK}"/>')


# ---------- the journey: the landing's four steps, played on a loop ----------

STEPS = [
    ("Inside the walls", "Your document starts on your side: a tenancy agreement, a payslip, a client email, with every name and account number still in it."),
    ("The guard", "At the gate, the MuGuard knight, a redaction model trained through Mubit, blacks out each personal value. You review every change."),
    ("Only placeholders ride out", "A messenger carries the redacted copy to the AI provider. It reads PERSON_1 and ACCOUNT_1, never the real values."),
    ("The answer comes home", "Back inside the walls, MuGuard swaps the placeholders for the real values, so the answer you read names the right people."),
]
DOC = [("Tenant", "Raj Patel", "PERSON_1"), ("Address", "41 Elm Road, Leeds", "ADDRESS_1"),
       ("Sort code", "20-45-77", "SORT_CODE_1"), ("Account", "31926819", "ACCOUNT_1")]


def journey():
    reset_glyphs()
    T, HOLD = 20, 0.1
    W, TOP = 1200, 150
    G = TOP + 440
    H = G + 64
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>', backdrop(W, G, H)]
    bounds = [0, 0.2, 0.56, 0.78, 1.0]

    # step tabs and captions across the top
    x = 40
    for i, (title, body) in enumerate(STEPS):
        label = title
        tw = width(label, 17, "pixel") + 64
        on = [(bounds[i] - 0.001, 0), (bounds[i], 1), (bounds[i + 1] - 0.001, 1), (bounds[i + 1], 0)] if i < 3 else [(bounds[i] - 0.001, 0), (bounds[i], 1)]
        if i == 0:
            on = [(0, 1), (bounds[1] - 0.001, 1), (bounds[1], 0)]
        b.append(f'<g>{frame(x, 20, tw, 44, PAPER, INK, 3)}<rect x="{x + 12}" y="{32}" width="22" height="20" fill="{MIST}"/>'
                 f'{text(str(i + 1), x + 23, 48, 14, "label", INK, "middle")}{text(label, x + 44, 49, 17, "pixel", INK)}</g>')
        b.append(f'<g opacity="0">{frame(x, 20, tw, 44, INK, INK, 3)}<rect x="{x + 12}" y="{32}" width="22" height="20" fill="{SIGNAL}"/>'
                 f'{text(str(i + 1), x + 23, 48, 14, "label", "#fff", "middle")}{text(label, x + 44, 49, 17, "pixel", BONE)}{fade(on, T, HOLD)}</g>')
        lines = wrap(body, 19, "pixel", 1100)
        cap = text(title, 40, 106, 28, "display", INK) + "".join(text(l, 40, 136 + j * 26, 19, "pixel", QUIET) for j, l in enumerate(lines))
        b.append(f'<g opacity="{1 if i == 0 else 0}">{cap}{fade(on, T, HOLD)}</g>')
        x += tw + 14

    g = G  # stage ground
    # your castle
    b.append(sprite(ART["CASTLE"], 40, g - 168, 3))
    b.append(stage_label("Your side", 70, g + 18))
    # the wall, its portcullis, the knight and a torch
    b.append(f'<defs><clipPath id="tunnel"><rect x="560" y="{g - 130}" width="80" height="130"/></clipPath></defs>')
    b.append(f'<g clip-path="url(#tunnel)"><g>{sprite(ART["PORTCULLIS"], 560, g - 130, 5)}'
             f'{move([(0.40, "0 0"), (0.46, "0 -140"), (0.54, "0 -140"), (0.60, "0 0")], T, HOLD)}</g></g>')
    b.append(sprite(ART["WALL_SIDE"], 540, g - 280, 5))
    bob = [(0.24, "0 0")] + [(0.25 + 0.02 * k, f"0 {-14 if k % 2 == 0 else 0}") for k in range(8)]
    b.append(f'<g>{sprite(ART["KNIGHT_SMALL"], 545, g - 350, 5)}{move(bob, T, HOLD)}</g>')
    b.append(flicker(ART["TORCH"], 518, g - 120, 4, 0.6))
    b.append(stage_label("The MuGuard knight, trained through Mubit", 478, g + 18))
    # the AI provider
    b.append(sprite(ART["AI_TOWER"], 1040, g - 256, 4))
    b.append(stage_label("AI provider", 1032, g + 18))

    # the document: waits, walks to the gate, gets each value blacked out, folds small and goes through the tunnel
    dw, dh = 220, 150
    d = [frame(0, 0, dw, dh), text("tenancy.pdf", 14, 26, 11, "label", INK)]
    for i, (label, value, tag) in enumerate(DOC):
        y = 56 + i * 26
        d.append(text(f"{label}:", 14, y, 14, "serif", INK))
        vx = 14 + width(f"{label}: ", 14, "serif")
        vw = width(value, 14, "serifb") + 6
        d.append(text(value, vx, y, 14, "serifb", SIGNAL_DEEP))
        w0, w1 = 0.24 + 0.04 * i, 0.28 + 0.04 * i
        d.append(f'<rect x="{vx - 3:.1f}" y="{y - 14}" height="19" width="0" fill="{INK}"><animate attributeName="width" '
                 f'{keyed([(w0, 0), (w1, round(vw, 1)), (0.985, round(vw, 1)), (0.99, 0)], T, HOLD)}/></rect>')
        d.append(f'<g opacity="0">{text(tag, vx + 1, y - 1, 10, "label", SIGNAL_SOFT)}{fade([(w1 - 0.006, 0), (w1, 1), (0.985, 1), (0.99, 0)], T, HOLD)}</g>')
    doc_xy = [(0, f"150 {g - 136 - dh / 2:.0f}"), (0.06, f"150 {g - 136 - dh / 2:.0f}"), (0.18, f"310 {g - 136 - dh / 2:.0f}"),
              (0.42, f"310 {g - 136 - dh / 2:.0f}"), (0.47, f"560 {g - 60:.0f}"), (0.56, f"700 {g - 60:.0f}")]
    scale = [(0.42, "1"), (0.47, "0.32"), (0.56, "0.32"), (0.60, "0.1")]
    b.append(f'<g>{move(doc_xy, T, HOLD)}<g>{"".join(d)}<animateTransform attributeName="transform" type="scale" {keyed(scale, T, HOLD)}/></g>'
             f'{fade([(0.57, 1), (0.61, 0), (0.99, 0), (0.995, 1)], T, HOLD)}</g>')

    # the messenger pigeon carries the scroll out to the AI provider, then the answer home
    pw = size(ART["PIGEON"][0])[0] * 4
    fly = [(0.58, "720 330"), (0.65, "880 170"), (0.72, "1040 215"), (0.77, "1040 215"), (0.85, "620 90"), (0.92, "200 228")]
    right = flicker(ART["PIGEON"], 0, 0, 4, 0.35) + sprite(ART["SCROLL"], 26, 44, 3)
    left = flicker([mirror(f) for f in ART["PIGEON"]], 0, 0, 4, 0.35) + sprite(mirror(ART["SCROLL"]), pw - 26 - 24, 44, 3)
    b.append(f'<g opacity="0">{move([(k, v) for k, v in fly], T, HOLD)}'
             f'<g>{right}{fade([(0.745, 1), (0.755, 0)], T, HOLD)}</g><g opacity="0">{left}{fade([(0.745, 0), (0.755, 1)], T, HOLD)}</g>'
             f'{fade([(0.56, 0), (0.60, 1), (0.94, 1), (0.97, 0)], T, HOLD)}</g>')

    # what the AI provider reads
    a = [frame(0, 0, 330, 108), text("WHAT THE AI PROVIDER READS", 14, 26, 11, "label", QUIET)]
    words = [("When does", None), ("PERSON_1", "tag"), ("pay rent from", None), ("ACCOUNT_1", "tag")]
    cx, cy = 14, 60
    for wtxt, kind in words:
        if kind:
            tw_ = width(wtxt, 11, "label") + 10
            if cx + tw_ > 316:
                cx, cy = 14, cy + 28
            a.append(f'<rect x="{cx}" y="{cy - 15}" width="{tw_:.0f}" height="20" fill="{INK}"/>' + text(wtxt, cx + 5, cy - 1, 11, "label", SIGNAL_SOFT))
            cx += tw_ + 6
        else:
            for wd in wtxt.split():
                ww = width(wd, 16, "serif")
                if cx + ww > 316:
                    cx, cy = 14, cy + 28
                a.append(text(wd, cx, cy, 16, "serif", INK))
                cx += ww + width(" ", 16, "serif")
    a.append(text("?", cx - 4, cy, 16, "serif", INK))
    b.append(f'<g opacity="0" transform="translate(740 {TOP + 30})">{"".join(a)}{fade([(0.68, 0), (0.72, 1), (0.8, 1), (0.84, 0)], T, HOLD)}</g>')

    # the answer, back inside: real values again
    h = [frame(0, 0, 360, 108), text("THE ANSWER, BACK INSIDE", 14, 26, 11, "label", QUIET)]
    parts = [("Raj Patel", True), ("pays £950 on the 1st", False), ("from account", False), ("31926819", True), (".", False)]
    cx, cy = 14, 60
    for ptxt, mark in parts:
        for wd in ([ptxt] if mark else ptxt.split()):
            face = "serifb" if mark else "serif"
            ww = width(wd, 16, face)
            if cx + ww > 346 and wd != ".":
                cx, cy = 14, cy + 28
            if mark:
                h.append(f'<rect x="{cx - 2:.1f}" y="{cy - 15}" width="{ww + 4:.1f}" height="21" fill="{SIGNAL}" opacity="0.15"/>'
                         f'<rect x="{cx - 2:.1f}" y="{cy + 4}" width="{ww + 4:.1f}" height="2" fill="{SIGNAL}"/>')
            h.append(text(wd, cx, cy, 16, face, SIGNAL_DEEP if mark else INK))
            cx += ww + (0 if wd == "." else width(" ", 16, "serif"))
    b.append(f'<g opacity="0" transform="translate(50 {TOP + 40})">{"".join(h)}{fade([(0.90, 0), (0.94, 1), (0.99, 1), (0.995, 0)], T, HOLD)}</g>')

    write("journey.svg", svg(W, H, "".join(b), "How MuGuard works, in four steps",
                             "A tenancy agreement leaves your castle; at the gate the MuGuard knight blacks out each personal value; "
                             "a pigeon carries only placeholders to the AI provider's tower; the answer comes home and the real values are put back."))


# ---------- what the AI provider receives ----------

SHEET = [
    [("Landlord: ", None), ("Helen Ward", "PERSON_1"), (", ", None), ("9 Marsh Lane, Bristol BS3 1QT", "ADDRESS_1")],
    [("Tenant: ", None), ("Raj Patel", "PERSON_2"), (", born ", None), ("14/02/1991", "DOB_1")],
    [("Property: ", None), ("41 Elm Road, Leeds LS6 2AB", "ADDRESS_2")],
    [("Rent: £950 a month to sort code ", None), ("20-45-77", "SORT_CODE_1"), (",", None)],
    [("account ", None), ("31926819", "ACCOUNT_1"), (", from the 1st of March.", None)],
    [("Contact: ", None), ("raj.patel@post.example", "EMAIL_1"), (", ", None), ("07700 900123", "PHONE_1")],
]


def sheet(x, y, w, h, title, redacted, T):
    out = [frame(x, y, w, h, PAPER, INK, 4, shadow=True)]
    out.append(f'<rect x="{x + 4}" y="{y + 4}" width="{w - 8}" height="40" fill="{INK if redacted else BONE}"/>')
    out.append(text(title, x + 20, y + 30, 13, "label", SIGNAL_SOFT if redacted else SIGNAL))
    out.append(text("ASSURED SHORTHOLD TENANCY AGREEMENT", x + 20, y + 78, 12, "label", QUIET))
    n = 0
    for i, line in enumerate(SHEET):
        ly = y + 116 + i * 36
        cx = x + 20
        for part, tag in line:
            if tag is None:
                out.append(text(part, cx, ly, 17, "serif", INK))
                cx += width(part, 17, "serif")
            elif not redacted:
                ww = width(part, 17, "serifb")
                out.append(f'<rect x="{cx:.1f}" y="{ly + 4}" width="{ww:.1f}" height="2" fill="{SIGNAL}"/>' + text(part, cx, ly, 17, "serifb", SIGNAL_DEEP))
                cx += ww
            else:
                ww = width(tag, 14, "label") + 12
                k = 0.08 + i * 0.1  # the guard's pass reaches this line
                out.append(f'<rect x="{cx:.1f}" y="{ly - 18}" width="{ww:.1f}" height="24" fill="{INK}">'
                           f'<animate attributeName="fill" values="{INK};{INK};{SIGNAL};{INK};{INK}" keyTimes="0;{k:.2f};{k + 0.03:.2f};{k + 0.08:.2f};1" dur="{T}s" repeatCount="indefinite"/></rect>')
                out.append(text(tag, cx + 6, ly + 1, 14, "label", SIGNAL_SOFT))
                cx += ww + 2
                n += 1
    return "".join(out)


def what_ai_sees():
    reset_glyphs()
    T = 6
    W, H = 1200, 470
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>']
    sw, sh = 556, 352
    b.append(sheet(36, 70, sw, sh, "WITHOUT MUGUARD: 9 REAL VALUES", False, T))
    b.append(sheet(W - 36 - sw - 4, 70, sw, sh, "WITH MUGUARD: 0 REAL VALUES", True, T))
    # the guard's pass sweeps the redacted sheet line by line
    x0 = W - 36 - sw
    b.append(f'<rect x="{x0}" width="{sw - 8}" height="3" fill="{SIGNAL}" opacity="0.8"><animate attributeName="y" '
             f'values="{70 + 92};{70 + 92 + 6 * 36};{70 + 92 + 6 * 36}" keyTimes="0;0.66;1" dur="{T}s" repeatCount="indefinite"/>'
             f'<animate attributeName="opacity" values="0.8;0.8;0" keyTimes="0;0.66;0.7" dur="{T}s" repeatCount="indefinite"/></rect>')
    b.append(text("What the AI provider receives", 36, 46, 28, "display", INK))
    b.append(text("Illustration with invented values", W - 36, 44, 12, "label", QUIET, "end"))
    b.append(text("The placeholders map back to the real values only on your side.", 36, H - 14, 17, "pixel", QUIET))
    write("what-ai-sees.svg", svg(W, H, "".join(b), "What the AI provider receives, with and without MuGuard",
                                  "Two copies of the same tenancy agreement. Without MuGuard the provider reads nine real names, addresses, "
                                  "dates and account details; with MuGuard it reads placeholders such as PERSON_1 and ACCOUNT_1."))


# ---------- the numbers ----------

def bar(x, y, w, h, pct, color, T0, track=MIST):
    full = round(w * pct / 100, 1)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{track}"/>'
            f'<rect x="{x}" y="{y}" height="{h}" width="{full}" fill="{color}">'
            f'<animate attributeName="width" values="0;{full}" dur="1.1s" begin="{T0}s" fill="freeze" calcMode="spline" keySplines="0.16 1 0.3 1" keyTimes="0;1"/></rect>')


def numbers(data):
    reset_glyphs()
    W, H = 1200, 690
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>', frame(24, 24, W - 52, H - 52, PAPER, INK, 4, shadow=True)]
    b.append(chip("THE GUARD'S LEDGER", 56, 56, 12))
    b.append(text("Rules and the model catch different things", 56, 128, 34, "display", INK))
    b.append(text(f"Share of {data['ALL']['n']} personal values fully hidden, in 50 synthetic documents", 56, 162, 19, "pixel", QUIET))
    rows = [("Rules only", "rules", QUIET), ("AI model only", "model", STONE), ("MuGuard: both", "both", SIGNAL)]
    for i, (label, key, color) in enumerate(rows):
        y = 206 + i * 64
        b.append(text(label, 56, y + 30, 22, "display" if key == "both" else "pixel", INK))
        b.append(bar(300, y + 6, 680, 34, data["ALL"][key], color, 0.2 + 0.25 * i))
        b.append(text(f"{data['ALL'][key]:.1f}%", 1130, y + 36, 30, "label", SIGNAL if key == "both" else INK, "end"))
    smalls = [("Names", "PERSON"), ("Client codes", "CUSTOM"), ("Addresses", "ADDRESS"), ("Phones", "PHONE")]
    sx, sw = 56, 252
    for j, (title, key) in enumerate(smalls):
        x = sx + j * (sw + 20)
        y = 420
        b.append(f'<rect x="{x}" y="{y}" width="{sw}" height="2" fill="{INK}"/>')
        b.append(text(title, x, y + 34, 20, "display", INK) + text(f"n = {data[key]['n']}", x + sw, y + 32, 11, "label", QUIET, "end"))
        for i, (label, k2, color) in enumerate(rows):
            yy = y + 54 + i * 34
            b.append(bar(x, yy, sw - 70, 20, data[key][k2], color, 1.0 + 0.15 * (j + i)))
            b.append(text(f"{data[key][k2]:.0f}%" if data[key][k2] >= 10 or data[key][k2] == 0 else f"{data[key][k2]:.1f}%", x + sw, yy + 17, 14, "label",
                          SIGNAL if k2 == "both" else INK, "end"))
    for i, (label, _, color) in enumerate(rows):
        lx = 56 + i * 200
        b.append(f'<rect x="{lx}" y="{H - 104}" width="14" height="14" fill="{color}"/>' + text(label, lx + 22, H - 92, 14, "label", INK))
    b.append(text("140 chunks with an answer key. Model: claude-haiku-4-5 answers sent through Mubit, scored offline.", 56, H - 64, 15, "pixel", QUIET))
    b.append(text("A value counts only when every character is hidden. The rules were tuned on similar templates.", 56, H - 42, 15, "pixel", QUIET))
    write("numbers.svg", svg(W, H, "".join(b), "Rules and the model catch different things",
                             f"Share of personal values fully hidden: rules only {data['ALL']['rules']}%, AI model only {data['ALL']['model']}%, "
                             f"MuGuard with both {data['ALL']['both']}%. Names: {data['PERSON']['rules']}%, {data['PERSON']['model']}%, {data['PERSON']['both']}%. "
                             f"Client codes: {data['CUSTOM']['rules']}%, {data['CUSTOM']['model']}%, {data['CUSTOM']['both']}%."))


# ---------- the guard's training in Mubit ----------

TICK = ["......kk", ".....kk.", "kk..kk..", ".kkkk...", "..kk...."]
QUEST = [
    ("done", "Recorded", "Every detection call lands in the Mubit task “Redact personal data”."),
    ("done", "Rated", "365 replies scored against our answer key: 231 good, the rest bad."),
    ("done", "Trained", "Adapter v1 on Qwen3-4B-Instruct-2507, from the kept examples."),
    ("done", "Examined", "Held-out test: v1 91.7%, the base model with the same prompt 66.7%."),
    ("now", "Silent test", "v1 shadows 100% of calls; waiting for Mubit to route the task to it."),
    ("todo", "Live", "v1 answers real detection calls, and every fix trains v2."),
]


def mubit():
    reset_glyphs()
    T = 1.2
    W, H = 1200, 560
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>']
    b.append(hills(ART["HILLS_NEAR"], H - 150, 6, 380, INK, MIST, 1, -200))
    b.append(f'<rect y="{H - 30}" width="380" height="30" fill="{MIST}"/><rect y="{H - 30}" width="380" height="4" fill="{INK}"/>')
    b.append(sprite(ART["GATEHOUSE"], 40, H - 30 - 44 * 5, 5))
    kw = size(ART["KNIGHT_SMALL"])[0] * 6
    b.append(f'<g>{sprite(ART["KNIGHT_SMALL"], 40 + 150 - kw / 2, H - 30 - 44 * 5 - 14 * 6 + 8, 6)}'
             f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" dur="1.6s" repeatCount="indefinite"/></g>')
    b.append(chip("TRAINED THROUGH MUBIT", 40, 40, 12))
    b.append(text("The guard's", 40, 112, 36, "display", INK) + text("training", 40, 152, 36, "display", INK))
    x0, y0, w = 400, 36, W - 400 - 36
    b.append(frame(x0, y0, w, H - 72, PAPER, INK, 4, shadow=True))
    for i, (state, title, body) in enumerate(QUEST):
        y = y0 + 34 + i * 78
        box = f'<rect x="{x0 + 28}" y="{y}" width="34" height="34" fill="{PAPER}"/>' + frame(x0 + 28, y, 34, 34, PAPER if state != "done" else INK, INK, 3)
        if state == "done":
            box += sprite(TICK, x0 + 33, y + 9, 3, {"k": SIGNAL_SOFT})
        elif state == "now":
            box += (f'<rect x="{x0 + 37}" y="{y + 9}" width="16" height="16" fill="{SIGNAL}">'
                    f'<animate attributeName="opacity" values="1;0.15;1" dur="{T}s" repeatCount="indefinite"/></rect>')
        b.append(box)
        color = QUIET if state == "todo" else INK
        b.append(text(title, x0 + 82, y + 16, 22, "display", color))
        if state == "now":
            b.append(f'<g>{chip("NOW", x0 + 82 + width(title, 22, "display") + 12, y - 2, 11)}</g>')
        b.append(text(body, x0 + 82, y + 44, 17, "pixel", QUIET))
        if title == "Examined":
            bx = x0 + 82 + width(title, 22, "display") + 24
            b.append(bar(bx, y - 2, 150, 9, 91.7, SIGNAL, 0.4) + text("v1 91.7%", bx + 160, y + 7, 11, "label", INK))
            b.append(bar(bx, y + 11, 150, 9, 66.7, STONE, 0.7) + text("base 66.7%", bx + 160, y + 20, 11, "label", INK))
    write("mubit.svg", svg(W, H, "".join(b), "The guard's training in Mubit",
                           "Recorded, rated, trained and examined: adapter v1 scored 91.7% against 66.7% for the base model. "
                           "Its silent test is running while Mubit routes the task to it; going live is the next step."))


# ---------- the training race and the five quests (scenes from the demo video) ----------

TEAM = [
    ("Mykola", "REALISM", SIGNAL, "180", "realistic documents", "public templates, invented values", "rewrites the text", "Claude Haiku 4.5", 91.7, "11 of 12 test cases"),
    ("Glib", "MIDDLE ROAD", SIGNAL_SOFT, "576", "synthetic cases", "12 scenario families", "returns sensitive spans", "Claude Haiku 4.5", 83.3, "10 of 12 test cases"),
    ("Dmytro", "VOLUME", STONE, "100,000", "generated documents", "synthetic UK paperwork", "returns a list of values", "gpt-6-luna, the cheapest", 60.0, "6 of 10 test cases"),
]


def training():
    reset_glyphs()
    W, H = 1200, 810
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>', frame(24, 24, W - 52, H - 52, PAPER, INK, 4, shadow=True)]
    b.append(chip("ONE JOB · THREE MUBIT ACCOUNTS", 56, 56, 12))
    b.append(text("Same student, three teachers", 56, 128, 34, "display", INK))
    b.append(text("Mubit records calls to a big teacher model and trains a small one to copy it. We trained ours three ways.", 56, 162, 18, "pixel", QUIET))
    cw, gap, y0 = 352, 24, 192
    for i, (name, road, tint, value, unit, note, answer, teacher, _, _) in enumerate(TEAM):
        x = 56 + i * (cw + gap)
        b.append(frame(x, y0, cw, 268, BONE if i else PAPER, INK, 3))
        b.append(f'<rect x="{x + 3}" y="{y0 + 3}" width="{cw - 6}" height="34" fill="{tint}"/>')
        b.append(text(road, x + 18, y0 + 26, 13, "label", "#ffffff" if i != 2 else INK))
        b.append(text(name, x + 18, y0 + 72, 26, "display", INK))
        b.append(text(value, x + 18, y0 + 124, 40, "label", INK) + text(unit, x + 18, y0 + 150, 17, "pixel", INK))
        b.append(text(note, x + 18, y0 + 174, 15, "pixel", QUIET))
        b.append(text("ANSWER", x + 18, y0 + 206, 11, "label", QUIET) + text(answer, x + 92, y0 + 206, 15, "pixel", INK))
        b.append(text("TEACHER", x + 18, y0 + 234, 11, "label", QUIET) + text(teacher, x + 92, y0 + 234, 15, "pixel", INK))
    # the race: Mubit's held-out test, with its 85% bar
    bx, bw, ry = 300, 690, 512
    b.append(text("STUDENT: QWEN3-4B-INSTRUCT-2507", 56, ry - 6, 12, "label", QUIET))
    tx = bx + bw * 0.85
    for i, (name, _, tint, _, _, _, _, _, pct, cases) in enumerate(TEAM):
        y = ry + 18 + i * 58
        b.append(text(name, 56, y + 26, 22, "display" if i == 0 else "pixel", INK) + text(cases, 56, y + 46, 12, "label", QUIET))
        b.append(bar(bx, y + 6, bw, 30, pct, tint, 0.3 + 0.25 * i))
        b.append(text(f"{pct:.1f}%" if pct % 1 else f"{pct:.0f}%", bx + bw + 132, y + 32, 26, "label", SIGNAL if i == 0 else INK, "end"))
    b.append(f'<rect x="{tx:.0f}" y="{ry + 12}" width="4" height="{3 * 58 - 4}" fill="{INK}"/>' +
             text("MUBIT TARGET 85%", tx - 10, ry + 8, 12, "label", INK, "end"))
    kw = size(ART["KNIGHT_SMALL"])[0] * 3
    b.append(f'<g>{sprite(ART["KNIGHT_SMALL"], bx + bw * 0.917 - kw / 2, ry - 30, 3)}'
             f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="1.4s" repeatCount="indefinite"/></g>')
    b.append(text("Only realism cleared the bar. Realism beat volume, so MuGuard runs on that design.", 56, H - 84, 18, "pixel", INK))
    b.append(text("Mubit quality: share of the teacher's answers each adapter matched on held-out cases. Small tests: read it as a signal.", 56, H - 58, 14, "pixel", QUIET))
    write("training.svg", svg(W, H, "".join(b), "Same student, three teachers",
                              "Three ways to train one 4B student through Mubit: 180 realistic documents scored 91.7%, 576 synthetic cases 83.3%, "
                              "100,000 generated documents 60%. Only the realistic set cleared Mubit's 85% target."))


def quest_list():
    return [("Drop a document", FILE), ("Review", TICK), ("Fix a miss", ["k.....", "kk....", ".kk...", "..kk..", "...kk.", "....kk", ".....k"]),
            ("Approve", ["..kkk..", ".k...k.", ".k...k.", "kkkkkkk", "kkk.kkk", "kkk.kkk", "kkkkkkk"]), ("Ask the AI", ARROW)]


def quests():
    reset_glyphs()
    T = 10
    W, H = 1200, 300
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>']
    cw, gap = 216, 14
    for i, (label, icon) in enumerate(quest_list()):
        x = 24 + i * (cw + gap)
        on = [(i / 5 - 0.001, 0), (i / 5, 1), ((i + 1) / 5 - 0.001, 1), ((i + 1) / 5, 0)] if i else [(0, 1), (0.199, 1), (0.2, 0)]
        card = lambda fill, ink, sub: (frame(x, 24, cw, 150, fill, INK, 4, shadow=True) + text(f"QUEST {i + 1}/5", x + 18, 56, 12, "label", sub)
                                       + sprite(icon, x + 18, 76, 4, {"k": ink}) + text(label, x + 18, 152, 21, "display", ink))
        b.append(card(PAPER, INK, QUIET))
        b.append(f'<g opacity="{1 if i == 0 else 0}">{card(INK, BONE, SIGNAL_SOFT)}{fade(on, T)}</g>')
    # the knight's dialog box, as in the video's captions
    b.append(frame(24, 200, W - 52, 76, INK, INK, 4))
    b.append(f'<rect x="44" y="188" width="{width("THE KNIGHT", 12, "label") + 20:.0f}" height="24" fill="{SIGNAL}"/>' + text("THE KNIGHT", 54, 205, 12, "label", "#ffffff"))
    b.append(text("Five quests, and only placeholders ever pass the gate.", 48, 248, 22, "pixel", BONE))
    write("quests.svg", svg(W, H, "".join(b), "The five quests of the demo",
                            "Quest 1 drop a document, 2 review, 3 fix a miss, 4 approve, 5 ask the AI; only placeholders ever pass the gate."))


# ---------- the backend in layers (backend/README.md, backend/docs/architecture.md, docs/ARCHITECTURE.md) ----------

LAYERS = [
    ("ENTRY", "HTTP in", 92, [("main.py", "create_app()"), ("api.py", "router registry"), ("dependencies.py", "settings, database, models")]),
    ("MODULES", "one per feature", 132, [("router", "HTTP only"), ("service", "rules and errors"), ("repository", "SQL, scoped by owner")]),
    ("DOMAIN", "no FastAPI, no database", 92, [("redaction", "detect, placeholders, PDF"), ("llm", "T1 and T2 calls"), ("ingest", "OCR, PDF text layers")]),
    ("CORE", "imports nothing", 76, [(n, "") for n in ("config", "logging", "errors", "security", "crypto", "db")]),
]
FEATURES = ["auth", "documents", "scan", "corrections", "ask", "samples", "files"]
# what each row talks to, and the colours of that box
OUTSIDE = [("Browser", "through Caddy, /api", PAPER, INK, QUIET), ("PostgreSQL", "encrypted rows", INK, BONE, HAZE),
           ("Mubit", "every model call", SIGNAL, "#ffffff", PAPER), ("migrations/", "applied at startup", BONE, INK, QUIET)]
# one scan, lit up box by box
SCAN = ["Browser", "api.py", "router", "service", "redaction", "llm", "Mubit", "repository", "PostgreSQL"]


def fit(s, px, face, maxw, low=11):
    while px > low and width(s, px, face) > maxw:
        px -= 1
    return px


def backend():
    reset_glyphs()
    W, H, T = 1200, 700, 9.0
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>', frame(24, 24, W - 52, H - 52, PAPER, INK, 4, shadow=True)]
    b.append(chip("BACKEND · FASTAPI", 56, 56, 12))
    b.append(text("The backend in four layers", 56, 124, 34, "display", INK))
    sub = "Routers speak HTTP, services hold the rules, repositories hold the SQL, and domain code never imports FastAPI."
    b.append(text(sub, 56, 156, fit(sub, 18, "pixel", W - 112), "pixel", QUIET))
    boxes: dict[str, tuple[float, float, float, float]] = {}

    def cell(x, y, w, h, name, note, fill=BONE, ink=INK, quiet=QUIET, px=17):
        boxes[name] = (x, y, w, h)
        out = frame(x, y, w, h, fill, INK, 3)
        if note or h > 60:
            out += text(name, x + 14, y + (27 if note else h / 2 + 6), fit(name, px, "display", w - 24), "display", ink)
        else:  # a small name-only box: centred
            out += text(name, x + w / 2, y + h / 2 + 6, fit(name, px, "display", w - 12), "display", ink, "middle")
        if note:
            out += text(note, x + 14, y + 48, fit(note, 13, "pixel", w - 24), "pixel", quiet)
        return out

    x0, rw, y = 56, 804, 184
    for (label, note, h, cells), (oname, onote, ofill, oink, oquiet) in zip(LAYERS, OUTSIDE):
        b.append(frame(x0, y, rw, h, PAPER, INK, 3))
        b.append(text(label, x0 + 18, y + (30 if h < 90 else 34), 13, "label", INK) + text(note, x0 + 18, y + (52 if h < 90 else 56), 14, "pixel", QUIET))
        cx, avail = x0 + 210, rw - 210 - 16
        gap = 24 if label == "MODULES" else 12 if len(cells) > 3 else 16
        cw = (avail - gap * (len(cells) - 1)) / len(cells)
        ch = 44 if label == "CORE" else 60
        px = min(fit(name, 17, "display", cw - (24 if cnote else 12)) for name, cnote in cells)  # one size per row
        for i, (name, cnote) in enumerate(cells):
            x = cx + i * (cw + gap)
            b.append(cell(x, y + 16, cw, ch, name, cnote, px=px))
            if label == "MODULES" and i:
                b.append(sprite(ARROW, x - gap / 2 - 9, y + 16 + ch / 2 - 7, 2, {"k": STONE}))
        if label == "MODULES":
            fx = cx
            for f in FEATURES:
                b.append(chip(f, fx, y + 92, 11))
                fx += width(f, 11, "label") + 14 + 8
        # the outside box this layer talks to, joined to the row
        mid = y + h / 2
        b.append(f'<rect x="{x0 + rw}" y="{mid - 2:.0f}" width="44" height="4" fill="{SIGNAL if oname == "Mubit" else INK}"/>')
        b.append(cell(904, mid - 32, 240, 64, oname, onote, ofill, oink, oquiet))
        y += h + 16

    # the scan's path: each box gets a red outline in turn, the whole path stays lit, then the loop starts again
    n = len(SCAN)
    for i, name in enumerate(SCAN):
        x, yy, w, h = boxes[name]
        on = [(i / n - 0.001, 0), (i / n, 1), (0.96, 1), (0.961, 0)]
        b.append(f'<rect x="{x - 4:.0f}" y="{yy - 4:.0f}" width="{w + 8:.0f}" height="{h + 8:.0f}" fill="none" stroke="{SIGNAL}" stroke-width="4" opacity="0">'
                 f'<animate attributeName="opacity" {keyed(on, T)}/></rect>')
    cap = "A scan lights up in order: router, service, the redaction pipeline, T1 through Mubit, then the repository saves the result."
    b.append(text(cap, 56, H - 48, fit(cap, 16, "pixel", W - 112), "pixel", QUIET))
    write("backend.svg", svg(W, H, "".join(b), "The backend in four layers",
                             "Entry (main.py, api.py, dependencies.py), feature modules (router, service, repository for auth, documents, scan, "
                             "corrections, ask, samples and files), domain packages (redaction, llm, ingest) and core. The browser reaches the entry "
                             "through Caddy, repositories use PostgreSQL, llm calls Mubit, and core applies the SQL migrations at startup."))


# ---------- buttons and footer ----------

ARROW = ["....k....", "....kk...", "kkkkkkk..", "kkkkkkkk.", "kkkkkkk..", "....kk...", "....k...."]
FILE = ["kkkkk..", "k...kk.", "k...kkk", "k.....k", "k.kkk.k", "k.....k", "k.kkk.k", "k.....k", "kkkkkkk"]
PLAY = ["kk.....", "kkkk...", "kkkkkk.", "kkkkkkk", "kkkkkk.", "kkkk...", "kk....."]


def button(name, label, fill, ink, icon, icon_right):
    reset_glyphs()
    px = 22
    tw = width(label, px, "display")
    iw = size(icon)[0] * 3
    w = int(tw + iw + 84)
    h = 64
    body = frame(0, 0, w, h, fill, INK, 4, shadow=True)
    if icon_right:
        body += text(label, 28, 41, px, "display", ink) + sprite(icon, 28 + tw + 16, (h - size(icon)[1] * 3) / 2, 3, {"k": ink})
    else:
        body += sprite(icon, 28, (h - size(icon)[1] * 3) / 2, 3, {"k": ink}) + text(label, 28 + iw + 16, 41, px, "display", ink)
    write(name, svg(w + 4, h + 4, body, label))


def footer():
    reset_glyphs()
    W, H = 1200, 210
    b = [f'<rect width="{W}" height="{H}" fill="{BONE}"/>', hills(ART["HILLS_NEAR"], 0, 6, W, INK, INK, 1, -100),
         f'<rect y="{20 * 6 - 2}" width="{W}" height="{H}" fill="{INK}"/>', f'<rect y="{H - 6}" width="{W}" height="6" fill="{SIGNAL}"/>']
    b.append(text("MuGuard", 40, 172, 30, "display", BONE))
    b.append(text("Pseudonymised, not anonymised: placeholders map back to real values only on your side.", 220, 160, 16, "pixel", HAZE))
    b.append(text("Demo documents are synthetic. Built at Night Shift, London, on Mubit.", 220, 182, 16, "pixel", HAZE))
    write("footer.svg", svg(W, H, "".join(b), "MuGuard", "Built at Night Shift, London, on Mubit."))


if __name__ == "__main__":
    import sys

    hero()
    journey()
    what_ai_sees()
    numbers(json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else json.loads((OUT / "numbers.json").read_text()))
    mubit()
    training()
    quests()
    backend()
    button("button-app.svg", "Protect a document", SIGNAL, "#ffffff", ARROW, True)
    button("button-sample.svg", "Try a sample", PAPER, INK, FILE, False)
    button("button-video.svg", "Watch the demo", INK, BONE, PLAY, False)
    footer()
