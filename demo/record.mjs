// Records the app part of the demo in one take, paced to the voiceover.
//
//   node record.mjs                      # needs the servers below and public/media/vo/durations.json (uv run voice.py)
//   DEMO_URL=http://localhost:5174 HEADED=1 node record.mjs
//
// Servers (`make demo-servers`, see README): backend (8002), mock stream (8010), frontend (5174).
// Each scene starts when the previous one ends and lasts at least LEAD + its voice clip + PAD, so the voice can
// never run behind the picture. Writes rec/take.webm, public/media/take.mp4 (30 fps H.264) and
// public/media/timeline.json: scene start/end times and the click and zoom events, in seconds from the first frame.

import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const ROOT = dirname(fileURLToPath(import.meta.url));
const BASE = process.env.DEMO_URL ?? "http://localhost:5174";
const SIZE = { width: 1600, height: 900 };
const LEAD = 0.25; // seconds of picture before the voice starts (edit.mjs uses the same value)
const PAD = 0.6; // seconds after the voice ends
const QUESTION = "When can the landlord raise the rent?";
const MISSED = "Evergreen Locksmiths LLP";

const spec = JSON.parse(readFileSync(join(ROOT, "scenes.json"), "utf8"));
const durations = JSON.parse(readFileSync(join(ROOT, "public/media/vo/durations.json"), "utf8"));
const clips = spec.scenes.filter((s) => s.kind === "clip");
for (const s of clips) if (!durations[s.id]) throw new Error(`No voice clip for "${s.id}". Run: uv run voice.py`);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A DOM copy of the app's sword cursor (native CSS cursors never reach the video), plus a pixel ripple on click.
// It shows whichever sprite the app's CSS asks for under the pointer: sword, red blade, quill or shield.
const CURSOR = () => {
  if (window.top !== window) return;
  const SCALE = 1.5;
  let x = -100, y = -100, hot = [2, 2], last = "";
  try { [x, y] = JSON.parse(sessionStorage.getItem("__demoCursor") ?? "[-100,-100]"); } catch {}
  const img = document.createElement("img");
  img.alt = "";
  img.style.cssText = "position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;image-rendering:pixelated;";
  img.onload = () => { img.style.width = `${img.naturalWidth * SCALE}px`; img.style.height = `${img.naturalHeight * SCALE}px`; };
  const sprite = (el) => {
    let v = el ? getComputedStyle(el).cursor : "";
    if (!v.includes("url(")) v = getComputedStyle(document.documentElement).getPropertyValue("--cursor-sword");
    if (!v || v === last) return;
    const m = v.match(/url\(\s*"?([^")]+)"?\s*\)\s*(\d+)?\s+(\d+)?/);
    if (!m) return;
    last = v;
    img.src = m[1];
    hot = [Number(m[2] ?? 0), Number(m[3] ?? 0)];
  };
  const place = () => { img.style.transform = `translate(${x - hot[0] * SCALE}px, ${y - hot[1] * SCALE}px)`; };
  addEventListener("mousemove", (e) => {
    x = e.clientX; y = e.clientY;
    sessionStorage.setItem("__demoCursor", JSON.stringify([x, y]));
    sprite(e.target); place();
  }, true);
  addEventListener("mousedown", (e) => {
    const r = document.createElement("div");
    r.style.cssText = `position:fixed;left:${e.clientX}px;top:${e.clientY}px;width:10px;height:10px;z-index:2147483646;` +
      "pointer-events:none;border:3px solid #e2231a;transform:translate(-50%,-50%);";
    document.documentElement.appendChild(r);
    r.animate([{ width: "10px", height: "10px", opacity: 1 }, { width: "54px", height: "54px", opacity: 0 }],
      { duration: 480, easing: "cubic-bezier(.2,.7,.3,1)" }).onfinish = () => r.remove();
  }, true);
  setInterval(() => { sprite(document.elementFromPoint(x, y)); place(); }, 100);
  const mount = () => { document.documentElement.appendChild(img); sprite(document.elementFromPoint(x, y)); place(); };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", mount); else mount();
};

const browser = await chromium.launch({ headless: !process.env.HEADED });
const context = await browser.newContext({ viewport: SIZE, deviceScaleFactor: 1, baseURL: BASE });
await context.addInitScript(CURSOR);

// A fresh local test account per take, so the session list starts empty. Never used again.
const account = { email: `demo-${randomBytes(3).toString("hex")}@veil.test`, password: randomBytes(18).toString("base64url") };
const reg = await context.request.post("/api/auth/register", { data: account, headers: { "X-Veil-Request": "1" } });
if (!reg.ok()) throw new Error(`Register failed: ${reg.status()} ${await reg.text()}`);

const page = await context.newPage();
// Vite may reload the page once while it optimises new dependencies; wait that out before recording.
for (let attempt = 0; ; attempt++) {
  try {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    break;
  } catch (e) {
    if (attempt === 2) throw e;
    await sleep(1500);
  }
}
await page.mouse.move(1180, 760);
await sleep(1200);

mkdirSync(join(ROOT, "rec"), { recursive: true });
const webm = join(ROOT, "rec/take.webm");
await page.screencast.start({ path: webm, size: SIZE, fps: 30, quality: 95 });
const T0 = Date.now();
const now = () => (Date.now() - T0) / 1000;

const events = [];
const scenes = [];
let mouse = { x: 1180, y: 760 };

// Eased move along a slight arc, at about 60 steps per second.
async function glide(x, y, ms = 650) {
  const { x: sx, y: sy } = mouse;
  const dx = x - sx, dy = y - sy, dist = Math.hypot(dx, dy) || 1;
  const bend = Math.min(50, dist * 0.1), nx = -dy / dist, ny = dx / dist;
  const steps = Math.max(8, Math.round(ms / 16)), start = Date.now();
  for (let i = 1; i <= steps; i++) {
    const t = i / steps, e = t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2, arc = Math.sin(Math.PI * e) * bend;
    await page.mouse.move(sx + dx * e + nx * arc, sy + dy * e + ny * arc);
    const wait = start + ms * t - Date.now();
    if (wait > 0) await sleep(wait);
  }
  mouse = { x, y };
}

async function boxOf(locator) {
  await locator.waitFor({ state: "visible", timeout: 60_000 });
  const box = await locator.boundingBox();
  if (!box) throw new Error(`No box for ${locator}`);
  return box;
}

async function moveTo(locator, ms) {
  const box = await boxOf(locator);
  await glide(box.x + box.width / 2, box.y + box.height / 2, ms);
  return box;
}

// `sfx` names the 8-bit sound the edit plays on this click (sfx.py): blip, coin or fanfare.
async function click(locator, ms = 650, sfx = "blip") {
  const box = await moveTo(locator, ms);
  await sleep(140);
  events.push({ t: now(), type: "click", x: mouse.x, y: mouse.y, box, sfx });
  await page.mouse.down();
  await sleep(70);
  await page.mouse.up();
  return box;
}

// Zoom the edit onto a box: reaches `scale` at the current moment and holds it for `hold` seconds.
function focus(box, scale = 1.3, hold = 3) {
  events.push({ t: now(), type: "zoom", box, scale, hold });
}

async function smoothScroll(dy, ms = 900) {
  const steps = Math.max(6, Math.round(ms / 30));
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, dy / steps);
    await sleep(ms / steps);
  }
}

async function typeText(text) {
  for (const ch of text) {
    await page.keyboard.type(ch);
    await sleep(38 + Math.random() * 45);
  }
}

// Bounding box of a phrase inside the document text, for selecting it with the mouse.
async function phraseBox(text) {
  return page.evaluate((needle) => {
    const root = document.querySelector('[aria-label="Document text"]');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const i = node.textContent.indexOf(needle);
      if (i < 0) continue;
      const range = document.createRange();
      range.setStart(node, i);
      range.setEnd(node, i + needle.length);
      const r = range.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    }
    return null;
  }, text);
}

const byName = (role, name) => page.getByRole(role, { name, exact: true });

const ACTIONS = {
  async landing(at) {
    await at(0.3);
    await glide(820, 330, 900);
    await at(3.2);
    await moveTo(page.getByRole("link", { name: "Try a sample" }).first(), 800);
    await at(LEAD + durations.landing.seconds - 0.4);
    await click(page.getByRole("link", { name: "Protect a document" }).nth(1));
    await page.getByText("Or try a sample").waitFor({ timeout: 30_000 });
    await page.evaluate(() => document.fonts.ready);
  },

  async scan(at) {
    const card = page.getByRole("button", { name: /^Open sample: Tenancy agreement, Periodic/ });
    await at(0.4);
    await moveTo(card, 900);
    await at(2.2);
    await click(card, 200);
    await page.getByRole("progressbar", { name: "Parts read" }).waitFor({ timeout: 30_000 }).catch(() => {});
    await at(4.5);
    const progress = page.getByRole("progressbar", { name: "Parts read" });
    if (await progress.isVisible()) focus(await progress.boundingBox(), 1.3, 2.5);
    await glide(900, 520, 1200);
    await byName("button", "Approve all").waitFor({ timeout: 90_000 });
  },

  async pages(at) {
    await at(0.3);
    await click(byName("tab", "Pages"));
    await at(1.6);
    focus({ x: 560, y: 110, width: 760, height: 330 }, 1.35, 4); // top of page one: landlord, tenants, property
    await glide(820, 420, 1500);
    await at(6.5);
    await smoothScroll(520, 1800);
  },

  async parts(at) {
    await at(0.2);
    await click(page.getByRole("button", { name: /^\d+ parts$/ }));
    await at(1.2);
    const panel = page.locator("#routing");
    if (await panel.isVisible()) focus(await panel.boundingBox(), 1.25, 3.2);
    await glide(900, 300, 1400);
    await at(LEAD + durations.parts.seconds);
    await click(page.getByRole("button", { name: /^\d+ parts$/ }), 500);
  },

  async fix(at) {
    await at(0.2);
    await click(byName("tab", "Lines"));
    await at(1.6);
    await click(byName("button", "Fix a miss"));
    await at(3.0);
    const r = await phraseBox(MISSED);
    if (!r) throw new Error(`"${MISSED}" not found in the document text`);
    focus({ x: r.x - 120, y: r.y - 60, width: r.width + 380, height: 200 }, 1.6, 5.5);
    await glide(r.x + 1, r.y + r.height / 2, 700);
    await page.mouse.down();
    await glide(r.x + r.width - 1, r.y + r.height / 2, 900);
    await page.mouse.up();
    await at(5.6);
    await click(page.getByRole("dialog", { name: "Hide selected text" }).getByRole("button", { name: "Hide" }), 600, "coin");
    await sleep(600);
    await glide(r.x + r.width + 140, r.y + 60, 700);
  },

  async approve(at) {
    await at(0.3);
    await click(byName("button", "Approve all"), 650, "fanfare");
    const done = page.getByRole("dialog", { name: /^Secured by/ }).getByRole("button", { name: "Continue" });
    await done.waitFor({ timeout: 15_000 });
    await sleep(3200);
    await click(done, 700);
    await page.getByPlaceholder("When is the rent due?").waitFor({ timeout: 15_000 });
    await sleep(500);
  },

  async ask(at) {
    const box = page.getByPlaceholder("When is the rent due?");
    await at(0.2);
    await click(box);
    await typeText(QUESTION);
    await sleep(250);
    await page.keyboard.press("Enter");
    const answer = page.locator('aside[aria-label="Ask an AI about this document"]').getByText(/real values put back by/).first();
    await answer.waitFor({ timeout: 60_000 }).catch(() => {});
    const panel = await page.locator('aside[aria-label="Ask an AI about this document"]').boundingBox();
    focus({ x: panel.x, y: panel.y + 20, width: panel.width, height: 260 }, 1.45, 4.5);
    await glide(panel.x + panel.width * 0.55, panel.y + 220, 900);
  },

  async sees(at) {
    await at(0.2);
    await click(byName("tab", "What it sees"));
    await at(1.2);
    const panel = await page.locator('aside[aria-label="Ask an AI about this document"]').boundingBox();
    focus({ x: panel.x, y: panel.y + 40, width: panel.width, height: 420 }, 1.35, 4.2);
    await glide(panel.x + panel.width / 2, panel.y + 360, 800);
    await smoothScroll(300, 1500);
  },
};

try {
  for (const scene of clips) {
    const start = now();
    const at = (s) => sleep(Math.max(0, (start + s - now()) * 1000));
    const minimum = at(LEAD + durations[scene.id].seconds + PAD);
    console.log(`${scene.id} at ${start.toFixed(2)}s`);
    await ACTIONS[scene.id](at);
    await minimum;
    scenes.push({ id: scene.id, start, end: now() });
  }
} catch (e) {
  await page.screenshot({ path: join(ROOT, "rec/failed.png") });
  console.error(`Failed in a scene; screenshot at rec/failed.png`);
  throw e;
} finally {
  await page.screencast.stop();
  await browser.close();
}

writeFileSync(join(ROOT, "public/media/timeline.json"), JSON.stringify({ size: SIZE, lead: LEAD, scenes, events }, null, 1));
console.log(`take: ${now().toFixed(1)}s, ${events.length} events`);

// 30 fps constant frame rate H.264, so Remotion can seek it frame-exactly. Remotion ships its own ffmpeg
// (a small build without the fps filter, hence -r).
execFileSync("npx", ["remotion", "ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-r", "30",
  "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p", join(ROOT, "public/media/take.mp4")], { stdio: "inherit", cwd: ROOT });
console.log("wrote public/media/take.mp4 and public/media/timeline.json");
