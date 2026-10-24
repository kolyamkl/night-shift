import { expect, test } from "@playwright/test";
import { NOTES, docText, intakeHeading, rail, reviewBar, toIntake, upload, reviewed } from "./app-helpers";

// VEIL-QA-2 · several documents: the rail, switching, New document, reload, double presses.

const named = (name: string, ref: string) => ({ name, mimeType: "text/plain", buffer: Buffer.from(NOTES(ref)) });

test("A12 every document gets a session; switching keeps each one's text", async ({ page }) => {
  const one = `qa-one-${Date.now()}.txt`;
  const two = `qa-two-${Date.now()}.txt`;
  await upload(page, named(one, "ONE-REF"));
  await reviewed(page, 20_000);
  await upload(page, named(two, "TWO-REF"));
  await reviewed(page, 20_000);
  await expect(rail(page).getByRole("button", { name: new RegExp(one) })).toBeVisible();
  await rail(page).getByRole("button", { name: new RegExp(one) }).click();
  await expect(docText(page)).toContainText("ONE-REF");
  await rail(page).getByRole("button", { name: new RegExp(two) }).click();
  await expect(docText(page)).toContainText("TWO-REF");
  await expect(rail(page).getByRole("button", { name: new RegExp(two) })).toHaveAttribute("aria-current", "true");
});

test("A12 New document goes back to the intake and reload reopens the open document", async ({ page }) => {
  const name = `qa-reload-${Date.now()}.txt`;
  await upload(page, named(name, "RELOAD-REF"));
  await reviewed(page, 20_000);
  const url = page.url();
  await page.reload();
  await expect(docText(page)).toContainText("RELOAD-REF", { timeout: 15_000 });
  expect(page.url()).toBe(url);
  await page.getByRole("button", { name: "New document" }).click();
  await expect(intakeHeading(page)).toBeVisible();
});

test.describe("on a fresh account", () => {
  test.use({ storageState: { cookies: [], origins: [] } }); // other tests add documents to account A meanwhile

  test("A13 a double click on Hide personal data opens one document, not two", async ({ page }) => {
    const email = `qa+double${Date.now()}${Math.floor(Math.random() * 1e6)}@example.test`;
    const made = await page.request.post("/api/auth/register", { data: { email, password: crypto.randomUUID() }, headers: { "X-Veil-Request": "1" } });
    expect(made.status()).toBe(201);
    await toIntake(page);
    const documents = async () => ((await (await page.request.get("/api/documents")).json()) as unknown[]).length;
    const before = await documents();
    await page.getByLabel("Or paste text").fill(NOTES(`double-${Date.now()}`));
    await page.getByRole("button", { name: "Hide personal data" }).dblclick();
    await reviewed(page, 20_000);
    await page.waitForTimeout(800);
    expect(await documents()).toBe(before + 1);
  });
});

test("A13 Back from a document returns to the intake and Forward reopens it", async ({ page }) => {
  await upload(page, named(`qa-back-${Date.now()}.txt`, "BACK-REF"));
  await reviewed(page, 20_000);
  const doc = page.url();
  await page.goBack();
  await expect(page).toHaveURL(/\/app$/);
  await expect(intakeHeading(page)).toBeVisible();
  await page.goForward();
  expect(page.url()).toBe(doc);
  await expect(docText(page)).toContainText("BACK-REF");
});

test("A13 Back walks through the documents opened from the rail", async ({ page }) => {
  const one = `qa-hist-one-${Date.now()}.txt`;
  const two = `qa-hist-two-${Date.now()}.txt`;
  await upload(page, named(one, "HIST-ONE"));
  await reviewed(page, 20_000);
  await upload(page, named(two, "HIST-TWO"));
  await reviewed(page, 20_000);
  await rail(page).getByRole("button", { name: new RegExp(one) }).click();
  await expect(docText(page)).toContainText("HIST-ONE");
  await page.goBack();
  await expect(docText(page)).toContainText("HIST-TWO");
});
