import { useState } from "react";
import type { Part, PartStatus } from "../scan";
import { Icon, Spinner } from "../ui/kit";

const LABEL: Record<PartStatus, string> = {
  pending: "Reading",
  ok: "Checked",
  error: "Not checked",
  empty: "Blank, skipped",
  off: "Model off",
};

const MARK: Record<PartStatus, string> = {
  pending: "",
  ok: "bg-ink",
  error: "bg-signal",
  empty: "bg-stone",
  off: "bg-stone",
};

const lineOf = (text: string, offset: number) => {
  let n = 1;
  for (let i = 0; i < Math.min(offset, text.length); i++) if (text.charCodeAt(i) === 10) n++;
  return n;
};

function CopyId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="flex min-w-0 items-center gap-1.5 px-1 text-left hover:bg-mist"
      title="Copy the Mubit request id"
      onClick={() => {
        void navigator.clipboard?.writeText(id).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      <code className="truncate font-pixel text-[13px]">{id}</code>
      <Icon name={copied ? "check" : "clipboard"} size={1} />
      <span className="sr-only" aria-live="polite">{copied ? "Copied" : ""}</span>
    </button>
  );
}

// How each part of the document was read: status, time and the Mubit request id of each call.
export function Routing({ text, parts, model, live }: { text: string; parts: Part[]; model: "on" | "off" | null; live: boolean }) {
  return (
    <div className="@container">
      <p className="px-label text-quiet">How each part was read</p>
      <p className="mt-1 text-[13px] text-quiet">
        {model === "off"
          ? "The AI model did not run, so no part was sent to Mubit. Only the number rules ran."
          : "Each part went to the redaction model through Mubit as its own request. The request id finds it in the Mubit console."}
        {!live && " This backend sent the result in one piece, so the parts appear together."}
      </p>
      <ol className="mt-3 flex flex-col gap-1">
        {parts.map((p) => (
          <li
            key={p.index}
            className="grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 border-t-2 border-mist pt-1.5 text-[13px] @2xl:grid-cols-[28px_120px_120px_120px_minmax(0,1fr)]"
          >
            <span className="font-label text-[10px] text-quiet tabular-nums">{String(p.index + 1).padStart(2, "0")}</span>
            <span className="text-quiet tabular-nums">
              Lines {lineOf(text, p.start)} to {lineOf(text, Math.max(p.start, p.end - 1))}
            </span>
            <span className="flex items-center gap-2" title={p.status === "error" ? (p.error ?? undefined) : undefined}>
              {p.status === "pending" ? <Spinner label="Reading" /> : <i className={`inline-block h-2.5 w-2.5 ${MARK[p.status]}`} aria-hidden />}
              <span className={p.status === "error" ? "text-signal-deep" : ""}>{LABEL[p.status]}</span>
            </span>
            <span className="col-start-2 font-label text-[10px] text-quiet tabular-nums @2xl:col-start-auto">
              {p.latency_ms !== null ? `${(p.latency_ms / 1000).toFixed(1)} s` : ""}
              {p.status === "ok" ? ` · ${p.found} found` : ""}
            </span>
            <span className="col-span-2 col-start-2 min-w-0 @2xl:col-span-1 @2xl:col-start-auto">
              {p.mreq_id ? <CopyId id={p.mreq_id} /> : p.status === "error" && p.error ? <span className="block truncate text-[12px] text-quiet" title={p.error}>{p.error}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
