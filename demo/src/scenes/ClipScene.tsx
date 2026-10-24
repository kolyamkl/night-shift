import { AbsoluteFill, Easing, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F, frame as pxFrame } from "../theme";
import type { ClipScene as Clip, TakeEvent } from "../types";

const SCALE = 0.9; // the take is 1600x900; shown at 1440x810 so zooms stay close to its real pixels
const BAR = 44;
const ease = Easing.inOut(Easing.cubic);

// How far each zoom is in at time t (0..1), and where it points. The strongest zoom wins.
function zoomAt(events: TakeEvent[], t: number) {
  let best = { weight: 0, scale: 1, cx: 0, cy: 0 };
  for (const e of events) {
    if (e.type !== "zoom") continue;
    const weight = interpolate(t, [e.t - 0.55, e.t, e.t + e.hold, e.t + e.hold + 0.6], [0, 1, 1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    });
    if (weight > best.weight) best = { weight, scale: e.scale, cx: e.box.x + e.box.width / 2, cy: e.box.y + e.box.height / 2 };
  }
  return best;
}

export const ClipScene = ({ scene, take, enter, exit }: { scene: Clip; take: { src: string; width: number; height: number }; enter: boolean; exit: boolean }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  const z = zoomAt(scene.events, t);
  const scale = 1 + (z.scale - 1) * z.weight;
  // Clamp the origin so the zoomed take never shows its own edges.
  const ox = Math.min(Math.max(z.cx, 0), take.width);
  const oy = Math.min(Math.max(z.cy, 0), take.height);

  const inP = enter ? spring({ frame, fps, config: { damping: 18, mass: 0.7 } }) : 1;
  const outP = exit ? interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], { extrapolateLeft: "clamp", easing: ease }) : 1;
  const w = take.width * SCALE;
  const h = take.height * SCALE;
  const label = interpolate(frame, [4, 14, 95, 110], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 70, opacity: Math.min(inP, outP) }}>
      <div style={{ width: w, transform: `translateY(${(1 - inP) * 60}px)`, position: "relative", ...pxFrame(6, 12), background: C.paper }}>
        <div style={{ height: BAR, background: C.ink, display: "flex", alignItems: "center", gap: 10, padding: "0 16px" }}>
          {[C.signal, C.stone, C.stone].map((c, i) => (
            <span key={i} style={{ width: 14, height: 14, background: c }} />
          ))}
          <span style={{ marginLeft: 18, color: C.haze, font: `400 15px ${F.label}`, letterSpacing: 1 }}>veil · {scene.id === "landing" ? "home" : "app"}</span>
        </div>
        <div style={{ width: w, height: h, overflow: "hidden", position: "relative" }}>
          <div style={{ width: take.width, height: take.height, transform: `scale(${SCALE})`, transformOrigin: "0 0" }}>
            <div style={{ width: take.width, height: take.height, transform: `scale(${scale})`, transformOrigin: `${ox}px ${oy}px` }}>
              <OffthreadVideo src={staticFile(take.src)} trimBefore={Math.round(scene.recStart * fps)} muted />
            </div>
          </div>
        </div>
        {scene.label && (
          <div
            style={{
              position: "absolute",
              left: -6,
              top: -54,
              background: C.signal,
              color: C.paper,
              font: `700 28px ${F.pixel}`,
              padding: "6px 16px",
              ...pxFrame(4, 6),
              opacity: label,
              transform: `translateY(${(1 - label) * 12}px)`,
            }}
          >
            {scene.label}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
