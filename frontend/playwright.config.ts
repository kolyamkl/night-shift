import { defineConfig, devices } from "@playwright/test";

// End-to-end checks against the Vite dev server. The landing page needs no backend.
// Files end in .e2e.ts so Vitest does not pick them up.
export default defineConfig({
  testDir: "e2e",
  timeout: 40_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", testMatch: "landing.e2e.ts", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "phone", testMatch: "landing-phone.e2e.ts", use: { ...devices["Pixel 7"] } },
  ],
  webServer: { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true },
});
