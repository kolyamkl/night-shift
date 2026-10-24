// The hero castle is a toy. Its gate glows and rattles until the visitor clicks anywhere on the castle; then the gate
// bursts open, documents fly out, the visitor slashes the personal data off the tenancy agreement for ten seconds,
// and the MuGuard knight hides the rest. Every run ends the same way: all values hidden, every document stamped, and the
// score under the castle. Reduced motion jumps straight to that end.

import { animate, motion, useReducedMotion, type MotionValue } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { Sprite } from "../sprites";
import { Button, Icon } from "../ui/kit";
import { CASTLE, CASTLE_H, CASTLE_TOP, CASTLE_W, CLOUD, DOOR, HILLS_FAR, HILLS_NEAR, PENNANT, TORCH } from "./art";
import { Hills } from "./Hills";

type Phase = "idle" | "opening" | "game" | "finale" | "done";

const DOCS = [
  { title: "Payslip", rows: [["Employee", "Amira Khan", "PERSON_2"], ["NI number", "QQ 12 34 56 C", "NI_1"]] },
  { title: "Client email", rows: [["From", "Tom Reid", "PERSON_3"], ["Phone", "07700 900123", "PHONE_1"]] },
  { title: "Tenancy agreement", rows: [["Tenant", "Raj Patel", "PERSON_1"], ["Address", "41 Elm Road, Leeds", "ADDRESS_1"], ["Sort code", "20-45-77", "SORT_CODE_1"], ["Account", "31926819", "ACCOUNT_1"]] },
  { title: "NDA", rows: [["Party", "Sara Lee", "PERSON_4"], ["Email", "sara@leeco.uk", "EMAIL_1"]] },
  { title: "Invoice", rows: [["Bill to", "Jan Novak", "PERSON_5"], ["Account", "40308669", "ACCOUNT_2"]] },
] as const;
const BIG = 2; // the tenancy agreement is the one the visitor plays
const GAME_MS = 10_000;
const CELLS = 10;

// The doorway in CASTLE: columns 31 to 46, rows 34 to 55, under a stepped arch.
const DOOR_X = 31;
const DOOR_Y = 34;
const DOOR_W = 16;
const DOOR_H = 22;
const DOOR_MIRROR = DOOR.map((r) => [...r].reverse().join(""));
const u = (x: number) => `${((x / DOOR_W) * 100).toFixed(2)}%`;
const v = (y: number) => `${((y / DOOR_H) * 100).toFixed(2)}%`;
const ARCH = `polygon(${u(2)} 0, ${u(12)} 0, ${u(12)} ${v(1)}, ${u(13)} ${v(1)}, ${u(13)} ${v(2)}, ${u(14)} ${v(2)}, ${u(14)} ${v(3)}, 100% ${v(3)}, 100% 100%, 0 100%, 0 ${v(2)}, ${u(1)} ${v(2)}, ${u(1)} ${v(1)}, ${u(2)} ${v(1)})`;

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const valueId = (doc: number, row: number) => `${doc}-${row}`;

function Flicker({ frames, scale, late }: { frames: readonly (readonly string[])[]; scale: number; late?: boolean }) {
  return (
    <span className={`relative block ${late ? "flick-late" : ""}`}>
      <Sprite rows={frames[0]} scale={scale} className="flick" />
      <Sprite rows={frames[1]} scale={scale} className="flick flick-b absolute inset-0" />
    </span>
  );
}

export function HeroScene({ p, farY, onPlayed }: {
  p: number;
  farY: MotionValue<number>;
  onPlayed: (played: boolean) => void;
}) {
  const still = useReducedMotion();
  const [run, setRun] = useState(0); // bumping it remounts the play layer for "Play again"
  const [slot, setSlot] = useState<HTMLDivElement | null>(null);
  return (
    <>
      <div className="scene relative mt-6 sm:mt-0" style={{ height: (CASTLE_H + 4) * p }}>
        <Sprite rows={CLOUD} scale={p} className="cloud absolute top-[4%] left-[8%] hidden md:block" />
        <Sprite rows={CLOUD} scale={Math.max(2, p - 2)} className="cloud cloud-slow absolute top-[18%] right-[10%] hidden md:block" />
        <motion.div style={{ y: farY }} className="pointer-events-none absolute inset-x-0 bottom-0">
          <Hills rows={HILLS_FAR} edge="#8b8a85" fill="#c9c7bd" cell={p} />
        </motion.div>
        <Play
          key={run}
          p={p}
          again={run > 0}
          still={Boolean(still)}
          slot={slot}
          onPlayed={onPlayed}
          onAgain={() => {
            onPlayed(false);
            setRun((n) => n + 1);
          }}
        />
      </div>
      <div className="relative z-10 flex flex-col items-center gap-4 bg-mist px-4 pt-2 pb-8">
        <div ref={setSlot} className="contents" />
        <a href="#journey" className="scroll-cue flex items-center gap-2 bg-paper px-3 py-2 px-frame-thin">
          <Icon name="down" />
          <span className="px-label">Follow a document</span>
        </a>
      </div>
    </>
  );
}

function Play({ p, again, still, slot, onPlayed, onAgain }: {
  p: number;
  again: boolean;
  still: boolean;
  slot: HTMLDivElement | null;
  onPlayed: (played: boolean) => void;
  onAgain: () => void;
}) {
  const scene = useRef<HTMLDivElement>(null);
  const castle = useRef<HTMLButtonElement>(null);
  const leaves = useRef<HTMLSpanElement>(null);
  const fx = useRef<HTMLDivElement>(null);
  const docEls = useRef<(HTMLDivElement | null)[]>([]);
  const alive = useRef(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [shown, setShown] = useState<number[]>([]); // indexes into DOCS, left to right
  const [cut, setCut] = useState<ReadonlySet<string>>(new Set());
  const [stamped, setStamped] = useState(0);
  const [left, setLeft] = useState(CELLS);
  const [won, setWon] = useState(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const cutRef = useRef(cut);
  cutRef.current = cut;

  useEffect(() => {
    alive.current = true;
    if (again) castle.current?.focus({ preventScroll: true }); // "Play again" hands focus back to the castle
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = shown.reduce((n, i) => n + DOCS[i].rows.length, 0);
  const bigHits = DOCS[BIG].rows.filter((_, r) => cut.has(valueId(BIG, r))).length;

  // Sparks, a slash streak and a "+1": loose DOM pieces in the effects layer, removed when their animation ends.
  const burst = (x: number, y: number, n = 9) => {
    const layer = fx.current;
    if (!layer || still) return;
    const box = layer.getBoundingClientRect();
    const colors = ["#ff6b61", "#e2231a", "#f8f7f3", "#0d0d0d"];
    for (let i = 0; i < n; i++) {
      const b = document.createElement("i");
      b.className = "gbit";
      b.style.cssText = `left:${x - box.left}px;top:${y - box.top}px;background:${colors[i % colors.length]}`;
      layer.appendChild(b);
      const a = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.7;
      const d = 30 + Math.random() * 50;
      b.animate([{ transform: "translate(0,0)", opacity: 1 }, { transform: `translate(${Math.cos(a) * d}px, ${Math.sin(a) * d + 30}px)`, opacity: 0 }],
        { duration: 500 + Math.random() * 250, easing: "cubic-bezier(.2,.7,.4,1)" }).onfinish = () => b.remove();
    }
  };
  const streak = (x0: number, y0: number, x1: number, y1: number) => {
    const layer = fx.current;
    if (!layer || still) return;
    const box = layer.getBoundingClientRect();
    const s = document.createElement("i");
    const ang = Math.atan2(y1 - y0, x1 - x0);
    s.className = "gstreak";
    s.style.cssText = `left:${x0 - box.left - Math.cos(ang) * 20}px;top:${y0 - box.top - Math.sin(ang) * 20}px;width:${Math.hypot(x1 - x0, y1 - y0) + 40}px;rotate:${ang}rad`;
    layer.appendChild(s);
    s.animate([{ opacity: 1, scale: "0 1" }, { opacity: 1, scale: "1 1", offset: 0.35 }, { opacity: 0, scale: "1 1" }], { duration: 260 }).onfinish = () => s.remove();
  };
  const plus = (x: number, y: number) => {
    const layer = fx.current;
    if (!layer || still) return;
    const box = layer.getBoundingClientRect();
    const t = document.createElement("i");
    t.className = "gplus";
    t.textContent = "+1";
    t.style.cssText = `left:${x - box.left}px;top:${y - box.top}px`;
    layer.appendChild(t);
    t.animate([{ opacity: 1, translate: "0 0" }, { opacity: 0, translate: "0 -26px" }], { duration: 600 }).onfinish = () => t.remove();
  };
  const shake = (px: number) => {
    if (!still) scene.current?.animate([{ translate: "0 0" }, { translate: `${-px}px ${px / 2}px` }, { translate: `${px}px ${-px / 2}px` }, { translate: "0 0" }], { duration: 160 });
  };

  const cutValue = (doc: number, row: number, effects = true) => {
    const id = valueId(doc, row);
    if (cutRef.current.has(id)) return false;
    const next = new Set(cutRef.current).add(id);
    cutRef.current = next;
    setCut(next);
    const el = docEls.current[doc]?.querySelector<HTMLElement>(`[data-value="${id}"]`);
    if (el && effects) {
      const r = el.getBoundingClientRect();
      burst(r.left + r.width / 2, r.top + r.height / 2);
    }
    return true;
  };

  // The castle opens on pointer down, so it answers the press itself, not the release.
  const open = () => {
    if (phaseRef.current !== "idle") return;
    const narrow = (scene.current?.clientWidth ?? 1000) < 640;
    setShown(narrow ? [1, 2, 3] : [0, 1, 2, 3, 4]);
    if (still) return;
    phaseRef.current = "opening";
    setPhase("opening");
    for (const leaf of leaves.current?.children ?? []) animate(leaf as HTMLElement, { scaleX: 0.12 }, { duration: 0.3, ease: [0.2, 0.9, 0.2, 1] });
    shake(3);
  };

  // The documents stand in a fan in front of the castle. Positions are recomputed whenever the scene resizes.
  const place = () => {
    const sc = scene.current;
    if (!sc) return [];
    const W = sc.clientWidth;
    const H = sc.clientHeight;
    const els = shown.map((i) => docEls.current[i]!).filter(Boolean);
    const dw = els[0]?.offsetWidth ?? 168;
    const gap = Math.min(dw + 26, (W - 16) / els.length);
    const mid = (els.length - 1) / 2;
    els.forEach((el, k) => {
      const x = W / 2 + (k - mid) * gap - dw / 2;
      const y = H - el.offsetHeight - (shown[k] === BIG ? 44 : 34) - Math.abs(k - mid) * 4; // room for the stamp and the tilt
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
      el.dataset.rot = String((k - mid) * 3);
    });
    return els;
  };
  // The big document sits in the middle of the scene while it is played.
  const bringForward = (duration: number) => {
    const sc = scene.current;
    const el = docEls.current[BIG];
    if (!sc || !el) return;
    const W = sc.clientWidth;
    const H = sc.clientHeight;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const top = W < 640 ? 84 : 60; // under the title, counter and timer
    const s = Math.max(1, Math.min(1.9, (W * 0.5) / w, (H - top - 16) / h));
    animate(el, { x: W / 2 - (parseFloat(el.style.left) + w / 2), y: (top + H - 8) / 2 - (parseFloat(el.style.top) + h / 2), scale: s, rotate: 0 },
      { duration, ease: [0.2, 0.9, 0.2, 1] });
  };

  useEffect(() => {
    const sc = scene.current;
    if (!shown.length || !sc) return;
    let first = true;
    const ro = new ResizeObserver(() => {
      if (first) {
        first = false; // the observer reports once on start; the fly-out places the documents itself
        return;
      }
      place();
      if (phaseRef.current === "game") bringForward(0);
    });
    ro.observe(sc);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown]);

  // Once the documents exist: fly them out of the gate into the fan, then bring the tenancy agreement forward.
  useEffect(() => {
    if (!shown.length) return;
    const sc = scene.current;
    const gate = leaves.current;
    if (!sc || !gate) return;
    const sb = sc.getBoundingClientRect();
    const gb = gate.getBoundingClientRect();
    const ox = gb.left - sb.left + gb.width / 2;
    const oy = gb.top - sb.top + gb.height * 0.55;
    const els = place();
    const dw = els[0]?.offsetWidth ?? 168;
    if (still) els.forEach((el) => (el.style.transform = `rotate(${el.dataset.rot}deg)`));
    if (still) {
      setCut(new Set(shown.flatMap((i) => DOCS[i].rows.map((_, r) => valueId(i, r)))));
      setStamped(shown.length);
      setPhase("done");
      onPlayed(true);
      return;
    }
    let cancelled = false;
    (async () => {
      const flood = fx.current?.appendChild(document.createElement("i"));
      if (flood) {
        flood.className = "gflood";
        flood.style.cssText = `left:${ox - 20}px;top:${oy - 20}px`;
        flood.animate([{ opacity: 0, transform: "scale(.5)" }, { opacity: 1, transform: "scale(9)", offset: 0.35 }, { opacity: 0, transform: "scale(14)" }],
          { duration: 900, easing: "ease-out" }).onfinish = () => flood.remove();
      }
      for (const [k, el] of els.entries()) {
        if (cancelled) return;
        const x = parseFloat(el.style.left) + dw / 2;
        const y = parseFloat(el.style.top) + el.offsetHeight / 2;
        const rot = Number(el.dataset.rot);
        const peak = Math.min(oy, y) - 120 - Math.random() * 40;
        el.style.visibility = "visible";
        animate(el, { x: [ox - x, (ox - x) * 0.45, 0], y: [oy - y, peak - y, 0], scale: [0.15, 0.7, 1], rotate: [0, rot * 4, rot], opacity: [0, 1, 1] },
          { duration: 0.6, ease: [0.3, 0.7, 0.3, 1], times: [0, 0.5, 1] });
        castle.current?.animate([{ translate: "0 0" }, { translate: "0 3px" }, { translate: "0 0" }], { duration: 120 }); // recoil on the button, not on the centred wrapper
        await wait(k === 0 ? 60 : 120);
      }
      await wait(700);
      if (cancelled || !alive.current) return;
      bringForward(0.42); // the tenancy agreement comes forward to be played
      setPhase("game");
    })();
    return () => {
      cancelled = true;
    };
    // one run per click: the list of documents is set once, when the gate opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown]);

  // Ten seconds on the clock; a fast stroke through a value, a tap or a click cuts it.
  useEffect(() => {
    if (phase !== "game") return;
    const start = performance.now();
    const timer = window.setInterval(() => {
      const t = (performance.now() - start) / GAME_MS;
      setLeft(Math.max(0, Math.ceil((1 - t) * CELLS)));
      if (t >= 1) void finish(false);
    }, 100);
    let prev: { x: number; y: number; t: number } | null = null;
    const onMove = (e: PointerEvent) => {
      const now = e.timeStamp;
      if (prev) {
        const dist = Math.hypot(e.clientX - prev.x, e.clientY - prev.y);
        const speed = dist / Math.max(1, now - prev.t);
        if (speed > 0.35 || e.pointerType === "touch" || e.buttons) {
          DOCS[BIG].rows.forEach((_, row) => {
            if (cutRef.current.has(valueId(BIG, row))) return;
            const el = docEls.current[BIG]?.querySelector<HTMLElement>(`[data-value="${valueId(BIG, row)}"]`);
            if (!el) return;
            const r = el.getBoundingClientRect();
            const steps = Math.max(2, Math.ceil(dist / 4));
            for (let k = 0; k <= steps; k++) {
              const x = prev!.x + ((e.clientX - prev!.x) * k) / steps;
              const y = prev!.y + ((e.clientY - prev!.y) * k) / steps;
              if (x >= r.left - 4 && x <= r.right + 4 && y >= r.top - 4 && y <= r.bottom + 4) {
                hit(row, [prev!.x, prev!.y, e.clientX, e.clientY]);
                break;
              }
            }
          });
        }
      }
      prev = { x: e.clientX, y: e.clientY, t: now };
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pointermove", onMove);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const hit = (row: number, line?: [number, number, number, number]) => {
    if (phaseRef.current !== "game" || !cutValue(BIG, row)) return;
    const el = docEls.current[BIG]?.querySelector<HTMLElement>(`[data-value="${valueId(BIG, row)}"]`);
    if (el) {
      const r = el.getBoundingClientRect();
      if (line) streak(...line);
      else streak(r.left - 20, r.top + r.height / 2, r.right + 20, r.top + r.height / 2);
      plus(r.right + 6, r.top - 6);
    }
    shake(2);
    const done = DOCS[BIG].rows.every((_, k) => cutRef.current.has(valueId(BIG, k)));
    if (done) window.setTimeout(() => void finish(true), 300);
  };

  const finish = async (clean: boolean) => {
    if (phaseRef.current !== "game") return;
    phaseRef.current = "finale";
    setWon(clean || DOCS[BIG].rows.every((_, k) => cutRef.current.has(valueId(BIG, k))));
    setPhase("finale");
    for (const [row] of DOCS[BIG].rows.entries()) {
      if (cutValue(BIG, row)) {
        const el = docEls.current[BIG]?.querySelector<HTMLElement>(`[data-value="${valueId(BIG, row)}"]`);
        const r = el?.getBoundingClientRect();
        if (r) streak(r.left - 20, r.top + r.height / 2, r.right + 20, r.top + r.height / 2);
        await wait(150);
      }
    }
    await wait(450);
    const big = docEls.current[BIG];
    if (big) animate(big, { x: 0, y: 0, scale: 1, rotate: Number(big.dataset.rot) }, { duration: 0.38, ease: [0.2, 0.9, 0.2, 1] });
    await wait(380);
    for (const i of shown) for (const [row] of DOCS[i].rows.entries()) {
      if (!alive.current) return;
      if (cutValue(i, row)) await wait(60);
    }
    await wait(200);
    for (let k = 1; k <= shown.length; k++) {
      if (!alive.current) return;
      setStamped(k);
      await wait(150);
      shake(5);
      await wait(70);
    }
    setPhase("done");
    onPlayed(true);
    slot?.parentElement?.scrollIntoView({ block: "nearest", behavior: "smooth" }); // the score, if it is below the fold
  };

  const idle = phase === "idle";
  const narrow = shown.length === 3;
  const skip = (
    <Button size="sm" variant="secondary" className={narrow ? "" : "gskip"} onClick={() => void finish(false)}>
      Let the guard do it
    </Button>
  );
  return (
    <>
      <div style={{ bottom: 3 * p }} className="absolute left-1/2 -translate-x-1/2">
        <button
          ref={castle}
          type="button"
          className={`castle-btn relative block ${idle ? "" : "is-open"} ${phase === "game" ? "is-dim" : ""}`}
          aria-label={idle ? "Open the castle gate" : "The castle gate is open"}
          tabIndex={idle ? 0 : -1}
          onPointerDown={(e) => {
            if (e.button === 0) open();
          }}
          onClick={(e) => {
            if (e.detail === 0) open(); // keyboard
          }}
        >
          <Sprite rows={CASTLE} scale={p} />
          <span className="absolute" style={{ left: 8 * p, top: 0 }}><Flicker frames={PENNANT} scale={p} /></span>
          <span className="absolute" style={{ left: (CASTLE_W - 9) * p, top: 0 }}><Flicker frames={PENNANT} scale={p} late /></span>
          <span className="absolute" style={{ left: 25 * p, top: (CASTLE_TOP + 35) * p }}><Flicker frames={TORCH} scale={p} /></span>
          <span className="absolute" style={{ left: 48 * p, top: (CASTLE_TOP + 35) * p }}><Flicker frames={TORCH} scale={p} late /></span>
          <span className={`gate absolute ${idle ? "is-idle" : "is-open"}`} style={{ left: DOOR_X * p, top: DOOR_Y * p, width: DOOR_W * p, height: DOOR_H * p }}>
            {idle && <span className="gate-spill" />}
            <span ref={leaves} className="gate-leaves" style={{ clipPath: ARCH }}>
              <span className="gate-leaf"><Sprite rows={DOOR} scale={p} /></span>
              <span className="gate-leaf is-right"><Sprite rows={DOOR_MIRROR} scale={p} /></span>
            </span>
            {idle && (
              <>
                <span className="gate-seam" />
                {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                  <span key={i} className="gate-mote" style={{ left: 8 * p - 2, top: (14 + (i % 4) * 1.6) * p, "--dx": `${(i % 2 ? 1 : -1) * (10 + i * 6)}px`, animationDelay: `${i * 0.34}s` } as CSSProperties} />
                ))}
              </>
            )}
          </span>
          {idle && <span className="gate-hint" style={{ left: (DOOR_X + DOOR_W / 2) * p, top: (DOOR_Y - 8) * p }}>Open the gate</span>}
        </button>
      </div>
      <Hills rows={HILLS_NEAR} edge="#0d0d0d" fill="#dcdad1" cell={p} className="pointer-events-none absolute inset-x-0 bottom-0" />

      <div ref={scene} className={`play absolute inset-0 ${phase === "game" ? "is-playing" : ""}`} aria-live="polite">
        {shown.map((i) => (
          <div
            key={i}
            ref={(el) => {
              docEls.current[i] = el;
            }}
            className={`gdoc ${phase === "game" && i !== BIG ? "is-dim" : ""} ${phase === "game" && i === BIG ? "is-big" : ""} ${stamped > shown.indexOf(i) ? "is-stamped" : ""}`}
            style={{ visibility: still && phase === "done" ? "visible" : "hidden" }}
          >
            <p className="gdoc-title">{DOCS[i].title}</p>
            {DOCS[i].rows.map(([label, value, tag], r) => {
              const id = valueId(i, r);
              const live = phase === "game" && i === BIG && !cut.has(id);
              return (
                <p key={id} className="gdoc-row">
                  {label}:{" "}
                  <button
                    type="button"
                    data-value={id}
                    className={`gval ${cut.has(id) ? "is-cut" : ""} ${live ? "is-live" : ""}`}
                    style={{ "--tag": tag.length } as CSSProperties}
                    tabIndex={live ? 0 : -1}
                    aria-label={cut.has(id) ? `${label} hidden as ${tag}` : `Hide ${value}`}
                    onPointerDown={() => live && hit(r)}
                    onClick={(e) => {
                      if (e.detail === 0 && live) hit(r);
                    }}
                  >
                    {value}
                    <i aria-hidden />
                    <em aria-hidden>{tag}</em>
                  </button>
                </p>
              );
            })}
            <span className="gstamp" aria-hidden>Protected</span>
          </div>
        ))}

        {(phase === "game" || phase === "finale") && (
          <div className="ghud">
            <span className="ghud-title">{phase === "finale" ? (won ? "Clean cut. Every value hidden" : "The MuGuard knight finished the job") : "Slash the personal data"}</span>
            <span className="ghud-count">{bigHits} / {DOCS[BIG].rows.length}</span>
            {phase === "game" && (
              <span className="gtimer" aria-label={`${left} seconds left`}>
                {Array.from({ length: CELLS }, (_, k) => (
                  <b key={k} className={k < left ? "" : "is-off"} />
                ))}
              </span>
            )}
          </div>
        )}
        {phase === "game" && !narrow && skip}
        <div ref={fx} className="gfx" aria-hidden />
      </div>

      {phase === "game" && narrow && slot && createPortal(skip, slot)}
      {phase === "done" && slot &&
        createPortal(
          <div className="gscore-wrap">
            <div className="gscore" role="status">
              <div className="is-before">
                <span className="px-label">Without MuGuard, the AI provider gets</span>
                <b>{total} real values</b>
              </div>
              <div className="is-after">
                <span className="px-label">With MuGuard, the AI provider gets</span>
                <b>0 real values</b>
              </div>
            </div>
            <Button size="sm" variant="ghost" className="gagain" onClick={onAgain}>
              Play again
            </Button>
          </div>,
          slot,
        )}
    </>
  );
}

