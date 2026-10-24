import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F } from "../theme";
import type { TitleScene as Title } from "../types";

const CPS = 26; // typed characters per second

// Lines typed out one after another in the pixel font, with a red block caret, like the app's headings.
export const TitleScene = ({ scene, outro }: { scene: Title; outro: boolean }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const fade = interpolate(frame, [0, 8, durationInFrames - 10, durationInFrames], [0, 1, 1, outro ? 1 : 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let start = 0.3;
  const typed = scene.lines.map((line) => {
    const shown = Math.max(0, Math.min(line.length, Math.floor((t - start) * CPS)));
    start += line.length / CPS + 0.5;
    return { line, shown };
  });
  const active = typed.findIndex((l) => l.shown < l.line.length);
  const caretOn = Math.floor(t * 2.4) % 2 === 0;

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: fade, paddingBottom: 90 }}>
      {outro && (
        <div style={{ font: `700 220px/1 ${F.pixel}`, color: C.ink, marginBottom: 36, letterSpacing: -4 }}>
          Veil<span style={{ color: C.signal }}>.</span>
        </div>
      )}
      {typed.map(({ line, shown }, i) => (
        <div key={i} style={{ font: `700 ${outro ? 64 : 84}px/1.15 ${F.pixel}`, color: i === typed.length - 1 && !outro ? C.signal : C.ink, height: outro ? 76 : 100, whiteSpace: "pre" }}>
          {line.slice(0, shown)}
          {(active === i || (active === -1 && i === typed.length - 1)) && (
            <span style={{ display: "inline-block", width: outro ? 26 : 34, height: outro ? 56 : 72, marginLeft: 8, background: C.signal, opacity: caretOn ? 1 : 0, verticalAlign: "-6px" }} />
          )}
        </div>
      ))}
      {outro && (
        <div style={{ marginTop: 40, font: `400 22px ${F.label}`, color: C.quiet, letterSpacing: 2 }}>
          BUILT ON MUBIT · NIGHT SHIFT, LONDON 2026
        </div>
      )}
    </AbsoluteFill>
  );
};
