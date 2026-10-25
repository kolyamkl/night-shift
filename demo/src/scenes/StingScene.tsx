import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { hash, Sfx } from "../pixel";
import { HERO, pixelsOf } from "../sprites";
import { C, F } from "../theme";
import type { StingScene as Sting } from "../types";

const PX = 9;
const KNIGHT = pixelsOf(HERO);
const ROWS = HERO.length;

// A two-second opening card: the knight snaps together and the name slams in, before the research starts.
export const StingScene = ({ scene }: { scene: Sting }) => {
  const frame = useCurrentFrame();
  const slam = 20;
  const name = interpolate(frame, [slam, slam + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scale = name < 1 ? 1.6 - Math.round(name * 3) * 0.2 : 1; // drop in three pixel steps
  const tag = frame >= slam + 10;

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 70 }}>
      <Sfx name="powerup" at={4} volume={0.4} />
      <Sfx name="coin" at={slam} volume={0.5} />
      <svg width={25 * PX} height={ROWS * PX} viewBox={`0 0 25 ${ROWS}`} shapeRendering="crispEdges" style={{ overflow: "visible" }}>
        {KNIGHT.map(({ x, y, c }) => {
          const land = 2 + (ROWS - 1 - y) * 0.35 + hash(x, y) * 4;
          if (frame < land - 8) return null;
          const fall = interpolate(frame, [land - 8, land], [-30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <rect key={`${x}-${y}`} x={x} y={y + Math.round(fall)} width={1} height={1} fill={c} />;
        })}
      </svg>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ font: `700 190px/1 ${F.pixel}`, color: C.ink, letterSpacing: -4, opacity: name > 0 ? 1 : 0, transform: `scale(${scale})`, transformOrigin: "0 60%" }}>
          MuGuard<span style={{ color: C.signal }}>.</span>
        </div>
        <div style={{ marginTop: 24, font: `400 22px ${F.label}`, color: C.quiet, letterSpacing: 3, opacity: tag ? 1 : 0 }}>{scene.tagline}</div>
      </div>
    </AbsoluteFill>
  );
};
