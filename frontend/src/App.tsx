import { useCallback, useEffect, useState } from "react";
import { api, type DocPayload, type Health, type User } from "./api";
import { AuthGate } from "./components/AuthGate";
import { AskPanel } from "./components/AskPanel";
import { DocumentPane } from "./components/DocumentPane";
import { Intake } from "./components/Intake";
import { Rail } from "./components/Rail";
import { Victory } from "./components/Victory";
import type { Session } from "./session";

const message = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");
const distinct = (s: Session) => new Set(s.result?.entities.map((e) => e.placeholder)).size;

export default function App() {
  return <AuthGate>{(user, logout) => <Workspace key={user.id} user={user} onLogout={logout} />}</AuthGate>;
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => Promise<void> }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [intake, setIntake] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [victory, setVictory] = useState<number | null>(null);

  const [checked, setChecked] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setChecked(true));
  }, []);

  // Only the document ID goes in browser history; content stays in the backend.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sample = params.get("sample");
    const id = params.get("doc");
    if (sample) {
      window.history.replaceState(null, "", "/app");
      void open(() => api.openSample(sample));
    } else if (id) {
      let cancelled = false;
      setBusy(true);
      api.document(id).then(({ document: doc, result }) => {
        if (cancelled) return;
        setSessions([{ id, doc, result: result ?? undefined,
          status: result ? "review" : "failed", revealed: false, at: Date.now(), turns: [],
          error: result ? undefined : "This document has not finished scanning. Retry to scan it." }]);
        setActiveId(id);
        setIntake(false);
      }).catch((e) => { if (!cancelled) setError(message(e)); })
        .finally(() => { if (!cancelled) setBusy(false); });
      return () => { cancelled = true; };
    }
  }, []);

  const update = useCallback((id: string, patch: (s: Session) => Partial<Session>) => {
    setSessions((all) => all.map((s) => (s.id === id ? { ...s, ...patch(s) } : s)));
  }, []);

  async function redact(id: string) {
    update(id, () => ({ status: "scanning", error: undefined, revealed: false }));
    try {
      const result = await api.redact(id);
      update(id, () => ({ status: "review", result }));
    } catch (e) {
      update(id, () => ({ status: "failed", error: message(e) }));
    }
  }

  async function open(load: () => Promise<DocPayload>) {
    setBusy(true);
    setError(null);
    try {
      const doc = await load();
      const session: Session = { id: doc.doc_id, doc, status: "scanning", revealed: false, at: Date.now(), turns: [] };
      setSessions((all) => [session, ...all]);
      setActiveId(doc.doc_id);
      window.history.replaceState(null, "", `/app?doc=${encodeURIComponent(doc.doc_id)}`);
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
  const askOpen = !showIntake && active?.status === "approved";
  const layout = askOpen
    ? "grid-rows-[auto_minmax(70vh,1fr)_minmax(420px,auto)] lg:grid-cols-[240px_minmax(0,1fr)_340px] xl:grid-cols-[270px_minmax(0,1fr)_400px]"
    : "grid-rows-[auto_minmax(70vh,1fr)] lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[270px_minmax(0,1fr)]";
  const revealedFor = useCallback((id: string) => () => update(id, () => ({ revealed: true })), [update]);

  return (
    <div className={`grid min-h-screen lg:h-screen lg:grid-rows-1 ${layout}`}>
      <Rail
        email={user.email}
        onLogout={onLogout}
        sessions={sessions}
        activeId={showIntake ? null : activeId}
        onSelect={(id) => {
          setActiveId(id);
          window.history.replaceState(null, "", `/app?doc=${encodeURIComponent(id)}`);
          setIntake(false);
        }}
        onNew={() => {
          window.history.replaceState(null, "", "/app");
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
          session={active}
          modelOn={health?.model === "on"}
          onRevealed={revealedFor(active.id)}
          onApprove={() => {
            update(active.id, () => ({ status: "approved" }));
            setVictory(distinct(active));
          }}
          onDecline={() => update(active.id, () => ({ status: "declined" }))}
          onRetry={() => redact(active.id)}
          onCorrect={async (action, text, type) => {
            const result = await api.correct(active.id, action, text, type);
            update(active.id, () => ({ result }));
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
