import { Audio } from "@remotion/media";
import { useEffect, useState } from "react";
import { AbsoluteFill, Sequence, Series, continueRender, delayRender, staticFile } from "remotion";
import { Dialog, PixelWipe, WIPE_CUT, WIPE_FRAMES } from "./pixel";
import { ChartScene } from "./scenes/ChartScene";
import { ClipScene } from "./scenes/ClipScene";
import { StatsScene } from "./scenes/StatsScene";
import { TitleScene } from "./scenes/TitleScene";
import { C, F, FONT_LOADS } from "./theme";
import type { Edit, Scene } from "./types";

export const Demo = ({ edit }: { edit: Edit | null }) => {
  const [fonts] = useState(() => delayRender("Loading fonts"));
  useEffect(() => {
    Promise.all(FONT_LOADS.map((f) => document.fonts.load(f))).finally(() => continueRender(fonts));
  }, [fonts]);
  if (!edit) return null;

  const frames = edit.scenes.map((s) => Math.round(s.seconds * edit.fps));
  const starts = frames.map((_, i) => frames.slice(0, i).reduce((a, b) => a + b, 0));
  // A pixel wipe opens the video and hides every cut that is not inside the one continuous take.
  const wipes = [0, ...edit.scenes.slice(1).flatMap((s, i) => (s.kind === "clip" && edit.scenes[i].kind === "clip" ? [] : [starts[i + 1]]))];

  return (
    <AbsoluteFill style={{ background: C.bone, fontFamily: F.pixel }}>
      <Grid />
      <Series>
        {edit.scenes.map((scene, i) => (
          <Series.Sequence key={scene.id} durationInFrames={frames[i]} name={scene.id}>
            <SceneView scene={scene} edit={edit} prev={edit.scenes[i - 1]} next={edit.scenes[i + 1]} />
            <Sequence from={Math.round(edit.lead * edit.fps)} name={`vo ${scene.id}`}>
              <Audio src={staticFile(scene.vo)} />
              <Dialog words={scene.words} />
            </Sequence>
          </Series.Sequence>
        ))}
      </Series>
      {wipes.map((at) => (
        <Sequence key={at} from={at - WIPE_CUT} durationInFrames={WIPE_FRAMES} name="pixel wipe">
          <PixelWipe />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

function SceneView({ scene, edit, prev, next }: { scene: Scene; edit: Edit; prev?: Scene; next?: Scene }) {
  if (scene.kind === "clip") return <ClipScene scene={scene} take={edit.take} enter={prev?.kind !== "clip"} exit={next?.kind !== "clip"} />;
  if (scene.kind === "stats") return <StatsScene scene={scene} lead={edit.lead} />;
  if (scene.kind === "chart") return <ChartScene scene={scene} lead={edit.lead} />;
  return <TitleScene scene={scene} />;
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
