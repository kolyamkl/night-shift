import { expect, test } from "@playwright/test";
import { box, castle, overlaps } from "./helpers";

// VEIL-QA-1 on a phone (Pixel 7, touch): the camera pans across the journey, and the game fits a narrow scene.

test("L11 the journey's hills cover the whole screen while the camera pans", async ({ page }) => {
  await page.goto("/");
  const width = page.viewportSize()!.width;
  const journey = page.locator("#journey");
  const top = await journey.evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  const height = await journey.evaluate((el) => el.offsetHeight);
  for (const f of [0.1, 0.3, 0.5, 0.7, 0.9]) {
    await page.evaluate((y) => window.scrollTo(0, y), top + height * f);
    await page.waitForTimeout(500);
    const layers = await page.locator("#journey [data-hills]").all();
    expect(layers.length, "far and near hill layers").toBeGreaterThanOrEqual(2);
    for (const layer of layers) {
      const b = await box(layer);
      expect(b.x, `hills left edge at ${f}`).toBeLessThanOrEqual(0.5);
      expect(b.x + b.width, `hills right edge at ${f}`).toBeGreaterThanOrEqual(width - 0.5);
    }
  }
});

test("L5 the skip button does not cover the enlarged document", async ({ page }) => {
  await page.goto("/");
  await castle(page).tap();
  const skip = page.getByRole("button", { name: "Let the guard do it" });
  await expect(skip).toBeVisible({ timeout: 4000 });
  await page.waitForTimeout(600);
  expect(overlaps(await box(skip), await box(page.locator(".gdoc.is-big")))).toBe(false);
});

test("L4 three documents fly out on a phone", async ({ page }) => {
  await page.goto("/");
  await castle(page).tap();
  await expect(page.locator(".gdoc")).toHaveCount(3);
});

test("L6 a tap hides a value on a phone", async ({ page }) => {
  await page.goto("/");
  await castle(page).tap();
  await expect(page.locator(".ghud")).toBeVisible({ timeout: 4000 });
  await page.waitForTimeout(500);
  await page.locator(".gdoc.is-big .gval").first().tap();
  await expect(page.locator(".ghud-count")).toHaveText("1 / 4");
});

test("L12 no custom cursor on a touch screen", async ({ page }) => {
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.classList.contains("has-sword-cursor"))).toBe(false);
});
