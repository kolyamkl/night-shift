import { animate, motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { KNIGHT_SMALL, Sprite } from "../sprites";
import { Button, LinkButton } from "../ui/kit";
import { CASTLE_H, CASTLE_W, GATEHOUSE, HILLS_FAR } from "./art";
import { Hills } from "./Hills";
import { HeroScene } from "./HeroScene";
import { Journey } from "./Journey";
import "./landing.css";

const SAMPLE = "/app?sample=01_tenancy_agreement.pdf";

// Each figure was checked on its source page; see docs/research/2026-10-24-veil-numbers.
const NUMBERS = [
  { to: 2, suffix: " in 3", text: "writing requests to ChatGPT ask it to rework text the user pasted in: edit, translate, summarise.", source: "OpenAI and NBER, 2025, 1.1m conversations", href: "https://www.nber.org/papers/w34255" },
  { to: 71, suffix: "%", text: "of UK employees have used AI tools their employer never approved. Only 32% worry about the customer data they put in.", source: "Microsoft UK and Censuswide, Oct 2025, 2,003 employees", href: "https://ukstories.microsoft.com/features/rise-in-shadow-ai-tools-raising-security-concerns-for-uk/" },
  { to: 3.13, prefix: "£", suffix: "m", text: "is the average cost of one data breach for a UK organisation in 2026.", source: "IBM Cost of a Data Breach, July 2026", href: "https://uk.newsroom.ibm.com/IBM-Study-More-Than-One-in-Five-Malicious-UK-Breaches-are-AI-Generated" },
];

function TopBar() {
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setSolid(v > 24));
  return (
    <header className={`topbar sticky top-0 z-40 ${solid ? "is-solid" : ""}`}>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-8">
        <a href="/" className="font-pixel text-[30px] leading-none font-bold">MuGuard</a>
        <nav className="ml-auto hidden items-center gap-8 sm:flex" aria-label="Page sections">
          <a href="#journey" className="topbar-link">How it works</a>
          <a href="#learns" className="topbar-link">Learning</a>
          <a href="#numbers" className="topbar-link">Numbers</a>
        </nav>
        <LinkButton href="/app" variant="primary" size="sm" iconRight="right" className="ml-auto sm:ml-0 sm:px-btn-md">
          Protect a document
        </LinkButton>
      </div>
    </header>
  );
}

function Hero() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const shift = (px: number) => (reduce ? [0, 0] : [0, px]);
  const textY = useTransform(scrollYProgress, [0, 1], shift(-90));
  const textOpacity = useTransform(scrollYProgress, [0, 0.7], [1, reduce ? 1 : 0]);
  const farY = useTransform(scrollYProgress, [0, 1], shift(40)); // only the far hills drift; the castle stands on the ground
  const [p, setP] = useState(6);
  const [played, setPlayed] = useState(false);
  const text = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // One pixel size for the whole scene (castle, hills, clouds). The castle may run a little past the first screen
    // so it reads big; it gets the room left under the headline and buttons. Heights come from the layout box (not
    // the scrolled, transformed one) and from 100svh, so a phone's URL bar showing or hiding does not resize it.
    const probe = document.createElement("div");
    probe.style.cssText = "position:fixed;top:0;height:100svh;width:0;visibility:hidden;pointer-events:none";
    document.body.appendChild(probe);
    const fit = () => {
      const el = text.current;
      const section = ref.current;
      if (!el || !section) return;
      const top = section.offsetTop + el.offsetTop + el.offsetHeight;
      const room = probe.offsetHeight * 1.1 - top - 64;
      setP(Math.max(4, Math.min(Math.floor((window.innerWidth * 0.6) / CASTLE_W), Math.floor(room / (CASTLE_H + 4)))));
    };
    fit();
    void document.fonts?.ready.then(fit); // the headline's height changes once the pixel font arrives
    let width = window.innerWidth;
    let height = probe.offsetHeight;
    const onResize = () => {
      if (window.innerWidth === width && probe.offsetHeight === height) return;
      width = window.innerWidth;
      height = probe.offsetHeight;
      fit();
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      probe.remove();
    };
  }, []);

  return (
    <section ref={ref} className="hero relative overflow-hidden">
      <motion.div ref={text} style={{ y: textY, opacity: textOpacity }} className="relative z-10 mx-auto max-w-5xl px-4 pt-8 text-center sm:pt-10">
        <h1 className="mx-auto max-w-[21ch] font-pixel text-hero font-bold text-balance">
          Your documents stay inside the walls.
        </h1>
        <p className="mx-auto mt-5 max-w-[56ch] text-lede text-quiet">
          MuGuard hides names, account numbers and IDs before a document goes to an AI, then puts the real values back in the answer.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <LinkButton href="/app" variant="primary" size="lg" iconRight="right" className={played ? "cta-nudge" : ""}>
            Protect a document
          </LinkButton>
          <LinkButton href={SAMPLE} variant="secondary" size="lg" icon="file">
            Try a sample
          </LinkButton>
        </div>
      </motion.div>

      <HeroScene p={p} farY={farY} onPlayed={setPlayed} />
    </section>
  );
}

function Learn() {
  const [hidden, setHidden] = useState(false);
  const [examples, setExamples] = useState(102);
  return (
    <section id="learns" className="relative bg-bone px-4 pt-20 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <h2 className="max-w-[22ch] font-pixel text-headline font-bold">It learns your firm's own codes</h2>
        <p className="mt-5 max-w-[60ch] text-lede text-quiet">
          Rules cannot learn, and a frontier model reads your data before it hides it. The MuGuard knight is trained through Mubit, and
          every miss you fix becomes a training example for its next version. In our test on 1,459 synthetic documents, pattern rules
          alone hid 38.5% of personal values.
        </p>
      </div>
      <div className="mx-auto mt-10 grid max-w-6xl items-end gap-10 lg:grid-cols-[auto_minmax(0,1fr)]">
        <div className="relative hidden lg:block" aria-hidden>
          <Sprite rows={GATEHOUSE} scale={4} />
          <span className="absolute bottom-0 left-[92px]" data-cursor="Your fixes train the guard">
            <Sprite rows={KNIGHT_SMALL} scale={4} className="bob" />
          </span>
        </div>
        <div className="learn-demo mb-6 bg-paper p-6 px-frame">
          <h3 className="font-pixel text-subhead font-bold">The guard's ledger</h3>
          <p className="mt-1 text-copy text-quiet">The guard missed a client code. Fix it once.</p>
          <p className="mt-4 bg-bone p-4 font-serif text-[19px] leading-relaxed px-frame-thin">
            Invoice for client ref{" "}
            <span className={`learn-val ${hidden ? "is-hidden" : ""}`} data-p="CUSTOM_1">
              LA-20931
            </span>{" "}
            is overdue.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            {hidden ? (
              <Button
                icon="close"
                onClick={() => {
                  setHidden(false);
                  setExamples(102);
                }}
              >
                Undo
              </Button>
            ) : (
              <Button
                variant="primary"
                icon="marker"
                onClick={() => {
                  setHidden(true);
                  window.setTimeout(() => setExamples(103), 450);
                }}
              >
                Hide LA-20931
              </Button>
            )}
            <span className={`learn-count flex items-center gap-2 ${examples > 102 ? "is-up" : ""}`}>
              <span className="px-label text-quiet">Training examples</span>
              <span className="font-label text-[20px] tabular-nums">{examples}</span>
            </span>
          </div>
          <p className="mt-4 min-h-[1.5em] text-copy text-quiet" aria-live="polite">
            {hidden ? "Fixed once. The next model version learns to catch client codes like this." : ""}
          </p>
        </div>
      </div>
      <div className="-mx-4 h-8 border-t-4 border-ink bg-mist sm:-mx-8" />
    </section>
  );
}

// The final figure is there at rest (for thumbnails, reduced motion and a missed observer); it counts up once when seen.
function Counter({ to, prefix = "", suffix = "" }: { to: number; prefix?: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-20% 0px" });
  const reduce = useReducedMotion();
  const [v, setV] = useState(to);
  useEffect(() => {
    if (!inView || reduce) return;
    const c = animate(0, to, { duration: 1.1, ease: [0.16, 1, 0.3, 1], onUpdate: setV });
    return () => c.stop();
  }, [inView, reduce, to]);
  const shown = Number.isInteger(to) ? Math.round(v).toString() : v.toFixed(2);
  return (
    <span ref={ref} aria-label={`${prefix}${to}${suffix}`}>
      {prefix}
      {shown}
      {suffix}
    </span>
  );
}

function Numbers() {
  return (
    <section id="numbers" className="wall-bg px-4 py-20 sm:px-8">
      <div className="notice relative mx-auto max-w-4xl bg-paper px-6 py-8 px-frame sm:px-10">
        <span className="nail left-3 top-3" aria-hidden />
        <span className="nail right-3 top-3" aria-hidden />
        <h2 className="max-w-[24ch] font-pixel text-headline font-bold">
          Notice: people already pass client documents to AI
        </h2>
        <ol className="mt-6">
          {NUMBERS.map((n, i) => (
            <li key={n.source} className="grid gap-x-6 gap-y-2 border-t-2 border-ink py-5 sm:grid-cols-[180px_minmax(0,1fr)]">
              <p className={`font-label text-[clamp(36px,4vw,46px)] leading-none tabular-nums ${i === 1 ? "text-signal-deep" : ""}`}>
                <Counter to={n.to} prefix={n.prefix} suffix={n.suffix} />
              </p>
              <div>
                <p className="text-copy">{n.text}</p>
                <a href={n.href} className="mt-2 inline-block text-note text-quiet underline underline-offset-4 hover:text-signal-deep">
                  {n.source}
                </a>
              </div>
            </li>
          ))}
        </ol>
        <p className="border-t-2 border-ink pt-5 text-copy">
          The solicitors' regulator has seen <q>confidential client information being entered into public AI tools</q>.{" "}
          <a href="https://www.sra.org.uk/solicitors/guidance/misuse-ai/" className="text-note whitespace-nowrap text-quiet underline underline-offset-4 hover:text-signal-deep">
            SRA warning notice, 17 Aug 2026
          </a>
        </p>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="final bg-ink text-bone">
      <Hills rows={HILLS_FAR} edge="#0d0d0d" fill="#0d0d0d" cell={6} className="bg-bone" />
      <div className="mx-auto grid max-w-6xl items-end gap-10 px-4 pt-12 sm:px-8 lg:grid-cols-[1fr_auto]">
        <div className="min-w-0 pb-16">
          <h2 className="max-w-[18ch] font-pixel text-headline font-bold">Protect your first document</h2>
          <p className="mt-5 max-w-[50ch] text-lede text-bone/80">
            Open MuGuard, drop a contract, a payslip or a client email, and approve every hidden value before any AI sees it.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <LinkButton href="/app" variant="primary" size="lg" iconRight="right" className="sm:px-btn-xl">
              Protect a document
            </LinkButton>
            <LinkButton href={SAMPLE} variant="secondary" size="lg" icon="file">
              Try a sample
            </LinkButton>
          </div>
        </div>
        <Sprite rows={GATEHOUSE} scale={5} className="final-gate hidden lg:block" label="The castle gate" />
      </div>
    </section>
  );
}

export function Landing() {
  return (
    <div className="landing min-h-screen bg-bone text-ink">
      <TopBar />
      <main>
        <Hero />
        <Journey />
        <Learn />
        <Numbers />
        <FinalCta />
      </main>
      <footer className="border-t-4 border-signal bg-ink px-4 py-8 text-bone/75 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 text-note">
          <span className="font-pixel text-[20px] font-bold text-bone">MuGuard</span>
          <span>Pseudonymised, not anonymised: placeholders map back to real values only on your side.</span>
          <span data-cursor="Mubit trains the MuGuard knight">Demo documents are synthetic. Built at Night Shift, London, on Mubit.</span>
        </div>
      </footer>
    </div>
  );
}
