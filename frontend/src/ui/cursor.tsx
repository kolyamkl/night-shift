// MuGuard's pointer is the guard's sword. The sprites ride on native CSS cursors, so the pointer never lags;
// one canvas draws the embers a fast swing leaves and the sparks a click strikes, and sleeps when nothing moves.
// Hot (clickable) things turn the blade red, text fields swap it for a quill, disabled controls show a shield.
// Elements with data-cursor="..." show that text on a pixel tag beside the pointer.

import { useEffect, useRef } from "react";
import { COLORS, runPaths, type Rows } from "../sprites";

const SWORD: Rows = [
  ".k..............", "kwk.............", "kwmk............", ".kwmk...........",
  "..kwmk..........", "...kwmk.....k...", "....kwmk...kmk..", ".....kwmk.kmgk..",
  "......kwmkmgk...", ".......kwmgk....", ".......kmgsk....", "......kmgkrsk...",
  ".....kmgk.ksrk..", ".....kgk...kmgk.", "......k.....kgk.", ".............k..",
];
const HOT: Rows = [
  ".k..............", "kok.............", "kork............", ".kork...........",
  "..kork..........", "...kork.....k...", "....kork...kmk..", ".....kork.kmgk..",
  "......korkmgk...", ".......komgk....", ".......kmgsk....", "......kmgkrsk...",
  ".....kmgk.ksrk..", ".....kgk...kmgk.", "......k.....kgk.", ".............k..",
];
const QUILL: Rows = [
  ".............kk.", "............krrk", "...........krork", "..........krorrk",
  ".........krorrk.", "........krorrk..", ".......krorrk...", "......krorrk....",
  "......krrrk.....", ".....krrkk......", "....kwkk........", "...kwk..........",
  "..kwk...........", ".ksk............", "ksk.............", ".k..............",
];
const SHIELD: Rows = [
  "................", "..kkkkkkkkkkkk..", ".krrwwwwwwwwwwk.", ".kwrrwwwwwwwwwk.",
  ".kwwrrwwwwwwwwk.", ".kwwwrrwwwwwwwk.", ".kwwwwrrwwwwwwk.", ".kwwwwwrrwwwwwk.",
  ".kwwwwwwrrwwwwk.", "..kwwwwwwrrwwk..", "...kwwwwwwrrk...", "....kwwwwwwk....",
  ".....kwwwwk.....", "......kwwk......", ".......kk.......", "................",
];

/** A CSS cursor value: the sprite as an SVG data URI at `scale`, its hotspot in CSS pixels, then a native fallback. */
export function cursorUrl(rows: Rows, hotspot: [number, number], fallback: string, scale = 2): string {
  const w = Math.max(...rows.map((r) => r.length));
  const paths = runPaths(rows).map(([ch, d]) => `<path fill='${COLORS[ch]}' d='${d}'/>`).join("");
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${w * scale}' height='${rows.length * scale}' viewBox='0 0 ${w} ${rows.length}' shape-rendering='crispEdges'>${paths}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}") ${hotspot[0]} ${hotspot[1]}, ${fallback}`;
}

const CURSORS: Record<string, string> = {
  "--cursor-sword": cursorUrl(SWORD, [2, 2], "default"),
  "--cursor-hot": cursorUrl(HOT, [2, 2], "pointer"),
  "--cursor-quill": cursorUrl(QUILL, [2, 29], "text"),
  "--cursor-shield": cursorUrl(SHIELD, [16, 16], "not-allowed"),
};

const PX = 3; // embers and sparks snap to a 3px lattice, so they read as pixels, not dots
const EMBER = ["#ff6b61", "#e2231a", "#b3170f"]; // young to old
const SPARK = ["#ff6b61", "#e2231a", "#f8f7f3", "#0d0d0d"];

type Bit = { x: number; y: number; vx: number; vy: number; age: number; life: number; size: number; color?: string; gravity: number };

const HOT_SELECTOR = "a[href], button, [role='button'], [role='tab'], summary, label[for], select, .sample-card, .val.is-live";

/** Mounted once for the whole site. `calm` (the app) needs a faster swing before embers show, and sheds fewer. */
export function SwordCursor({ calm = false }: { calm?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tagRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    const canvas = canvasRef.current;
    const tag = tagRef.current;
    const ctx = canvas?.getContext("2d");
    if (!fine.matches || !canvas || !tag || !ctx) return;

    const root = document.documentElement;
    for (const [name, value] of Object.entries(CURSORS)) root.style.setProperty(name, value);
    root.classList.add("has-sword-cursor");

    const still = window.matchMedia("(prefers-reduced-motion: reduce)");
    const bits: Bit[] = [];
    let frame = 0;
    let last = 0;
    let prev: { x: number; y: number; t: number } | null = null;
    let hot: Element | null = null;
    let label = "";

    const fit = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(window.innerWidth * dpr);
      canvas.height = Math.round(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    fit();

    const draw = (now: number) => {
      const dt = Math.min(now - (last || now), 48);
      last = now;
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      for (let i = bits.length - 1; i >= 0; i--) {
        const b = bits[i];
        b.age += dt;
        if (b.age >= b.life) {
          bits.splice(i, 1);
          continue;
        }
        b.vy += b.gravity * dt;
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        const t = b.age / b.life;
        ctx.globalAlpha = 1 - t * t;
        ctx.fillStyle = b.color ?? EMBER[Math.min(EMBER.length - 1, Math.floor(t * EMBER.length))];
        ctx.fillRect(Math.round(b.x / PX) * PX, Math.round(b.y / PX) * PX, b.size, b.size);
      }
      ctx.globalAlpha = 1;
      frame = bits.length ? requestAnimationFrame(draw) : 0;
      if (!frame) last = 0;
    };
    const wake = () => {
      if (!frame) frame = requestAnimationFrame(draw);
    };

    const burst = (x: number, y: number) => {
      for (let i = 0; i < 12; i++) {
        const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.6; // mostly upward, like sparks off a blade
        const speed = 0.12 + Math.random() * 0.3;
        bits.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, age: 0, life: 360 + Math.random() * 260,
          size: Math.random() < 0.3 ? PX * 2 : PX, color: SPARK[i % SPARK.length], gravity: 0.0011 });
      }
      wake();
    };

    const showTag = (x: number, y: number) => {
      if (!label) return;
      const left = Math.min(x + 22, window.innerWidth - tag.offsetWidth - 8);
      tag.style.transform = `translate(${left}px, ${y + 26}px)`;
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      const now = e.timeStamp;
      showTag(e.clientX, e.clientY);
      if (prev && !still.matches) {
        const dx = e.clientX - prev.x;
        const dy = e.clientY - prev.y;
        const dist = Math.hypot(dx, dy);
        const speed = dist / Math.max(now - prev.t, 1);
        if (speed > (calm ? 1.4 : 0.6) && dist > 4) {
          const n = Math.min(calm ? 3 : 6, Math.ceil(dist / 9));
          for (let i = 0; i < n; i++) {
            const k = i / n;
            bits.push({ x: prev.x + dx * k + (Math.random() - 0.5) * 6, y: prev.y + dy * k + (Math.random() - 0.5) * 6,
              vx: -dx * 0.002 + (Math.random() - 0.5) * 0.03, vy: -0.02 - Math.random() * 0.03, age: 0,
              life: 240 + Math.random() * 220, size: speed > 2 && Math.random() < 0.25 ? PX * 2 : PX, gravity: 0.0004 });
          }
          wake();
        }
      }
      prev = { x: e.clientX, y: e.clientY, t: now };
    };

    const onOver = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      const target = e.target instanceof Element ? e.target : null;
      const next = target?.closest(HOT_SELECTOR) ?? null;
      if (next && next !== hot && !still.matches && !(next as HTMLButtonElement).disabled) {
        for (let i = 0; i < 4; i++) // the blade catches the light as it heats
          bits.push({ x: e.clientX + 2, y: e.clientY + 2, vx: (Math.random() - 0.5) * 0.08, vy: -0.03 - Math.random() * 0.05,
            age: 0, life: 220 + Math.random() * 120, size: PX, color: i % 2 ? "#f8f7f3" : "#ff6b61", gravity: 0 });
        wake();
      }
      hot = next;
      const text = target?.closest("[data-cursor]")?.getAttribute("data-cursor") ?? "";
      if (text !== label) {
        label = text;
        tag.textContent = text;
        tag.classList.toggle("is-on", Boolean(text));
        showTag(e.clientX, e.clientY);
      }
    };

    const onDown = (e: PointerEvent) => {
      if (e.pointerType === "touch" || e.button !== 0 || still.matches) return;
      burst(e.clientX, e.clientY);
    };

    const onLeave = () => {
      label = "";
      tag.classList.remove("is-on");
      prev = null;
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerover", onOver, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", fit);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerover", onOver);
      window.removeEventListener("pointerdown", onDown);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", fit);
      root.classList.remove("has-sword-cursor");
      for (const name of Object.keys(CURSORS)) root.style.removeProperty(name);
    };
  }, [calm]);

  return (
    <>
      <canvas ref={canvasRef} className="sword-fx" aria-hidden />
      <div ref={tagRef} className="cursor-tag px-chip px-chip-dark" aria-hidden />
    </>
  );
}
