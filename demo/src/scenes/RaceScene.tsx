import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Sfx } from "../pixel";
import { KNIGHT_SMALL, Sprite } from "../sprites";
import { C, F, frame as pxFrame } from "../theme";
import { cueAt, type RaceScene as Race } from "../types";

const LEFT = 330; // where 0% sits
const WIDTH = 1240; // 0% to 100%
const BLOCKS = 20; // 5% each
const ROW = 150;
const TOP = 280;
const RUN = 3.4; // seconds every knight runs, so the faster one goes further

// Three knights race along block tracks toward Mubit's 85% gate; only the one that clears it gets the banner.
export const RaceScene = ({ scene, lead }: { scene: Race; lead: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = Math.round(0.6 * fps);
  const progress = interpolate(frame, [start, start + RUN * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const running = progress > 0 && progress < 1;
  const done = progress >= 1;
  const winner = scene.runners.reduce((a, b) => (b.value > a.value ? b : a));
  const crowned = Math.round(cueAt(scene, new RegExp(`^${winner.name}`), lead, scene.voSeconds / 2) * fps);
  // Frame the winner crosses the gate, for the flash and the coin.
  const crossAt = start + Math.round(fps * RUN * (1 - Math.cbrt(1 - scene.target / winner.value)));
  const gateFlash = frame >= crossAt && frame < crossAt + 10 && Math.floor((frame - crossAt) / 3) % 2 === 0;
  const head = spring({ frame, fps, config: { damping: 16, mass: 0.6 } });
  const gateX = LEFT + (scene.target / 100) * WIDTH;
  const rowsHeight = scene.runners.length * ROW;

  return (
    <AbsoluteFill>
      <Sfx name="sweep" at={start} volume={0.3} />
      <Sfx name="fill" at={start + 4} volume={0.3} />
      <Sfx name="coin" at={crossAt} volume={0.55} />
      <Sfx name="fanfare" at={crowned} volume={0.45} />

      <div style={{ position: "absolute", left: 150, top: 56, opacity: head }}>
        <div style={{ font: `700 62px/1.05 ${F.pixel}`, color: C.ink }}>{scene.title}</div>
        <div style={{ marginTop: 16, display: "inline-flex", alignItems: "center", gap: 12, background: C.ink, color: C.paper, padding: "8px 14px" }}>
          <span style={{ font: `400 15px ${F.label}`, letterSpacing: 2, color: C.haze }}>STUDENT</span>
          <span style={{ font: `500 24px ${F.pixel}` }}>{scene.student}</span>
        </div>
      </div>

      {/* Mubit's bar: a dashed pixel pole with a red flag across every track. */}
      <div style={{ position: "absolute", left: gateX - 4, top: TOP - 40, width: 8, height: rowsHeight + 40, backgroundImage: `linear-gradient(${gateFlash ? C.signal : C.ink} 60%, transparent 60%)`, backgroundSize: "8px 20px" }} />
      <svg width={48} height={30} viewBox="0 0 8 5" shapeRendering="crispEdges" style={{ position: "absolute", left: gateX + 4, top: TOP - 40 }}>
        <path d="M0 0h8v1h-1v1h-1v1h1v1h1v1h-8z" fill={C.signal} />
      </svg>
      <div style={{ position: "absolute", left: gateX - 120, top: TOP - 78, width: 240, textAlign: "center", font: `400 16px ${F.label}`, letterSpacing: 2, color: C.ink }}>
        MUBIT TARGET {scene.target}%
      </div>

      {scene.runners.map((r, i) => {
        const y = TOP + i * ROW;
        const value = r.value * progress;
        const x = LEFT + (value / 100) * WIDTH;
        const lit = Math.floor((value / 100) * BLOCKS);
        const isWinner = r.name === winner.name;
        const bob = running ? (Math.floor(frame / 4) % 2) * -6 : 0;
        const badge = done ? spring({ frame: frame - (start + RUN * fps) - i * 4, fps, config: { damping: 14 } }) : 0;
        const halo = isWinner && frame >= crowned;
        return (
          <div key={r.name}>
            {halo && (
              <div style={{ position: "absolute", left: 110, top: y - 14, width: WIDTH + LEFT - 110 + 270, height: ROW - 16, ...pxFrame(6, 0), borderColor: C.signal, opacity: frame - crowned < 12 && Math.floor((frame - crowned) / 3) % 2 ? 0 : 1 }} />
            )}
            <div style={{ position: "absolute", left: 130, top: y + 20, width: 180, textAlign: "right" }}>
              <div style={{ font: `700 40px/1 ${F.pixel}`, color: C.ink }}>{r.name}</div>
              <div style={{ marginTop: 8, font: `400 13px ${F.label}`, letterSpacing: 1, color: C.quiet }}>{r.cases.toUpperCase()}</div>
            </div>
            <div style={{ position: "absolute", left: LEFT, top: y + 74, display: "flex", gap: 4 }}>
              {Array.from({ length: BLOCKS }, (_, k) => (
                <div key={k} style={{ width: WIDTH / BLOCKS - 4, height: 34, background: k < lit ? r.tint : C.mist }} />
              ))}
            </div>
            <div style={{ position: "absolute", left: LEFT, top: y + 112, width: WIDTH, height: 6, background: C.ink }} />
            <div style={{ position: "absolute", left: x - 42, top: y - 4 + bob }}>
              <Sprite rows={KNIGHT_SMALL} scale={6} tint={{ r: r.tint }} />
            </div>
            <div style={{ position: "absolute", left: LEFT + WIDTH + 34, top: y + 34 }}>
              <div style={{ font: `700 56px/1 ${F.pixel}`, color: isWinner ? C.signal : C.ink, fontVariantNumeric: "tabular-nums" }}>{value.toFixed(1)}%</div>
              {done && (
                <div
                  style={{
                    marginTop: 10,
                    display: "inline-block",
                    font: `400 14px ${F.label}`,
                    letterSpacing: 2,
                    padding: "5px 9px",
                    background: isWinner ? C.signal : C.paper,
                    color: isWinner ? C.paper : C.quiet,
                    border: `3px solid ${isWinner ? C.signal : C.stone}`,
                    transform: `scale(${Math.min(1, badge)})`,
                    transformOrigin: "0 50%",
                  }}
                >
                  {r.value >= scene.target ? "TARGET MET" : "BELOW TARGET"}
                </div>
              )}
            </div>
          </div>
        );
      })}

      <div style={{ position: "absolute", left: 150, right: 150, top: TOP + rowsHeight + 18, font: `400 18px/1.4 ${F.serif}`, color: C.quiet }}>
        {scene.note} {scene.source}.
      </div>
    </AbsoluteFill>
  );
};
