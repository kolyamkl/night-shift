// Typed calls to the Veil backend (FastAPI in backend/, proxied at /api by Vite).

import type { Entity } from "./redaction";
import { sseParser } from "./sse";

export type DocPayload = {
  doc_id: string;
  kind: "pdf" | "text";
  filename: string;
  text: string;
  pages: { width: number; height: number }[];
};

export type Box = { page: number; x0: number; y0: number; x1: number; y1: number; type: string; placeholder: string };

// "off": no key, no call made. "empty": a blank part, no call made.
export type ChunkStatus = "ok" | "error" | "empty" | "off";

export type ChunkInfo = {
  chunk_id: string;
  index: number;
  start: number;
  end: number;
  mreq_id: string | null;
  error: string | null;
  found: number;
  latency_ms: number | null;
  status: ChunkStatus;
};

export type RedactResult = {
  doc_id: string;
  redacted_text: string;
  entities: Entity[];
  boxes: Box[];
  chunks: ChunkInfo[];
  stats: Record<string, number>;
  model: "on" | "off";
};

// The live scan stream (POST /api/documents/{id}/redact/stream). Offsets are the backend's character offsets.
export type ScanEntity = { start: number; end: number; text: string; type: string; source: "regex" | "model" | "result" };
export type ChunkRange = Pick<ChunkInfo, "index" | "chunk_id" | "start" | "end">;
export type ScanStart = {
  doc_id: string;
  model: "on" | "off";
  t1_model: string | null;
  t1_prompt: "evalkit" | "rewrite" | null;
  chunks: ChunkRange[];
};
export type ScanEvent =
  | { type: "start"; data: ScanStart }
  | { type: "regex"; data: { entities: ScanEntity[] } }
  | { type: "chunk"; data: ChunkInfo & { entities: ScanEntity[] } }
  | { type: "done"; data: RedactResult }
  | { type: "error"; data: { message: string } };

export type StreamHandlers = {
  onEvent: (event: ScanEvent) => void;
  // The backend has no stream route: the result came in one response and the events were rebuilt from it.
  onFallback?: () => void;
};

export type AskResult = {
  answer: string;
  answer_with_placeholders: string;
  sent_text: string;
  unknown_placeholders: string[];
  mreq_id: string | null;
};

export type Health = {
  model: "on" | "off"; t1_model: string | null; t2_model: string | null;
  t1_prompt?: "evalkit" | "rewrite" | null; key_source?: string | null;
};
export type User = { id: string; email: string };
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export type Sample = {
  name: string;
  label: string;
  title: string;
  kind: string;
  pages: number;
  values: number | null;
  types: Record<string, number>;
};

const OFFLINE = "The Veil backend is not running. Start it on port 8000 and try again.";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.method && !["GET", "HEAD"].includes(init.method)) headers.set("X-Veil-Request", "1");
    res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  } catch (e) {
    if (init?.signal?.aborted) throw e;
    throw new Error(OFFLINE);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("veil:unauthorized"));
    }
    throw new ApiError(typeof body?.detail === "string" ? body.detail : `The backend answered ${res.status}.`, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  me: () => call<User>("/api/auth/me"),
  register: (email: string, password: string) => call<User>("/api/auth/register", json({ email, password })),
  login: (email: string, password: string) => call<User>("/api/auth/login", json({ email, password })),
  logout: () => call<{ ok: boolean }>("/api/auth/logout", json({})),
  document: (id: string) => call<{ document: DocPayload; result: RedactResult | null; revision: number }>(
    `/api/documents/${encodeURIComponent(id)}`,
  ),
  health: () => call<Health>("/api/health"),
  samples: () => call<Sample[]>("/api/samples"),
  openSample: (name: string) => call<DocPayload>(`/api/samples/${encodeURIComponent(name)}`, { method: "POST" }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<DocPayload>("/api/documents", { method: "POST", body: form });
  },
  paste: (text: string) => {
    const form = new FormData();
    form.append("text", text);
    return call<DocPayload>("/api/documents", { method: "POST", body: form });
  },
  redact: (id: string, signal?: AbortSignal) => call<RedactResult>(`/api/documents/${id}/redact`, { method: "POST", signal }),
  redactStream,
  correct: (id: string, action: "hide" | "unhide", text: string, type = "CUSTOM") =>
    call<RedactResult>(`/api/documents/${id}/corrections`, json({ action, text, type })),
  ask: (id: string, question: string) => call<AskResult>(`/api/documents/${id}/ask`, json({ question })),
  fileUrl: (id: string) => `/api/documents/${id}/file`,
  thumbUrl: (name: string) => `/api/samples/${encodeURIComponent(name)}/thumb.png`,
  pageUrl: (id: string, page: number, scale = 2) => `/api/documents/${id}/pages/${page}.png?scale=${scale}`,
};

// Render scale for a page image. Pages are shown at most 760 px wide, so about 1600 px covers a 2x screen.
// A photo or scan becomes a page of one point per pixel at 72 dpi (4032 points wide for a phone photo),
// where scale 2 would ask for an 8000 px image; the area cap keeps very long pages (receipts) small too.
export function pageScale(page: { width: number; height: number }): number {
  const fit = Math.min(2, 1600 / page.width, Math.sqrt(8_000_000 / (page.width * page.height)));
  return Math.max(0.05, Math.round(fit * 1000) / 1000);
}

// Older results (the backend on main) have no index, latency or status on their chunks; fill them in.
export function normaliseChunk(c: Partial<ChunkInfo>, i: number, model: "on" | "off"): ChunkInfo {
  const error = c.error ?? null;
  const mreq_id = c.mreq_id ?? null;
  const found = c.found ?? 0;
  return {
    chunk_id: String(c.chunk_id ?? i),
    index: c.index ?? i,
    start: c.start ?? 0,
    end: c.end ?? Number.MAX_SAFE_INTEGER,
    mreq_id,
    error,
    found,
    latency_ms: c.latency_ms ?? null,
    status: c.status ?? (model === "off" ? "off" : error ? "error" : mreq_id || found ? "ok" : "empty"),
  };
}

// Rebuilds the stream's events from one finished result, so the UI has a single code path.
export function synthesise(result: RedactResult): ScanEvent[] {
  const raw: Partial<ChunkInfo>[] = result.chunks.length ? result.chunks : [{}];
  const chunks = raw.map((c, i) => normaliseChunk(c, i, result.model));
  const inside = (c: ChunkInfo): ScanEntity[] =>
    result.entities
      .filter((e) => e.start >= c.start && e.start < c.end)
      .map(({ start, end, text, type }) => ({ start, end, text, type, source: "result" }));
  return [
    {
      type: "start",
      data: {
        doc_id: result.doc_id,
        model: result.model,
        t1_model: null,
        t1_prompt: null,
        chunks: chunks.map(({ index, chunk_id, start, end }) => ({ index, chunk_id, start, end })),
      },
    },
    ...chunks.map((c): ScanEvent => ({ type: "chunk", data: { ...c, entities: inside(c) } })),
    { type: "done", data: { ...result, chunks } },
  ];
}

const EVENTS = new Set(["start", "regex", "chunk", "done", "error"]);
const STALL_MS = 45_000; // the backend pings at least every 10 s, so this much silence means it is gone

// Runs the redaction as a live stream. Resolves after "done"; rejects on an "error" event, a dropped
// connection or a stream that ends early. Rejects with the AbortError when the signal aborts.
// retry "failed": the backend sends parts it already read without calling T1 again and reads only the parts
// that failed. A backend without that ignores it and reads every part, which the UI handles the same way.
async function redactStream(id: string, handlers: StreamHandlers, signal?: AbortSignal, opts: { retry?: "failed" } = {}): Promise<void> {
  const query = opts.retry ? `?retry=${opts.retry}` : "";
  let res: Response;
  try {
    res = await fetch(`/api/documents/${id}/redact/stream${query}`, { method: "POST", headers: { Accept: "text/event-stream", "X-Veil-Request": "1" }, credentials: "same-origin", signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new Error(OFFLINE);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // FastAPI answers an unknown route with 404 "Not Found" (or 405 for a known path): no stream on this backend.
    if (res.status === 405 || (res.status === 404 && body?.detail === "Not Found")) {
      handlers.onFallback?.();
      const result = await api.redact(id, signal);
      for (const event of synthesise(result)) handlers.onEvent(event);
      return;
    }
    if (res.status === 401) window.dispatchEvent(new Event("veil:unauthorized"));
    throw new ApiError(body?.detail ?? `The backend answered ${res.status}.`, res.status);
  }
  if (!res.body) throw new Error("The backend sent an empty answer.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let ended = false;
  let failure: string | null = null;
  let stalled = false;
  const parser = sseParser(({ event, data }) => {
    if (ended || !EVENTS.has(event)) return;
    let payload: unknown;
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }
    const parsed = { type: event, data: payload } as ScanEvent;
    if (parsed.type === "done") ended = true;
    if (parsed.type === "error") {
      ended = true;
      failure = parsed.data.message || "The redaction stopped.";
    }
    handlers.onEvent(parsed);
  });

  let timer: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      stalled = true;
      void reader.cancel();
    }, STALL_MS);
  };
  try {
    arm();
    while (!ended) {
      const { done, value } = await reader.read();
      if (done) break;
      arm();
      parser.push(decoder.decode(value, { stream: true }));
    }
    if (!ended) {
      parser.push(decoder.decode());
      parser.end();
    } else {
      // The backend closes the stream right after its last event: let it, rather than cut the request
      // off (which shows as an aborted request), but do not wait on a stream that stays open.
      const late = setTimeout(() => void reader.cancel().catch(() => undefined), 1000);
      try {
        while (!(await reader.read()).done);
      } catch {
        // already ended; nothing left to read
      } finally {
        clearTimeout(late);
      }
    }
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new Error("The connection to the backend dropped. Try again.");
  } finally {
    clearTimeout(timer);
  }
  if (failure) throw new Error(failure);
  if (!ended) throw new Error(stalled ? "The backend stopped answering. Try again." : "The connection closed before the scan finished. Try again.");
}
