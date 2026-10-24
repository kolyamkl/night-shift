import { expect, test } from "@playwright/test";
import { NOTES, approve, askPanel, noSideScroll, pasteAndHide, reviewBar, toIntake } from "./app-helpers";

// VEIL-QA-2 · the app on a phone (Pixel 7, touch).

test("M1 the intake fits the phone and keeps New document at hand", async ({ page }) => {
  await toIntake(page);
  await noSideScroll(page);
  await expect(page.getByRole("button", { name: "New document" })).toBeInViewport();
});

test("M2 the review bar stays on screen while scrolling a long document", async ({ page }) => {
  const long = Array.from({ length: 120 }, (_, i) => `Line ${i + 1}: call 07700 900${String(100 + i).padStart(3, "0")} about the lease.`).join("\n");
  await pasteAndHide(page, long);
  for (const f of [0.2, 0.5, 0.9]) {
    await page.evaluate((k) => window.scrollTo(0, document.documentElement.scrollHeight * k), f);
    await page.waitForTimeout(250);
    await expect(reviewBar(page)).toBeInViewport();
  }
  await noSideScroll(page);
});

test("M3 approve and ask on a phone", async ({ page }) => {
  await pasteAndHide(page, NOTES("phone"));
  await approve(page);
  const panel = askPanel(page);
  await panel.scrollIntoViewIfNeeded();
  await panel.getByLabel("Ask about this document").fill("Who is the tenant?");
  await panel.getByRole("button", { name: "Ask", exact: true }).tap();
  await expect(panel.locator("mark").first()).toBeVisible({ timeout: 15_000 });
  await noSideScroll(page);
});
