import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Sample } from "../api";
import { Sprite } from "../sprites";
import { pictogramFor } from "../ui/icons";
import { Button, Chip, Icon, Spinner, TextArea } from "../ui/kit";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,.heic,.heif,.tif,.tiff,.webp,.txt,.eml,.md,.csv,.json";
const FIRST = 8;

// One sample per document type first, so the opening grid shows the range of documents.
function byVariety(list: Sample[]): Sample[] {
  const seen = new Set<string>();
  const first: Sample[] = [];
  const rest: Sample[] = [];
  for (const s of list) {
    (seen.has(s.kind) ? rest : first).push(s);
    seen.add(s.kind);
  }
  return [...first, ...rest];
}

function SampleCard({ sample, busy, opening, onOpen }: { sample: Sample; busy: boolean; opening: boolean; onOpen: () => void }) {
  const top = Object.entries(sample.types).sort((a, b) => b[1] - a[1]).slice(0, 3);
  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={busy}
      className={`sample-card px-frame relative flex min-w-0 flex-col bg-paper text-left ${opening ? "is-opening" : ""}`}
      aria-label={`Open sample: ${sample.label}, ${sample.title}`}
    >
      <span className="relative flex h-44 items-start justify-center overflow-hidden border-b-4 border-ink bg-mist pt-3">
        <img src={api.thumbUrl(sample.name)} alt="" width={120} height={170} loading="lazy" className="pixelated sample-thumb w-[150px] bg-white" />
        <span className="absolute top-2 left-2 bg-paper p-1 px-frame-thin">
          <Sprite rows={pictogramFor(sample.name)} scale={2} />
        </span>
        <span className="sample-open absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 bg-ink py-2 text-bone">
          {opening ? <Spinner label="Opening" /> : <Icon name="right" />}
          <span className="px-label">{opening ? "Opening" : "Open sample"}</span>
        </span>
      </span>
      <span className="flex flex-1 flex-col gap-1.5 p-3">
        <span className="text-[16px] leading-tight font-semibold">{sample.label}</span>
        <span className="line-clamp-2 font-serif text-[13px] leading-snug text-quiet">{sample.title}</span>
        <span className="mt-auto flex flex-wrap gap-1.5 pt-2">
          <Chip>{sample.pages === 1 ? "1 page" : `${sample.pages} pages`}</Chip>
          {sample.values !== null && <Chip tone="red">{sample.values} values</Chip>}
        </span>
        {top.length > 0 && (
          <span className="px-label text-[10px] text-quiet">{top.map(([t, n]) => `${t.replace("_", " ")} ${n}`).join(" · ")}</span>
        )}
      </span>
    </button>
  );
}

export function Intake({ busy, error, onFile, onText, onSample }: {
  busy: boolean;
  error: string | null;
  onFile: (f: File) => void;
  onText: (t: string) => void;
  onSample: (name: string) => void;
}) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [all, setAll] = useState(false);
  const [over, setOver] = useState(false);
  const [text, setText] = useState("");
  const [opening, setOpening] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const ordered = useMemo(() => byVariety(samples), [samples]);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => setSamples([]));
  }, []);
  useEffect(() => {
    if (!busy) setOpening(null);
  }, [busy]);

  return (
    <section className="min-h-0 overflow-y-auto bg-bone px-5 pt-8 pb-12 sm:px-10">
      <div className="mx-auto max-w-6xl">
        <h2 className="font-pixel text-[clamp(28px,3.4vw,40px)] leading-none font-bold">Hide the personal data in a document</h2>
        <p className="mt-3 max-w-[64ch] text-[16px] text-quiet">
          Drop a file or paste text. MuGuard blacks out names, addresses, account numbers and IDs line by line, and you approve every
          change before the AI you ask sees the document. It only ever sees the placeholders.
        </p>

        <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              const f = e.dataTransfer.files[0];
              if (f && !busy) onFile(f);
            }}
            className={`dropzone flex flex-col items-center justify-center gap-4 px-6 py-10 text-center ${over ? "is-over" : ""}`}
          >
            <span className={`dropzone-icon ${over ? "text-signal" : ""}`}>
              <Icon name="upload" size={5} />
            </span>
            <p className="font-pixel text-[22px] leading-tight font-bold">{over ? "Let go to open it" : busy ? "Opening the document" : "Drop a file here"}</p>
            <span className="flex flex-wrap justify-center gap-1.5">
              <Chip>PDF</Chip>
              <Chip>Photo</Chip>
              <Chip>EML</Chip>
              <Chip>TXT</Chip>
              <Chip>Up to 20 MB</Chip>
            </span>
            <Button variant="primary" size="lg" icon="file" loading={busy && !opening} onClick={() => input.current?.click()}>
              Choose a file
            </Button>
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              tabIndex={-1}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
                e.target.value = "";
              }}
            />
          </div>

          <form
            className="flex flex-col"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim() && !busy) onText(text);
            }}
          >
            <TextArea
              id="paste"
              label="Or paste text"
              rows={7}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste an email, a message or a contract clause"
            />
            <div className="mt-4 flex items-center gap-3">
              <Button type="submit" variant="dark" icon="clipboard" disabled={!text.trim()} loading={busy && !opening && !!text.trim()}>
                Hide personal data
              </Button>
              <span className="text-xs text-quiet">{text.trim() ? `${text.trim().length} characters` : ""}</span>
            </div>
          </form>
        </div>

        {error && (
          <p role="alert" className="mt-6 flex items-center gap-3 bg-paper px-4 py-3 px-frame px-frame-red text-signal-deep">
            <Icon name="close" />
            {error}
          </p>
        )}

        <div className="mt-12 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="font-pixel text-[24px] leading-none font-bold">Or try a sample</h3>
            <p className="mt-2 text-[14px] text-quiet">Synthetic documents with fake people. Each card shows page one and how many personal values it holds.</p>
          </div>
          {samples.length > FIRST && (
            <Button variant="ghost" size="sm" iconRight={all ? "up" : "down"} onClick={() => setAll((a) => !a)}>
              {all ? "Show fewer" : `Show all ${samples.length}`}
            </Button>
          )}
        </div>
        <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-6">
          {samples.length === 0 && <p className="text-quiet">No samples found. Start the backend to load them.</p>}
          {(all ? ordered : ordered.slice(0, FIRST)).map((s) => (
            <SampleCard
              key={s.name}
              sample={s}
              busy={busy}
              opening={opening === s.name}
              onOpen={() => {
                setOpening(s.name);
                onSample(s.name);
              }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
