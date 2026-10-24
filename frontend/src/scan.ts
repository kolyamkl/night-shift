// Live scan state: what the backend has really done so far, built from its stream events.
// Pure functions only, so the event-to-state logic can be unit tested.

import { normaliseChunk, synthesise, type ChunkInfo, type RedactResult, type ScanEntity, type ScanEvent } from "./api";
import type { Entity } from "./redaction";
import type { Open, Session } from "./session";

export type PartStatus = "pending" | ChunkInfo["status"];

export type Part = Omit<ChunkInfo, "status"> & {
  status: PartStatus;
  order: number | null; // when this part was read, counted across runs (parts finish out of index order)
};

export type Scan = {
  live: boolean; // false when the backend has no stream and the parts were rebuilt from one response
  model: "on" | "off" | null;
  t1Prompt: string | null;
  parts: Part[]; // by index
  finished: number;
  seq: number; // orders handed out so far; never reused, so a part read again gets a new pass
  entities: ScanEntity[]; // regex + model so far, deduplicated by start and end
  done: boolean;
  error: string | null;
};

// seq carries over from an earlier run of the same document, so its passes are not mistaken for new ones.
export const emptyScan = (seq = 0): Scan => ({
  live: true,
  model: null,
  t1Prompt: null,
  parts: [],
  finished: 0,
  seq,
  entities: [],
  done: false,
  error: null,
});

const key = (e: { start: number; end: number }) => `${e.start}:${e.end}`;

function addEntities(have: ScanEntity[], more: ScanEntity[]): ScanEntity[] {
  if (!more.length) return have;
  const seen = new Set(have.map(key));
  const out = [...have];
  for (const e of more) {
    if (seen.has(key(e))) continue;
    seen.add(key(e));
    out.push(e);
  }
  return out;
}

const pending = (c: Pick<ChunkInfo, "index" | "chunk_id" | "start" | "end">): Part => ({
  index: c.index,
  chunk_id: c.chunk_id,
  start: c.start,
  end: c.end,
  mreq_id: null,
  error: null,
  found: 0,
  latency_ms: null,
  status: "pending",
  order: null,
});

const finishedCount = (parts: Part[]) => parts.filter((p) => p.status !== "pending").length;

function finish(scan: Scan, c: ChunkInfo): Scan {
  const at = scan.parts.findIndex((p) => p.index === c.index);
  const prev = at >= 0 ? scan.parts[at] : undefined;
  // A part already read (kept from the earlier run on a retry, or sent again by a backend that reruns
  // everything): take its details, keep its order, so it keeps its bars and gets no new pass.
  if (prev && prev.status !== "pending") return { ...scan, parts: scan.parts.map((p, i) => (i === at ? { ...c, order: prev.order } : p)) };
  const part: Part = { ...c, order: scan.seq };
  const parts = prev ? scan.parts.map((p, i) => (i === at ? part : p)) : [...scan.parts, part].sort((a, b) => a.index - b.index);
  return { ...scan, parts, finished: scan.finished + 1, seq: scan.seq + 1 };
}

// Retry the parts the AI could not check (POST .../redact/stream?retry=failed): they go back to being
// read; parts already read keep their state, bars and pass.
export function retryScan(scan: Scan): Scan {
  const parts = scan.parts.map((p) => (p.status === "error" ? pending(p) : p));
  return { ...scan, live: true, parts, finished: finishedCount(parts), done: false, error: null };
}

export function scanReducer(scan: Scan, ev: ScanEvent): Scan {
  switch (ev.type) {
    case "start": {
      // A part from an earlier run stands only if the plan is the same and the backend will not read it
      // again: it read fine ("ok", "empty"), or it was "off" and the model is still off.
      const known = new Map(scan.parts.map((p) => [p.index, p]));
      const kept = (c: ChunkRangeLike) => {
        const p = known.get(c.index);
        if (!p || p.start !== c.start || p.end !== c.end) return undefined;
        return p.status === "ok" || p.status === "empty" || (p.status === "off" && ev.data.model === "off") ? p : undefined;
      };
      const parts = [...ev.data.chunks].sort((a, b) => a.index - b.index).map((c) => kept(c) ?? pending(c));
      return { ...scan, model: ev.data.model, t1Prompt: ev.data.t1_prompt, parts, finished: finishedCount(parts) };
    }
    case "regex":
      return { ...scan, entities: addEntities(scan.entities, ev.data.entities) };
    case "chunk": {
      const { entities, ...chunk } = ev.data;
      const next = finish(scan, chunk);
      return { ...next, entities: addEntities(next.entities, entities) };
    }
    case "done": {
      let next: Scan = { ...scan, model: scan.model ?? ev.data.model, done: true, error: null };
      ev.data.chunks.forEach((c, i) => (next = finish(next, normaliseChunk(c, i, ev.data.model))));
      return next;
    }
    case "error":
      return { ...scan, error: ev.data.message };
  }
}

type ChunkRangeLike = Pick<ChunkInfo, "index" | "start" | "end">;

// The scan behind a stored result, as if it had just been read: a reopened document can then retry only
// the parts the AI could not check, and the other parts keep their bars. Parts get the order of their
// index, as partsOf gives them, so no pass is replayed.
export const scanOf = (result: RedactResult): Scan => synthesise(result).reduce(scanReducer, emptyScan());

// ---------- Offsets ----------

// The backend counts characters as Python code points; JS strings count UTF-16 units. They differ only
// after an emoji or another character outside the Basic Multilingual Plane, so map offsets when one is there.
let memo: { text: string; map: (n: number) => number } | null = null;

export function unitMap(text: string): (n: number) => number {
  if (memo?.text === text) return memo.map;
  let map = (n: number) => n;
  if (/[\uD800-\uDBFF][\uDC00-\uDFFF]/.test(text)) {
    const units: number[] = [];
    let u = 0;
    for (const ch of text) {
      units.push(u);
      u += ch.length;
    }
    units.push(u);
    map = (n: number) => (n >= units.length ? u + (n - units.length + 1) : units[Math.max(0, n)]);
  }
  memo = { text, map };
  return map;
}

function moveSpan<T extends { start: number; end: number }>(x: T, map: (n: number) => number): T {
  return { ...x, start: map(x.start), end: map(x.end) };
}

export function resultInUnits(result: RedactResult, text: string): RedactResult {
  const map = unitMap(text);
  return {
    ...result,
    entities: result.entities.map((e) => moveSpan(e, map)),
    chunks: result.chunks.map((c, i) => moveSpan(normaliseChunk(c, i, result.model), map)),
  };
}

export function eventInUnits(ev: ScanEvent, text: string): ScanEvent {
  const map = unitMap(text);
  switch (ev.type) {
    case "start":
      return { ...ev, data: { ...ev.data, chunks: ev.data.chunks.map((c) => moveSpan(c, map)) } };
    case "regex":
      return { ...ev, data: { entities: ev.data.entities.map((e) => moveSpan(e, map)) } };
    case "chunk":
      return { ...ev, data: { ...moveSpan(ev.data, map), entities: ev.data.entities.map((e) => moveSpan(e, map)) } };
    case "done":
      return { ...ev, data: resultInUnits(ev.data, text) };
    case "error":
      return ev;
  }
}

// One stream event applied to a session: the scan state, plus the result and status when the run ends.
// A scan that ends while its document is not on screen has nothing left to show: it goes straight to review.
export function applyEvent(s: Open, raw: ScanEvent, visible = true): Partial<Session> {
  const ev = eventInUnits(raw, s.doc.text);
  const scan = scanReducer(s.scan ?? emptyScan(), ev);
  if (ev.type === "done") return { scan, status: "review", result: ev.data, ...(visible ? {} : { revealed: true }) };
  if (ev.type === "error") return { scan, status: "failed", error: ev.data.message };
  return { scan };
}

// ---------- What the page shows ----------

// Live values merged the way the backend merges them (overlaps become one span, typed by the longest),
// with a type-only tag until the final result numbers them.
export function liveEntities(found: ScanEntity[], text: string): Entity[] {
  const out: Entity[] = [];
  for (const e of [...found].sort((a, b) => a.start - b.start || b.end - a.end)) {
    const last = out[out.length - 1];
    if (last && e.start < last.end) {
      const type = e.end - e.start > last.end - last.start ? e.type : last.type;
      const end = Math.max(last.end, e.end);
      out[out.length - 1] = { start: last.start, end, text: text.slice(last.start, end), type, placeholder: `[${type}]` };
    } else {
      out.push({ start: e.start, end: e.end, text: text.slice(e.start, e.end), type: e.type, placeholder: `[${e.type}]` });
    }
  }
  return out;
}

// The parts of a session: from the live scan, else from a finished result.
export function partsOf(s: Pick<Session, "scan" | "result">): Part[] {
  if (s.scan?.parts.length) return s.scan.parts;
  return (s.result?.chunks ?? []).map((c, i) => ({ ...c, order: i }));
}

// The part an offset falls in: the last one starting at or before it (parts are contiguous).
export function partAt(parts: Part[], offset: number): Part | undefined {
  let found: Part | undefined;
  for (const p of parts) if (p.start <= offset) found = p;
  return found;
}

// While parts are read again, the earlier result keeps its bars; values found since are added where they
// do not overlap one of them.
export function withLive(previous: Entity[], live: Entity[]): Entity[] {
  const extra = live.filter((e) => !previous.some((b) => b.start < e.end && e.start < b.end));
  return extra.length ? [...previous, ...extra].sort((a, b) => a.start - b.start) : previous;
}

// Values the backend has reported in parts that have finished: the real count so far. On a retry, the
// earlier result's values in parts being read again still count: their bars stay up.
export function hiddenSoFar(entities: Entity[], parts: Part[], previous?: Entity[]): number {
  if (!parts.length) return 0;
  const finished = (e: Entity) => {
    const p = partAt(parts, e.start);
    return !!p && p.status !== "pending";
  };
  return entities.filter(finished).length + (previous ?? []).filter((e) => !finished(e)).length;
}

// ---------- The pass ----------

// Line range of each part: a line belongs to the part its first character is in.
export function partLines(parts: Part[], lineStarts: number[]): Map<number, [number, number]> {
  const out = new Map<number, [number, number]>();
  lineStarts.forEach((start, line) => {
    const p = partAt(parts, start);
    if (!p) return;
    const span = out.get(p.index);
    if (span) span[1] = line;
    else out.set(p.index, [line, line]);
  });
  return out;
}

// A pass belongs to one reading of one part (its order), so a part read again on a retry sweeps again,
// and a part whose pass has ended is never swept twice.
export type Pass = { order: number; at: number };

// One tick of the pass. Each finished part sweeps its own lines, one per tick, from its first line to one
// past its last; parts that finish later start later. "calm" (reduced motion) resolves a part at once.
export function advancePasses(
  passes: Record<number, Pass>,
  parts: Part[],
  lines: Map<number, [number, number]>,
  calm: boolean,
): Record<number, Pass> {
  let next = passes;
  for (const p of parts) {
    if (p.status === "pending") continue;
    const order = p.order ?? -1;
    const [first, last] = lines.get(p.index) ?? [0, -1];
    const pass = passes[p.index];
    let at: number;
    if (!pass || pass.order !== order) at = calm ? last + 1 : first;
    else if (pass.at <= last) at = pass.at + 1;
    else continue;
    if (next === passes) next = { ...passes };
    next[p.index] = { order, at };
  }
  return next;
}

// Coming back to a document: parts read while it was off screen are shown done, not swept again.
export function settledPasses(parts: Part[], lines: Map<number, [number, number]>): Record<number, Pass> {
  const out: Record<number, Pass> = {};
  for (const p of parts) if (p.status !== "pending") out[p.index] = { order: p.order ?? -1, at: (lines.get(p.index)?.[1] ?? -1) + 1 };
  return out;
}

export function sweeping(passes: Record<number, Pass>, parts: Part[], lines: Map<number, [number, number]>): boolean {
  return parts.some((p) => {
    if (p.status === "pending") return false;
    const pass = passes[p.index];
    return !pass || pass.order !== (p.order ?? -1) || pass.at <= (lines.get(p.index)?.[1] ?? -1);
  });
}

export function passesDone(passes: Record<number, Pass>, parts: Part[], lines: Map<number, [number, number]>): boolean {
  return parts.every((p) => p.status !== "pending") && !sweeping(passes, parts, lines);
}
