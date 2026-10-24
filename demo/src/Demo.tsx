import { Audio } from "@remotion/media";
import { useEffect, useState } from "react";
import { AbsoluteFill, Sequence, Series, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ChartScene } from "./scenes/ChartScene";
import { ClipScene } from "./scenes/ClipScene";
import { TitleScene } from "./scenes/TitleScene";
import { C, F, FONT_LOADS } from "./theme";
import type { Edit, Scene, Word } from "./types";

export const Demo = ({ edit }: { edit: Edit | null }) => {
  const [fonts] = useState(() => delayRender("Loading fonts"));
  useEffect(() => {
    Promise.all(FONT_LOADS.map((f) => document.fonts.load(f))).finally(() => continueRender(fonts));
  }, [fonts]);
  if (!edit) return null;

  return (
    <AbsoluteFill style={{ background: C.bone, fontFamily: F.pixel }}>
      <Grid />
      <Series>
        {edit.scenes.map((scene, i) => (
          <Series.Sequence key={scene.id} durationInFrames={Math.round(scene.seconds * edit.fps)} name={scene.id}>
            <SceneView scene={scene} edit={edit} prev={edit.scenes[i - 1]} next={edit.scenes[i + 1]} />
            <Sequence from={Math.round(edit.lead * edit.fps)} name={`vo ${scene.id}`}>
              <Audio src={staticFile(scene.vo)} />
              <Captions words={scene.words} />
            </Sequence>
          </Series.Sequence>
        ))}
      </Series>
    </AbsoluteFill>
  );
};

function SceneView({ scene, edit, prev, next }: { scene: Scene; edit: Edit; prev?: Scene; next?: Scene }) {
  if (scene.kind === "clip") return <ClipScene scene={scene} take={edit.take} enter={prev?.kind !== "clip"} exit={next?.kind !== "clip"} />;
  if (scene.kind === "chart") return <ChartScene scene={scene} />;
  return <TitleScene scene={scene} outro={!next} />;
}

// A faint pixel grid behind everything.
const Grid = () => (
  <AbsoluteFill
    style={{
      backgroundImage: `linear-gradient(${C.mist} 2px, transparent 2px), linear-gradient(90deg, ${C.mist} 2px, transparent 2px)`,
      backgroundSize: "48px 48px",
      opacity: 0.55,
    }}
  />
);

// Spoken words in chunks of a few words, shown while they are said. Times come from the TTS, so they match the script.
// Each sentence is split into even chunks of at most 8 words, so no chunk is a lone word.
const MAX_WORDS = 8;
const join = (ws: Word[]) => ws.reduce((s, w) => (/^[.,!?;:'’]/.test(w.w) || !s ? s + w.w : `${s} ${w.w}`), "");
function chunks(words: Word[]) {
  // A word plus the punctuation tokens that follow it.
  const units: Word[][] = [];
  for (const w of words) {
    if (/^[.,!?;:'’]+$/.test(w.w) && units.length) units[units.length - 1].push(w);
    else units.push([w]);
  }
  const sentences: Word[][][] = [[]];
  for (const u of units) {
    sentences[sentences.length - 1].push(u);
    if (/[.!?]$/.test(u[u.length - 1].w)) sentences.push([]);
  }
  const out: { text: string; start: number; end: number }[] = [];
  for (const s of sentences.filter((s) => s.length)) {
    const size = Math.ceil(s.length / Math.ceil(s.length / MAX_WORDS));
    for (let i = 0; i < s.length; i += size) {
      const part = s.slice(i, i + size).flat();
      out.push({ text: join(part), start: part[0].start, end: part[part.length - 1].end });
    }
  }
  return out;
}

function Captions({ words }: { words: Word[] }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const current = chunks(words).find((c) => t >= c.start - 0.05 && t <= c.end + 0.25);
  if (!current) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 46 }}>
      <div
        style={{
          background: C.ink,
          color: C.paper,
          font: `500 36px/1.25 ${F.pixel}`,
          padding: "12px 24px",
          maxWidth: 1400,
          textAlign: "center",
        }}
      >
        {current.text}
      </div>
    </AbsoluteFill>
  );
}
