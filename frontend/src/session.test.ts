import { describe, expect, it } from "vitest";
import type { DocSummary, RedactResult, StoredDoc, StoredStatus } from "./api";
import { partsOf, retryScan, scanOf } from "./scan";
import { fromStored, fromSummary, fromTurn, mergeList, uiStatus, withOpened, type Session } from "./session";

// Invented data only.
const TEXT = "Tenant: Ada Fenwick 🙂\nPhone 07700 900461.";
const NAME = TEXT.indexOf("Ada");
const PHONE = TEXT.indexOf("07700");

// The backend counts the emoji as one character, the browser as two.
const result: RedactResult = {
  doc_id: "doc1",
  redacted_text: "Tenant: [PERSON_1] 🙂\nPhone [PHONE_1].",
  entities: [
    { start: NAME, end: NAME + 11, text: "Ada Fenwick", type: "PERSON", placeholder: "[PERSON_1]" },
    { start: PHONE - 1, end: PHONE - 1 + 12, text: "07700 900461", type: "PHONE", placeholder: "[PHONE_1]" },
  ],
  boxes: [],
  chunks: [
    { chunk_id: "doc1-c00", index: 0, start: 0, end: 21, mreq_id: "mreq_a", error: null, found: 1, latency_ms: 900, status: "ok" },
    { chunk_id: "doc1-c01", index: 1, start: 21, end: TEXT.length - 1, mreq_id: null, error: "TimeoutError", found: 0, latency_ms: null, status: "error" },
  ],
  stats: { PERSON: 1, PHONE: 1 },
  model: "on",
};

const stored = (extra: Partial<StoredDoc> = {}): StoredDoc => ({
  document: { doc_id: "doc1", kind: "text", filename: "tenancy.txt", text: TEXT, pages: [] },
  revision: 3,
  result,
  status: "approved",
  turns: [
    {
      turn_id: 7,
      created_at: "2026-10-24T18:02:00Z",
      question: "Who is the tenant?",
      answer: "The tenant is Ada Fenwick.",
      answer_with_placeholders: "The tenant is [PERSON_1].",
      unknown_placeholders: [],
      mreq_id: "mreq_t2",
    },
    {
      turn_id: 9,
      created_at: "2026-10-24T18:04:00Z",
      question: "And the landlord?",
      answer: "[PERSON_9] is not in the document.",
      answer_with_placeholders: "[PERSON_9] is not in the document.",
      unknown_placeholders: ["[PERSON_9]"],
      mreq_id: null,
    },
  ],
  ...extra,
});

const row = (doc_id: string, extra: Partial<DocSummary> = {}): DocSummary => ({
  doc_id,
  filename: `${doc_id}.pdf`,
  kind: "pdf",
  pages: 2,
  status: "review",
  created_at: "2026-10-24T17:00:00Z",
  updated_at: "2026-10-24T18:00:00Z",
  has_result: true,
  changes: 12,
  turns: 0,
  ...extra,
});

describe("uiStatus", () => {
  it.each<[StoredStatus | undefined, boolean, string]>([
    ["new", false, "new"],
    ["review", true, "review"],
    ["approved", true, "approved"],
    ["declined", true, "declined"],
    // a result stored before the backend kept a status, or an older backend with no status at all
    ["new", true, "review"],
    [undefined, true, "review"],
    [undefined, false, "new"],
    // no result: nothing to review or ask about, whatever the status says, so the page offers Scan
    ["review", false, "new"],
    ["approved", false, "new"],
    ["declined", false, "new"],
  ])("%s with a result %s shows %s", (status, hasResult, ui) => {
    expect(uiStatus(status, hasResult)).toBe(ui);
  });
});

describe("fromSummary", () => {
  it("makes a rail entry that opens on click, with no scan to replay", () => {
    const s = fromSummary(row("a1", { status: "approved", changes: 4, turns: 3 }));
    expect(s).toMatchObject({ id: "a1", filename: "a1.pdf", status: "approved", revealed: true, changes: 4, turns: [] });
    expect(s.doc).toBeUndefined();
    expect(s.at).toBe(Date.parse("2026-10-24T18:00:00Z"));
  });

  it("offers Scan for a document with no result", () => {
    expect(fromSummary(row("n1", { status: "new", has_result: false, changes: null })).status).toBe("new");
  });
});

describe("fromStored", () => {
  it("opens a stored document with its result revealed, its review status and its chat", () => {
    const s = fromStored(stored());
    expect(s).toMatchObject({ id: "doc1", filename: "tenancy.txt", status: "approved", revealed: true });
    expect(s.scan).toBeUndefined(); // nothing to sweep again
    // offsets moved to UTF-16 units, so the bars land on the values
    const [, phone] = s.result!.entities;
    expect(TEXT.slice(phone.start, phone.end)).toBe("07700 900461");
    expect(s.turns).toHaveLength(2);
    expect(s.turns[0]).toEqual({
      question: "Who is the tenant?",
      answer: {
        answer: "The tenant is Ada Fenwick.",
        answer_with_placeholders: "The tenant is [PERSON_1].",
        sent_text: result.redacted_text, // not stored per turn: what the AI sees now
        unknown_placeholders: [],
        mreq_id: "mreq_t2",
        turn_id: 7,
        created_at: "2026-10-24T18:02:00Z",
      },
    });
    expect(s.turns[1].answer?.unknown_placeholders).toEqual(["[PERSON_9]"]);
  });

  it("reads a document from an older backend, with no status and no turns", () => {
    const s = fromStored(stored({ status: undefined, turns: undefined }));
    expect(s.status).toBe("review");
    expect(s.turns).toEqual([]);
  });

  it("offers Scan when the scan never finished", () => {
    const s = fromStored(stored({ result: null, status: "new", turns: [] }));
    expect(s.status).toBe("new");
    expect(s.result).toBeUndefined();
  });
});

describe("mergeList", () => {
  const open = (id: string): Session => ({ ...fromStored(stored()), id, status: "scanning" });

  it("follows the backend's order and keeps what is open in this tab", () => {
    const mine = open("b2");
    const merged = mergeList([mine], [row("a1"), row("b2"), row("c3")]);
    expect(merged.map((s) => s.id)).toEqual(["a1", "b2", "c3"]);
    expect(merged[1]).toBe(mine);
    expect(merged[0].doc).toBeUndefined();
  });

  it("keeps a document opened while the list loaded on top", () => {
    const merged = mergeList([open("z9")], [row("a1")]);
    expect(merged.map((s) => s.id)).toEqual(["z9", "a1"]);
  });
});

describe("withOpened", () => {
  it("fills in a rail entry, and adds a deep-linked one the list does not have yet", () => {
    const opened = fromStored(stored());
    const filled = withOpened([fromSummary(row("doc1")), fromSummary(row("a1"))], opened);
    expect(filled.map((s) => s.id)).toEqual(["doc1", "a1"]);
    expect(filled[0]).toBe(opened);
    expect(withOpened([fromSummary(row("a1"))], opened).map((s) => s.id)).toEqual(["doc1", "a1"]);
  });

  it("does not overwrite a document that is already open here", () => {
    const here: Session = { ...fromStored(stored()), status: "scanning" };
    expect(withOpened([here], fromStored(stored()))[0]).toBe(here);
  });
});

describe("scanOf", () => {
  it("lets a reopened document retry only its failed part, with no pass replayed", () => {
    const s = fromStored(stored({ status: "review" }));
    const scan = retryScan(scanOf(s.result!));
    expect(scan.parts.map((p) => p.status)).toEqual(["ok", "pending"]);
    // the kept part has the order partsOf gave it on screen, so its pass counts as ended
    expect(scan.parts[0].order).toBe(partsOf(s)[0].order);
    expect(scan.seq).toBe(2);
  });
});

describe("fromTurn", () => {
  it("keeps the question as the AI received it", () => {
    const turn = fromTurn({ turn_id: 3, created_at: "2026-10-24T18:00:00.000Z", question: "When can Ada Fenwick leave?",
      sent_question: "When can [PERSON_1] leave?", answer: "Ada Fenwick can leave in May.",
      answer_with_placeholders: "[PERSON_1] can leave in May.", unknown_placeholders: [], mreq_id: null }, "Tenant: [PERSON_1]");
    expect(turn.question).toBe("When can Ada Fenwick leave?");
    expect(turn.answer?.sent_question).toBe("When can [PERSON_1] leave?");
    expect(turn.answer?.sent_text).toBe("Tenant: [PERSON_1]");
  });
});
