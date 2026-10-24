import type { AskResult, DocPayload, DocSummary, RedactResult, StoredDoc, StoredStatus, StoredTurn } from "./api";
import { resultInUnits, type Scan } from "./scan";

// "new": no redaction yet (never scanned, or a scan stopped when the person left), so the page offers Scan.
export type Status = "new" | "scanning" | "review" | "approved" | "declined" | "failed";

export type Turn = { question: string; answer?: AskResult; error?: string };

// UI state is in memory. The backend keeps each document, its result, review status and chat, encrypted;
// the URL holds only the open document's ID.
export type Session = {
  id: string;
  filename: string;
  doc?: DocPayload; // a document from the saved list has only its summary until it is opened
  status: Status;
  scan?: Scan; // the live scan: parts, values found so far, done
  result?: RedactResult; // offsets in UTF-16 units, like the document text in the browser
  error?: string;
  notice?: string; // a review step the backend could not save
  revealed: boolean;
  at: number;
  turns: Turn[];
  changes?: number | null; // from the saved list, until the document is opened
};

export type Open = Session & { doc: DocPayload };

// The saved list: "on" when the backend keeps every document with its review status and chat; "off" on an
// older backend without the list, where the rail holds only what was opened in this tab, as before.
export type Saved = "loading" | "on" | "off" | "error";
export const isOpen = (s: Session | null | undefined): s is Open => !!s?.doc;

// The page state for a stored status. Without a result there is nothing to review, whatever the status
// says, so the page offers Scan. A result stored before the backend kept a status is ready for review.
export function uiStatus(status: StoredStatus | undefined, hasResult: boolean): Status {
  if (!hasResult) return "new";
  return status === "approved" || status === "declined" ? status : "review";
}

const time = (iso: string) => Date.parse(iso) || 0;

// A row of the saved list: shown in the rail, opened when the person clicks it.
export function fromSummary(d: DocSummary): Session {
  return {
    id: d.doc_id,
    filename: d.filename,
    status: uiStatus(d.status, d.has_result),
    revealed: true,
    at: time(d.updated_at),
    turns: [],
    changes: d.changes,
  };
}

// A stored turn as the Ask panel shows it. Turns do not keep the text that was sent, so "What it sees"
// shows the current redacted text.
export function fromTurn(t: StoredTurn, sent: string): Turn {
  const { turn_id, created_at, question, sent_question, answer, answer_with_placeholders, unknown_placeholders, mreq_id } = t;
  return {
    question,
    answer: { answer, answer_with_placeholders, sent_text: sent, sent_question, unknown_placeholders, mreq_id, turn_id, created_at },
  };
}

// A stored document, opened: its result shown at once with no replay of the scan, and its chat.
export function fromStored(stored: StoredDoc): Open {
  const doc = stored.document;
  const result = stored.result ? resultInUnits(stored.result, doc.text) : undefined;
  return {
    id: doc.doc_id,
    filename: doc.filename,
    doc,
    status: uiStatus(stored.status, !!result),
    result,
    revealed: true,
    at: Date.now(),
    turns: (stored.turns ?? []).map((t) => fromTurn(t, result?.redacted_text ?? "")),
  };
}

// The saved list arriving: rows in the backend's order (most recently updated first). Documents already
// open in this tab keep their state; ones the list does not have yet (opened while it loaded) stay on top.
export function mergeList(sessions: Session[], list: DocSummary[]): Session[] {
  const listed = new Set(list.map((d) => d.doc_id));
  const have = new Map(sessions.map((s) => [s.id, s]));
  return [...sessions.filter((s) => !listed.has(s.id)), ...list.map((d) => have.get(d.doc_id) ?? fromSummary(d))];
}

// A document that finished loading. One that is already open here keeps its state (a scan or chat may
// have moved on since the request went out).
export function withOpened(sessions: Session[], opened: Open): Session[] {
  if (!sessions.some((s) => s.id === opened.id)) return [opened, ...sessions];
  return sessions.map((s) => (s.id === opened.id && !s.doc ? opened : s));
}
