import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocPayload, type Health } from "./api";
import { AskPanel } from "./components/AskPanel";
import { DocumentPane } from "./components/DocumentPane";
import { Intake } from "./components/Intake";
import { Rail } from "./components/Rail";
import { Victory } from "./components/Victory";
import { applyEvent, emptyScan, resultInUnits, retryScan } from "./scan";
import type { Session } from "./session";

const message = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");
const distinct = (s: Session) => new Set(s.result?.entities.map((e) => e.placeholder)).size;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [intake, setIntake] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [victory, setVictory] = useState<number | null>(null);

  const [checked, setChecked] = useState(false);
  const streams = useRef(new Map<string, AbortController>());
  const visible = useRef<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setChecked(true));
  }, []);

  // "Try a sample" on the landing page opens /app?sample=<file>; start it straight away.
  useEffect(() => {
    const sample = new URLSearchParams(window.location.search).get("sample");
    if (!sample) return;
    window.history.replaceState(null, "", "/app");
    void open(() => api.openSample(sample));
  }, []);

  const update = useCallback((id: string, patch: (s: Session) => Partial<Session>) => {
    setSessions((all) => all.map((s) => (s.id === id ? { ...s, ...patch(s) } : s)));
  }, []);

  // One live scan per document: every stream event updates the session as it arrives. A scan keeps
  // running while the person looks at another document or the intake; only closing the app stops it.
  // "failed" reads again only the parts the AI could not check; "all" starts the page over after a
  // failed run. Both ask the backend to reuse parts it already read (?retry=failed).
  async function redact(id: string, run: "first" | "failed" | "all" = "first") {
    streams.current.get(id)?.abort();
    const ctrl = new AbortController();
    streams.current.set(id, ctrl);
    const mine = () => streams.current.get(id) === ctrl && !ctrl.signal.aborted;
    update(id, (s) =>
      run === "failed" && s.scan
        ? { status: "scanning", error: undefined, revealed: false, scan: retryScan(s.scan) }
        : { status: "scanning", error: undefined, revealed: false, result: undefined, scan: emptyScan(s.scan?.seq) },
    );
    try {
      await api.redactStream(
        id,
        {
          onEvent: (ev) => mine() && update(id, (s) => applyEvent(s, ev, visible.current === id)),
          onFallback: () => mine() && update(id, (s) => ({ scan: { ...(s.scan ?? emptyScan()), live: false } })),
        },
        ctrl.signal,
        run === "first" ? undefined : { retry: "failed" },
      );
    } catch (e) {
      if (streams.current.get(id) !== ctrl || ctrl.signal.aborted) return; // a newer run took over, or the app closed
      update(id, () => ({ status: "failed", error: message(e) }));
    } finally {
      if (streams.current.get(id) === ctrl) streams.current.delete(id);
    }
  }

  async function open(load: () => Promise<DocPayload>) {
    setBusy(true);
    setError(null);
    try {
      const doc = await load();
      const session: Session = { id: doc.doc_id, doc, status: "scanning", scan: emptyScan(), revealed: false, at: Date.now(), turns: [] };
      setSessions((all) => [session, ...all]);
      setActiveId(doc.doc_id);
      setIntake(false);
      void redact(doc.doc_id);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function ask(id: string, question: string) {
    update(id, (s) => ({ turns: [...s.turns, { question }] }));
    const settle = (patch: object) =>
      update(id, (s) => ({ turns: s.turns.map((t, i) => (i === s.turns.length - 1 ? { ...t, ...patch } : t)) }));
    try {
      settle({ answer: await api.ask(id, question) });
    } catch (e) {
      settle({ error: message(e) });
    }
  }

  const active = sessions.find((s) => s.id === activeId) ?? null;
  const showIntake = intake || !active;
  const visibleId = showIntake ? null : activeId;

  // Leaving a document mid-pass: its scan carries on, but nobody is watching the pass, so its review is
  // ready when the person comes back (and the rail says so).
  useEffect(() => {
    const left = visible.current;
    visible.current = visibleId;
    if (left && left !== visibleId) update(left, (s) => (s.status === "review" && !s.revealed ? { revealed: true } : {}));
  }, [visibleId, update]);
  useEffect(() => {
    const all = streams.current;
    return () => all.forEach((ctrl) => ctrl.abort());
  }, []);

  const askOpen = !showIntake && active?.status === "approved";
  const layout = askOpen
    ? "grid-rows-[auto_minmax(70vh,1fr)_minmax(420px,auto)] lg:grid-cols-[240px_minmax(0,1fr)_340px] xl:grid-cols-[270px_minmax(0,1fr)_400px]"
    : "grid-rows-[auto_minmax(70vh,1fr)] lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[270px_minmax(0,1fr)]";
  const revealedFor = useCallback((id: string) => () => update(id, () => ({ revealed: true })), [update]);

  return (
    <div className={`grid min-h-screen grid-cols-[minmax(0,1fr)] lg:h-screen lg:grid-rows-1 ${layout}`}>
      <Rail
        sessions={sessions}
        activeId={showIntake ? null : activeId}
        onSelect={(id) => {
          setActiveId(id);
          setIntake(false);
        }}
        onNew={() => {
          setIntake(true);
          setError(null);
        }}
        modelOn={checked ? health?.model === "on" : null}
      />
      {showIntake ? (
        <Intake
          busy={busy}
          error={error}
          onFile={(f) => open(() => api.upload(f))}
          onText={(t) => open(() => api.paste(t))}
          onSample={(name) => open(() => api.openSample(name))}
        />
      ) : (
        <DocumentPane
          key={`pane-${active.id}`}
          session={active}
          onRevealed={revealedFor(active.id)}
          onApprove={() => {
            update(active.id, () => ({ status: "approved" }));
            setVictory(distinct(active));
          }}
          onDecline={() => update(active.id, () => ({ status: "declined" }))}
          onRetry={(only) => void redact(active.id, only)}
          onCorrect={async (action, text, type) => {
            const result = await api.correct(active.id, action, text, type);
            update(active.id, (s) => ({ result: resultInUnits(result, s.doc.text) }));
          }}
        />
      )}
      {askOpen && (
        <AskPanel key={active.id} session={active} t2Model={health?.t2_model ?? null} onAsk={(q) => ask(active.id, q)} />
      )}
      {victory !== null && <Victory hidden={victory} onDone={() => setVictory(null)} />}
    </div>
  );
}
