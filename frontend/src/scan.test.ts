import { describe, expect, it } from "vitest";
import { synthesise, type ChunkInfo, type RedactResult, type ScanEntity, type ScanEvent } from "./api";
import { toLines } from "./redaction";
import {
  advancePasses,
  applyEvent,
  emptyScan,
  hiddenSoFar,
  liveEntities,
  partLines,
  passesDone,
  resultInUnits,
  retryScan,
  scanReducer,
  settledPasses,
  withLive,
  type Scan,
} from "./scan";
import type { Open } from "./session";

// Three parts of a short letter, one line each, as the backend would cut it.
const TEXT = "Dear Raj Patel,\nSort code 20-45-77, account 31926819.\nCall 07700 900123 or write to Mia Chen.";
const at = (value: string, from = 0) => {
  const start = TEXT.indexOf(value, from);
  return { start, end: start + value.length, text: value };
};
const cut = [0, TEXT.indexOf("Sort"), TEXT.indexOf("Call"), TEXT.length];
const ranges = [0, 1, 2].map((index) => ({ index, chunk_id: `d0c-c0${index}`, start: cut[index], end: cut[index + 1] }));
const regex = (value: string, type: string): ScanEntity => ({ ...at(value), type, source: "regex" });
const model = (value: string, type: string): ScanEntity => ({ ...at(value), type, source: "model" });

const start: ScanEvent = { type: "start", data: { doc_id: "d0c", model: "on", t1_model: "t1", t1_prompt: "evalkit", chunks: ranges } };
const regexEv: ScanEvent = {
  type: "regex",
  data: { entities: [regex("20-45-77", "SORT_CODE"), regex("31926819", "BANK_ACCOUNT"), regex("07700 900123", "PHONE")] },
};
const chunk = (index: number, extra: Partial<ChunkInfo> & { entities?: ScanEntity[] } = {}): ScanEvent => ({
  type: "chunk",
  data: { ...ranges[index], status: "ok", error: null, mreq_id: `mreq_${index}`, latency_ms: 800 + index, found: extra.entities?.length ?? 0, entities: [], ...extra },
});

const placeholderFor = (type: string, n = 1) => `[${type}_${n}]`;
const finalResult = (entities: { value: string; type: string }[], chunks: ChunkInfo[], modelOn = true): RedactResult => ({
  doc_id: "d0c",
  redacted_text: "",
  entities: entities.map(({ value, type }) => ({ ...at(value), type, placeholder: placeholderFor(type) })),
  boxes: [],
  chunks,
  stats: {},
  model: modelOn ? "on" : "off",
});

const run = (events: ScanEvent[], from: Scan = emptyScan()) => events.reduce(scanReducer, from);

describe("scanReducer", () => {
  it("starts with every part pending", () => {
    const s = run([start]);
    expect(s.model).toBe("on");
    expect(s.parts.map((p) => [p.index, p.status])).toEqual([[0, "pending"], [1, "pending"], [2, "pending"]]);
    expect(s.finished).toBe(0);
  });

  it("takes parts in the order they finish, not index order", () => {
    const s = run([start, regexEv, chunk(2, { entities: [model("Mia Chen", "PERSON")] }), chunk(0, { entities: [model("Raj Patel", "PERSON")] })]);
    expect(s.parts.map((p) => [p.index, p.status, p.order])).toEqual([[0, "ok", 1], [1, "pending", null], [2, "ok", 0]]);
    expect(s.finished).toBe(2);
    expect(s.parts[2]).toMatchObject({ mreq_id: "mreq_2", latency_ms: 802, found: 1 });
  });

  it("keeps regex values, then adds model values, one per start and end", () => {
    const again = chunk(1, { entities: [{ ...regex("20-45-77", "SORT_CODE"), source: "model" }] });
    const s = run([start, regexEv, again]);
    expect(s.entities).toHaveLength(3);
    expect(s.entities.find((e) => e.text === "20-45-77")?.source).toBe("regex");
  });

  it("goes regex, then parts, then done", () => {
    const events = [start, regexEv, chunk(1), chunk(0, { entities: [model("Raj Patel", "PERSON")] }), chunk(2)];
    const before = run(events);
    expect(before.done).toBe(false);
    const result = finalResult([{ value: "Raj Patel", type: "PERSON" }], ranges.map((r) => ({ ...r, status: "ok", error: null, mreq_id: "m", latency_ms: 1, found: 0 })));
    const after = scanReducer(before, { type: "done", data: result });
    expect(after.done).toBe(true);
    expect(after.finished).toBe(3);
    // done is the final word on each part's details, but no part gets a second pass from it.
    expect(after.parts.map((p) => [p.index, p.mreq_id, p.order])).toEqual([[0, "m", 1], [1, "m", 0], [2, "m", 2]]);
  });

  it("marks a part the model could not check, with its reason", () => {
    const s = run([start, regexEv, chunk(1, { status: "error", error: "Mubit timed out", mreq_id: null, found: 0 })]);
    expect(s.parts[1]).toMatchObject({ status: "error", error: "Mubit timed out" });
  });

  it("runs with the model off: every part off, regex values only", () => {
    const off = { ...start, data: { ...start.data, model: "off" as const, t1_model: null } };
    const offChunk = (i: number) => chunk(i, { status: "off", mreq_id: null, latency_ms: null });
    const s = run([off, regexEv, offChunk(0), offChunk(1), offChunk(2)]);
    expect(s.model).toBe("off");
    expect(s.parts.every((p) => p.status === "off")).toBe(true);
    expect(s.entities.every((e) => e.source === "regex")).toBe(true);
  });

  it("takes the details of a repeated part event but keeps its order, so it gets no second pass", () => {
    const s = run([start, chunk(0), chunk(0, { status: "error", error: "late", mreq_id: null })]);
    expect(s.finished).toBe(1);
    expect(s.parts[0]).toMatchObject({ status: "error", error: "late", order: 0 });
    expect(s.seq).toBe(1);
  });

  it("records an error that stops the run", () => {
    const s = run([start, { type: "error", data: { message: "The model gateway is down." } }]);
    expect(s.error).toBe("The model gateway is down.");
    expect(s.done).toBe(false);
  });
});

describe("retry only the failed parts (?retry=failed)", () => {
  // First run: parts 1 and 0 read fine, part 2 failed. Mia Chen is in part 2.
  const first = run([start, regexEv, chunk(1), chunk(0, { entities: [model("Raj Patel", "PERSON")] }), chunk(2, { status: "error", error: "TimeoutError", mreq_id: null })]);

  it("puts only the failed parts back to being read", () => {
    const r = retryScan(first);
    expect(r.parts.map((p) => [p.index, p.status, p.order])).toEqual([[0, "ok", 1], [1, "ok", 0], [2, "pending", null]]);
    expect(r.finished).toBe(2);
    expect(r.done).toBe(false);
    expect(r.entities).toEqual(first.entities); // the bars already drawn stay
  });

  it("keeps unchanged parts as they were when the backend sends them again at once", () => {
    const again = [start, regexEv, chunk(0, { entities: [model("Raj Patel", "PERSON")] }), chunk(1), chunk(2, { entities: [model("Mia Chen", "PERSON")] })];
    const r = run(again, retryScan(first));
    expect(r.parts.map((p) => [p.index, p.status, p.order])).toEqual([[0, "ok", 1], [1, "ok", 0], [2, "ok", 3]]);
    expect(r.parts[0].mreq_id).toBe("mreq_0");
    expect(r.entities.map((e) => e.text)).toContain("Mia Chen");
  });

  it("reads every part again when the plan changed", () => {
    const other = { ...start, data: { ...start.data, chunks: [{ index: 0, chunk_id: "d0c-c00", start: 0, end: TEXT.length }] } };
    const r = scanReducer(retryScan(first), other);
    expect(r.parts.map((p) => [p.index, p.status])).toEqual([[0, "pending"]]);
    expect(r.finished).toBe(0);
  });

  it("reads parts that were off again once the model is on", () => {
    const off = { ...start, data: { ...start.data, model: "off" as const } };
    const offRun = run([off, chunk(0, { status: "off" }), chunk(1, { status: "off" }), chunk(2, { status: "off" })]);
    expect(scanReducer(retryScan(offRun), off).parts.every((p) => p.status === "off")).toBe(true);
    expect(scanReducer(retryScan(offRun), start).parts.every((p) => p.status === "pending")).toBe(true);
  });

  it("works with a backend that ignores the parameter and reads everything again", () => {
    const rerun = [start, regexEv, chunk(1, { mreq_id: "mreq_new1" }), chunk(2), chunk(0, { mreq_id: "mreq_new0" })];
    const r = run(rerun, retryScan(first));
    expect(r.parts.map((p) => [p.index, p.status, p.order, p.mreq_id])).toEqual([[0, "ok", 1, "mreq_new0"], [1, "ok", 0, "mreq_new1"], [2, "ok", 3, "mreq_2"]]);
  });

  it("sweeps only the part read again; the others keep their ended pass", () => {
    const lines = partLines(first.parts, toLines(TEXT, []).map((l) => l.start));
    const ended = settledPasses(first.parts, lines);
    const r = run([start, chunk(0), chunk(1), chunk(2)], retryScan(first));
    const next = advancePasses(ended, r.parts, lines, false);
    expect(next).toEqual({ ...ended, 2: { order: 3, at: 2 } });
  });

  it("keeps the earlier result's bars and counts them while their part is read again", () => {
    const previous = [{ ...at("Mia Chen"), type: "PERSON", placeholder: "[PERSON_2]" }, { ...at("07700 900123"), type: "PHONE", placeholder: "[PHONE_1]" }];
    const live = liveEntities([regex("07700 900123", "PHONE"), model("Raj Patel", "PERSON")], TEXT);
    const shown = withLive(previous, live);
    expect(shown.map((e) => e.placeholder)).toEqual(["[PERSON]", "[PHONE_1]", "[PERSON_2]"]);
    const r = retryScan(first);
    // Raj Patel is in a finished part; the two earlier values sit in part 2, which is being read again.
    expect(hiddenSoFar(shown, r.parts, previous)).toBe(3);
  });
});

describe("synthesise (backend without the stream route)", () => {
  it("rebuilds start, one part per result chunk and done, filling in what an older backend leaves out", () => {
    const old = finalResult([{ value: "20-45-77", type: "SORT_CODE" }, { value: "07700 900123", type: "PHONE" }], []);
    old.chunks = [
      { chunk_id: "d0c-c00", start: cut[0], end: cut[1], mreq_id: null, error: "model off", found: 0 },
      { chunk_id: "d0c-c01", start: cut[1], end: cut[3], mreq_id: null, error: "model off", found: 0 },
    ] as ChunkInfo[];
    old.model = "off";
    const events = synthesise(old);
    expect(events.map((e) => e.type)).toEqual(["start", "chunk", "chunk", "done"]);
    const s = run(events);
    expect(s.parts.map((p) => [p.index, p.status])).toEqual([[0, "off"], [1, "off"]]);
    expect(s.entities.map((e) => e.text)).toEqual(["20-45-77", "07700 900123"]);
    expect(s.done).toBe(true);
  });

  it("derives ok, error and empty for a model-on result without statuses", () => {
    const r = finalResult([], [
      { chunk_id: "a", start: 0, end: 5, mreq_id: "mreq_a", error: null, found: 2 },
      { chunk_id: "b", start: 5, end: 9, mreq_id: null, error: "HTTPError: 502", found: 0 },
      { chunk_id: "c", start: 9, end: 12, mreq_id: null, error: null, found: 0 },
    ] as ChunkInfo[]);
    const s = run(synthesise(r));
    expect(s.parts.map((p) => p.status)).toEqual(["ok", "error", "empty"]);
    expect(s.parts.map((p) => p.index)).toEqual([0, 1, 2]);
  });
});

describe("applyEvent", () => {
  const session = (text = TEXT): Open => ({
    id: "d0c",
    filename: "letter.txt",
    doc: { doc_id: "d0c", kind: "text", filename: "letter.txt", text, pages: [] },
    status: "scanning",
    revealed: false,
    at: 0,
    turns: [],
  });

  it("moves the session to review with the final result on done", () => {
    const result = finalResult([{ value: "Raj Patel", type: "PERSON" }], []);
    const patch = applyEvent(session(), { type: "done", data: result });
    expect(patch.status).toBe("review");
    expect(patch.result?.entities[0].placeholder).toBe("[PERSON_1]");
    expect(patch.scan?.done).toBe(true);
  });

  it("sends a scan that ends off screen straight to review, with no pass left to show", () => {
    const result = finalResult([], []);
    expect(applyEvent(session(), { type: "done", data: result }, false)).toMatchObject({ status: "review", revealed: true });
    expect(applyEvent(session(), { type: "done", data: result }, true).revealed).toBeUndefined();
  });

  it("fails the session on an error event", () => {
    expect(applyEvent(session(), { type: "error", data: { message: "Stopped." } })).toMatchObject({ status: "failed", error: "Stopped." });
  });

  it("maps code point offsets to UTF-16 units after an emoji", () => {
    const text = "Hi 👋 Raj Patel\nok";
    // Python counts the emoji as one character, so the name starts at 5 there and at 6 here.
    const ev: ScanEvent = { type: "regex", data: { entities: [{ start: 5, end: 14, text: "Raj Patel", type: "PERSON", source: "model" }] } };
    const e = applyEvent(session(text), ev).scan!.entities[0];
    expect(text.slice(e.start, e.end)).toBe("Raj Patel");
    const r = resultInUnits(finalResult([], [{ chunk_id: "x", index: 0, start: 0, end: 17, status: "ok", error: null, mreq_id: null, latency_ms: 1, found: 0 }]), text);
    expect(r.chunks[0].end).toBe(text.length);
  });
});

describe("what the page shows", () => {
  it("merges overlapping live values into one bar typed by the longest", () => {
    const text = "Lives at 14 Elm Road, Leeds LS1 4AB.";
    const pos = (v: string) => ({ start: text.indexOf(v), end: text.indexOf(v) + v.length, text: v });
    const merged = liveEntities(
      [
        { ...pos("LS1 4AB"), type: "POSTCODE", source: "regex" },
        { ...pos("14 Elm Road, Leeds LS1 4AB"), type: "ADDRESS", source: "model" },
      ],
      text,
    );
    expect(merged).toEqual([{ ...pos("14 Elm Road, Leeds LS1 4AB"), type: "ADDRESS", placeholder: "[ADDRESS]" }]);
  });

  it("counts only values in parts that have finished", () => {
    const s = run([start, regexEv, chunk(2, { entities: [model("Mia Chen", "PERSON")] })]);
    const shown = liveEntities(s.entities, TEXT);
    expect(shown).toHaveLength(4);
    expect(hiddenSoFar(shown, s.parts)).toBe(2); // the phone number and Mia Chen, both in part 2
    const all = run([chunk(0), chunk(1)], s);
    expect(hiddenSoFar(liveEntities(all.entities, TEXT), all.parts)).toBe(4);
  });
});

describe("the pass", () => {
  const lines = toLines(TEXT, []);
  const starts = lines.map((l) => l.start);

  it("sweeps each finished part over its own lines, and only those", () => {
    const s = run([start, chunk(2)]);
    const spans = partLines(s.parts, starts);
    expect([...spans.entries()]).toEqual([[0, [0, 0]], [1, [1, 1]], [2, [2, 2]]]);
    let c = advancePasses({}, s.parts, spans, false);
    expect(c).toEqual({ 2: { order: 0, at: 2 } });
    c = advancePasses(c, s.parts, spans, false);
    expect(c).toEqual({ 2: { order: 0, at: 3 } });
    expect(advancePasses(c, s.parts, spans, false)).toBe(c); // nothing left to move
    expect(passesDone(c, s.parts, spans)).toBe(false); // parts 0 and 1 are still being read
  });

  it("starts a part that finishes later from its own first line", () => {
    const s = run([start, chunk(2), chunk(0)]);
    const spans = partLines(s.parts, starts);
    const c = advancePasses({ 2: { order: 0, at: 3 } }, s.parts, spans, false);
    expect(c).toEqual({ 0: { order: 1, at: 0 }, 2: { order: 0, at: 3 } });
  });

  it("resolves parts at once with reduced motion", () => {
    const s = run([start, chunk(0), chunk(1), chunk(2)]);
    const spans = partLines(s.parts, starts);
    const c = advancePasses({}, s.parts, spans, true);
    expect(c).toEqual({ 0: { order: 0, at: 1 }, 1: { order: 1, at: 2 }, 2: { order: 2, at: 3 } });
    expect(passesDone(c, s.parts, spans)).toBe(true);
  });

  it("does not replay passes that ended while the document was off screen", () => {
    // The person opened the intake while parts 2 and 0 were read; part 1 is still being read.
    const s = run([start, chunk(2), chunk(0)]);
    const spans = partLines(s.parts, starts);
    const back = settledPasses(s.parts, spans);
    expect(back).toEqual({ 0: { order: 1, at: 1 }, 2: { order: 0, at: 3 } });
    expect(advancePasses(back, s.parts, spans, false)).toBe(back);
    // Part 1 arrives after the person came back: only it is swept.
    const later = run([chunk(1)], s);
    expect(advancePasses(back, later.parts, spans, false)).toEqual({ ...back, 1: { order: 2, at: 1 } });
  });

  it("starts a new pass when a full rerun hands out new orders", () => {
    const s = run([start, chunk(0), chunk(1), chunk(2)]);
    const spans = partLines(s.parts, starts);
    const ended = settledPasses(s.parts, spans);
    const again = run([start, chunk(0)], emptyScan(s.seq));
    expect(advancePasses(ended, again.parts, spans, false)[0]).toEqual({ order: 3, at: 0 });
  });
});
