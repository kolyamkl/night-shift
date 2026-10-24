import { expect, test } from "@playwright/test";
import { NOTES, SECRETS, collectErrors, docText, intakeHeading, pasteAndHide, placeholders, reviewBar, toIntake } from "./app-helpers";

// VEIL-QA-2 · the main path: intake, paste, the redaction pass. The model is the mock's.

test("A2 the intake offers a drop zone, a paste field and sample cards with thumbnails", async ({ page }) => {
  await toIntake(page);
  await expect(page.getByRole("button", { name: "Choose a file" })).toBeVisible();
  await expect(page.getByLabel("Or paste text")).toBeVisible();
  const cards = page.getByRole("button", { name: /^Open sample:/ });
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBe(8);
  const thumbs = page.locator(".sample-thumb img, img.sample-thumb");
  await expect.poll(async () => thumbs.first().evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
  await page.getByRole("button", { name: /^Show all \d+/ }).click();
  expect(await cards.count()).toBeGreaterThan(8);
});

test("A2 the paste button needs text", async ({ page }) => {
  await toIntake(page);
  await page.getByLabel("Or paste text").fill("   ");
  const hide = page.getByRole("button", { name: "Hide personal data" });
  if (await hide.isEnabled()) {
    await hide.click();
    await expect(intakeHeading(page)).toBeVisible(); // nothing opens for blank text
    await expect(page).not.toHaveURL(/doc=/);
  } else {
    await expect(hide).toBeDisabled();
  }
});

test("A3 a pasted note is read part by part and every personal value ends up behind a bar", async ({ page }) => {
  const errors = collectErrors(page);
  await pasteAndHide(page, NOTES("A3"));
  // The real value stays in the page under its bar (the review is local); what matters is that a bar covers it.
  for (const v of SECRETS) await expect(docText(page).locator(".val", { hasText: v }).first(), `${v} behind a bar`).toHaveClass(/is-hidden/);
  await expect(docText(page).locator(".val", { hasText: "Raj Patel" }).first(), "the name behind a bar").toHaveClass(/is-hidden/);
  const tags = await placeholders(page);
  expect(tags).toEqual(expect.arrayContaining([expect.stringMatching(/^PERSON_\d+$/), expect.stringMatching(/^PHONE_\d+$/)]));
  await expect(page.getByText(/\d+ changes?/).first()).toBeVisible();
  await expect(reviewBar(page)).toBeEnabled();
  expect(errors).toEqual([]);
});

test("A3 the parts list shows how each part was read", async ({ page }) => {
  await pasteAndHide(page, NOTES("parts"));
  const parts = page.getByRole("button", { name: /\d+ parts?/ });
  await parts.click();
  await expect(parts).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("How each part was read")).toBeVisible();
  await expect(page.getByText("Checked").first()).toBeVisible();
  await parts.click();
  await expect(page.getByText("How each part was read")).toBeHidden();
});
