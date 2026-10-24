import type { AskResult, DocPayload, RedactResult } from "./api";
import type { Scan } from "./scan";

export type Status = "scanning" | "review" | "approved" | "declined" | "failed";

export type Turn = { question: string; answer?: AskResult; error?: string };

// UI state is in memory; the URL holds an opaque ID for reopening the encrypted backend record.
export type Session = {
  id: string;
  doc: DocPayload;
  status: Status;
  scan?: Scan; // the live scan: parts, values found so far, done
  result?: RedactResult; // offsets in UTF-16 units, like the document text in the browser
  error?: string;
  revealed: boolean;
  at: number;
  turns: Turn[];
};
