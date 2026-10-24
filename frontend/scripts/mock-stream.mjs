#!/usr/bin/env node
// A stand-in for the live scan stream (POST /api/documents/{id}/redact/stream), for checking the frontend
// before the real stream lands. Every other /api call is passed through to the real backend.
//
//   cd backend && uv run uvicorn app.main:app --port 8000   # the real backend, no key needed
//   npm --prefix frontend run mock                          # this mock on :8010
//   npm --prefix frontend run dev:mock                      # Vite on :5173, talking to the mock
//
// Options (environment):
//   MOCK_PORT=8010  MOCK_BACKEND=http://127.0.0.1:8000  MOCK_PARTS=5
//   MOCK_MODEL=off      every part "off", number rules only, like a backend without a key
//   MOCK_ERROR=none     no failed part (by default part 3 fails on the first run, so "not checked" shows;
//                       MOCK_ERROR=always keeps it failing on every retry too)
//   MOCK_FAIL=1         an "error" event after two parts, then the stream ends
//   MOCK_NO_STREAM=1    answer the stream route with FastAPI's 404 "Not Found", to try the fallback
//   MOCK_RETRY=ignore   ignore ?retry=failed and read every part again, like a stream backend that predates it
//   MOCK_SLOW=2         multiply every delay
//
// ?retry=failed follows the backend: with an earlier run of the same plan, parts that were "ok" or "empty"
// come back at once with their stored request id, time and values; only the others are read again.
//
// The "model" values are fake: for a sample they come from its answer key (*.gold.json), for pasted text
// from a title-plus-name pattern. The final result is made by the real backend: the mock hides each value it
// "found" through POST /corrections, so placeholders, boxes and the download stay real. No call goes to Mubit.

import { readFileSync } from "node:fs";
import http from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PORT = Number(process.env.MOCK_PORT ?? 8010);
const BACKEND = new URL(process.env.MOCK_BACKEND ?? "http://127.0.0.1:8000");
const PARTS = Number(process.env.MOCK_PARTS ?? 5);
const MODEL_ON = process.env.MOCK_MODEL !== "off";
const ERROR_PART = process.env.MOCK_ERROR === "none" ? -1 : 2;
const ERROR_ALWAYS = process.env.MOCK_ERROR === "always";
const FAIL = process.env.MOCK_FAIL === "1";
const NO_STREAM = process.env.MOCK_NO_STREAM === "1";
const IGNORE_RETRY = process.env.MOCK_RETRY === "ignore";
const SLOW = Number(process.env.MOCK_SLOW ?? 1);
const DELAYS = [1600, 600, 2400, 3000, 1100, 1900, 800]; // ms per part, so parts finish out of order
const SAMPLES = join(dirname(fileURLToPath(import.meta.url)), "../../data/synthetic/pdfs");
const REGEX_TYPES = new Set(["POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE", "IBAN", "CARD", "NI_NUMBER"]);

const docs = new Map(); // doc_id -> { text, sample }
const runs = new Map(); // doc_id -> { plan, model, attempts, parts: Map(index -> { info, hits }) }, for ?retry=failed

// ---------- backend calls ----------

function backend(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body === undefined ? undefined : JSON.stringify(body);
    const req = http.request(
      { host: BACKEND.hostname, port: BACKEND.port, method, path, headers: data ? { "Content-Type": "application/json" } : {} },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let json = null;
          try {
            json = JSON.parse(text);
          } catch {}
          resolve({ status: res.statusCode, json, text });
        });
      },
    );
    req.on("error", reject);
    req.end(data);
  });
}

function pass(req, res, sniff) {
  const out = http.request(
    { host: BACKEND.hostname, port: BACKEND.port, method: req.method, path: req.url, headers: { ...req.headers, host: BACKEND.host } },
    (back) => {
      if (!sniff) {
        res.writeHead(back.statusCode, back.headers);
        back.pipe(res);
        return;
      }
      const chunks = [];
      back.on("data", (c) => chunks.push(c));
      back.on("end", () => {
        let body = Buffer.concat(chunks);
        try {
          const replaced = sniff(back.statusCode, JSON.parse(body.toString("utf8")));
          if (replaced) body = Buffer.from(JSON.stringify(replaced));
        } catch {}
        const headers = { ...back.headers, "content-length": String(body.length) };
        delete headers["transfer-encoding"];
        res.writeHead(back.statusCode, headers);
        res.end(body);
      });
    },
  );
  out.on("error", () => {
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ detail: `The mock could not reach the backend at ${BACKEND.origin}.` }));
  });
  req.pipe(out);
}

// ---------- the fake model ----------

// Offsets in the stream are Python code points; JS strings count UTF-16 units.
function codePoints(text) {
  if (!/[\uD800-\uDBFF][\uDC00-\uDFFF]/.test(text)) return (i) => i;
  const map = new Map();
  let cp = 0;
  for (let i = 0; i <= text.length; i++) {
    map.set(i, cp);
    const c = text.charCodeAt(i);
    if (!(c >= 0xd800 && c <= 0xdbff)) cp++;
  }
  return (i) => map.get(i) ?? i;
}

// Up to n parts of roughly equal size, cut after a line break.
function cutParts(text, n) {
  const cuts = [0];
  for (let k = 1; k < n; k++) {
    const nl = text.indexOf("\n", Math.floor((text.length * k) / n));
    if (nl < 0) break;
    if (nl + 1 > cuts[cuts.length - 1] && nl + 1 < text.length) cuts.push(nl + 1);
  }
  cuts.push(text.length);
  return cuts.slice(0, -1).map((start, i) => ({ start, end: cuts[i + 1] }));
}

function modelValues(doc) {
  if (doc.sample) {
    try {
      const gold = JSON.parse(readFileSync(join(SAMPLES, doc.sample.replace(/\.pdf$/, ".gold.json")), "utf8"));
      return gold.entities.filter((e) => !REGEX_TYPES.has(e.type)).map((e) => ({ text: e.text, type: e.type }));
    } catch {}
  }
  return [...doc.text.matchAll(/\b(?:Mr|Mrs|Ms|Miss|Dr)\.? [A-Z][a-z]+(?: [A-Z][a-z'-]+)?/g)].map((m) => ({ text: m[0], type: "PERSON" }));
}

// Occurrences of each value inside [start, end), the way the backend reports a part's values.
function findIn(text, values, start, end) {
  const out = [];
  const seen = new Set();
  for (const v of values) {
    if (!v.text.trim()) continue;
    let at = text.indexOf(v.text, start);
    while (at >= 0 && at + v.text.length <= end) {
      const key = `${at}:${at + v.text.length}`;
      if (!seen.has(key)) {
        seen.add(key);
        out.push({ start: at, end: at + v.text.length, text: v.text, type: v.type });
      }
      at = text.indexOf(v.text, at + 1);
    }
  }
  return out;
}

const hex = () => Math.random().toString(16).slice(2, 10).padEnd(8, "0");

// ---------- the stream ----------

async function stream(id, req, res, retry) {
  const doc = docs.get(id);
  const first = await backend("POST", `/api/documents/${id}/redact`).catch(() => null);
  if (!first) {
    res.writeHead(502, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ detail: `The mock could not reach the backend at ${BACKEND.origin}.` }));
  }
  if (first.status !== 200 || !doc) {
    res.writeHead(404, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ detail: "Document not found. Upload it again." }));
  }

  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
  let closed = false;
  const waiting = new Set();
  const stop = () => {
    if (closed) return;
    closed = true;
    clearInterval(ping);
    waiting.forEach((w) => (clearTimeout(w.timer), w.resolve()));
    res.end();
  };
  res.on("close", stop); // the browser went away (Retry, another document, a closed tab)
  const send = (event, data) => !closed && res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  const ping = setInterval(() => !closed && res.write(": ping\n\n"), 1000);
  const later = (ms) =>
    new Promise((resolve) => {
      const w = { resolve, timer: setTimeout(() => (waiting.delete(w), resolve()), ms * SLOW) };
      waiting.add(w);
    });

  const { text } = doc;
  const cp = codePoints(text);
  const at = (e) => ({ ...e, start: cp(e.start), end: cp(e.end) });
  const parts = cutParts(text, PARTS).map((p, index) => ({ ...p, index, chunk_id: `${id}-c${String(index).padStart(2, "0")}` }));
  const values = MODEL_ON ? modelValues(doc) : [];
  const plan = parts.map((p) => `${p.start}:${p.end}`).join(",");
  const earlier = runs.get(id);
  const reuse = retry && earlier?.plan === plan ? earlier.parts : new Map();
  const run = { plan, model: MODEL_ON, attempts: (earlier?.attempts ?? 0) + 1, parts: new Map(reuse) };
  runs.set(id, run);
  const kept = (i) => {
    const old = reuse.get(i)?.info.status;
    return old === "ok" || old === "empty" || (old === "off" && !MODEL_ON);
  };
  console.log(`${id}: ${retry ? "retry" : "run"} ${run.attempts}, reused parts [${parts.filter((p) => kept(p.index)).map((p) => p.index + 1)}], reading [${parts.filter((p) => !kept(p.index)).map((p) => p.index + 1)}]`);

  send("start", {
    doc_id: id,
    model: MODEL_ON ? "on" : "off",
    t1_model: MODEL_ON ? "mock-t1" : null,
    t1_prompt: "evalkit",
    chunks: parts.map(({ index, chunk_id, start, end }) => at({ index, chunk_id, start, end })),
  });
  await later(250);
  // The real backend's regex layer, from its own result (without a key that is every value it found).
  const regex = first.json.entities.filter((e) => REGEX_TYPES.has(e.type)).map(({ start, end, text: t, type }) => ({ start, end, text: t, type, source: "regex" }));
  send("regex", { entities: regex });

  const infos = [];
  const found = new Map();
  await Promise.all(
    parts.map(async (p) => {
      if (kept(p.index)) {
        // Read fine last time: no T1 call, the stored answer comes back at once.
        const { info, hits } = reuse.get(p.index);
        await later(20 * p.index);
        if (closed) return;
        for (const h of hits) found.set(h.text, h.type);
        infos.push(info);
        send("chunk", { ...info, entities: hits.map((h) => ({ ...at(h), source: "model" })) });
        return;
      }
      const off = !MODEL_ON;
      const blank = !text.slice(p.start, p.end).trim();
      const failed = !off && p.index === ERROR_PART && (ERROR_ALWAYS || run.attempts === 1);
      const ms = off || blank ? 40 * p.index : DELAYS[p.index % DELAYS.length];
      await later(ms);
      if (closed) return;
      const hits = off || blank || failed ? [] : findIn(text, values, p.start, p.end);
      for (const h of hits) found.set(h.text, h.type);
      const info = {
        index: p.index,
        chunk_id: p.chunk_id,
        ...at({ start: p.start, end: p.end }),
        status: off ? "off" : blank ? "empty" : failed ? "error" : "ok",
        error: off ? "model off" : failed ? "TimeoutError: Mubit gateway timed out after 30 s (mock)" : null,
        mreq_id: off || blank || failed ? null : `mreq_mock${hex()}`,
        latency_ms: off || blank ? null : Math.round(ms * SLOW + Math.random() * 90),
        found: new Set(hits.map((h) => h.text)).size,
      };
      infos.push(info);
      run.parts.set(p.index, { info, hits });
      send("chunk", { ...info, entities: hits.map((h) => ({ ...at(h), source: "model" })) });
      if (FAIL && infos.length === 2) {
        send("error", { message: "Mubit stopped answering (mock). Try again." });
        stop();
      }
    }),
  );
  if (closed) return;

  // The final result comes from the real backend: each value the fake model found is hidden there too.
  let result = first.json;
  for (const [value, type] of found) {
    const r = await backend("POST", `/api/documents/${id}/corrections`, { action: "hide", text: value, type });
    if (r.status === 200) result = r.json;
  }
  infos.sort((a, b) => a.index - b.index);
  send("done", { ...result, chunks: infos, model: MODEL_ON ? "on" : "off" });
  stop();
}

// ---------- routes ----------

const remember = (sample) => (status, body) => {
  if (status === 200 && body?.doc_id) docs.set(body.doc_id, { text: body.text, sample });
};

http
  .createServer((req, res) => {
    const url = new URL(req.url, "http://mock");
    const streamRoute = url.pathname.match(/^\/api\/documents\/([^/]+)\/redact\/stream$/);
    if (streamRoute && req.method === "POST") {
      if (NO_STREAM) {
        res.writeHead(404, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ detail: "Not Found" }));
      }
      return void stream(streamRoute[1], req, res, !IGNORE_RETRY && url.searchParams.get("retry") === "failed");
    }
    if (url.pathname === "/api/health")
      return pass(req, res, (_, body) => ({
        ...body,
        model: MODEL_ON ? "on" : "off",
        t1_model: MODEL_ON ? "mock-t1" : null,
        t1_prompt: "evalkit",
        key_source: MODEL_ON ? "mock" : null,
      }));
    if (url.pathname === "/api/documents" && req.method === "POST") return pass(req, res, remember(null));
    const sample = url.pathname.match(/^\/api\/samples\/([^/]+\.pdf)$/);
    if (sample && req.method === "POST") return pass(req, res, remember(decodeURIComponent(sample[1])));
    pass(req, res);
  })
  .listen(PORT, "127.0.0.1", () => {
    console.log(`Veil mock stream on http://127.0.0.1:${PORT}, passing the rest to ${BACKEND.origin}`);
    console.log(`model ${MODEL_ON ? "on (fake)" : "off"}, ${PARTS} parts, failed part: ${ERROR_PART < 0 ? "none" : ERROR_PART + 1}${FAIL ? ", error event after two parts" : ""}${NO_STREAM ? ", no stream route" : ""}${IGNORE_RETRY ? ", ignores retry=failed" : ""}`);
  });
