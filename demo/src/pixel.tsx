// The pixel-art layer of the edit: block wipes between chapters, the knight's dialog box for captions,
// the quest HUD, the zoom reticle and the 8-bit sound cues.
import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { KNIGHT_SMALL, Sprite } from "./sprites";
import { C, F, frame as pxFrame } from "./theme";
import type { Word } from "./types";

// Deterministic noise per cell, so every render is identical.
export const hash = (a: number, b: number) => {
  const s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
  return s - Math.floor(s);
};

export const Sfx = ({ name, at = 0, volume = 0.5 }: { name: string; at?: number; volume?: number }) => (
  <Sequence from={Math.max(0, Math.round(at))} name={`sfx ${name}`} layout="none">
    <Audio src={staticFile(`media/sfx/${name}.wav`)} volume={volume} />
  </Sequence>
);

// A screen of blocks sweeps in from the left, holds over the cut, then sweeps away in the same order.
export const WIPE_CUT = 14;
export const WIPE_FRAMES = 30;
const CELL = 60;

export const PixelWipe = () => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const cols = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  const cells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const delay = Math.floor((c / cols) * 10 + hash(r, c) * 3);
      const inFor = f - delay;
      const outIn = WIPE_CUT + delay - f;
      if (inFor < 0 || outIn <= 0) continue;
      const size = Math.min(inFor, outIn) < 2 ? CELL / 2 : CELL; // grow and shrink in one pixel step
      const n = hash(c, r);
      const color = n < 0.08 ? C.signal : n < 0.16 ? C.stone : C.ink;
      cells.push(<div key={`${r}-${c}`} style={{ position: "absolute", left: c * CELL + (CELL - size) / 2, top: r * CELL + (CELL - size) / 2, width: size, height: size, background: color }} />);
    }
  }
  return (
    <AbsoluteFill>
      {cells}
      <Sfx name="sweep" volume={0.45} />
    </AbsoluteFill>
  );
};

// Captions as an RPG dialog box: the knight speaks, the words type in as they are said.
const MAX_WORDS = 8;
const join = (ws: Word[]) => ws.reduce((s, w) => (/^[.,!?;:'’]/.test(w.w) || !s ? s + w.w : `${s} ${w.w}`), "");

export function chunks(words: Word[]) {
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
  const out: { units: Word[][]; start: number; end: number }[] = [];
  for (const s of sentences.filter((s) => s.length)) {
    const size = Math.ceil(s.length / Math.ceil(s.length / MAX_WORDS));
    for (let i = 0; i < s.length; i += size) {
      const part = s.slice(i, i + size);
      out.push({ units: part, start: part[0][0].start, end: part[part.length - 1].at(-1)!.end });
    }
  }
  return out;
}

export function Dialog({ words, speaker = "THE KNIGHT" }: { words: Word[]; speaker?: string }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const all = chunks(words);
  const i = all.findIndex((c, k) => t >= c.start - 0.08 && (t <= c.end + 0.35 || (all[k + 1] && t < all[k + 1].start - 0.08)));
  if (i < 0) return null;
  const current = all[i];
  // Each word types in over its own spoken time.
  let typed = "";
  for (const unit of current.units) {
    const w = unit[0];
    const text = join(unit);
    if (t < w.start) break;
    const share = Math.min(1, (t - w.start) / Math.max(0.08, (w.end - w.start) * 0.8));
    const piece = text.slice(0, Math.max(1, Math.ceil(text.length * share)));
    typed = typed ? `${typed} ${piece}` : piece;
  }
  const done = t > current.end;
  const blink = Math.floor(frame / 8) % 2 === 0;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 26 }}>
      <div style={{ position: "relative", width: 1300, height: 112, display: "flex", background: C.paper, ...pxFrame(6, 8) }}>
        <div style={{ position: "absolute", left: 118, top: -30, background: C.ink, color: C.paper, font: `400 16px ${F.label}`, letterSpacing: 2, padding: "5px 12px" }}>
          {speaker}
        </div>
        <div style={{ width: 112, height: 100, background: C.mist, borderRight: `6px solid ${C.ink}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Sprite rows={KNIGHT_SMALL} scale={6} />
        </div>
        <div style={{ flex: 1, padding: "14px 28px", font: `500 34px/1.3 ${F.pixel}`, color: C.ink, display: "flex", alignItems: "center" }}>
          {typed}
        </div>
        {done && blink && (
          <svg width="22" height="14" viewBox="0 0 11 7" shapeRendering="crispEdges" style={{ position: "absolute", right: 22, bottom: 12 }}>
            <path d="M0 0h11v1h-1v1h-1v1h-1v1h-1v1h-1v1h-1v1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1v-1h-1z" fill={C.signal} />
          </svg>
        )}
      </div>
    </AbsoluteFill>
  );
}

// Quest progress in the corner, like a game HUD.
export function Hud({ quest, total = 5 }: { quest: number; total?: number }) {
  const frame = useCurrentFrame();
  const blink = Math.floor(frame / 10) % 2 === 0;
  return (
    <div style={{ position: "absolute", right: 248, top: 22, display: "flex", alignItems: "center", gap: 14 }}>
      <span style={{ font: `400 18px ${F.label}`, color: C.ink, letterSpacing: 2 }}>QUEST {quest}/{total}</span>
      <div style={{ display: "flex", gap: 6 }}>
        {Array.from({ length: total }, (_, i) => (
          <div key={i} style={{ width: 22, height: 22, border: `4px solid ${C.ink}`, background: i < quest - 1 || (i === quest - 1 && blink) ? C.signal : C.paper }} />
        ))}
      </div>
    </div>
  );
}

// Four pixel corner brackets around a box, in the content's own coordinates.
export function Reticle({ x, y, width, height, opacity }: { x: number; y: number; width: number; height: number; opacity: number }) {
  const arm = 30;
  const th = 7;
  const corner = (left: number, top: number, sx: number, sy: number) => (
    <div style={{ position: "absolute", left, top, width: arm, height: arm, transform: `scale(${sx}, ${sy})`, transformOrigin: "0 0" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: arm, height: th, background: C.signal, boxShadow: `0 0 0 2px ${C.ink}` }} />
      <div style={{ position: "absolute", left: 0, top: 0, width: th, height: arm, background: C.signal, boxShadow: `0 0 0 2px ${C.ink}` }} />
    </div>
  );
  return (
    <div style={{ position: "absolute", inset: 0, opacity, pointerEvents: "none" }}>
      {corner(x, y, 1, 1)}
      {corner(x + width, y, -1, 1)}
      {corner(x, y + height, 1, -1)}
      {corner(x + width, y + height, -1, -1)}
    </div>
  );
}
