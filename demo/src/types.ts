export type Word = { w: string; start: number; end: number };

export type Box = { x: number; y: number; width: number; height: number };

export type TakeEvent =
  | { t: number; type: "click"; x: number; y: number; box: Box }
  | { t: number; type: "zoom"; box: Box; scale: number; hold: number };

type Base = { id: string; label?: string; vo: string; voSeconds: number; words: Word[]; seconds: number };

export type TitleScene = Base & { kind: "title"; lines: string[] };
export type ClipScene = Base & { kind: "clip"; recStart: number; events: TakeEvent[] };
export type ChartScene = Base & {
  kind: "chart";
  rules: { title: string; note: string; stats: { label: string; value: number }[] };
  adapter: { title: string; note: string; bars: { label: string; value: number; highlight?: boolean }[] };
};
export type Scene = TitleScene | ClipScene | ChartScene;

export type Edit = {
  fps: number;
  lead: number;
  take: { src: string; width: number; height: number };
  scenes: Scene[];
};
