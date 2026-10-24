import { expect, test, type Page } from "@playwright/test";
import { NOTES, SECRETS, approve, docText, downloadedText, pasteAndHide, placeholders, rail, reviewBar } from "./app-helpers";

// VEIL-QA-2 · reviewing a document: moving through changes, fixing a miss, showing a value, declining, approving.

const focused = (page: Page) => docText(page).locator(".val.is-focus").getAttribute("data-entity");

test("A4 Next and Prev walk through the changes and wrap around", async ({ page }) => {
  await pasteAndHide(page, NOTES("walk"));
  const total = (await placeholders(page)).length;
  expect(total).toBeGreaterThanOrEqual(4);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  const first = await focused(page);
  expect(first).not.toBeNull();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  const second = await focused(page);
  expect(second).not.toBe(first);
  await page.getByRole("button", { name: "Prev", exact: true }).click();
  expect(await focused(page)).toBe(first);
  await page.getByRole("button", { name: "Prev", exact: true }).click(); // before the first change: wraps to the last
  const last = await focused(page);
  expect(last).not.toBe(first);
});

// Select `word` inside one document line and release the mouse, as a person does to mark a miss.
async function selectWord(page: Page, word: string) {
  await page.evaluate((w) => {
    const walker = document.createTreeWalker(document.querySelector('[aria-label="Document text"]')!, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const i = n.textContent!.indexOf(w);
      if (i < 0 || n.parentElement!.closest(".val")) continue;
      const range = document.createRange();
      range.setStart(n, i);
      range.setEnd(n, i + w.length);
      const sel = window.getSelection()!;
      sel.removeAllRanges();
      sel.addRange(range);
      const r = range.getBoundingClientRect();
      n.parentElement!.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, clientX: r.right, clientY: r.bottom }));
      return;
    }
    throw new Error(`"${w}" is not in the document`);
  }, word);
}

test("A5 Fix a miss: a selected word gets hidden, then shown again from its bar", async ({ page }) => {
  await pasteAndHide(page, NOTES("fix"));
  const before = (await placeholders(page)).length;
  const fix = page.getByRole("button", { name: "Fix a miss", exact: true });
  await fix.click();
  await expect(fix).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Select the missed text on the page, then press Hide.")).toBeVisible();
  await selectWord(page, "Rent");
  const pick = page.getByRole("dialog", { name: "Hide selected text" });
  await expect(pick).toBeVisible();
  await pick.getByRole("button", { name: "Hide" }).click();
  await expect.poll(async () => (await placeholders(page)).length).toBe(before + 1);
  const bar = docText(page).locator(".val.is-hidden", { hasText: "Rent" }).first();
  await expect(bar).toBeVisible();

  await bar.click();
  const pop = page.getByRole("dialog", { name: "Hidden value" });
  await expect(pop).toBeVisible();
  await pop.getByRole("button", { name: "Not personal, show it" }).click();
  await expect(docText(page).locator(".val", { hasText: "Rent" })).toHaveCount(0);
  await expect.poll(async () => (await placeholders(page)).length).toBe(before);
});

test("A5 Fix a miss explains a selection that spans two lines", async ({ page }) => {
  await pasteAndHide(page, NOTES("span"));
  await page.getByRole("button", { name: "Fix a miss", exact: true }).click();
  await page.evaluate(() => {
    const lines = [...document.querySelectorAll('[aria-label="Document text"] .doc-line')].filter((l) => l.textContent!.includes("Rent") || l.textContent!.includes("Client"));
    const range = document.createRange();
    range.setStart(lines[0], 0);
    range.setEnd(lines[lines.length - 1], 1);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    lines[0].dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await expect(page.getByText("Select text within one line, then press Hide.")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Hide selected text" })).toHaveCount(0);
});

test("A6 Decline keeps the document out of the AI's hands", async ({ page }) => {
  await pasteAndHide(page, NOTES("decline"));
  await page.getByRole("button", { name: "Decline", exact: true }).click();
  await expect(page.getByText("Declined. Nothing from this document was sent to the AI provider.")).toBeVisible();
  await expect(reviewBar(page)).toHaveCount(0);
  await expect(rail(page).locator('[aria-current="true"]')).toContainText("Declined");
});

test("A7 Approve all: the victory scene closes with Escape, Enter or a click", async ({ page }) => {
  for (const close of ["Escape", "Enter", "click"] as const) {
    await pasteAndHide(page, NOTES(`win-${close}`));
    await reviewBar(page).click();
    const scene = page.getByRole("dialog", { name: "Secured by MuGuard" });
    await expect(scene).toBeVisible();
    if (close === "click") await scene.click({ position: { x: 20, y: 20 } });
    else await page.keyboard.press(close);
    await expect(scene).toBeHidden();
    await expect(page.getByText("Approved. Ask about it on the right")).toBeVisible();
  }
});

test("A8 the redacted download has placeholders and no personal value", async ({ page }) => {
  await pasteAndHide(page, NOTES("download"));
  await approve(page);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download redacted text" }).click()]);
  expect(download.suggestedFilename()).toMatch(/-redacted\.txt$/);
  const text = await downloadedText(download);
  expect(text).toContain("[PERSON_1]");
  for (const v of [...SECRETS, "Raj Patel"]) expect(text).not.toContain(v);
});

test("A9 Edit redactions reopens an approved document for review", async ({ page }) => {
  await pasteAndHide(page, NOTES("edit"));
  await approve(page);
  await page.getByRole("button", { name: "Edit redactions", exact: true }).click();
  await expect(reviewBar(page)).toBeVisible();
  await expect(rail(page).locator('[aria-current="true"]')).toContainText(/Review/);
});
