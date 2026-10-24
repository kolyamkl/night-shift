import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../ui/kit";
import { COLORS, HACKER, HACKER_DOWN, HERO, HERO_SWORD, INK, SIGNAL, STONE, Sprite } from "../sprites";

const COLS = 25;
const ROWS = 31; // the knight's feet stand on row 31, the ground line
const LIFT = 8; // rows the knight hangs above the hacker before the strike
const CONFETTI = [INK, SIGNAL, STONE, SIGNAL];

type Px = { x: number; y: number; c: string; fx: number; fy: number; d: number };

function heroPixels(): Px[] {
  const grid: (string | null)[][] = HERO.map((row) => [...row].map((ch) => (ch === "." ? null : COLORS[ch])));
  for (const [r, row] of HERO_SWORD) [...row].forEach((ch, x) => ch !== "." && (grid[r][x] = COLORS[ch]));
  const far = Math.max(window.innerWidth, window.innerHeight);
  const out: Px[] = [];
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c) return;
      const a = Math.random() * Math.PI * 2;
      const r = far * (0.55 + Math.random() * 0.5);
      out.push({ x, y, c, fx: Math.cos(a) * r, fy: Math.sin(a) * r, d: Math.random() * 0.5 + (y / ROWS) * 0.2 });
    }),
  );
  return out;
}

const sizeFor = () =>
  Math.max(6, Math.min(24, Math.floor(Math.min((window.innerHeight - 250) / ROWS, (window.innerWidth - 48) / (COLS + 4)))));

// After "Approve all": pixels fly in from every side and build the knight, who drives his sword down into a hacker.
export function Victory({ hidden, onDone }: { hidden: number; onDone: () => void }) {
  const button = useRef<HTMLButtonElement>(null);
  const [p, setP] = useState(sizeFor);
  const pixels = useMemo(heroPixels, []);
  const dust = useMemo(
    () => Array.from({ length: 26 }, (_, i) => {
      const side = i % 2 ? 1 : -1;
      return { dx: side * (40 + Math.random() * 260), dy: -(30 + Math.random() * 150), c: i % 3 ? STONE : INK };
    }),
    [],
  );
  const confetti = useMemo(
    () => Array.from({ length: 70 }, (_, i) => ({
      x: Math.random() * 100, delay: 2.2 + Math.random() * 1.6, dur: 1.8 + Math.random() * 1.6,
      size: 8 + Math.round(Math.random()) * 6, c: CONFETTI[i % 4], spin: Math.random() > 0.5 ? 1 : -1,
    })),
    [],
  );

  useEffect(() => {
    const fit = () => setP(sizeFor());
    window.addEventListener("resize", fit);
    const close = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "Enter") && onDone();
    window.addEventListener("keydown", close);
    const auto = window.setTimeout(onDone, 8000);
    const focus = window.setTimeout(() => button.current?.focus(), 3200);
    return () => {
      window.removeEventListener("resize", fit);
      window.removeEventListener("keydown", close);
      window.clearTimeout(auto);
      window.clearTimeout(focus);
    };
  }, [onDone]);

  return (
    <div role="dialog" aria-modal="true" aria-label="Secured by MuGuard" className="victory fixed inset-0 z-50 overflow-hidden" onClick={onDone}>
      {confetti.map((c, i) => (
        <i key={i} className="v-confetti" style={{ left: `${c.x}%`, width: c.size, height: c.size, background: c.c, animationDelay: `${c.delay}s`, animationDuration: `${c.dur}s`, ["--spin" as string]: c.spin }} />
      ))}

      <div className="relative flex h-full flex-col items-center justify-center gap-5 px-4">
        <h2 className="v-title font-pixel leading-none font-bold whitespace-nowrap">Secured by MuGuard</h2>

        <div className="v-stage relative" style={{ width: COLS * p, height: ROWS * p, ["--p" as string]: `${p}px`, ["--lift" as string]: LIFT }}>
          <div className="absolute top-full left-1/2 h-[3px] w-[200vw] -translate-x-1/2 bg-ink" />

          <div className="absolute" style={{ left: 7 * p, top: (ROWS - HACKER.length) * p }}>
            <div className="v-hacker">
              <p className="v-taunt absolute bottom-full left-1/2 mb-3 -translate-x-1/2 bg-paper px-2.5 py-1 text-sm whitespace-nowrap px-frame-thin">
                Your data, please
              </p>
              <Sprite rows={HACKER} scale={p} label="A hacker" />
            </div>
          </div>
          <div className="v-down absolute" style={{ left: 7 * p, top: (ROWS - HACKER_DOWN.length) * p }}>
            <Sprite rows={HACKER_DOWN} scale={p} label="The hacker, beaten" />
          </div>

          <div className="v-hero absolute top-0 left-0" style={{ width: COLS * p, height: ROWS * p }} role="img" aria-label="The MuGuard knight drives his sword into the ground">
            {pixels.map((px, i) => (
              <i key={i} className="v-px" style={{ left: px.x * p, top: px.y * p, width: p + 1, height: p + 1, background: px.c, ["--fx" as string]: `${px.fx}px`, ["--fy" as string]: `${px.fy}px`, animationDelay: `${px.d}s` }} />
            ))}
          </div>

          <div className="absolute" style={{ left: 12.5 * p, top: ROWS * p }}>
            {dust.map((d, i) => (
              <i key={i} className="v-dust" style={{ width: p * 0.6, height: p * 0.6, background: d.c, ["--dx" as string]: `${d.dx}px`, ["--dy" as string]: `${d.dy}px` }} />
            ))}
          </div>
        </div>

        <p className="v-sub max-w-[56ch] text-center font-serif text-lg">
          {hidden} values hidden. The AI only sees the placeholders, and MuGuard puts the real values back for you.
        </p>
        <span className="v-go">
          <Button ref={button} variant="dark" size="lg" iconRight="right" onClick={onDone}>
            Continue
          </Button>
        </span>
      </div>
    </div>
  );
}
