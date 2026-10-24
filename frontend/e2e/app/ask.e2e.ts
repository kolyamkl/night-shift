import { expect, test } from "@playwright/test";
import { NOTES, SECRETS, approve, askPanel, pasteAndHide } from "./app-helpers";

// VEIL-QA-2 · Ask the AI after approval. The mock answers with the document's placeholders; the page puts the
// real values back. "What it sees" must never show a real value.

test("A10 Ask: the answer comes back with the real values, marked", async ({ page }) => {
  await pasteAndHide(page, NOTES("ask"));
  await approve(page);
  const panel = askPanel(page);
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("tab", { name: "Ask the AI" })).toHaveAttribute("aria-selected", "true");
  const ask = panel.getByRole("button", { name: "Ask", exact: true });
  await expect(ask).toBeDisabled();
  const box = panel.getByLabel("Ask about this document");
  await box.fill("Who is the tenant and what is the phone number?");
  await expect(ask).toBeEnabled();
  await box.press("Enter");
  await expect(panel.getByText("Who is the tenant and what is the phone number?")).toBeVisible();
  const answer = panel.locator("mark").first();
  await expect(answer).toBeVisible({ timeout: 15_000 });
  const marked = await panel.locator("mark").allInnerTexts();
  expect(marked.some((m) => [...SECRETS, "Mr Raj Patel", "Raj Patel"].some((v) => m.includes(v)))).toBe(true);
  await expect(box).toHaveValue("");
});

test("A10 Shift+Enter starts a new line instead of sending", async ({ page }) => {
  await pasteAndHide(page, NOTES("shift"));
  await approve(page);
  const box = askPanel(page).getByLabel("Ask about this document");
  await box.fill("First line");
  await box.press("Shift+Enter");
  await box.pressSequentially("second line");
  await expect(box).toHaveValue("First line\nsecond line");
  await expect(askPanel(page).locator("mark")).toHaveCount(0);
});

test("A11 What it sees: only placeholders, never a real value", async ({ page }) => {
  await pasteAndHide(page, NOTES("sees"));
  await approve(page);
  const panel = askPanel(page);
  await panel.getByLabel("Ask about this document").fill("When is the rent due?");
  await panel.getByLabel("Ask about this document").press("Enter");
  await expect(panel.locator("mark, p").filter({ hasText: /due|1st|rent/i }).first()).toBeVisible({ timeout: 15_000 });
  await panel.getByRole("tab", { name: "What it sees" }).click();
  await expect(panel.getByText("The only text the AI receives")).toBeVisible();
  const seen = await panel.innerText();
  expect(seen).toContain("PERSON_1");
  for (const v of [...SECRETS, "Raj Patel"]) expect(seen, `${v} reached the AI`).not.toContain(v);
});

test("A14 the Ask conversation is still there after a reload", async ({ page }) => {
  await pasteAndHide(page, NOTES("keep"));
  await approve(page);
  const panel = askPanel(page);
  await panel.getByLabel("Ask about this document").fill("Who is the tenant?");
  await panel.getByLabel("Ask about this document").press("Enter");
  await expect(panel.locator("mark").first()).toBeVisible({ timeout: 15_000 });
  await page.reload();
  await expect(askPanel(page).getByText("Who is the tenant?")).toBeVisible({ timeout: 15_000 });
  await expect(askPanel(page).locator("mark").first()).toBeVisible();
});
