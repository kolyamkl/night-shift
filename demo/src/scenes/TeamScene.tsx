import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Sfx } from "../pixel";
import { KNIGHT_SMALL, Sprite } from "../sprites";
import { C, F, frame as pxFrame } from "../theme";
import { cueAt, type Person, type TeamScene as Team } from "../types";

const METER = 10; // data volume on a log scale: 10 blocks = 100,000

// A party-select screen: each developer's card unlocks when the narration names them,
// with their data, answer format and teacher, like a character's stats.
export const TeamScene = ({ scene, lead }: { scene: Team; lead: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveals = scene.people.map((p, i) => Math.round(cueAt(scene, new RegExp(`^${p.name}$`), lead, 3 + i * 4) * fps));
  const title = spring({ frame, fps, config: { damping: 16, mass: 0.6 } });

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 54 }}>
      {reveals.map((at, i) => (
        <span key={i}>
          <Sfx name="powerup" at={at} volume={0.4} />
          <Sfx name="fill" at={at + 10} volume={0.35} />
        </span>
      ))}
      <div style={{ font: `400 18px ${F.label}`, color: C.quiet, letterSpacing: 3, opacity: title }}>{scene.kicker}</div>
      <div style={{ marginTop: 10, font: `700 62px/1.05 ${F.pixel}`, color: C.ink, transform: `translateY(${Math.round((1 - title) * 4) * 4}px)`, opacity: title }}>
        {scene.title}
      </div>
      <div style={{ marginTop: 40, display: "flex", gap: 40 }}>
        {scene.people.map((p, i) => (
          <Card key={p.name} person={p} at={reveals[i]} />
        ))}
      </div>
      <div style={{ marginTop: 26, font: `400 18px ${F.serif}`, color: C.quiet }}>{scene.source}</div>
    </AbsoluteFill>
  );
};

function Card({ person, at }: { person: Person; at: number }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const open = frame >= at;
  const pop = spring({ frame: frame - at, fps, config: { damping: 13, mass: 0.5 } });
  const lit = Math.round(Math.min(METER, Math.max(1, Math.log10(person.data.value) * 2)));
  const shown = Math.floor(interpolate(frame - at - 10, [0, 18], [0, lit], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const count = Math.round(person.data.value * interpolate(frame - at, [0, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const label = { font: `400 15px ${F.label}`, color: C.quiet, letterSpacing: 2, marginTop: 22 };

  return (
    <div
      style={{
        width: 520,
        height: 590,
        background: open ? C.paper : C.mist,
        padding: "30px 34px",
        ...pxFrame(6, 12),
        display: "flex",
        flexDirection: "column",
        transform: open ? `translateY(${-Math.round(Math.sin(Math.min(1, pop) * Math.PI) * 4) * 4}px) scale(${0.96 + 0.04 * Math.min(1, pop)})` : undefined,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ width: 104, height: 104, background: open ? C.mist : C.haze, border: `6px solid ${C.ink}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Sprite rows={KNIGHT_SMALL} scale={6} tint={open ? { r: person.tint } : { r: C.stone, g: C.stone, w: C.stone }} />
        </div>
        <div>
          <div style={{ font: `700 46px/1 ${F.pixel}`, color: C.ink }}>{open ? person.name : "? ? ?"}</div>
          <div style={{ marginTop: 10, display: "inline-block", background: open ? person.tint : C.stone, color: C.paper, font: `400 15px ${F.label}`, letterSpacing: 2, padding: "5px 10px" }}>
            {open ? person.road : "LOCKED"}
          </div>
        </div>
      </div>
      {open && (
        <div style={{ opacity: Math.min(1, pop * 1.5) }}>
          <div style={label}>DATA</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginTop: 6 }}>
            <span style={{ font: `700 52px/1 ${F.pixel}`, color: person.tint === C.stone ? C.ink : person.tint, fontVariantNumeric: "tabular-nums" }}>{count.toLocaleString("en-GB")}</span>
            <span style={{ font: `500 24px/1.1 ${F.pixel}`, color: C.ink }}>{person.data.unit}</span>
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 5 }}>
            {Array.from({ length: METER }, (_, k) => (
              <div key={k} style={{ width: 38, height: 22, background: k < shown ? person.tint : C.mist }} />
            ))}
          </div>
          <div style={{ marginTop: 6, font: `400 17px ${F.serif}`, color: C.quiet }}>{person.data.note} · volume, log scale</div>
          <div style={label}>ANSWER</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 6, flexWrap: "wrap" }}>
            <span style={{ font: `500 26px ${F.pixel}`, color: C.ink }}>{person.answer}</span>
            <span style={{ background: C.ink, color: C.signalSoft, font: `400 15px ${F.label}`, padding: "6px 9px" }}>{person.sample}</span>
          </div>
          <div style={label}>TEACHER</div>
          <div style={{ marginTop: 6, font: `500 26px ${F.pixel}`, color: C.ink }}>{person.teacher}</div>
        </div>
      )}
    </div>
  );
}
