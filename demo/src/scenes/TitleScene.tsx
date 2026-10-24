import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { hash, Sfx } from "../pixel";
import { HERO, pixelsOf } from "../sprites";
import { C, F } from "../theme";
import type { TitleScene as Title } from "../types";

const CPS = 26; // typed characters per second
const PX = 12; // one sprite pixel on screen
const KNIGHT = pixelsOf(HERO);
const ROWS = HERO.length;

// The closing card: the knight drops in pixel by pixel from the bottom row up, then the name and the line type out.
export const TitleScene = ({ scene }: { scene: Title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const built = 4 + ROWS * 0.9 + 12; // frame when the last pixel lands

  let start = 1.5;
  const typed = scene.lines.map((line) => {
    const shown = Math.max(0, Math.min(line.length, Math.floor((t - start) * CPS)));
    start += line.length / CPS + 0.4;
    return { line, shown };
  });
  const caretOn = Math.floor(t * 2.4) % 2 === 0;
  const name = interpolate(frame, [built - 6, built + 2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 90, paddingBottom: 150 }}>
      <Sfx name="fanfare" at={built} volume={0.55} />
      <svg width={25 * PX} height={ROWS * PX} viewBox={`0 0 25 ${ROWS}`} shapeRendering="crispEdges" style={{ overflow: "visible" }}>
        {KNIGHT.map(({ x, y, c }) => {
          const land = 4 + (ROWS - 1 - y) * 0.9 + hash(x, y) * 10;
          const fall = interpolate(frame, [land - 12, land], [-40, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          if (frame < land - 12) return null;
          return <rect key={`${x}-${y}`} x={x} y={y + Math.round(fall)} width={1} height={1} fill={c} />;
        })}
      </svg>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ font: `700 200px/1 ${F.pixel}`, color: C.ink, letterSpacing: -4, opacity: name, transform: `translateY(${Math.round((1 - name) * 5) * 4}px)` }}>
          MuGuard<span style={{ color: C.signal }}>.</span>
        </div>
        {typed.map(({ line, shown }, i) => (
          <div key={i} style={{ marginTop: 26, font: `700 52px/1.15 ${F.pixel}`, color: C.ink, height: 62, whiteSpace: "pre" }}>
            {line.slice(0, shown)}
            <span style={{ display: "inline-block", width: 22, height: 46, marginLeft: 8, background: C.signal, opacity: caretOn ? 1 : 0, verticalAlign: "-6px" }} />
          </div>
        ))}
        <div style={{ marginTop: 36, font: `400 20px ${F.label}`, color: C.quiet, letterSpacing: 2, opacity: name }}>
          BUILT ON MUBIT · NIGHT SHIFT, LONDON 2026
        </div>
      </div>
    </AbsoluteFill>
  );
};
