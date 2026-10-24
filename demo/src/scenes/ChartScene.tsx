import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F, frame as pxFrame } from "../theme";
import type { ChartScene as Chart } from "../types";

// Two panels timed to the narration: rules alone first, then the trained adapter against its base model.
export const ChartScene = ({ scene }: { scene: Chart }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const fade = interpolate(frame, [0, 8, durationInFrames - 10, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // The second panel comes in when the narration reaches "adapter".
  const adapterWord = scene.words.find((w) => /adapter/i.test(w.w));
  const second = Math.round(((adapterWord?.start ?? scene.voSeconds / 2) + 0.25) * fps);
  const pop = (from: number) => spring({ frame: frame - from, fps, config: { damping: 16, mass: 0.6 } });
  const count = (value: number, from: number) => Math.round(value * interpolate(frame - from, [0, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));

  const panel = (p: number) => ({
    width: 760,
    height: 620,
    background: C.paper,
    padding: "40px 48px",
    ...pxFrame(6, 12),
    opacity: p,
    transform: `translateY(${(1 - p) * 40}px)`,
    display: "flex",
    flexDirection: "column" as const,
  });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 64, flexDirection: "row", opacity: fade, paddingBottom: 100 }}>
      <div style={panel(pop(8))}>
        <div style={{ font: `400 20px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>{scene.rules.title.toUpperCase()}</div>
        <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 26 }}>
          {scene.rules.stats.map((s, i) => (
            <div key={s.label} style={{ display: "flex", alignItems: "baseline", gap: 22 }}>
              <span style={{ font: `700 104px/1 ${F.pixel}`, color: s.value === 0 ? C.signal : C.ink, width: 250, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {count(s.value, 14 + i * 10)}%
              </span>
              <span style={{ font: `500 30px/1.2 ${F.pixel}`, color: C.ink }}>{s.label}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", font: `400 20px/1.4 ${F.serif}`, color: C.quiet }}>{scene.rules.note}</div>
      </div>

      <div style={panel(pop(second))}>
        <div style={{ font: `400 20px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>{scene.adapter.title.toUpperCase()}</div>
        <div style={{ marginTop: 40, display: "flex", flexDirection: "column", gap: 40 }}>
          {scene.adapter.bars.map((b, i) => {
            const grow = interpolate(frame - second - 6 - i * 8, [0, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={b.label}>
                <div style={{ display: "flex", justifyContent: "space-between", font: `500 30px ${F.pixel}`, color: C.ink }}>
                  <span>{b.label}</span>
                  <span style={{ fontVariantNumeric: "tabular-nums", color: b.highlight ? C.signal : C.ink }}>{(b.value * grow).toFixed(1)}%</span>
                </div>
                <div style={{ marginTop: 12, height: 64, background: C.mist, position: "relative" }}>
                  <div style={{ position: "absolute", inset: 0, width: `${b.value * grow}%`, background: b.highlight ? C.signal : C.stone }} />
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: "auto", font: `400 20px/1.4 ${F.serif}`, color: C.quiet }}>{scene.adapter.note}</div>
      </div>
    </AbsoluteFill>
  );
};
