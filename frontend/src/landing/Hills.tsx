// A hill strip from art.ts, repeated across any width at a fixed pixel size: a wider screen gets more hills,
// never bigger ones. The strip's middle sits at the container's middle, so a valley drawn there stays centred.
// `shift` slides the pattern sideways inside the strip (parallax, a panning camera) without ever showing an edge.

import { motion, useTransform, type MotionValue } from "motion/react";
import { useMemo, type CSSProperties } from "react";
import { runPaths } from "../sprites";

export function Hills({ rows, edge, fill, cell, shift, className, style }: {
  rows: readonly string[];
  edge: string;
  fill: string;
  cell: number; // CSS pixels per art pixel
  shift?: MotionValue<number>;
  className?: string;
  style?: CSSProperties;
}) {
  const image = useMemo(() => {
    const paths = runPaths(rows).map(([ch, d]) => `<path fill='${ch === "k" ? edge : fill}' d='${d}'/>`).join("");
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${rows[0].length} ${rows.length}' preserveAspectRatio='none' shape-rendering='crispEdges'>${paths}</svg>`;
    return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
  }, [rows, edge, fill]);
  const width = Math.round(rows[0].length * cell); // whole pixels, so tiles meet without a hairline seam
  const height = Math.round(rows.length * cell);
  const x = useTransform(() => `calc(50% + ${Math.round(shift?.get() ?? 0)}px)`);
  return (
    <motion.div
      aria-hidden
      data-hills
      className={className}
      style={{ height, backgroundImage: image, backgroundRepeat: "repeat-x", backgroundSize: `${width}px ${height}px`, backgroundPositionX: x, backgroundPositionY: 0, ...style }}
    />
  );
}
