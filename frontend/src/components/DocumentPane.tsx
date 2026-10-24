import { Fragment, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { api, pageScale } from "../api";
import { changeList, stepMs, toLines, type Line } from "../redaction";
import { advancePasses, hiddenSoFar, liveEntities, partAt, partLines, partsOf, passesDone, settledPasses, sweeping as sweepingAny, withLive } from "../scan";
import type { Open } from "../session";
import { Button, Chip, Icon, LinkButton, Spinner, Tabs } from "../ui/kit";
import { Routing } from "./Routing";

const TYPES: [string, string][] = [
  ["CUSTOM", "Client or case reference"], ["PERSON", "Person"], ["ADDRESS", "Address"], ["POSTCODE", "Postcode"],
  ["EMAIL", "Email"], ["PHONE", "Phone"], ["DOB", "Date of birth"], ["BANK_ACCOUNT", "Account number"],
  ["SORT_CODE", "Sort code"], ["IBAN", "IBAN"], ["CARD", "Card number"], ["NI_NUMBER", "NI number"], ["ID_DOC", "ID document"],
  ["IP_ADDRESS", "IP address"],
];

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const isHeading = (t: string) => t.length > 0 && t.length < 60 && /[A-Z]/.test(t) && t === t.toUpperCase();
const lineText = (l: Line) => l.segments.map((s) => s.text).join("");
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// A page image is fetched only when it comes within one screen of view: a scan of many photo-sized pages
// would otherwise render every page at once. Width and height give the page its shape before it loads.
function PageImage({ src, width, height, alt, scroller }: { src: string; width: number; height: number; alt: string; scroller: RefObject<HTMLDivElement | null> }) {
  const ref = useRef<HTMLImageElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (near || !el) return;
    // The document pane scrolls on its own on wide screens; on phones the whole page scrolls.
    const pane = scroller.current;
    const root = pane && pane.scrollHeight > pane.clientHeight + 1 ? pane : null;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setNear(true), { root, rootMargin: "100% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [near, scroller]);
  return <img ref={ref} src={near ? src : undefined} width={width} height={height} decoding="async" alt={alt} className="block h-auto w-full" />;
}

type Pop = { entity: number; x: number; y: number };
type Pick = { text: string; x: number; y: number };

export function DocumentPane({ session, onRevealed, onApprove, onReopen, onDecline, onRetry, onCorrect }: {
  session: Open;
  onRevealed: () => void;
  onApprove: () => void;
  onReopen: () => void;
  onDecline: () => void;
  onRetry: (only: "failed" | "all") => void;
  onCorrect: (action: "hide" | "unhide", text: string, type?: string) => Promise<void>;
}) {
  const { doc, result, status, scan } = session;
  // Until the final result arrives, the page shows what the stream has found so far. On a retry the
  // earlier result stays up, plus what the parts read again find.
  const found = scan?.entities;
  const retrying = status === "scanning" && !!result;
  const entities = useMemo(() => {
    const live = liveEntities(found ?? [], doc.text);
    if (!result) return live;
    return retrying ? withLive(result.entities, live) : result.entities;
  }, [result, found, doc.text, retrying]);
  const lines = useMemo(() => toLines(doc.text, entities), [doc.text, entities]);
  const changes = useMemo(() => changeList(lines), [lines]);
  const parts = useMemo(() => partsOf(session), [session.scan, session.result]);
  const spans = useMemo(() => partLines(parts, lines.map((l) => l.start)), [parts, lines]);
  const partOfLine = useMemo(() => lines.map((l) => partAt(parts, l.start)), [lines, parts]);
  const done = session.revealed || status === "approved" || status === "declined";
  const idle = status === "new" || status === "failed"; // no redaction to show: Scan or Try again
  const editable = status === "review" && session.revealed;

  // Parts read while this document was off screen start out swept: no replay of passes that ended.
  const [passes, setPasses] = useState(() => settledPasses(parts, spans));
  const [view, setView] = useState<"lines" | "pages">("lines");
  const [routing, setRouting] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const [pop, setPop] = useState<Pop | null>(null);
  const [pick, setPick] = useState<Pick | null>(null);
  const [pickType, setPickType] = useState("CUSTOM");
  const [note, setNote] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [fixing, setFixing] = useState(false);
  const lineEls = useRef<(HTMLDivElement | null)[]>([]);
  const body = useRef<HTMLDivElement>(null);
  const revealed = useRef(onRevealed);
  revealed.current = onRevealed;
  const latest = useRef({ parts, spans });
  latest.current = { parts, spans };

  // The pass, driven by real events: when a part comes back, its lines are swept one per tick, its values
  // flash and turn into bars. Parts finish out of order, so several passes can run at once. A part that
  // comes back unchanged on a retry keeps its pass, so only the parts read again sweep.
  const sweeping = !done && sweepingAny(passes, parts, spans);
  const step = stepMs(lines.length);
  useEffect(() => {
    if (!sweeping) return;
    const calm = reducedMotion();
    const tick = () => setPasses((c) => advancePasses(c, latest.current.parts, latest.current.spans, calm));
    tick();
    if (calm) return;
    const timer = window.setInterval(tick, step);
    return () => window.clearInterval(timer);
  }, [sweeping, step]);

  // Follow the pass that started last.
  useEffect(() => {
    if (done) return;
    const { parts, spans } = latest.current;
    const moving = parts
      .filter((p) => passes[p.index]?.order === p.order && passes[p.index].at <= (spans.get(p.index)?.[1] ?? -1))
      .sort((a, b) => (b.order ?? 0) - (a.order ?? 0))[0];
    if (moving) lineEls.current[passes[moving.index].at]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [passes, done]);

  // The review bar comes up once the backend is done and the last pass has ended.
  const settled = status === "review" && !session.revealed && passesDone(passes, parts, spans);
  useEffect(() => {
    if (!settled) return;
    const t = window.setTimeout(() => revealed.current(), reducedMotion() ? 0 : 250);
    return () => window.clearTimeout(t);
  }, [settled]);

  const total = parts.length;
  const finished = parts.filter((p) => p.status !== "pending").length;
  const unchecked = parts.filter((p) => p.status === "error");
  const modelOff = (scan?.model ?? result?.model) === "off";
  const hidden = done ? changes.length : hiddenSoFar(entities, parts, retrying ? result?.entities : undefined);
  const progress = total ? finished / total : 0;
  const distinct = new Set(result?.entities.map((e) => e.placeholder)).size;
  const why = unchecked.map((p) => p.error).filter(Boolean).join("; ");
  const statusNote = modelOff
    ? "Numbers only for now. The AI model did not run, so check names and addresses yourself."
    : unchecked.length
      ? `${plural(unchecked.length, "part")} not checked by the AI. Check those lines yourself, or retry.`
      : "Check the changes. Missed one? Use Fix a miss.";

  function goTo(next: number) {
    if (!changes.length) return;
    const i = (next + changes.length) % changes.length;
    setFocus(i);
    body.current?.querySelector(`[data-entity="${changes[i].entity}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  async function correct(action: "hide" | "unhide", text: string, type?: string) {
    setWorking(true);
    try {
      await onCorrect(action, text, type);
      setNote(action === "hide" ? "Hidden. The AI gets a placeholder." : "Shown. The AI will see this value.");
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setWorking(false);
      setFixing(false);
      setPop(null);
      setPick(null);
      window.getSelection()?.removeAllRanges();
    }
  }

  function onMouseUp() {
    if (!editable) return;
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    if (!sel || !text || !body.current?.contains(sel.anchorNode)) return setPick(null);
    if (text.includes("\n")) return setNote("Select text within one line, then press Hide.");
    const r = sel.getRangeAt(0).getBoundingClientRect();
    setPop(null);
    setPick({ text, x: r.left, y: r.bottom + 10 });
  }

  const popEntity = pop ? entities[pop.entity] : null;

  return (
    <section className="relative flex min-h-0 flex-col bg-bone">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-4 border-ink bg-paper px-5 py-3.5">
        <h2 className="min-w-0 max-w-full truncate font-pixel text-[22px] leading-tight font-bold" title={doc.filename}>
          {doc.filename}
        </h2>
        <Chip>{status === "new" ? "Not scanned" : status === "failed" ? "Not finished" : status === "scanning" && !finished ? "Reading" : plural(hidden, "change")}</Chip>
        {modelOff && !idle && <Chip>Numbers only</Chip>}
        {unchecked.length > 0 && !idle && (
          <span title={why || undefined}>
            <Chip tone="red">{plural(unchecked.length, "part")} not checked by the AI</Chip>
          </span>
        )}
        <span className="ml-auto flex items-center gap-3">
          {doc.kind === "pdf" && done && !idle && (
            <Tabs
              label="View"
              value={view}
              options={[["lines", "Lines"], ["pages", "Pages"]]}
              onChange={(v) => {
                setView(v);
                body.current?.scrollTo({ top: 0 });
              }}
            />
          )}
          {!done && !idle && (
            <span className="relative block h-3 w-[142px] text-stone/40 segments" role="progressbar" aria-label="Parts read" aria-valuenow={Math.round(progress * 100)}>
              <span
                className={`absolute inset-y-0 left-0 block text-signal segments ${!total ? "indeterminate w-full" : ""}`}
                style={!total ? undefined : { width: `${progress * 100}%`, transition: "width .3s ease-out" }}
              />
            </span>
          )}
          {total > 0 && (
            <button type="button" className="px-tab tabular-nums" aria-expanded={routing} aria-controls="routing" onClick={() => setRouting((r) => !r)}>
              {done || finished === total ? plural(total, "part") : `${finished}/${total} parts`}
            </button>
          )}
        </span>
      </header>

      {routing && (
        <div id="routing" className="max-h-[42vh] overflow-y-auto border-b-4 border-ink bg-paper px-5 py-4">
          <Routing text={doc.text} parts={parts} model={scan?.model ?? result?.model ?? null} live={scan?.live ?? true} />
        </div>
      )}

      <div ref={body} onMouseUp={onMouseUp} className={`relative min-h-0 flex-1 overflow-y-auto px-3 pt-6 pb-8 sm:px-6 lg:pb-44 ${fixing ? "cursor-quill" : ""}`}>
        {modelOff && !idle && view === "lines" && (
          <p className="mx-auto mb-4 flex max-w-[860px] items-center gap-2 bg-paper px-3 py-2 text-[14px] px-frame-thin">
            <span className="inline-block h-2.5 w-2.5 shrink-0 bg-stone" aria-hidden />
            Numbers only for now. The AI model did not run, so names and addresses were not looked for.
          </p>
        )}
        {status === "new" ? (
          <div className="mx-auto max-w-[760px] bg-paper p-5 px-frame">
            <p className="font-semibold">Not scanned yet.</p>
            <p className="mt-1 text-quiet">Scan it to find the personal data, then review what MuGuard hides.</p>
            <Button className="mt-4" variant="primary" icon="right" onClick={() => onRetry("all")}>
              Scan
            </Button>
          </div>
        ) : status === "failed" ? (
          <div className="mx-auto max-w-[760px] bg-paper p-5 px-frame px-frame-red">
            <p className="font-semibold text-signal-deep">The redaction did not finish.</p>
            <p className="mt-1 text-quiet">{session.error}</p>
            <Button className="mt-4" icon="right" onClick={() => onRetry("all")}>
              Try again
            </Button>
          </div>
        ) : view === "pages" ? (
          <div className="flex flex-col items-center gap-8">
            {doc.pages.map((p, n) => {
              const scale = pageScale(p);
              return (
                <div key={n} className="relative w-full max-w-[760px] bg-white px-frame">
                  <PageImage
                    src={api.pageUrl(doc.doc_id, n, scale)}
                    width={Math.round(p.width * scale)}
                    height={Math.round(p.height * scale)}
                    alt={`Page ${n + 1} with personal data covered`}
                    scroller={body}
                  />
                  {result?.boxes.filter((b) => b.page === n).map((b, i) => (
                    <span key={i} title={b.placeholder} className="absolute bg-ink"
                      style={{ left: `${(b.x0 / p.width) * 100}%`, top: `${(b.y0 / p.height) * 100}%`, width: `${((b.x1 - b.x0) / p.width) * 100}%`, height: `${((b.y1 - b.y0) / p.height) * 100}%` }} />
                  ))}
                </div>
              );
            })}
          </div>
        ) : (
          <article className="paper-sheet mx-auto max-w-[860px] bg-paper py-6 px-frame" aria-label="Document text">
            {lines.map((line) => {
              const text = lineText(line);
              const part = partOfLine[line.index];
              const span = part ? spans.get(part.index) : undefined;
              const first = !!part && span?.[0] === line.index;
              const failed = part?.status === "error";
              const noteRow = failed && first && (
                <div className="grid grid-cols-[48px_12px_1fr] items-center" title={part.error ?? undefined}>
                  <span />
                  <i className="unchecked-mark block h-full min-h-[30px] w-1" />
                  <span className="flex flex-wrap items-center gap-2 py-1.5 pr-6">
                    <Chip tone="red">Not checked by the AI</Chip>
                    <span className="text-[13px] text-quiet">
                      {span[0] === span[1] ? `Line ${span[0] + 1}` : `Lines ${span[0] + 1} to ${span[1] + 1}`}. Only the number rules ran here.
                    </span>
                    {status === "review" && (
                      <Button size="sm" variant="ghost" icon="right" onClick={() => onRetry("failed")}>
                        Retry
                      </Button>
                    )}
                  </span>
                </div>
              );
              if (!text.trim()) return <Fragment key={line.index}>{noteRow}<div className="h-3" /></Fragment>;
              const at = part ? passes[part.index]?.at : undefined;
              const reading = status === "scanning" && (!part || part.status === "pending");
              const current = !done && at === line.index;
              const passed = done || (at !== undefined && line.index <= at);
              const cls = [
                "doc-line grid grid-cols-[48px_12px_1fr] items-center",
                reading ? "is-reading" : "",
                current ? "is-current" : "",
                passed ? "is-passed" : "",
                failed ? "is-unchecked" : "",
              ].join(" ");
              return (
                <Fragment key={line.index}>
                  {noteRow}
                  <div
                    ref={(el) => { lineEls.current[line.index] = el; }}
                    className={cls}
                    style={{ ["--i" as string]: line.index - (span?.[0] ?? 0) }}
                    title={failed ? `Not checked by the AI${part.error ? `: ${part.error}` : ""}` : undefined}
                  >
                    <span className="pr-3 text-right font-label text-[10px] text-quiet tabular-nums">{String(line.index + 1).padStart(2, "0")}</span>
                    <i className={`gutter-mark block h-[22px] w-1 ${line.changes ? "bg-signal" : ""}`} />
                    <span className={`min-h-[30px] py-1 pr-6 leading-[22px] whitespace-pre-wrap ${isHeading(text.trim()) ? "font-serif text-[13px] font-semibold tracking-[0.06em]" : "font-serif text-[15px]"}`}>
                      {line.segments.map((s, i) =>
                        s.kind === "text" ? (
                          <Fragment key={i}>{s.text}</Fragment>
                        ) : (
                          <button
                            key={i}
                            type="button"
                            data-entity={s.entity}
                            data-p={s.placeholder.replace(/[[\]]/g, "")}
                            style={{ ["--tag" as string]: `${s.placeholder.length * 7 + 2}px` }}
                            tabIndex={editable ? 0 : -1}
                            aria-label={passed ? `${s.placeholder}, hidden` : undefined}
                            onClick={(e) => {
                              if (!editable) return;
                              const r = e.currentTarget.getBoundingClientRect();
                              setPick(null);
                              setPop({ entity: s.entity, x: r.left, y: r.bottom + 10 });
                            }}
                            className={[
                              "val",
                              passed ? "is-hidden" : "",
                              current ? "is-flash" : "",
                              editable ? "is-live" : "",
                              focus !== null && changes[focus]?.entity === s.entity ? "is-focus" : "",
                            ].join(" ")}
                          >
                            {s.text}
                          </button>
                        ),
                      )}
                    </span>
                  </div>
                </Fragment>
              );
            })}
          </article>
        )}
      </div>

      {popEntity && pop && (
        <div role="dialog" aria-label="Hidden value" className="pop fixed z-30 w-72 bg-paper p-3 px-frame" style={{ left: pop.x, top: pop.y }}>
          <p className="px-label text-signal-deep">{popEntity.placeholder.replace(/[[\]]/g, "")}</p>
          <p className="mt-1 font-serif text-[16px] break-words">{popEntity.text}</p>
          <p className="mt-2 text-xs text-quiet">Only you see this value. The AI gets the placeholder.</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" icon="eye" disabled={working} onClick={() => correct("unhide", popEntity.text)}>
              Not personal, show it
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPop(null)}>
              Close
            </Button>
          </div>
        </div>
      )}

      {pick && (
        <div role="dialog" aria-label="Hide selected text" className="pop fixed z-30 flex flex-wrap items-center gap-2 bg-paper p-2 px-frame" style={{ left: pick.x, top: pick.y }}>
          <span className="max-w-48 truncate font-serif">“{pick.text}”</span>
          <label className="sr-only" htmlFor="pick-type">Type</label>
          <select id="pick-type" value={pickType} onChange={(e) => setPickType(e.target.value)} className="px-frame-thin bg-bone px-1.5 py-1 text-[13px]">
            {TYPES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <Button size="sm" variant="primary" icon="marker" loading={working} onClick={() => correct("hide", pick.text, pickType)}>
            Hide
          </Button>
        </div>
      )}

      {status === "review" && (
        <div className={`review-bar sticky bottom-3 mx-3 mb-3 lg:absolute lg:right-4 lg:bottom-4 lg:left-4 lg:mx-0 lg:mb-0 z-20 flex flex-col gap-3 bg-ink px-4 py-3 text-bone px-frame ${session.revealed ? "is-up" : ""}`}>
          <p className={`min-w-0 truncate text-[14px] ${fixing ? "font-semibold text-signal-soft" : "text-bone/85"}`} aria-live="polite">
            {fixing ? "Select the missed text on the page, then press Hide." : (session.notice ?? note ?? statusNote)}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <span className="mr-auto font-label text-[12px] whitespace-nowrap tabular-nums">
              {plural(changes.length, "change")} · {plural(distinct, "value")}
            </span>
            <Button size="sm" icon="up" onClick={() => goTo((focus ?? 0) - 1)}>Prev</Button>
            <Button size="sm" icon="down" onClick={() => goTo(focus === null ? 0 : focus + 1)}>Next</Button>
            <Button size="sm" icon="marker" aria-pressed={fixing} onClick={() => setFixing((f) => !f)}>Fix a miss</Button>
            <Button size="sm" variant="ghost" icon="close" onClick={onDecline}>Decline</Button>
            <Button variant="primary" icon="check" onClick={onApprove}>Approve all</Button>
          </div>
        </div>
      )}
      {status === "approved" && (
        <div className="sticky bottom-3 mx-3 mb-3 lg:absolute lg:right-4 lg:bottom-4 lg:left-4 lg:mx-0 lg:mb-0 z-20 flex flex-wrap items-center gap-3 bg-paper px-4 py-3 px-frame">
          {session.notice ? (
            <span role="alert" className="mr-auto text-[15px] text-signal-deep">{session.notice}</span>
          ) : (
            <span className="mr-auto flex items-center gap-2 text-[15px]">
              <Icon name="check" className="text-signal" />
              Approved. Ask about it on the right; the AI only sees the placeholders.
            </span>
          )}
          <Button size="sm" icon="marker" onClick={onReopen}>Edit redactions</Button>
          <LinkButton href={api.fileUrl(doc.doc_id)} download variant="dark" icon="download">
            Download redacted {doc.kind === "pdf" ? "PDF" : "text"}
          </LinkButton>
        </div>
      )}
      {status === "declined" && (
        <div className="sticky bottom-3 mx-3 mb-3 lg:absolute lg:right-4 lg:bottom-4 lg:left-4 lg:mx-0 lg:mb-0 z-20 flex items-center gap-2 bg-paper px-4 py-3 px-frame">
          <Icon name="close" />
          Declined. Nothing from this document was sent to the AI provider.
        </div>
      )}
    </section>
  );
}

// A saved document while it loads, or why it did not.
export function Opening({ filename, error, onRetry }: { filename?: string; error: string | null; onRetry: () => void }) {
  return (
    <section className="relative flex min-h-0 flex-col bg-bone">
      <header className="flex min-h-[64px] items-center border-b-4 border-ink bg-paper px-5 py-3.5">
        {filename && (
          <h2 className="min-w-0 max-w-full truncate font-pixel text-[22px] leading-tight font-bold" title={filename}>
            {filename}
          </h2>
        )}
      </header>
      <div className="px-3 pt-6 sm:px-6">
        {error ? (
          <div className="mx-auto max-w-[760px] bg-paper p-5 px-frame px-frame-red" role="alert">
            <p className="font-semibold text-signal-deep">This document did not open.</p>
            <p className="mt-1 text-quiet">{error}</p>
            <Button className="mt-4" icon="right" onClick={onRetry}>
              Try again
            </Button>
          </div>
        ) : (
          <p className="mx-auto flex max-w-[760px] items-center gap-3 text-[15px] text-quiet">
            <Spinner label="Opening the document" /> Opening the document
          </p>
        )}
      </div>
    </section>
  );
}
