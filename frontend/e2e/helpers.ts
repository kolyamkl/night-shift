import { expect, type Locator, type Page } from "@playwright/test";

export type Box = { x: number; y: number; width: number; height: number };

export async function box(locator: Locator): Promise<Box> {
  const b = await locator.boundingBox();
  expect(b, "element should be on the page").not.toBeNull();
  return b!;
}

export const overlaps = (a: Box, b: Box) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

export const castle = (page: Page) => page.getByRole("button", { name: "Open the castle gate" });
export const scene = (page: Page) => page.locator(".scene");
export const docs = (page: Page) => page.locator(".gdoc");
export const score = (page: Page) => page.getByRole("status").filter({ hasText: "With MuGuard, the AI provider gets" });

// Console errors collected for the whole test; the dev server's own HMR chatter is not an app error.
export function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("[vite]")) errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

export async function openGate(page: Page) {
  const c = await box(castle(page));
  await page.mouse.move(c.x + c.width / 2, c.y + c.height - 40);
  await page.mouse.down();
  await page.mouse.up();
}

// Every finished document sits inside the scene, with its stamp above the band under the castle.
export async function expectFanInsideScene(page: Page, count: number) {
  await expect(docs(page)).toHaveCount(count);
  const s = await box(scene(page));
  for (const d of await docs(page).all()) {
    const b = await box(d);
    expect(b.x, "document left edge inside the scene").toBeGreaterThanOrEqual(s.x - 1);
    expect(b.x + b.width, "document right edge inside the scene").toBeLessThanOrEqual(s.x + s.width + 1);
    const stamp = await box(d.locator(".gstamp"));
    expect(stamp.y + stamp.height, "stamp above the band").toBeLessThanOrEqual(s.y + s.height + 1);
  }
}
