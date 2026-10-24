import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Sfx } from "../pixel";
import { C, F, frame as pxFrame } from "../theme";
import { cueAt, type ChartScene as Chart } from "../types";

const BLOCKS = 20; // each block is 5%

// Results as block meters that fill one block at a time: rules alone, then the adapter against its base model.
export const ChartScene = ({ scene, lead }: { scene: Chart; lead: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const second = Math.round(cueAt(scene, /adapter/i, lead, scene.voSeconds / 2) * fps);
  const pop = (from: number) => spring({ frame: frame - from, fps, config: { damping: 15, mass: 0.6 } });
  const count = (value: number, from: number) => Math.round(value * interpolate(frame - from, [0, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));

  const panel = (p: number) => ({
    width: 780,
    height: 640,
    background: C.paper,
    padding: "36px 44px",
    ...pxFrame(6, 12),
    opacity: p,
    transform: `translateY(${Math.round((1 - p) * 10) * 4}px)`,
    display: "flex",
    flexDirection: "column" as const,
  });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: 60, flexDirection: "row", paddingBottom: 150 }}>
      <Sfx name="powerup" at={14} />
      <Sfx name="fill" at={second + 6} />
      <Sfx name="powerup" at={second + 40} />

      <div style={panel(pop(4))}>
        <div style={{ font: `400 18px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>{scene.rules.title.toUpperCase()}</div>
        <div style={{ marginTop: 26, display: "flex", flexDirection: "column", gap: 22 }}>
          {scene.rules.stats.map((s, i) => (
            <div key={s.label} style={{ display: "flex", alignItems: "baseline", gap: 22 }}>
              <span style={{ font: `700 100px/1 ${F.pixel}`, color: s.value === 0 ? C.signal : C.ink, width: 240, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {count(s.value, 14 + i * 10)}%
              </span>
              <span style={{ font: `500 30px/1.2 ${F.pixel}`, color: C.ink }}>{s.label}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", font: `400 19px/1.35 ${F.serif}`, color: C.quiet }}>{scene.rules.note}</div>
      </div>

      <div style={panel(pop(second))}>
        <div style={{ font: `400 18px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>{scene.adapter.title.toUpperCase()}</div>
        <div style={{ marginTop: 40, display: "flex", flexDirection: "column", gap: 44 }}>
          {scene.adapter.bars.map((b, i) => {
            const lit = Math.floor(interpolate(frame - second - 6 - i * 10, [0, 30], [0, (b.value / 100) * BLOCKS], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
            return (
              <div key={b.label}>
                <div style={{ display: "flex", justifyContent: "space-between", font: `500 30px ${F.pixel}`, color: C.ink }}>
                  <span>{b.label}</span>
                  <span style={{ fontVariantNumeric: "tabular-nums", color: b.highlight ? C.signal : C.ink }}>{lit >= Math.floor((b.value / 100) * BLOCKS) ? b.value.toFixed(1) : ((lit / BLOCKS) * 100).toFixed(1)}%</span>
                </div>
                <div style={{ marginTop: 14, display: "flex", gap: 5 }}>
                  {Array.from({ length: BLOCKS }, (_, k) => (
                    <div key={k} style={{ width: 29, height: 56, background: k < lit ? (b.highlight ? C.signal : C.stone) : C.mist }} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: "auto", font: `400 19px/1.35 ${F.serif}`, color: C.quiet }}>{scene.adapter.note}</div>
      </div>
    </AbsoluteFill>
  );
};
