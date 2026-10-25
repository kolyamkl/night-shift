#!/usr/bin/env node
// A stand-in for the live scan stream (POST /api/documents/{id}/redact/stream) and for the saved list,
// review status and chat (GET /api/documents, PATCH /api/documents/{id}, stored turns), for checking the
// frontend without Mubit. Every other /api call is passed through to the real backend.
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
//   MOCK_NO_LIST=1      answer like an older backend: GET /api/documents is 404 "Not Found", PATCH is 405,
//                       documents have no status or turns, asks get no turn_id
//   MOCK_LEAVE=stop     stop a scan when the browser goes away (by default it carries on and is stored,
//                       like the backend's), so the document comes back as "new" with Scan
//
// Saved list, status and chat: the mock keeps them in memory for the documents created through it (or
// opened through it), per signed-in account; nothing is written to disk, so a restart forgets them. A
// document's result is hidden (null) until the mock's own scan of it finishes, as on the backend. When the
// backend has no chat model (no key, /ask answers 503), the mock answers itself with the document's
// placeholders and puts the values back; it never calls an AI.
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
const NO_LIST = process.env.MOCK_NO_LIST === "1";
const LEAVE_STOPS = process.env.MOCK_LEAVE === "stop";
const DELAYS = [1600, 600, 2400, 3000, 1100, 1900, 800]; // ms per part, so parts finish out of order
const SAMPLES = join(dirname(fileURLToPath(import.meta.url)), "../../backend/samples");
const REGEX_TYPES = new Set(["POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE", "IBAN", "CARD", "NI_NUMBER"]);

const docs = new Map(); // doc_id -> { text, sample, owner (a promise of the user id), status, created_at, updated_at, turns }
const runs = new Map(); // doc_id -> { plan, model, attempts, parts: Map(index -> { info, hits }) }, for ?retry=failed
const scans = new Map(); // doc_id -> the newest scan's number: an older scan stops, as on the backend
let turnIds = 0;

// ---------- backend calls ----------

function backend(method, path, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const data = body === undefined ? undefined : JSON.stringify(body);
    const req = http.request(
      { host: BACKEND.hostname, port: BACKEND.port, method, path, headers: { ...(data ? { "Content-Type": "application/json" } : {}), cookie: headers.cookie ?? "", "X-Veil-Request": headers["x-veil-request"] ?? "" } },
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
        let parsed = null; // a 204 has no body
        try {
          parsed = JSON.parse(body.toString("utf8"));
        } catch {}
        try {
          const replaced = sniff(back.statusCode, parsed);
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

const json = (res, status, body) => {
  res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(body));
};
const unreachable = (res) => json(res, 502, { detail: `The mock could not reach the backend at ${BACKEND.origin}.` });

function readJson(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch {
        resolve(null);
      }
    });
  });
}

// ---------- the saved list, status and chat ----------

const now = () => new Date().toISOString();
const whoami = (req) =>
  backend("GET", "/api/auth/me", undefined, req.headers)
    .then((r) => (r.status === 200 ? r.json.id : null))
    .catch(() => null);

// A document the mock has not seen (created before it started): kept from what the backend says.
function adopt(id, stored, req) {
  const at = now();
  const doc = { text: stored.document.text, sample: null, owner: whoami(req), status: stored.result ? "review" : "new", created_at: at, updated_at: at, turns: [] };
  docs.set(id, doc);
  return doc;
}

// The backend stores its own one-shot result (no key: every part "off"); the mock's scan streamed other
// parts. A stored result carries the parts of the mock's last finished scan, so a reopened document
// matches what was streamed.
const asScanned = (id, result) => {
  const last = runs.get(id)?.done;
  return result && last ? { ...result, chunks: last.chunks, model: last.model } : result;
};

const touch = (id) => {
  const doc = docs.get(id);
  if (doc) doc.updated_at = now();
};

// GET /api/documents/{id}: the backend's answer plus the status and turns; no result until a scan finished.
const withSaved = (id, req) => (status, body) => {
  if (status !== 200 || NO_LIST) return;
  const doc = docs.get(id) ?? adopt(id, body, req);
  return { ...body, result: doc.status === "new" ? null : asScanned(id, body.result), status: doc.status, turns: doc.turns };
};

async function list(req, res) {
  if (NO_LIST) return json(res, 404, { detail: "Not Found" });
  const me = await backend("GET", "/api/auth/me", undefined, req.headers).catch(() => null);
  if (!me) return unreachable(res);
  if (me.status !== 200) return json(res, me.status, me.json ?? { detail: "Please log in to continue." });
  const mine = [];
  for (const [id, doc] of docs) if ((await doc.owner) === me.json.id) mine.push([id, doc]);
  const rows = await Promise.all(
    mine.map(async ([id, doc]) => {
      const r = await backend("GET", `/api/documents/${id}`, undefined, req.headers).catch(() => null);
      if (r?.status === 404) docs.delete(id); // deleted without the mock seeing it
      if (r?.status !== 200) return null;
      const { document, result: stored } = r.json;
      const result = doc.status === "new" ? null : stored;
      return {
        doc_id: id,
        filename: document.filename,
        kind: document.kind,
        pages: document.pages.length,
        status: doc.status,
        created_at: doc.created_at,
        updated_at: doc.updated_at,
        has_result: !!result,
        changes: result ? result.entities.length : null,
        turns: doc.turns.length,
      };
    }),
  );
  json(res, 200, rows.filter(Boolean).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
}

async function setStatus(id, req, res) {
  if (NO_LIST) return json(res, 405, { detail: "Method Not Allowed" });
  if (req.headers["x-veil-request"] !== "1") return json(res, 403, { detail: "Missing request protection header." });
  const body = await readJson(req);
  if (!["review", "approved", "declined"].includes(body?.status)) return json(res, 422, { detail: "Status must be review, approved or declined." });
  const r = await backend("GET", `/api/documents/${id}`, undefined, req.headers).catch(() => null);
  if (!r) return unreachable(res);
  if (r.status !== 200) return json(res, r.status, r.json);
  const doc = docs.get(id) ?? adopt(id, r.json, req);
  doc.status = body.status;
  doc.updated_at = now();
  console.log(`${id}: status ${doc.status}`);
  json(res, 200, { doc_id: id, status: doc.status });
}

// The backend's answer when it has a chat model; otherwise one made here from the placeholders.
function mockAnswer(result) {
  const values = new Map();
  for (const e of [...result.entities].sort((a, b) => a.start - b.start)) if (!values.has(e.placeholder)) values.set(e.placeholder, e.text);
  const named = [...values.keys()].slice(0, 3);
  const raw = named.length
    ? `Mock answer, no AI was asked. The document mentions ${named.join(", ")}.`
    : "Mock answer, no AI was asked. Nothing in the document is hidden.";
  const answer = raw.replace(/\[[A-Z_]+_\d+\]/g, (p) => values.get(p) ?? p);
  return { answer, answer_with_placeholders: raw, sent_text: result.redacted_text, unknown_placeholders: [], mreq_id: null };
}

async function ask(id, req, res) {
  const body = await readJson(req);
  let r = await backend("POST", `/api/documents/${id}/ask`, body ?? {}, req.headers).catch(() => null);
  if (!r) return unreachable(res);
  if (r.status === 503) {
    const stored = await backend("GET", `/api/documents/${id}`, undefined, req.headers).catch(() => null);
    if (stored?.status === 200 && stored.json.result) r = { status: 200, json: mockAnswer(stored.json.result) };
  }
  if (r.status !== 200 || NO_LIST) return json(res, r.status, r.json);
  const doc = docs.get(id);
  const turn = { turn_id: ++turnIds, created_at: now(), question: body?.question ?? "", ...r.json };
  if (doc) {
    const { sent_text: _, ...kept } = turn; // the backend does not keep the text sent per turn
    doc.turns.push(kept);
    doc.updated_at = turn.created_at;
  }
  json(res, 200, turn);
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
  const known = await backend("GET", `/api/documents/${id}`, undefined, req.headers).catch(() => null);
  if (!known) return unreachable(res);
  if (known.status !== 200) return json(res, 404, { detail: "Document not found." });
  const doc = docs.get(id) ?? adopt(id, known.json, req);
  const first = await backend("POST", `/api/documents/${id}/redact`, undefined, req.headers).catch(() => null);
  if (!first) return unreachable(res);
  if (first.status !== 200) return json(res, first.status, first.json);

  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
  const mine = (scans.get(id) ?? 0) + 1;
  scans.set(id, mine);
  let gone = false; // the browser went away (Retry, another document, the landing page, a closed tab)
  let closed = false; // this scan stopped: a newer one started, or the browser left with MOCK_LEAVE=stop
  const waiting = new Set();
  const wake = () => waiting.forEach((w) => (clearTimeout(w.timer), w.resolve()));
  const stop = () => {
    if (closed) return;
    closed = true;
    clearInterval(ping);
    wake();
    if (!gone) res.end();
  };
  res.on("close", () => {
    if (closed) return; // the stream ended normally
    gone = true;
    clearInterval(ping);
    // Like the backend, a scan carries on when nobody is reading the stream, and stores its result.
    if (LEAVE_STOPS || scans.get(id) !== mine) stop();
    else console.log(`${id}: the browser left, the scan carries on`);
  });
  const send = (event, data) => !gone && !closed && res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  const ping = setInterval(() => !gone && !closed && res.write(": ping\n\n"), 1000);
  const later = (ms) =>
    new Promise((resolve) => {
      const w = { resolve, timer: setTimeout(() => (waiting.delete(w), resolve()), ms * SLOW) };
      waiting.add(w);
    }).then(() => {
      if (scans.get(id) !== mine) stop(); // a newer scan of this document took over
    });

  const { text } = doc;
  const cp = codePoints(text);
  const at = (e) => ({ ...e, start: cp(e.start), end: cp(e.end) });
  const parts = cutParts(text, PARTS).map((p, index) => ({ ...p, index, chunk_id: `${id}-c${String(index).padStart(2, "0")}` }));
  const values = MODEL_ON ? modelValues(doc) : [];
  const plan = parts.map((p) => `${p.start}:${p.end}`).join(",");
  const earlier = runs.get(id);
  const reuse = retry && earlier?.plan === plan ? earlier.parts : new Map();
  const run = { plan, model: MODEL_ON, attempts: (earlier?.attempts ?? 0) + 1, parts: new Map(reuse), done: earlier?.done };
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
    const r = await backend("POST", `/api/documents/${id}/corrections`, { action: "hide", text: value, type }, req.headers);
    if (r.status === 200) result = r.json;
  }
  if (scans.get(id) !== mine) stop();
  if (closed) return;
  infos.sort((a, b) => a.index - b.index);
  // As on the backend, a finished scan stores its result and moves a new document to review.
  if (doc.status === "new") doc.status = "review";
  doc.updated_at = now();
  run.done = { chunks: infos, model: MODEL_ON ? "on" : "off" };
  if (gone) console.log(`${id}: the scan finished with nobody watching, stored`);
  send("done", { ...result, chunks: infos, model: MODEL_ON ? "on" : "off" });
  stop();
}

// ---------- routes ----------

const remember = (req, sample) => (status, body) => {
  if (status !== 200 || !body?.doc_id) return;
  const at = now();
  docs.set(body.doc_id, { text: body.text, sample, owner: whoami(req), status: "new", created_at: at, updated_at: at, turns: [] });
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
    if (url.pathname === "/api/documents" && req.method === "POST") return pass(req, res, remember(req, null));
    if (url.pathname === "/api/documents" && req.method === "GET") return void list(req, res);
    const sample = url.pathname.match(/^\/api\/samples\/([^/]+\.pdf)$/);
    if (sample && req.method === "POST") return pass(req, res, remember(req, decodeURIComponent(sample[1])));
    const one = url.pathname.match(/^\/api\/documents\/([^/]+)$/);
    if (one && req.method === "GET") return pass(req, res, withSaved(one[1], req));
    if (one && req.method === "PATCH") return void setStatus(one[1], req, res);
    if (one && req.method === "DELETE") return pass(req, res, (status) => void (status === 204 && docs.delete(one[1])));
    const asking = url.pathname.match(/^\/api\/documents\/([^/]+)\/ask$/);
    if (asking && req.method === "POST") return void ask(asking[1], req, res);
    // The one-shot scan (the frontend's fallback with MOCK_NO_STREAM=1) moves a new document to review too.
    const once = url.pathname.match(/^\/api\/documents\/([^/]+)\/redact$/);
    if (once && req.method === "POST")
      return pass(req, res, (status) => {
        const doc = docs.get(once[1]);
        if (status !== 200 || !doc) return;
        if (doc.status === "new") doc.status = "review";
        doc.updated_at = now();
      });
    const changed = url.pathname.match(/^\/api\/documents\/([^/]+)\/corrections$/);
    if (changed && req.method === "POST")
      return pass(req, res, (status, body) => {
        if (status !== 200) return;
        touch(changed[1]);
        return asScanned(changed[1], body);
      });
    pass(req, res);
  })
  .listen(PORT, "127.0.0.1", () => {
    console.log(`MuGuard mock stream on http://127.0.0.1:${PORT}, passing the rest to ${BACKEND.origin}`);
    console.log(`model ${MODEL_ON ? "on (fake)" : "off"}, ${PARTS} parts, failed part: ${ERROR_PART < 0 ? "none" : ERROR_PART + 1}${FAIL ? ", error event after two parts" : ""}${NO_STREAM ? ", no stream route" : ""}${IGNORE_RETRY ? ", ignores retry=failed" : ""}${NO_LIST ? ", no saved list (older backend)" : ""}${LEAVE_STOPS ? ", a scan stops when the browser leaves" : ""}`);
  });
