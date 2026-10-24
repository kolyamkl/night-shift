import type { AskResult, DocPayload, RedactResult } from "./api";

export type Status = "scanning" | "review" | "approved" | "declined" | "failed";

export type Turn = { question: string; answer?: AskResult; error?: string };

// UI state is in memory; the URL holds an opaque ID for reopening the encrypted backend record.
export type Session = {
  id: string;
  doc: DocPayload;
  status: Status;
  result?: RedactResult;
  error?: string;
  revealed: boolean;
  at: number;
  turns: Turn[];
};
