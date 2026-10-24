import { defineConfig, devices } from "@playwright/test";

// End-to-end checks. Files end in .e2e.ts so Vitest does not pick them up.
//
// - desktop, phone: the landing page on the plain dev server (:5173). No backend needed.
// - app, app-phone: the app on a second dev server (:5175) whose /api goes through the mock stream (:8011,
//   frontend/scripts/mock-stream.mjs) to the real backend. The mock plays the redaction model and the Ask model,
//   so names, parts and answers can be checked without a Mubit key.
// - app-real: the app on :5173 straight against the real backend with the model off: uploads, OCR, downloads,
//   accounts and access between accounts.
//
// The app projects need the backend on :8000 with its database:
//   python3 scripts/local_db.py start
//   uv run --directory backend --env-file ../.env uvicorn app.main:app --port 8000
const MOCK = "http://127.0.0.1:8011";
const APP = "http://localhost:5175";
const REAL = "http://localhost:5173";
const MOCK_FAILS = "http://127.0.0.1:8012"; // the same mock, but part 3 fails on the first read
const APP_FAILS = "http://localhost:5176";

export default defineConfig({
  testDir: "e2e",
  timeout: 40_000,
  fullyParallel: true,
  workers: 4, // the backend allows 30 sign-ins a minute per address
  reporter: [["list"]],
  use: { baseURL: REAL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", testMatch: "landing.e2e.ts", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "phone", testMatch: "landing-phone.e2e.ts", use: { ...devices["Pixel 7"] } },
    { name: "accounts", testMatch: "app/accounts.setup.ts", use: { baseURL: APP } },
    {
      name: "app",
      testMatch: "app/{flow,review,ask,sessions,polish}.e2e.ts",
      dependencies: ["accounts"],
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, baseURL: APP, storageState: "e2e/.auth/a.json" },
    },
    {
      name: "app-retry",
      testMatch: "app/retry.e2e.ts",
      dependencies: ["accounts"],
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, baseURL: APP_FAILS, storageState: "e2e/.auth/a.json" },
    },
    {
      name: "app-phone",
      testMatch: "app/phone.e2e.ts",
      dependencies: ["accounts"],
      use: { ...devices["Pixel 7"], baseURL: APP, storageState: "e2e/.auth/a.json" },
    },
    {
      name: "app-real",
      testMatch: "app/{auth,uploads,access}.e2e.ts",
      dependencies: ["accounts"],
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, baseURL: REAL, acceptDownloads: true },
    },
  ],
  webServer: [
    { command: "npm run dev", url: REAL, reuseExistingServer: true },
    { command: `MOCK_PORT=8011 MOCK_ERROR=none node scripts/mock-stream.mjs`, url: `${MOCK}/api/health`, reuseExistingServer: true },
    { command: `VEIL_API=${MOCK} npx vite --port 5175 --strictPort`, url: APP, reuseExistingServer: true },
    { command: `MOCK_PORT=8012 node scripts/mock-stream.mjs`, url: `${MOCK_FAILS}/api/health`, reuseExistingServer: true },
    { command: `VEIL_API=${MOCK_FAILS} npx vite --port 5176 --strictPort`, url: APP_FAILS, reuseExistingServer: true },
  ],
});
