import type { Session } from "../session";
import { Sprite } from "../sprites";
import { pictogramFor } from "../ui/icons";
import { Button, Chip, Spinner } from "../ui/kit";

function Status({ s, on }: { s: Session; on: boolean }) {
  const changes = s.result?.entities.length ?? 0;
  const hidden = s.result ? new Set(s.result.entities.map((e) => e.placeholder)).size : 0;
  if (s.status === "scanning" || (s.status === "review" && !s.revealed))
    return (
      <span className={`flex items-center gap-2 text-xs ${on ? "text-signal-soft" : "text-signal-deep"}`}>
        <Spinner label="Working" />
        {s.status === "scanning" ? reading(s) : "Redacting"}
      </span>
    );
  if (s.status === "review") return <Chip tone="red">Review · {changes} changes</Chip>;
  if (s.status === "approved") return <Chip tone="dark">Approved · {hidden} hidden</Chip>;
  if (s.status === "declined") return <Chip>Declined</Chip>;
  return <Chip tone="red">Failed</Chip>;
}

function reading(s: Session) {
  const parts = s.scan?.parts ?? [];
  if (!parts.length) return "Reading";
  return `Reading ${parts.filter((p) => p.status !== "pending").length}/${parts.length}`;
}

export function Rail({ sessions, activeId, onSelect, onNew, modelOn }: {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  modelOn: boolean | null;
}) {
  const model = modelOn === null ? "Checking" : modelOn ? "Mubit adapter, plus rules" : "Rules only";
  const short = modelOn === null ? "Checking" : modelOn ? "Model on" : "Model off"; // the phone row fits about 9 characters
  return (
    <aside className="flex min-h-0 flex-col gap-3 border-b-4 border-ink bg-bone px-4 py-3 lg:gap-5 lg:border-r-4 lg:border-b-0 lg:pt-5 lg:pb-4">
      <div className="flex items-center gap-2 lg:flex-col lg:items-stretch lg:gap-5">
        <a href="/" className="font-pixel text-[30px] leading-none font-bold lg:text-[38px]" aria-label="Veil home">
          Veil
        </a>
        <Chip className="lg:hidden">{short}</Chip>
        <Button variant="primary" icon="plus" onClick={onNew} className="ml-auto lg:ml-0 lg:w-full">
          New document
        </Button>
      </div>

      {sessions.length > 0 && (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 lg:hidden" aria-label="Documents in this session">
          {sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={s.id === activeId ? "true" : undefined}
              className={`session px-frame flex shrink-0 items-center gap-2 px-2 py-1.5 text-[13px] ${s.id === activeId ? "is-on bg-ink text-bone" : "px-frame-bone"}`}
            >
              <Sprite rows={pictogramFor(s.doc.filename)} scale={1} />
              <span className="max-w-[140px] truncate">{s.doc.filename}</span>
            </button>
          ))}
        </div>
      )}

      <nav className="-mx-1 hidden min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-1 pt-1 pb-2 lg:flex" aria-label="Documents in this session">
        <p className="px-label text-quiet">Sessions</p>
        {sessions.length === 0 && <p className="text-[14px] text-quiet">Documents you open appear here. They stay in this browser tab only.</p>}
        {sessions.map((s) => {
          const on = s.id === activeId;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={on ? "true" : undefined}
              className={`session px-frame grid grid-cols-[36px_minmax(0,1fr)] items-start gap-x-3 gap-y-1.5 p-2.5 text-left ${on ? "is-on bg-ink text-bone" : "px-frame-bone"}`}
            >
              <span className="row-span-2 bg-paper p-[2px]">
                <Sprite rows={pictogramFor(s.doc.filename)} scale={2} />
              </span>
              <b className="truncate text-[14px] font-semibold">{s.doc.filename}</b>
              <Status s={s} on={on} />
            </button>
          );
        })}
      </nav>

      <div className="hidden bg-paper px-3 py-2.5 px-frame-thin lg:block">
        <p className="px-label text-quiet">Redaction model</p>
        <p className="mt-1 flex items-center gap-2 text-[14px]">
          <span className={`inline-block h-2.5 w-2.5 ${modelOn ? "bg-signal" : "bg-stone"}`} aria-hidden />
          {model}
        </p>
        {modelOn === false && <p className="mt-1 text-xs text-quiet">Numbers only for now. Names and addresses need the Mubit model, which is not connected.</p>}
      </div>
    </aside>
  );
}
