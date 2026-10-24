import { expect, test } from "@playwright/test";
import { NOTES, approve, docText, pasteAndHide } from "./app-helpers";

// VEIL-QA-2 · a part the model could not read. The mock fails part 3 on the first read and reads it on a retry.

test("R1 a part that was not checked says so, and Retry reads it again", async ({ page }) => {
  const long = Array.from({ length: 12 }, (_, i) => `${NOTES(`R1-${i}`)}\n`).join("\n");
  await pasteAndHide(page, long);
  await expect(page.getByText(/1 part not checked by the AI/).first()).toBeVisible();
  await expect(docText(page).getByText("Not checked by the AI").first()).toBeVisible();
  await docText(page).getByRole("button", { name: "Retry" }).first().click();
  await expect(page.getByText(/not checked by the AI/)).toHaveCount(0, { timeout: 20_000 });
  await approve(page);
});
