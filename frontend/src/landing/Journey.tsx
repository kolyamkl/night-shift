import { motion, useMotionValue, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { KNIGHT_SMALL, Sprite } from "../sprites";
import { AI_TOWER, CASTLE, HILLS_FAR, HILLS_NEAR, PIGEON, PORTCULLIS, SCROLL, TORCH, WALL_SIDE } from "./art";
import { Hills } from "./Hills";

// The stage is drawn at 1200 x 500 design pixels (5px per art cell) and scaled to fit; the art is vector, so it stays crisp.
const W = 1200;
const H = 500;
const GROUND = 440;

export const STEPS = [
  ["Inside the walls", "Your document starts on your side: a tenancy agreement, a payslip, a client email, with every name and account number still in it."],
  ["The guard", "At the gate, the MuGuard knight, a redaction model trained through Mubit, blacks out each personal value. You review every change."],
  ["Only placeholders ride out", "A messenger carries the redacted copy to the AI provider. It reads PERSON_1 and ACCOUNT_1, never the real values."],
  ["The answer comes home", "Back inside the walls, MuGuard swaps the placeholders for the real values, so the answer you read names the right people."],
] as const;

const DOC = [
  ["Tenant", "Raj Patel", "PERSON_1"],
  ["Address", "41 Elm Road, Leeds", "ADDRESS_1"],
  ["Sort code", "20-45-77", "SORT_CODE_1"],
  ["Account", "31926819", "ACCOUNT_1"],
] as const;

// The scene box takes the full window width and the height left under the captions. Wide screens fit the stage
// to that box (hills and ground carry on past its sides); narrow ones show it larger and pan a camera along the action.
const MIN_SCALE = 0.62;

function useFit(ref: RefObject<HTMLDivElement | null>) {
  const [box, setBox] = useState({ w: W, h: H });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  const byWidth = box.w / W;
  const byHeight = box.h / H;
  const pan = byWidth < MIN_SCALE;
  const scale = pan ? Math.min(1, Math.max(MIN_SCALE, byHeight)) : Math.min(byWidth, Math.max(byHeight, MIN_SCALE));
  return { width: box.w, scale, pan };
}

// Behind the actors: hills and ground across the whole window, at the stage's pixel size.
function Backdrop({ scale, far, near }: { scale: number; far: MotionValue<number>; near: MotionValue<number> }) {
  const cell = Math.round(6 * scale * 10) / 10;
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      <Hills rows={HILLS_FAR} edge="#8b8a85" fill="#c9c7bd" cell={cell} shift={far} className="absolute inset-x-0 opacity-70" style={{ top: (GROUND - 240) * scale }} />
      <Hills rows={HILLS_NEAR} edge="#0d0d0d" fill="#dcdad1" cell={cell} shift={near} className="absolute inset-x-0" style={{ top: (GROUND - 120) * scale }} />
      <div className="absolute inset-x-0 bottom-0 bg-mist" style={{ top: GROUND * scale }} />
      <div className="absolute inset-x-0 bg-ink" style={{ top: GROUND * scale, height: Math.max(2, Math.round(4 * scale)) }} />
    </div>
  );
}

// The whole picture, pinned to the bottom of its box: backdrop, then the 1200 x 500 stage, centred or panned.
function Scene({ p, still, scale, width, pan, camX }: {
  p: MotionValue<number>;
  still: boolean;
  scale: number;
  width: number;
  pan: boolean;
  camX: MotionValue<number>;
}) {
  const far = useTransform(() => (still ? 0 : p.get() * -80 * scale) + (pan ? camX.get() * 0.4 : 0));
  const near = useTransform(() => (still ? 0 : p.get() * -200 * scale) + (pan ? camX.get() * 0.7 : 0));
  return (
    <div className="absolute inset-x-0 bottom-0" style={{ height: H * scale }}>
      <Backdrop scale={scale} far={far} near={near} />
      <motion.div className="absolute top-0" style={{ left: pan ? 0 : (width - W * scale) / 2, x: pan ? camX : 0 }}>
        <div className="origin-top-left" style={{ transform: `scale(${scale})`, width: W }}>
          <Stage p={p} still={still} />
        </div>
      </motion.div>
    </div>
  );
}

function Bar({ wipe, tag, children }: { wipe: MotionValue<number>; tag: string; children: string }) {
  const tagOpacity = useTransform(wipe, [0.85, 1], [0, 1]);
  return (
    <span className="relative inline-block font-semibold text-signal-deep">
      {children}
      <motion.span className="absolute -inset-x-0.5 -inset-y-0.5 origin-left bg-ink" style={{ scaleX: wipe }} />
      <motion.span className="absolute inset-0 flex items-center px-1 font-label text-[9px] leading-none text-signal-soft" style={{ opacity: tagOpacity }}>
        {tag}
      </motion.span>
    </span>
  );
}

function Stage({ p, still }: { p: MotionValue<number>; still: boolean }) {
  // Step 1: the sheet waits inside the walls. Step 2: the guard blacks out each value in full view, the portcullis
  // rises, the sheet folds small and passes through the tunnel. Step 3: the pigeon takes it to the AI provider.
  // Step 4: the pigeon lands at the castle and the answer unrolls there.
  const wipes = [
    useTransform(p, [0.24, 0.28], [0, 1]),
    useTransform(p, [0.28, 0.32], [0, 1]),
    useTransform(p, [0.32, 0.36], [0, 1]),
    useTransform(p, [0.36, 0.4], [0, 1]),
  ];
  const full = useMotionValue(1);
  const guardY = useTransform(p, [0.24, 0.26, 0.28, 0.3, 0.32, 0.34, 0.36, 0.38, 0.4], [0, -14, 0, -14, 0, -14, 0, -14, 0]);
  const docX = useTransform(p, [0, 0.06, 0.18, 0.44, 0.5, 0.56], [150, 150, 320, 320, 562, 700]);
  const docY = useTransform(p, [0.42, 0.47], [0, 76]);
  const docScale = useTransform(p, [0, 0.42, 0.47, 0.56, 0.6], [1, 1, 0.38, 0.38, 0.1]);
  const docOpacity = useTransform(p, [0.58, 0.62], [1, 0]);
  const portY = useTransform(p, [0.4, 0.46, 0.54, 0.6], [0, -140, -140, 0]);
  const birdX = useTransform(p, [0.58, 0.72, 0.77, 0.92], [720, 1040, 1040, 200]);
  const birdY = useTransform(p, [0.58, 0.65, 0.72, 0.77, 0.85, 0.92], [330, 170, 215, 215, 90, 228]);
  const birdFlip = useTransform(p, [0.745, 0.755], [1, -1]);
  const birdOpacity = useTransform(p, [0.56, 0.6, 0.94, 0.97], [0, 1, 1, 0]);
  const aiOpacity = useTransform(p, [0.68, 0.72, 0.8, 0.84], [0, 1, 1, 0]);
  const aiY = useTransform(p, [0.68, 0.72], [12, 0]);
  const homeOpacity = useTransform(p, [0.9, 0.93], [0, 1]);
  const homeScale = useTransform(p, [0.9, 0.97], [0.15, 1]);

  const at = (x: number, y: number) => ({ left: x, top: y });
  return (
    <div className="relative" style={{ width: W, height: H }}>
      <span className="absolute" style={at(40, GROUND - 168)} data-cursor="Your side: the real values come back here">
        <Sprite rows={CASTLE} scale={3} label="Your castle" />
      </span>
      <span className="stage-label absolute" style={at(70, GROUND + 14)}>Your side</span>

      <motion.div
        className="absolute w-[200px] origin-top-left bg-paper p-3 px-frame"
        style={still ? at(320, 304) : { left: 0, top: 304, x: docX, y: docY, scale: docScale, opacity: docOpacity }}
      >
        <p className="font-label text-[10px] leading-none">tenancy.pdf</p>
        <div className="mt-2 space-y-1.5 font-serif text-[13px] leading-snug">
          {DOC.map(([label, value, tag], i) => (
            <p key={label} className="truncate">
              {label}:{" "}
              <Bar wipe={still ? full : wipes[i]} tag={tag}>
                {value}
              </Bar>
            </p>
          ))}
        </div>
      </motion.div>

      <span className="absolute" style={at(560, GROUND - 130)}>
        <span className="relative block overflow-hidden" style={{ width: 80, height: 130 }}>
          <motion.span className="absolute left-0 top-0 block" style={{ y: still ? 0 : portY }}>
            <Sprite rows={PORTCULLIS} scale={5} />
          </motion.span>
        </span>
      </span>
      <span className="absolute" style={at(540, GROUND - 280)}>
        <Sprite rows={WALL_SIDE} scale={5} label="The castle wall and its gate" />
      </span>
      <motion.span className="absolute block" style={{ left: 545, top: GROUND - 350, y: still ? 0 : guardY }} data-cursor="The MuGuard knight, trained through Mubit">
        <Sprite rows={KNIGHT_SMALL} scale={5} label="The MuGuard knight on the wall" />
      </motion.span>
      <span className="absolute" style={at(518, GROUND - 120)}>
        <span className="relative block">
          <Sprite rows={TORCH[0]} scale={4} className="flick" />
          <Sprite rows={TORCH[1]} scale={4} className="flick flick-b absolute inset-0" />
        </span>
      </span>
      <span className="stage-label absolute" style={at(478, GROUND + 14)}>The MuGuard knight, trained through Mubit</span>

      <span className="absolute" style={at(1040, GROUND - 256)} data-cursor="AI provider: sees placeholders only">
        <Sprite rows={AI_TOWER} scale={4} label="The AI provider's tower" />
      </span>
      <span className="stage-label absolute" style={at(1032, GROUND + 14)}>AI provider</span>

      <motion.div className="absolute" style={{ left: 0, top: 0, x: birdX, y: birdY, opacity: still ? 0 : birdOpacity }}>
        <motion.span className="relative block" style={{ scaleX: birdFlip }}>
          <Sprite rows={PIGEON[0]} scale={4} className="flick" />
          <Sprite rows={PIGEON[1]} scale={4} className="flick flick-b absolute inset-0" />
          <span className="absolute left-[26px] top-[44px]">
            <Sprite rows={SCROLL} scale={3} />
          </span>
        </motion.span>
      </motion.div>

      <motion.div className="absolute w-[300px] bg-paper p-3 px-frame" style={{ left: 760, top: 40, opacity: still ? 1 : aiOpacity, y: still ? 0 : aiY }}>
        <p className="px-label text-quiet">What the AI provider reads</p>
        <p className="mt-2 font-serif text-[14px] leading-relaxed">
          When does <span className="bg-ink px-1 font-label text-[10px] text-signal-soft">PERSON_1</span> pay rent from{" "}
          <span className="bg-ink px-1 font-label text-[10px] text-signal-soft">ACCOUNT_1</span>?
        </p>
      </motion.div>

      <motion.div
        className="absolute w-[330px] origin-bottom bg-paper p-3 px-frame"
        style={{ left: 60, top: 104, opacity: still ? 1 : homeOpacity, scale: still ? 1 : homeScale }}
      >
        <p className="px-label text-quiet">The answer, back inside</p>
        <p className="mt-2 font-serif text-[14px] leading-relaxed">
          <mark className="bg-signal/15 underline decoration-signal decoration-2 underline-offset-4">Raj Patel</mark> pays £950 on the 1st from account{" "}
          <mark className="bg-signal/15 underline decoration-signal decoration-2 underline-offset-4">31926819</mark>.
        </p>
      </motion.div>
    </div>
  );
}

function Caption({ i, step }: { i: number; step: number }) {
  return (
    <div className={`caption absolute inset-0 ${step === i ? "is-on" : ""}`} aria-hidden={step !== i}>
      <h3 className="font-pixel text-headline font-bold">{STEPS[i][0]}</h3>
      <p className="mt-3 max-w-[60ch] text-lede text-quiet">{STEPS[i][1]}</p>
    </div>
  );
}

export function Journey() {
  const section = useRef<HTMLElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const { width, scale, pan } = useFit(box);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: section, offset: ["start start", "end end"] });
  const p = useSpring(scrollYProgress, { stiffness: 140, damping: 30, mass: 0.35 });
  const focus = useTransform(p, [0, 0.2, 0.42, 0.52, 0.6, 0.72, 0.8, 0.92, 1], [250, 420, 470, 640, 760, 948, 948, 240, 240]);
  const camX = useTransform(focus, (f) => Math.min(0, Math.max(width - W * scale, width / 2 - f * scale)));
  const [step, setStep] = useState(0);
  useMotionValueEvent(p, "change", (v) => setStep(v < 0.2 ? 0 : v < 0.56 ? 1 : v < 0.78 ? 2 : 3));

  if (reduce) {
    // No pinning: the finished scene at full width, sized from the width alone, then the four steps as a list.
    const still = Math.min(1.2, width / W);
    return (
      <section id="journey" ref={section} className="py-20">
        <h2 className="mx-auto max-w-6xl px-4 font-pixel text-headline font-bold sm:px-8">How MuGuard keeps a document inside the walls</h2>
        <div ref={box} className="relative mt-8" style={{ height: H * still }}>
          <Scene p={p} still scale={still} width={width} pan={false} camX={camX} />
        </div>
        <ol className="mx-auto mt-8 grid max-w-6xl gap-6 px-4 sm:px-8 md:grid-cols-2">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="flex gap-4">
              <span className="step-dot is-on">{i + 1}</span>
              <span>
                <b className="text-subhead">{t}</b>
                <span className="mt-1 block text-copy text-quiet">{d}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>
    );
  }

  return (
    <section id="journey" ref={section} className="relative h-[460vh]" aria-label="How MuGuard keeps a document inside the walls">
      <div className="sticky top-16 flex h-[calc(100svh-4rem)] flex-col overflow-hidden">
        <div className="mx-auto w-full max-w-6xl px-4 pt-6 sm:px-8 sm:pt-10">
          <ol className="flex flex-wrap gap-2" aria-label="Steps">
            {STEPS.map(([t], i) => (
              <li key={t} className={`step ${step === i ? "is-on" : step > i ? "is-done" : ""}`}>
                <span className="step-dot">{i + 1}</span>
                <span className="hidden text-copy md:inline">{t}</span>
              </li>
            ))}
          </ol>
          <div className="relative mt-5 h-[210px] sm:h-[150px] lg:h-[170px]" aria-live="polite">
            {STEPS.map((_, i) => (
              <Caption key={i} i={i} step={step} />
            ))}
          </div>
        </div>
        <div ref={box} className="relative mt-4 min-h-0 flex-1">
          <Scene p={p} still={false} scale={scale} width={width} pan={pan} camX={camX} />
        </div>
      </div>
    </section>
  );
}
