import { expect, test as setup } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

// Two fresh test accounts on the local backend, saved as browser state for the app projects.
// A owns the documents; B checks that it cannot see them. Passwords are random and never printed.

setup("the backend is up with its database", async ({ request }) => {
  const res = await request.get("http://127.0.0.1:8000/api/health").catch(() => null);
  expect(res?.ok(), "start the backend: python3 scripts/local_db.py start, then uv run --directory backend --env-file ../.env uvicorn app.main:app --port 8000").toBe(true);
  expect((await res!.json()).database).toBe("postgresql");
});

for (const who of ["a", "b"]) {
  setup(`account ${who}`, async ({ request, baseURL }) => {
    const email = `qa+${who}${Date.now()}${Math.floor(Math.random() * 1e6)}@example.test`;
    const password = crypto.randomUUID();
    const res = await request.post(`${baseURL}/api/auth/register`, { data: { email, password }, headers: { "X-Veil-Request": "1" } });
    expect(res.status(), await res.text()).toBe(201);
    mkdirSync("e2e/.auth", { recursive: true });
    await request.storageState({ path: `e2e/.auth/${who}.json` });
    writeFileSync(`e2e/.auth/${who}.email`, email);
  });
}
