import { expect, type Download, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

// Text with UK personal data. The number rules find the phone, sort code and account; the mock's model also
// finds the name. `ref` makes each pasted document tell itself apart.
export const NOTES = (ref = "") =>
  `Client notes${ref ? ` ${ref}` : ""}\n\nTenant: Mr Raj Patel\nPhone: 07700 900123\nSort code: 20-45-77\nAccount: 31926819\n\nRent of 950 pounds is due on the 1st.`;
export const SECRETS = ["07700 900123", "20-45-77", "31926819"];

export const reviewBar = (page: Page) => page.getByRole("button", { name: "Approve all", exact: true });
export const docText = (page: Page) => page.getByRole("article", { name: "Document text" });
export const rail = (page: Page) => page.getByRole("navigation", { name: "Documents in this session" }).last();
export const askPanel = (page: Page) => page.getByRole("complementary", { name: "Ask an AI about this document" });
export const intakeHeading = (page: Page) => page.getByRole("heading", { name: "Hide the personal data in a document" });

export function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("[vite]")) errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

/** Open the intake (a fresh document), whatever the app shows now. */
export async function toIntake(page: Page) {
  if (!page.url().includes("/app")) await page.goto("/app");
  await expect(page.getByRole("button", { name: "New document" })).toBeVisible();
  if (!(await intakeHeading(page).isVisible())) await page.getByRole("button", { name: "New document" }).click();
  await expect(intakeHeading(page)).toBeVisible();
}

/** Paste text, press "Hide personal data" and wait until the pass ends with the review bar. Returns the doc id. */
export async function pasteAndHide(page: Page, text: string): Promise<string> {
  await toIntake(page);
  await page.getByLabel("Or paste text").fill(text);
  await page.getByRole("button", { name: "Hide personal data" }).click();
  await reviewed(page);
  await expect(page).toHaveURL(/doc=/);
  return new URL(page.url()).searchParams.get("doc")!;
}

/** The pass has finished: the review bar has risen and the document can be edited. */
export async function reviewed(page: Page, timeout = 30_000) {
  await expect(page.locator(".review-bar.is-up")).toBeVisible({ timeout });
}

export async function upload(page: Page, file: string | { name: string; mimeType: string; buffer: Buffer }) {
  await toIntake(page);
  await page.locator('input[type="file"]').setInputFiles(typeof file === "string" ? `e2e/fixtures/${file}` : file);
}

/** Approve all, close the victory scene with Escape and wait for the approved bar. */
export async function approve(page: Page) {
  await reviewBar(page).click();
  await expect(page.getByRole("dialog", { name: "Secured by MuGuard" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByText("Approved. Ask about it on the right")).toBeVisible();
}

export async function downloadedText(download: Download): Promise<string> {
  return readFileSync((await download.path())!, "utf8");
}

/** Values hidden on the page: their placeholders, in document order. */
export async function placeholders(page: Page): Promise<string[]> {
  return docText(page).locator("[aria-label$=', hidden']").evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")!.replace(", hidden", "").replace(/^\[|\]$/g, "")));
}

/** Every visible text smaller than `min` px, outside the placeholder tags drawn inside black bars. */
export async function tinyText(scope: Locator, min = 10): Promise<string[]> {
  return scope.evaluate((root, floor) => {
    const out: string[] = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el || !n.textContent?.trim() || el.closest(".val, [aria-hidden='true'], .sr-only")) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (size < floor) out.push(`${size}px "${n.textContent.trim().slice(0, 40)}"`);
    }
    return out;
  }, min);
}

export async function noSideScroll(page: Page) {
  const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(scroll, "no horizontal scroll").toBeLessThanOrEqual(width);
}
