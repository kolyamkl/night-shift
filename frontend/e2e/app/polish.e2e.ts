import { expect, test } from "@playwright/test";
import { NOTES, approve, askPanel, noSideScroll, pasteAndHide, tinyText, toIntake } from "./app-helpers";

// VEIL-QA-2 · the look: straight rules, readable sizes, no side scroll, hover and focus states.

test("P1 the document header and the Ask header end on the same line", async ({ page }) => {
  await pasteAndHide(page, NOTES("rules"));
  await approve(page);
  const doc = await page.locator("section > header").first().boundingBox();
  const ask = await askPanel(page).locator("> div").first().boundingBox();
  expect(Math.round(doc!.y + doc!.height)).toBe(Math.round(ask!.y + ask!.height));
});

for (const width of [1440, 1024]) {
  test(`P2 no side scroll at ${width} px on the intake, in review and after approval`, async ({ page }) => {
    await page.setViewportSize({ width, height: 860 });
    await toIntake(page);
    await noSideScroll(page);
    await pasteAndHide(page, NOTES(`w${width}`));
    await noSideScroll(page);
    await approve(page);
    await noSideScroll(page);
  });
}

test("P3 no text under 10 px on the intake, in review or in the Ask panel", async ({ page }) => {
  await toIntake(page);
  expect(await tinyText(page.locator("body"))).toEqual([]);
  await pasteAndHide(page, NOTES("sizes"));
  expect(await tinyText(page.locator("body"))).toEqual([]);
  await approve(page);
  expect(await tinyText(askPanel(page))).toEqual([]);
});

test("P4 a button rises on hover and shows a focus ring from the keyboard", async ({ page }) => {
  await toIntake(page);
  const button = page.getByRole("button", { name: "Choose a file" });
  const rest = await button.evaluate((el) => { const s = getComputedStyle(el); return `${s.transform}|${s.translate}|${s.filter}`; });
  await button.hover();
  await page.waitForTimeout(250);
  const hover = await button.evaluate((el) => { const s = getComputedStyle(el); return `${s.transform}|${s.translate}|${s.filter}`; });
  expect(hover, "hover changes the button").not.toBe(rest);
  await page.mouse.move(0, 0);
  await button.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await expect(button).toBeFocused();
  const ring = await button.evaluate((el) => { const s = getComputedStyle(el); return s.outlineStyle !== "none" || s.boxShadow !== "none"; });
  expect(ring, "visible keyboard focus").toBe(true);
});

test("P5 pixel faces for MuGuard, the serif for the document", async ({ page }) => {
  await pasteAndHide(page, NOTES("fonts"));
  const font = (sel: string) => page.locator(sel).first().evaluate((el) => getComputedStyle(el).fontFamily);
  expect(await font('[aria-label="Document text"] .doc-line span.font-serif')).toMatch(/Source Serif/);
  expect(await font('button:has-text("Approve all")')).toMatch(/Pixelify|Silkscreen/);
  expect(await font("h2")).toMatch(/Pixelify|Silkscreen/);
});

test("P6 a sample card lifts and shows Open sample on hover and on keyboard focus", async ({ page }) => {
  await toIntake(page);
  const card = page.getByRole("button", { name: /^Open sample:/ }).first();
  const bar = card.locator(".sample-open");
  const y = async () => (await card.boundingBox())!.y;
  const rest = await y();
  const hiddenBar = await bar.evaluate((el) => getComputedStyle(el).transform);
  await card.hover();
  await page.waitForTimeout(350);
  expect(await y(), "card lifts").toBeLessThan(rest);
  expect(await bar.evaluate((el) => getComputedStyle(el).transform), "Open sample slides in").not.toBe(hiddenBar);
  await page.mouse.move(0, 0);
  await card.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await page.waitForTimeout(350);
  expect(await bar.evaluate((el) => getComputedStyle(el).transform)).not.toBe(hiddenBar);
});
