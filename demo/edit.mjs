// Joins the script, the voice clips and the recorded take into public/media/edit.json, which the Remotion
// composition reads. Run after `uv run voice.py` and `node record.mjs`; then `npm run studio` or `npm run render`.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const read = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));
const FPS = 30;
const TAIL = 0.7; // seconds after the voice on scenes that are not recorded

const spec = read("scenes.json");
const durations = read("public/media/vo/durations.json");
const timeline = read("public/media/timeline.json");
const recorded = new Map(timeline.scenes.map((s) => [s.id, s]));

const scenes = spec.scenes.map((scene) => {
  if (!scene.vo) return { ...scene, vo: null, voSeconds: 0, words: [], seconds: scene.seconds };
  const voice = durations[scene.id];
  if (!voice) throw new Error(`No voice clip for "${scene.id}". Run: uv run voice.py`);
  const words = read(`public/media/vo/${scene.id}.json`);
  const base = { ...scene, vo: `media/vo/${scene.id}.wav`, voSeconds: voice.seconds, words };
  if (scene.kind !== "clip") return { ...base, seconds: timeline.lead + voice.seconds + TAIL };
  const rec = recorded.get(scene.id);
  if (!rec) throw new Error(`Scene "${scene.id}" is not in the take. Run: node record.mjs`);
  const events = timeline.events
    // A zoom may start easing in just before its scene; a click before the scene belongs to no scene.
    .filter((e) => (e.type === "zoom" ? e.t >= rec.start - 0.5 : e.t >= rec.start) && e.t < rec.end)
    .map((e) => ({ ...e, t: e.t - rec.start }));
  return { ...base, seconds: rec.end - rec.start, recStart: rec.start, events };
});

const edit = { fps: FPS, lead: timeline.lead, take: { src: "media/take.mp4", ...timeline.size }, scenes };
writeFileSync(join(ROOT, "public/media/edit.json"), JSON.stringify(edit, null, 1));
const total = scenes.reduce((n, s) => n + s.seconds, 0);
console.log(`${scenes.length} scenes, ${Math.floor(total / 60)}:${String(Math.round(total % 60)).padStart(2, "0")} in total`);
