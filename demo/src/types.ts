export type Word = { w: string; start: number; end: number };

export type Box = { x: number; y: number; width: number; height: number };

export type TakeEvent =
  | { t: number; type: "click"; x: number; y: number; box: Box; sfx?: string }
  | { t: number; type: "zoom"; box: Box; scale: number; hold: number };

// `vo` is null on a silent card (the opening sting).
type Base = { id: string; label?: string; quest?: number; vo: string | null; voSeconds: number; words: Word[]; seconds: number };

export type Stat = { value?: number; of?: [number, number]; cue?: string; label: string; source: string };

export type StatsScene = Base & { kind: "stats"; stats: Stat[]; leaveCue?: string };
export type TitleScene = Base & { kind: "title"; lines: string[] };
export type ClipScene = Base & { kind: "clip"; recStart: number; events: TakeEvent[] };
export type ChartScene = Base & {
  kind: "chart";
  rules: { title: string; note: string; stats: { label: string; value: number }[] };
  adapter: { title: string; note: string; bars: { label: string; value: number; highlight?: boolean }[] };
};
export type Person = {
  name: string;
  road: string;
  tint: string;
  data: { value: number; unit: string; note: string };
  answer: string;
  sample: string;
  teacher: string;
};
export type TeamScene = Base & { kind: "team"; title: string; kicker: string; people: Person[]; source: string };
export type RaceScene = Base & {
  kind: "race";
  title: string;
  student: string;
  target: number;
  runners: { name: string; tint: string; value: number; cases: string }[];
  note: string;
  source: string;
};
export type StingScene = Base & { kind: "sting"; tagline: string };
export type Scene = StatsScene | TitleScene | ClipScene | ChartScene | TeamScene | RaceScene | StingScene;

export type Edit = {
  fps: number;
  lead: number;
  take: { src: string; width: number; height: number };
  scenes: Scene[];
};

/** When a word is spoken in a scene, in seconds from the scene start (the voice starts `lead` in). */
export const cueAt = (scene: Base, pattern: RegExp, lead: number, fallback: number) =>
  lead + (scene.words.find((w) => pattern.test(w.w))?.start ?? fallback);
