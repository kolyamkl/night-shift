import { describe, expect, it } from "vitest";
import { sseParser, type SseEvent } from "./sse";

function feed(reads: string[], end = true): SseEvent[] {
  const out: SseEvent[] = [];
  const p = sseParser((e) => out.push(e));
  reads.forEach((r) => p.push(r));
  if (end) p.end();
  return out;
}

describe("sseParser", () => {
  it("reads one event", () => {
    expect(feed(['event: start\ndata: {"a":1}\n\n'])).toEqual([{ event: "start", data: '{"a":1}' }]);
  });

  it("joins an event split across reads, even inside a field name", () => {
    expect(feed(["eve", "nt: chunk\nda", 'ta: {"index"', ":2}\n", "\n"], false)).toEqual([{ event: "chunk", data: '{"index":2}' }]);
  });

  it("reads several events from one read", () => {
    const got = feed(["event: regex\ndata: 1\n\nevent: chunk\ndata: 2\n\nevent: done\ndata: 3\n\n"], false);
    expect(got.map((e) => [e.event, e.data])).toEqual([["regex", "1"], ["chunk", "2"], ["done", "3"]]);
  });

  it("skips ping comments", () => {
    expect(feed([": ping\n\n", "event: start\n: ping\ndata: x\n\n", ": ping\n\n"], false)).toEqual([{ event: "start", data: "x" }]);
  });

  it("accepts CRLF and bare CR line ends, including a CRLF split between reads", () => {
    expect(feed(["event: a\r\ndata: 1\r\n\r\n", "event: b\rdata: 2\r\r", "event: c\r", "\ndata: 3\r", "\n\r\n"], false)).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
      { event: "c", data: "3" },
    ]);
  });

  it("does not dispatch an event before its blank line, and delivers a trailing one at the end", () => {
    const out: SseEvent[] = [];
    const p = sseParser((e) => out.push(e));
    p.push("event: done\ndata: {}\n");
    expect(out).toEqual([]);
    p.end();
    expect(out).toEqual([{ event: "done", data: "{}" }]);
  });

  it("joins multi-line data and names an unnamed event message", () => {
    expect(feed(["data: one\ndata: two\n\n"], false)).toEqual([{ event: "message", data: "one\ntwo" }]);
  });
});
