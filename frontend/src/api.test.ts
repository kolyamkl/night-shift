import { afterEach, describe, expect, it, vi } from "vitest";
import { api, pageScale, type RedactResult, type ScanEvent } from "./api";

const result: RedactResult = {
  doc_id: "d1",
  redacted_text: "Call [PHONE_1]",
  entities: [{ start: 5, end: 17, text: "07700 900123", type: "PHONE", placeholder: "[PHONE_1]" }],
  boxes: [],
  chunks: [{ chunk_id: "d1-c00", index: 0, start: 0, end: 17, mreq_id: "mreq_1", error: null, found: 0, latency_ms: 900, status: "ok" }],
  stats: { PHONE: 1 },
  model: "on",
};

const sse = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

// A streamed response whose body arrives in the given pieces, one read each.
function streamed(pieces: string[], opts: { hang?: boolean } = {}) {
  const enc = new TextEncoder();
  return (_url: string, init?: RequestInit) => {
    const body = new ReadableStream<Uint8Array>({
      start(ctrl) {
        pieces.forEach((p) => ctrl.enqueue(enc.encode(p)));
        if (!opts.hang) ctrl.close();
        init?.signal?.addEventListener("abort", () => ctrl.error(new DOMException("Aborted", "AbortError")));
      },
    });
    return Promise.resolve(new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
  };
}

const jsonResponse = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function collect(signal?: AbortSignal) {
  const events: ScanEvent[] = [];
  let fellBack = false;
  const done = api.redactStream("d1", { onEvent: (e) => events.push(e), onFallback: () => (fellBack = true) }, signal);
  return { events, done, fellBack: () => fellBack };
}

afterEach(() => vi.unstubAllGlobals());

describe("api.redactStream", () => {
  it("sends session credentials and CSRF protection with streaming requests", async () => {
    const fetch = vi.fn(streamed([sse("done", result)]));
    vi.stubGlobal("fetch", fetch);
    await api.redactStream("d1", { onEvent: () => {} });
    expect(fetch.mock.calls[0][1]).toMatchObject({
      credentials: "same-origin", headers: { "X-Veil-Request": "1" },
    });
  });

  it("clears the workspace on an expired session without retrying a scan", async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    const fetch = vi.fn(() => Promise.resolve(jsonResponse(401, { detail: "Please log in to continue." })));
    vi.stubGlobal("fetch", fetch);
    await expect(api.redactStream("d1", { onEvent: () => {} })).rejects.toThrow("Please log in");
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect(dispatchEvent.mock.calls[0][0].type).toBe("veil:unauthorized");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("parses the live events in order, across awkward reads", async () => {
    const start = { doc_id: "d1", model: "on", t1_model: "t1", t1_prompt: "evalkit", chunks: [{ index: 0, chunk_id: "d1-c00", start: 0, end: 17 }] };
    const all =
      sse("start", start) +
      ": ping\n\n" +
      sse("regex", { entities: [{ start: 5, end: 17, text: "07700 900123", type: "PHONE", source: "regex" }] }) +
      sse("chunk", { ...result.chunks[0], entities: [] }) +
      sse("done", result);
    const pieces = [all.slice(0, 7), all.slice(7, 90), all.slice(90, 91), all.slice(91)].map((p) => p.replace(/\n/g, "\r\n"));
    vi.stubGlobal("fetch", vi.fn(streamed(pieces)));
    const { events, done } = await collect();
    await done;
    expect(events.map((e) => e.type)).toEqual(["start", "regex", "chunk", "done"]);
    expect(events[3]).toEqual({ type: "done", data: result });
  });

  it("rejects with the message of an error event", async () => {
    vi.stubGlobal("fetch", vi.fn(streamed([sse("start", { doc_id: "d1", model: "on", t1_model: null, t1_prompt: "evalkit", chunks: [] }), sse("error", { message: "Mubit is not answering." })])));
    const { events, done } = await collect();
    await expect(done).rejects.toThrow("Mubit is not answering.");
    expect(events.map((e) => e.type)).toEqual(["start", "error"]);
  });

  it("rejects when the stream ends before done", async () => {
    vi.stubGlobal("fetch", vi.fn(streamed([sse("start", { doc_id: "d1", model: "on", t1_model: null, t1_prompt: "evalkit", chunks: [] })])));
    const { done } = await collect();
    await expect(done).rejects.toThrow("closed before the scan finished");
  });

  it("falls back to the one-shot redact when the route does not exist, and rebuilds the events", async () => {
    const fetch = vi.fn((url: string) =>
      Promise.resolve(url.endsWith("/redact/stream") ? jsonResponse(404, { detail: "Not Found" }) : jsonResponse(200, result)),
    );
    vi.stubGlobal("fetch", fetch);
    const { events, done, fellBack } = await collect();
    await done;
    expect(fellBack()).toBe(true);
    expect(fetch.mock.calls.map((c) => c[0])).toEqual(["/api/documents/d1/redact/stream", "/api/documents/d1/redact"]);
    expect(events.map((e) => e.type)).toEqual(["start", "chunk", "done"]);
    expect(events[1]).toMatchObject({ type: "chunk", data: { index: 0, mreq_id: "mreq_1", entities: [{ text: "07700 900123", source: "result" }] } });
  });

  it("falls back on 405 too", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(url.endsWith("/stream") ? jsonResponse(405, { detail: "Method Not Allowed" }) : jsonResponse(200, result))));
    const { events, done } = await collect();
    await done;
    expect(events.at(-1)?.type).toBe("done");
  });

  it("treats an unknown document as a real error, not a fallback", async () => {
    const fetch = vi.fn(() => Promise.resolve(jsonResponse(404, { detail: "Document not found. Upload it again." })));
    vi.stubGlobal("fetch", fetch);
    const { done } = await collect();
    await expect(done).rejects.toThrow("Document not found. Upload it again.");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("gives up when the backend goes silent, pings included, for 45 seconds", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      vi.stubGlobal("fetch", vi.fn(streamed([sse("start", { doc_id: "d1", model: "on", t1_model: null, t1_prompt: "evalkit", chunks: [] })], { hang: true })));
      const { done } = await collect();
      const settled = expect(done).rejects.toThrow("The backend stopped answering.");
      await vi.advanceTimersByTimeAsync(45_000);
      await settled;
    } finally {
      vi.useRealTimers();
    }
  });

  it("lets the backend close the stream after done, and does not wait on one that stays open", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      vi.stubGlobal("fetch", vi.fn(streamed([sse("done", result)], { hang: true })));
      const { events, done } = await collect();
      let resolved = false;
      void done.then(() => (resolved = true));
      await vi.advanceTimersByTimeAsync(900);
      expect(resolved).toBe(false);
      await vi.advanceTimersByTimeAsync(200);
      expect(resolved).toBe(true);
      expect(events.map((e) => e.type)).toEqual(["done"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("asks for a retry of the failed parts only, and still works when an older backend has no stream", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        urls.push(url);
        return Promise.resolve(url.includes("/stream") ? jsonResponse(404, { detail: "Not Found" }) : jsonResponse(200, result));
      }),
    );
    const events: ScanEvent[] = [];
    await api.redactStream("d1", { onEvent: (e) => events.push(e) }, undefined, { retry: "failed" });
    expect(urls).toEqual(["/api/documents/d1/redact/stream?retry=failed", "/api/documents/d1/redact"]);
    expect(events.map((e) => e.type)).toEqual(["start", "chunk", "done"]);
  });

  it("stops on abort and rethrows the AbortError", async () => {
    vi.stubGlobal("fetch", vi.fn(streamed([sse("start", { doc_id: "d1", model: "on", t1_model: null, t1_prompt: "evalkit", chunks: [] })], { hang: true })));
    const ctrl = new AbortController();
    const { events, done } = await collect(ctrl.signal);
    await vi.waitFor(() => expect(events).toHaveLength(1));
    ctrl.abort();
    await expect(done).rejects.toMatchObject({ name: "AbortError" });
    expect(events).toHaveLength(1);
  });
});

describe("pageScale", () => {
  it("keeps 2x for paper pages and caps photos and long scans", () => {
    expect(pageScale({ width: 595, height: 842 })).toBe(2); // A4
    expect(pageScale({ width: 4032, height: 3024 })).toBe(0.397); // a phone photo at 72 dpi: 1600 px wide
    const receipt = { width: 800, height: 14400 };
    const s = pageScale(receipt);
    expect(receipt.width * s * receipt.height * s).toBeLessThanOrEqual(8_000_000);
  });
});

describe("the saved list on an older backend", () => {
  const row = { doc_id: "a1", filename: "lease.pdf", kind: "pdf", pages: 3, status: "approved", created_at: "2026-10-24T17:00:00Z",
    updated_at: "2026-10-24T18:00:00Z", has_result: true, changes: 9, turns: 2 };

  it("reads the list from GET /api/documents", async () => {
    const fetch = vi.fn(() => Promise.resolve(jsonResponse(200, [row])));
    vi.stubGlobal("fetch", fetch);
    expect(await api.documents()).toEqual([row]);
    expect(fetch.mock.calls[0]).toMatchObject(["/api/documents", { credentials: "same-origin" }]);
  });

  it.each([
    [404, "Not Found"],
    [405, "Method Not Allowed"], // the backend on main has only POST /api/documents
  ])("gives null, not an error, when the list route answers %i %s", async (status, detail) => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(status, { detail }))));
    await expect(api.documents()).resolves.toBeNull();
  });

  it("still fails on a real error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(500, { detail: "Database unavailable." }))));
    await expect(api.documents()).rejects.toThrow("Database unavailable.");
  });

  it("saves a review step with PATCH, and gives null on a backend without the route", async () => {
    const fetch = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve(jsonResponse(200, { doc_id: "a1", status: "approved" })));
    vi.stubGlobal("fetch", fetch);
    await expect(api.setStatus("a1", "approved")).resolves.toEqual({ doc_id: "a1", status: "approved" });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/documents/a1");
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("X-Veil-Request")).toBe("1");
    expect(JSON.parse(String(init?.body))).toEqual({ status: "approved" });

    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(405, { detail: "Method Not Allowed" }))));
    await expect(api.setStatus("a1", "declined")).resolves.toBeNull();
  });

  it("treats a missing document as a real error, not an older backend", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(404, { detail: "Document not found." }))));
    await expect(api.setStatus("gone", "review")).rejects.toThrow("Document not found.");
  });
});
