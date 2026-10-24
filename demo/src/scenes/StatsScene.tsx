import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { hash, Sfx } from "../pixel";
import { DOC, HACKER, Sprite } from "../sprites";
import { C, F, frame as pxFrame } from "../theme";
import { cueAt, type StatsScene as Stats } from "../types";

const BLOCK = 32;
const GAP = 5;

// The opening: the research, as pixels. 71 of 100 blocks fill red, then two of three pages turn red,
// then the pages fly off to the model provider.
export const StatsScene = ({ scene, lead }: { scene: Stats; lead: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [first, second] = scene.stats;
  const fillStart = Math.round(0.35 * fps);
  const fillFrames = Math.round(1.6 * fps);
  const secondAt = Math.round(cueAt(scene, new RegExp(`^${second?.cue ?? "Two"}$`, "i"), lead, scene.voSeconds / 3) * fps);
  const leaveAt = Math.round(cueAt(scene, new RegExp(`^${scene.leaveCue ?? "rides"}$`, "i"), lead, scene.voSeconds * 0.8) * fps);
  const pop = (from: number) => spring({ frame: frame - from, fps, config: { damping: 15, mass: 0.6 } });

  const filled = Math.floor(interpolate(frame, [fillStart, fillStart + fillFrames], [0, first.value ?? 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const leave = interpolate(frame, [leaveAt, leaveAt + 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const panel = (p: number) => ({
    width: 720,
    height: 700,
    background: C.paper,
    padding: "36px 44px",
    ...pxFrame(6, 12),
    opacity: p,
    transform: `translateY(${Math.round((1 - p) * 10) * 4}px)`,
    display: "flex",
    flexDirection: "column" as const,
  });

  const [red, of] = second?.of ?? [2, 3];
  return (
    <AbsoluteFill style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 50, paddingBottom: 150 }}>
      <div style={{ display: "flex", gap: 50, transform: `translateX(${-Math.round(Math.min(1, leave * 2) * 8) * 20}px)` }}>
      <Sfx name="fill" at={fillStart} />
      <Sfx name="powerup" at={fillStart + fillFrames} />
      <Sfx name="powerup" at={secondAt + 6} />
      <Sfx name="sweep" at={leaveAt} volume={0.4} />

      <div style={panel(pop(0))}>
        <div style={{ font: `400 18px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>UK WORKERS</div>
        <div style={{ display: "flex", gap: 36, alignItems: "flex-end", marginTop: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(10, ${BLOCK}px)`, gap: GAP }}>
            {Array.from({ length: 100 }, (_, i) => (
              <div key={i} style={{ width: BLOCK, height: BLOCK, background: i < filled ? C.signal : C.mist, outline: i === filled - 1 ? `3px solid ${C.ink}` : undefined }} />
            ))}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 20, marginTop: 26 }}>
          <span style={{ font: `700 104px/1 ${F.pixel}`, color: C.signal, fontVariantNumeric: "tabular-nums" }}>{filled}%</span>
          <span style={{ font: `500 26px/1.2 ${F.pixel}`, color: C.ink, maxWidth: 400 }}>{first.label}</span>
        </div>
        <div style={{ marginTop: "auto", font: `400 19px/1.35 ${F.serif}`, color: C.quiet }}>{first.source}</div>
      </div>

      <div style={panel(pop(secondAt))}>
        <div style={{ font: `400 18px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>CHATGPT WRITING REQUESTS</div>
        <div style={{ position: "relative", height: 330, marginTop: 30, display: "flex", gap: 46, justifyContent: "center", alignItems: "center" }}>
          {Array.from({ length: of }, (_, i) => {
            const turned = i < red && frame >= secondAt + 10 + i * 6;
            // Red pages lift and fly right, off the panel, one after another.
            const go = turned ? interpolate(leave * 1.4 - i * 0.2, [0, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
            const step = Math.round(go * 24) / 24; // move in pixel steps
            return (
              <div key={i} style={{ transform: `translate(${step * (760 - i * 200)}px, ${step * -40 - Math.sin(step * Math.PI) * 140}px) scale(${1 - step * 0.75})`, opacity: step > 0.95 ? 0 : 1, position: "relative" }}>
                <Sprite rows={DOC} scale={13} tint={turned ? { w: "#ffd9d6" } : undefined} />
                {turned && <div style={{ position: "absolute", left: 18, top: 70, width: 100, height: 14, background: C.signal }} />}
                {go > 0 && go < 1 && [0, 1, 2].map((k) => (
                  <div key={k} style={{ position: "absolute", left: -30 - k * 34, top: 80 + hash(i, k) * 70, width: 18 - k * 4, height: 18 - k * 4, background: k % 2 ? C.ink : C.signal }} />
                ))}
              </div>
            );
          })}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 20, marginTop: 18 }}>
          <span style={{ font: `700 104px/1 ${F.pixel}`, color: C.signal, whiteSpace: "nowrap" }}>{red} in {of}</span>
          <span style={{ font: `500 26px/1.2 ${F.pixel}`, color: C.ink, maxWidth: 300 }}>{second?.label}</span>
        </div>
        <div style={{ marginTop: "auto", font: `400 19px/1.35 ${F.serif}`, color: C.quiet }}>{second?.source}</div>
      </div>

      </div>
      {leave > 0 && (
        <div style={{ position: "absolute", right: 60, top: 260, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: Math.min(1, leave * 3) }}>
          <Sprite rows={HACKER} scale={14} />
          <div style={{ background: C.ink, color: C.paper, font: `400 16px ${F.label}`, letterSpacing: 2, padding: "6px 10px" }}>MODEL PROVIDER</div>
        </div>
      )}
    </AbsoluteFill>
  );
};
