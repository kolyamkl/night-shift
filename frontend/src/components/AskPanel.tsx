import { useEffect, useRef, useState } from "react";
import { markValues } from "../redaction";
import { partsOf } from "../scan";
import type { Session } from "../session";
import { Button, Spinner, Tabs } from "../ui/kit";
import { Routing } from "./Routing";

function Placeholders({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[[A-Z_]+_\d+\])/g).map((part, i) =>
        /^\[[A-Z_]+_\d+\]$/.test(part) ? (
          <span key={i} className="bg-ink px-1 font-label text-[11px] text-signal-soft">
            {part.slice(1, -1)}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function AskPanel({ session, t2Model, onAsk }: {
  session: Session;
  t2Model: string | null;
  onAsk: (question: string) => Promise<void>;
}) {
  const [tab, setTab] = useState<"ask" | "sent">("ask");
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const thread = useRef<HTMLDivElement>(null);
  const turns = session.turns;
  const values = session.result?.entities.map((e) => e.text) ?? [];
  const lastSent = [...turns].reverse().find((t) => t.answer)?.answer;
  const parts = partsOf(session);

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight, behavior: "smooth" });
  }, [turns.length, pending]);

  async function send() {
    const q = question.trim();
    if (!q || pending) return;
    setQuestion("");
    setPending(true);
    try {
      await onAsk(q);
    } finally {
      setPending(false);
    }
  }

  return (
    <aside className="ask-in flex min-h-0 flex-col border-t-4 border-ink bg-bone lg:border-t-0 lg:border-l-4" aria-label="Ask an AI about this document">
      <div className="flex items-center justify-between gap-3 border-b-4 border-ink bg-paper px-4 py-3">
        <Tabs label="Ask panel" value={tab} options={[["ask", "Ask the AI"], ["sent", "What it sees"]]} onChange={setTab} />
      </div>

      {tab === "sent" ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <p className="px-label text-quiet">The only text the AI receives</p>
          <div className="mt-2 bg-paper p-3 font-serif text-[14px] leading-relaxed whitespace-pre-wrap px-frame-thin">
            <Placeholders text={lastSent?.sent_text ?? session.result?.redacted_text ?? ""} />
          </div>
          {lastSent && (
            <>
              <p className="mt-5 px-label text-quiet">Its last answer, before Veil put the values back</p>
              <div className="mt-2 bg-paper p-3 font-serif text-[14px] leading-relaxed px-frame-thin">
                <Placeholders text={lastSent.answer_with_placeholders} />
              </div>
            </>
          )}
          {parts.length > 0 && (
            <div className="mt-5">
              <Routing
                text={session.doc.text}
                parts={parts}
                model={session.scan?.model ?? session.result?.model ?? null}
                live={session.scan?.live ?? true}
              />
            </div>
          )}
        </div>
      ) : (
        <div ref={thread} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
          {turns.length === 0 && (
            <p className="text-[14px] text-quiet">
              Ask anything about this document. The AI gets the redacted copy; the answer comes back with the real names, highlighted.
            </p>
          )}
          {turns.map((t, i) => (
            <div key={i} className="flex flex-col gap-2">
              <p className="max-w-[90%] self-end bg-ink px-3 py-2 font-serif text-[15px] text-bone px-frame">{t.question}</p>
              {t.answer && (
                <div className="bg-paper p-3 px-frame">
                  <p className="font-serif text-[15px] leading-relaxed">
                    {markValues(t.answer.answer, values).map((p, j) =>
                      p.real ? (
                        <mark key={j} className="bg-signal/15 px-0.5 text-ink underline decoration-signal decoration-2 underline-offset-4">
                          {p.text}
                        </mark>
                      ) : (
                        <span key={j}>{p.text}</span>
                      ),
                    )}
                  </p>
                  <p className="mt-2 px-label text-[10px] text-quiet">
                    {t2Model ?? "AI"} · real values put back by Veil
                    {t.answer.unknown_placeholders.length > 0 && ` · ${t.answer.unknown_placeholders.join(", ")} not found`}
                  </p>
                </div>
              )}
              {t.error && <p className="bg-paper p-3 text-[14px] text-signal-deep px-frame px-frame-red">{t.error}</p>}
            </div>
          ))}
          {pending && (
            <p className="flex items-center gap-2 text-[14px] text-quiet">
              <Spinner label="Waiting for the answer" /> The AI is answering
            </p>
          )}
        </div>
      )}

      <form
        className="border-t-4 border-ink bg-paper p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <label htmlFor="question" className="sr-only">
          Ask about this document
        </label>
        <div className="px-field">
          <textarea
            id="question"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder="When is the rent due?"
          />
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="px-label text-[10px] text-quiet">Enter to send</span>
          <Button type="submit" variant="primary" size="sm" icon="right" loading={pending} disabled={!question.trim()}>
            Ask
          </Button>
        </div>
      </form>
    </aside>
  );
}
