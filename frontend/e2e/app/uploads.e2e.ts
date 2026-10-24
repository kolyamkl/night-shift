import { expect, test } from "@playwright/test";
import { approve, docText, reviewBar, upload, reviewed } from "./app-helpers";

// VEIL-QA-2 · files, against the real backend with the model off (number rules only).

test.use({ storageState: "e2e/.auth/a.json" });

const alert = (page: import("@playwright/test").Page) => page.getByRole("alert");

test("F1 a text file opens, numbers are hidden and the page says the model is off", async ({ page }) => {
  await upload(page, "notes.txt");
  await reviewed(page, 20_000);
  await expect(page.getByText(/Numbers only for now/).first()).toBeVisible();
  await expect(docText(page).locator(".val", { hasText: "20-45-77" }).first()).toHaveClass(/is-hidden/);
  await expect(docText(page).getByText("Raj Patel")).toBeVisible(); // honest: names are not looked for without the model
});

test("F2 an email shows its headers and hides the account numbers", async ({ page }) => {
  await upload(page, "client.eml");
  await reviewed(page, 20_000);
  await expect(docText(page)).toContainText("Subject: Payment details for the lease");
  await expect(docText(page).locator(".val", { hasText: "31926819" }).first()).toHaveClass(/is-hidden/);
});

test("F3 a PDF has page images and downloads as a redacted PDF", async ({ page }) => {
  await upload(page, "tenancy.pdf");
  await reviewed(page, 30_000);
  await page.getByRole("tab", { name: "Pages" }).click();
  const img = page.locator("img[src*='/pages/']").first();
  await expect(img).toBeVisible();
  await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true);
  await page.getByRole("tab", { name: "Lines" }).click();
  await approve(page);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download redacted PDF" }).click()]);
  expect(download.suggestedFilename()).toMatch(/-redacted\.pdf$/);
});

test("F4 a photo is read on this Mac and its numbers hidden", async ({ page }) => {
  await upload(page, "scan.png");
  await reviewed(page, 30_000);
  await expect(docText(page)).toContainText("Raj Patel");
  await expect(docText(page).locator(".val", { hasText: "20-45-77" }).first()).toHaveClass(/is-hidden/);
});

test("F5 an unsupported file, an empty file and a file over 20 MB each get a clear message", async ({ page }) => {
  await upload(page, "notes.docx");
  await expect(alert(page)).toContainText(/not supported|cannot|can't/i);
  await upload(page, "empty.txt");
  await expect(alert(page)).toBeVisible();
  await upload(page, { name: "huge.txt", mimeType: "text/plain", buffer: Buffer.alloc(21 * 1024 * 1024, 97) });
  await expect(alert(page)).toContainText(/20 MB/);
  await expect(page).not.toHaveURL(/doc=/);
});

test("F6 a sample opens with its pages", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: /^Open sample: Tenancy agreement/ }).first().click();
  await reviewed(page, 30_000);
  await expect(page.getByRole("tab", { name: "Pages" })).toBeVisible();
});
