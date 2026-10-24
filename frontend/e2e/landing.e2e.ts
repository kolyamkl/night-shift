import { expect, test } from "@playwright/test";
import { box, castle, collectErrors, docs, expectFanInsideScene, openGate, overlaps, scene, score } from "./helpers";

// VEIL-QA-1: the landing page's castle game, cursor and scroll scenes, on a 1440 x 900 desktop.

test("L3 the castle stays put when the gate opens", async ({ page }) => {
  await page.goto("/");
  const before = await box(page.locator(".hero-castle"));
  await openGate(page);
  for (const ms of [40, 120, 260, 520, 900]) {
    await page.waitForTimeout(ms === 40 ? 40 : 100);
    const now = await page.locator(".hero-castle").boundingBox();
    expect(Math.abs(now!.x - before.x), `castle x after ${ms} ms`).toBeLessThanOrEqual(2);
    expect(Math.abs(now!.y - before.y), `castle y after ${ms} ms`).toBeLessThanOrEqual(6);
  }
});

test("L4 L7 finale: every document stamped inside the scene and the score shown", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  await page.getByRole("button", { name: "Let the guard do it" }).click();
  await expect(score(page)).toBeVisible({ timeout: 8000 });
  await expect(page.locator(".gdoc.is-stamped")).toHaveCount(5);
  await expect(score(page)).toContainText("12 real values");
  await expectFanInsideScene(page, 5);
});

test("L10 the documents keep their fan after the window is resized", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  await page.getByRole("button", { name: "Let the guard do it" }).click();
  await expect(score(page)).toBeVisible({ timeout: 8000 });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(400);
  await expectFanInsideScene(page, 5);
  await page.setViewportSize({ width: 1180, height: 760 });
  await page.waitForTimeout(400);
  await expectFanInsideScene(page, 5);
});

test("L5 the game header and controls do not cover the enlarged document", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  const hud = page.locator(".ghud");
  await expect(hud).toBeVisible({ timeout: 4000 });
  await page.waitForTimeout(600);
  const big = await box(page.locator(".gdoc.is-big"));
  expect(overlaps(await box(hud), big), "header over the document").toBe(false);
});

test("L11 the castle base never slides under the band while scrolling", async ({ page }) => {
  await page.goto("/");
  for (const y of [150, 300, 450, 600]) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(150);
    const s = await box(scene(page));
    const c = await page.locator(".hero-castle").boundingBox();
    if (!c) continue;
    expect(c.y + c.height, `castle bottom at scroll ${y}`).toBeLessThanOrEqual(s.y + s.height + 1);
  }
});

test("L13 reduced motion: a press shows the finished state with the gate open", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const errors = collectErrors(page);
  await openGate(page);
  await expect(page.locator(".gdoc.is-stamped")).toHaveCount(5);
  await expect(score(page)).toBeVisible();
  const leaf = await box(page.locator(".gate-leaf").first());
  const gate = await box(page.locator(".gate"));
  expect(leaf.width, "left gate leaf swung open").toBeLessThan(gate.width / 4);
  expect(errors).toEqual([]);
});

test("L15 no console errors on load, during the game and while scrolling", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/");
  await openGate(page);
  await page.getByRole("button", { name: "Let the guard do it" }).click();
  await expect(score(page)).toBeVisible({ timeout: 8000 });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await page.waitForTimeout(300);
  expect(errors).toEqual([]);
});

test("L15 reduced motion: the journey loads without console errors", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const errors = collectErrors(page);
  await page.goto("/");
  await page.locator("#journey").scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  expect(errors).toEqual([]);
});

test.describe("documents count", () => {
  test("L4 five documents fly out on a wide screen", async ({ page }) => {
    await page.goto("/");
    await openGate(page);
    await expect(docs(page)).toHaveCount(5);
  });
});

// Regression checks for what already worked in VEIL-QA-1.

test("L1 the hero leads to the app and to a sample", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your documents stay inside the walls.");
  const main = page.locator("section.hero");
  await expect(main.getByRole("link", { name: "Protect a document" })).toHaveAttribute("href", "/app");
  await expect(main.getByRole("link", { name: "Try a sample" })).toHaveAttribute("href", "/app?sample=01_tenancy_agreement.pdf");
});

test("L2 the closed castle invites a press", async ({ page }) => {
  await page.goto("/");
  await expect(castle(page)).toBeVisible();
  await expect(page.getByText("Open the gate", { exact: true })).toBeVisible();
  await expect(page.locator(".gate.is-idle .gate-seam")).toBeVisible();
});

test("L6 a fast stroke hides a value, a slow hover does not, a click and Enter do", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  await expect(page.locator(".ghud")).toBeVisible({ timeout: 4000 });
  await page.waitForTimeout(500);
  const values = page.locator(".gdoc.is-big .gval");
  const count = page.locator(".ghud-count");

  // A pointer that drifts at about 0.2 px per ms hovers; it never swings.
  const drift = async (x0: number, y0: number, x1: number, y1: number) => {
    const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 3);
    for (let k = 0; k <= n; k++) {
      await page.mouse.move(x0 + ((x1 - x0) * k) / n, y0 + ((y1 - y0) * k) / n);
      await page.waitForTimeout(16);
    }
  };
  const first = await box(values.nth(0));
  const y = first.y + first.height / 2;
  await page.mouse.move(first.x - 40, y);
  await drift(first.x - 40, y, first.x + first.width + 40, y);
  await expect(count).toHaveText("0 / 4");

  await page.mouse.move(first.x - 60, y);
  await page.mouse.move(first.x + first.width + 60, y, { steps: 3 });
  await expect(count).toHaveText("1 / 4");
  await expect(values.nth(0)).toHaveClass(/is-cut/);

  const third = await box(values.nth(2));
  await drift(first.x + first.width + 60, y, third.x + third.width / 2, third.y + third.height / 2);
  await page.mouse.down();
  await page.mouse.up();
  await expect(count).toHaveText("2 / 4");

  await values.nth(1).focus();
  await page.keyboard.press("Enter");
  await expect(count).toHaveText("3 / 4");
});

test("L7 Play again closes the castle and gives it the focus", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  await page.getByRole("button", { name: "Let the guard do it" }).click();
  await expect(score(page)).toBeVisible({ timeout: 8000 });
  await expect(page.locator("section.hero").getByRole("link", { name: "Protect a document" })).toHaveClass(/cta-nudge/);
  await page.getByRole("button", { name: "Play again" }).click();
  await expect(castle(page)).toBeFocused();
  await expect(docs(page)).toHaveCount(0);
  await expect(score(page)).toHaveCount(0);
});

test("L8 when the clock runs out the guard finishes the job", async ({ page }) => {
  await page.goto("/");
  await openGate(page);
  await expect(page.locator(".ghud-title")).toHaveText("Slash the personal data", { timeout: 4000 });
  await expect(page.locator(".ghud-title")).toHaveText("The MuGuard knight finished the job", { timeout: 12_000 });
  await expect(score(page)).toBeVisible({ timeout: 8000 });
});

test("L12 the pointer is a sword, red over things to press, with tags in the journey", async ({ page }) => {
  await page.goto("/");
  const cursor = (selector: string) => page.locator(selector).first().evaluate((el) => getComputedStyle(el).cursor);
  expect(await cursor("body")).toMatch(/^url\("data:image\/svg\+xml.*\) 2 2, default$/);
  expect(await cursor("section.hero a.px-btn")).toMatch(/^url\("data:image\/svg\+xml.*\) 2 2, pointer$/);
  const guard = page.locator('#journey [data-cursor^="AI provider"]');
  await guard.scrollIntoViewIfNeeded();
  const g = await box(guard);
  await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
  await expect(page.locator(".cursor-tag")).toHaveClass(/is-on/);
  await expect(page.locator(".cursor-tag")).toHaveText((await guard.getAttribute("data-cursor"))!);
});

test("L14 keyboard: the castle shows a focus ring and Enter opens it", async ({ page }) => {
  await page.goto("/");
  for (let i = 0; i < 15 && !(await castle(page).evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(castle(page)).toBeFocused();
  expect(await castle(page).evaluate((el) => getComputedStyle(el).outlineStyle)).toBe("solid");
  await page.keyboard.press("Enter");
  await expect(docs(page)).toHaveCount(5);
});

// The castle is a toy beyond its gate: only the door opens it; presses on a tower knock stones off it.
const tower = async (page: import("@playwright/test").Page, side: "left" | "right", row = 0.6) => {
  const c = await box(page.locator(".hero-castle"));
  return { x: c.x + c.width * (side === "left" ? 0.1 : 0.9), y: c.y + c.height * row };
};

test("L16 a press on the castle wall does nothing; only the door opens the gate", async ({ page }) => {
  await page.goto("/");
  const c = await box(page.locator(".hero-castle"));
  await page.mouse.click(c.x + c.width * 0.3, c.y + c.height * 0.55); // the wall between the left tower and the gate
  await page.waitForTimeout(400);
  await expect(docs(page)).toHaveCount(0);
  await expect(page.getByText("Open the gate", { exact: true })).toBeVisible();
  await openGate(page);
  await expect(docs(page)).toHaveCount(5);
});

test("L17 presses on a tower knock stones off it and leave the gate shut", async ({ page }) => {
  await page.goto("/");
  for (const row of [0.5, 0.56, 0.62]) {
    const t = await tower(page, "left", row);
    await page.mouse.click(t.x, t.y);
  }
  await expect(page.locator(".gchip").first()).toBeVisible();
  expect(Number(await page.locator(".hero-castle").getAttribute("data-damage-left"))).toBeGreaterThan(0);
  await expect(docs(page)).toHaveCount(0);
});

test("L18 a dozen presses bring a tower's roof down, then the tower rebuilds", async ({ page }) => {
  await page.goto("/");
  for (let i = 0; i < 12; i++) {
    const t = await tower(page, "right", 0.45 + (i % 4) * 0.08);
    await page.mouse.click(t.x, t.y);
    await page.waitForTimeout(60);
  }
  await expect(page.locator(".gcollapse")).toHaveCount(1);
  await expect(page.locator(".hero-castle")).toHaveAttribute("data-damage-right", "0", { timeout: 6000 });
  await expect(page.locator(".gcollapse")).toHaveCount(0);
});
