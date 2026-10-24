import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocPayload, type Health, type StoredStatus, type User } from "./api";
import { AuthGate } from "./components/AuthGate";
import { AskPanel } from "./components/AskPanel";
import { DocumentPane, Opening } from "./components/DocumentPane";
import { Intake } from "./components/Intake";
import { Rail } from "./components/Rail";
import { Victory } from "./components/Victory";
import { applyEvent, emptyScan, resultInUnits, retryScan, scanOf } from "./scan";
import { fromStored, isOpen, mergeList, withOpened, type Saved, type Session, type Status } from "./session";

const message = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");
const distinct = (s: Session) => new Set(s.result?.entities.map((e) => e.placeholder)).size;
const docUrl = (id: string) => `/app?doc=${encodeURIComponent(id)}`;
// A new history entry, so the browser's Back returns to where the person was (the intake or another document).
const go = (url: string) => {
  if (window.location.pathname + window.location.search !== url) window.history.pushState(null, "", url);
};

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
  const [saved, setSaved] = useState<Saved>("loading");
  const [listRun, setListRun] = useState(0);
  // Documents being fetched to open: null while the request runs, else why it failed.
  const [fetching, setFetching] = useState<Record<string, string | null>>({});
  const streams = useRef(new Map<string, AbortController>());
  const visible = useRef<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setChecked(true));
  }, []);

  // Every document the person has, so going to the landing page and back, or a reload, loses nothing.
  // Each one is opened only when clicked.
  useEffect(() => {
    let cancelled = false;
    setSaved("loading");
    api.documents().then((list) => {
      if (cancelled) return;
      setSaved(list ? "on" : "off");
      if (list) setSessions((all) => mergeList(all, list));
    }).catch(() => { if (!cancelled) setSaved("error"); });
    return () => { cancelled = true; };
  }, [listRun]);

  // A stored document, opened: its result, review status and chat.
  async function openSaved(id: string) {
    setFetching((f) => ({ ...f, [id]: null }));
    try {
      const opened = fromStored(await api.document(id));
      setSessions((all) => withOpened(all, opened));
      setFetching(({ [id]: _, ...rest }) => rest);
    } catch (e) {
      setFetching((f) => ({ ...f, [id]: message(e) }));
    }
  }

  // Only the document ID goes in browser history; content stays in the backend.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sample = params.get("sample");
    const id = params.get("doc");
    if (sample) {
      window.history.replaceState(null, "", "/app");
      void open(() => api.openSample(sample));
    } else if (id) {
      setActiveId(id);
      setIntake(false);
      void openSaved(id);
    }
  }, []);

  // Back and Forward: the address says which document is open, or the intake when there is none.
  const known = useRef(sessions);
  known.current = sessions;
  useEffect(() => {
    const onPop = () => {
      const id = new URLSearchParams(window.location.search).get("doc");
      if (!id) {
        setIntake(true);
        setError(null);
        return;
      }
      setActiveId(id);
      setIntake(false);
      if (!known.current.find((s) => s.id === id)?.doc) void openSaved(id);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
    // openSaved only sets state, so the first render's copy is enough
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    update(id, (s) => {
      // A reopened document has its stored result but no scan yet: rebuild the scan so only failed parts sweep.
      const scan = s.scan ?? (s.result ? scanOf(s.result) : undefined);
      return run === "failed" && scan
        ? { status: "scanning", error: undefined, notice: undefined, revealed: false, scan: retryScan(scan) }
        : { status: "scanning", error: undefined, notice: undefined, revealed: false, result: undefined, scan: emptyScan(scan?.seq) };
    });
    try {
      await api.redactStream(
        id,
        {
          onEvent: (ev) => mine() && update(id, (s) => (isOpen(s) ? applyEvent(s, ev, visible.current === id) : {})),
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
      const session: Session = { id: doc.doc_id, filename: doc.filename, doc, status: "scanning", scan: emptyScan(), revealed: false, at: Date.now(), turns: [] };
      setSessions((all) => [session, ...all.filter((s) => s.id !== doc.doc_id)]);
      setActiveId(doc.doc_id);
      go(docUrl(doc.doc_id));
      setIntake(false);
      void redact(doc.doc_id);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  // Approve, Decline and Edit redactions are kept by the backend too, so they are still there after leaving.
  // The page changes at once; if the backend cannot save the step, the page goes back and says so.
  function review(id: string, status: Exclude<StoredStatus, "new">, back: Status) {
    update(id, () => ({ status, notice: undefined }));
    if (saved === "off") return;
    api.setStatus(id, status).catch((e) =>
      update(id, (s) => (s.status === status ? { status: back, notice: `Not saved. ${message(e)}` } : {})),
    );
  }

  // The backend stores each turn as it answers, so a new ask is simply added to the chat.
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
  const showIntake = intake || !activeId;
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

  const askOpen = !showIntake && isOpen(active) && active.status === "approved";
  const layout = askOpen
    ? "grid-rows-[auto_minmax(70vh,1fr)_minmax(420px,auto)] lg:grid-cols-[240px_minmax(0,1fr)_340px] xl:grid-cols-[270px_minmax(0,1fr)_400px]"
    : "grid-rows-[auto_minmax(70vh,1fr)] lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[270px_minmax(0,1fr)]";
  const revealedFor = useCallback((id: string) => () => update(id, () => ({ revealed: true })), [update]);

  return (
    <div className={`grid min-h-screen grid-cols-[minmax(0,1fr)] overflow-x-clip lg:h-screen lg:grid-rows-1 ${layout}`}>
      <Rail
        email={user.email}
        onLogout={onLogout}
        sessions={sessions}
        saved={saved}
        onReloadList={() => setListRun((n) => n + 1)}
        activeId={showIntake ? null : activeId}
        onSelect={(id) => {
          setActiveId(id);
          go(docUrl(id));
          setIntake(false);
          if (!sessions.find((s) => s.id === id)?.doc && fetching[id] !== null) void openSaved(id);
        }}
        onNew={() => {
          go("/app");
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
      ) : isOpen(active) ? (
        <DocumentPane
          key={`pane-${active.id}`}
          session={active}
          onRevealed={revealedFor(active.id)}
          onApprove={() => {
            review(active.id, "approved", "review");
            setVictory(distinct(active));
          }}
          onReopen={() => review(active.id, "review", "approved")}
          onDecline={() => review(active.id, "declined", "review")}
          onRetry={(only) => void redact(active.id, only)}
          onCorrect={async (action, text, type) => {
            const result = await api.correct(active.id, action, text, type);
            update(active.id, () => ({ result: resultInUnits(result, active.doc.text), notice: undefined }));
          }}
        />
      ) : (
        <Opening filename={active?.filename} error={fetching[activeId] ?? null} onRetry={() => void openSaved(activeId)} />
      )}
      {askOpen && (
        <AskPanel key={active.id} session={active} t2Model={health?.t2_model ?? null} onAsk={(q) => ask(active.id, q)} />
      )}
      {victory !== null && <Victory hidden={victory} onDone={() => setVictory(null)} />}
    </div>
  );
}
