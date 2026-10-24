import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { intakeHeading } from "./app-helpers";

// VEIL-QA-2 · accounts, against the real backend. Each test starts signed out.

const email = () => `qa+auth${Date.now()}${Math.floor(Math.random() * 1e6)}@example.test`;

async function register(page: import("@playwright/test").Page, address: string, password: string) {
  await page.goto("/app");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await page.getByLabel("Email").fill(address);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).last().click();
}

test("U1 sign up, log out, log back in", async ({ page }) => {
  const address = email();
  const password = crypto.randomUUID();
  await register(page, address, password);
  await expect(intakeHeading(page)).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: /Welcome back|Create your account/ })).toBeVisible();
  if (await page.getByRole("heading", { name: "Create your account" }).isVisible()) await page.getByRole("button", { name: "Log in" }).last().click();
  await page.getByLabel("Email").fill(address);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).first().click();
  await expect(intakeHeading(page)).toBeVisible();
});

test("U2 after logging out the form offers Log in, not sign-up", async ({ page }) => {
  await register(page, email(), crypto.randomUUID());
  await expect(intakeHeading(page)).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("U3 a wrong password says so and keeps the form", async ({ page }) => {
  await page.goto("/app");
  await page.getByLabel("Email").fill(readFileSync("e2e/.auth/a.email", "utf8"));
  await page.getByLabel("Password").fill("not-the-password-123");
  await page.getByRole("button", { name: "Log in" }).first().click();
  await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect.");
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("U4 an email that already has an account is turned away politely", async ({ page }) => {
  await register(page, readFileSync("e2e/.auth/a.email", "utf8"), crypto.randomUUID());
  await expect(page.getByRole("alert")).toContainText("An account with this email already exists");
});

test("U5 a password under 8 characters is not sent", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Email").fill(email());
  await page.getByLabel("Password").fill("short");
  let sent = false;
  page.on("request", (r) => {
    if (r.url().includes("/api/auth/register")) sent = true;
  });
  await page.getByRole("button", { name: "Create account" }).last().click();
  await page.waitForTimeout(300);
  expect(sent).toBe(false);
  expect(await page.getByLabel("Password").evaluate((el: HTMLInputElement) => el.validity.tooShort)).toBe(true);
});
