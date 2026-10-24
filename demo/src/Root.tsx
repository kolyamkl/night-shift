import { Composition, staticFile, type CalculateMetadataFunction } from "remotion";
import { Demo } from "./Demo";
import type { Edit } from "./types";

type Props = { edit: Edit | null };

// The edit plan is made by edit.mjs; reading it here means a new take or voice needs no code change.
const calculateMetadata: CalculateMetadataFunction<Props> = async ({ abortSignal }) => {
  const edit: Edit = await fetch(staticFile("media/edit.json"), { signal: abortSignal }).then((r) => r.json());
  const frames = edit.scenes.reduce((n, s) => n + Math.round(s.seconds * edit.fps), 0);
  return { durationInFrames: frames, fps: edit.fps, props: { edit }, defaultCodec: "h264", defaultPixelFormat: "yuv420p" };
};

export const Root = () => (
  <Composition
    id="Demo"
    component={Demo}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={30}
    defaultProps={{ edit: null } as Props}
    calculateMetadata={calculateMetadata}
  />
);
