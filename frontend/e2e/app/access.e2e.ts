import { expect, test } from "@playwright/test";
import { NOTES, docText, pasteAndHide } from "./app-helpers";

// VEIL-QA-2 · one account cannot reach another's documents; a signed-out visitor sees the sign-in form.

test("S1 account B cannot open account A's document, and nobody signed out can", async ({ browser }) => {
  const a = await browser.newContext({ storageState: "e2e/.auth/a.json" });
  const pageA = await a.newPage();
  const id = await pasteAndHide(pageA, NOTES("PRIVATE-A"));
  await expect(docText(pageA)).toContainText("PRIVATE-A");

  const b = await browser.newContext({ storageState: "e2e/.auth/b.json" });
  const pageB = await b.newPage();
  const fileB = await pageB.request.get(`/api/documents/${id}/file`);
  expect(fileB.status()).toBe(404);
  await pageB.goto(`/app?doc=${id}`);
  await pageB.waitForTimeout(1500);
  await expect(pageB.getByText("PRIVATE-A")).toHaveCount(0);

  const nobody = await browser.newContext();
  const pageN = await nobody.newPage();
  await pageN.goto(`/app?doc=${id}`);
  await expect(pageN.getByRole("heading", { name: /Welcome back|Create your account/ })).toBeVisible();
  await expect(pageN.getByText("PRIVATE-A")).toHaveCount(0);
  await Promise.all([a.close(), b.close(), nobody.close()]);
});
