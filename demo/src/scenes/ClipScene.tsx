import { AbsoluteFill, Easing, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Hud, Reticle, Sfx } from "../pixel";
import { C, F, frame as pxFrame } from "../theme";
import type { ClipScene as Clip, TakeEvent } from "../types";

const SCALE = 0.86; // the take is 1600x900; shown at 1376x774, leaving room for the dialog box below
const BAR = 44;
const ease = Easing.inOut(Easing.cubic);

// How far each zoom is in at time t (0..1), where it points, and how long it has held.
function zoomAt(events: TakeEvent[], t: number) {
  let best = { weight: 0, scale: 1, cx: 0, cy: 0, since: 0, box: null as null | { x: number; y: number; width: number; height: number } };
  for (const e of events) {
    if (e.type !== "zoom") continue;
    const weight = interpolate(t, [e.t - 0.55, e.t, e.t + e.hold, e.t + e.hold + 0.6], [0, 1, 1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    });
    if (weight > best.weight) best = { weight, scale: e.scale, cx: e.box.x + e.box.width / 2, cy: e.box.y + e.box.height / 2, since: t - e.t, box: e.box };
  }
  return best;
}

export const ClipScene = ({ scene, take, enter, exit }: { scene: Clip; take: { src: string; width: number; height: number }; enter: boolean; exit: boolean }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;

  const z = zoomAt(scene.events, t);
  const scale = 1 + (z.scale - 1) * z.weight;
  // Centre the box, but never pull the take's own edges into view, so a box near an edge stays whole.
  const pan = (c: number, size: number) => Math.min(0, Math.max(size - size * scale, size / 2 - c * scale));
  const tx = pan(z.cx, take.width);
  const ty = pan(z.cy, take.height);
  // The reticle frames the zoomed box in screen space and blinks twice as it locks on.
  const map = (x: number, y: number) => ({ x: (x * scale + tx) * SCALE, y: (y * scale + ty) * SCALE });
  const lockBlink = z.since >= 0 && z.since < 0.4 ? Math.floor(z.since * 10) % 2 : 1;
  const reticle = z.box && z.weight > 0.85 ? (() => {
    const pad = 14;
    const a = map(z.box.x, z.box.y);
    const b = map(z.box.x + z.box.width, z.box.y + z.box.height);
    const w = take.width * SCALE, h = take.height * SCALE;
    const x = Math.max(8, a.x - pad), y = Math.max(8, a.y - pad);
    return { x, y, width: Math.min(w - 8, b.x + pad) - x, height: Math.min(h - 8, b.y + pad) - y, opacity: lockBlink };
  })() : null;

  const inP = enter ? spring({ frame, fps, config: { damping: 18, mass: 0.7 } }) : 1;
  const outP = exit ? interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], { extrapolateLeft: "clamp", easing: ease }) : 1;
  const w = take.width * SCALE;
  const h = take.height * SCALE;
  // The step label drops in like a game banner, in 4px steps.
  const label = interpolate(frame, [4, 12, 100, 112], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 76, opacity: Math.min(inP, outP) }}>
      {scene.events.map((e, i) =>
        e.type === "click" ? <Sfx key={i} name={e.sfx ?? "blip"} at={(e.t + (e.sfx === "fanfare" ? 1.3 : 0)) * fps} volume={e.sfx === "blip" ? 0.4 : 0.55} /> : null,
      )}
      {scene.events.map((e, i) => (e.type === "zoom" ? <Sfx key={`z${i}`} name="blip" at={(e.t - 0.1) * fps} volume={0.2} /> : null))}
      {scene.quest && <Hud quest={scene.quest} />}
      <div style={{ width: w, transform: `translateY(${Math.round((1 - inP) * 15) * 4}px)`, position: "relative", ...pxFrame(6, 12), background: C.paper }}>
        <div style={{ height: BAR, background: C.ink, display: "flex", alignItems: "center", gap: 10, padding: "0 16px" }}>
          {[C.signal, C.stone, C.stone].map((c, i) => (
            <span key={i} style={{ width: 14, height: 14, background: c }} />
          ))}
          <span style={{ marginLeft: 18, color: C.haze, font: `400 15px ${F.label}`, letterSpacing: 1 }}>muguard · {scene.id === "landing" ? "home" : "app"}</span>
        </div>
        <div style={{ width: w, height: h, overflow: "hidden", position: "relative" }}>
          <div style={{ width: take.width, height: take.height, transform: `scale(${SCALE})`, transformOrigin: "0 0" }}>
            <div style={{ width: take.width, height: take.height, transform: `translate(${tx}px, ${ty}px) scale(${scale})`, transformOrigin: "0 0" }}>
              <OffthreadVideo src={staticFile(take.src)} trimBefore={Math.round(scene.recStart * fps)} muted />
            </div>
          </div>
          {reticle && <Reticle {...reticle} />}
        </div>
        {scene.label && (
          <div
            style={{
              position: "absolute",
              left: -6,
              top: -60,
              background: C.signal,
              color: C.paper,
              font: `700 28px ${F.pixel}`,
              padding: "6px 16px",
              ...pxFrame(4, 6),
              opacity: label > 0 ? 1 : 0,
              transform: `translateY(${-Math.round((1 - label) * 6) * 4}px)`,
            }}
          >
            {scene.label}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
