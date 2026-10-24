import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "../api";
import { Button, Input, Spinner } from "../ui/kit";

export function AuthGate({ children }: { children: (user: User, logout: () => Promise<void>) => ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.me().then((value) => { if (!cancelled) setUser(value); }).catch((e) => {
      if (!cancelled && !(e instanceof ApiError && e.status === 401)) setError(e.message);
    }).finally(() => { if (!cancelled) setChecking(false); });
    const expired = () => { setUser(null); setPassword(""); setError("Your session ended. Please log in again."); };
    window.addEventListener("veil:unauthorized", expired);
    return () => { cancelled = true; window.removeEventListener("veil:unauthorized", expired); };
  }, []);

  async function logout() {
    await api.logout();
    window.history.replaceState(null, "", "/app");
    setPassword("");
    setError(null);
    setUser(null);
  }

  if (checking) return <main className="flex min-h-screen items-center justify-center gap-3 bg-bone"><Spinner label="Checking login" /> Opening MuGuard</main>;
  if (user) return children(user, logout);

  return (
    <main className="flex min-h-screen items-center justify-center bg-bone px-5 py-12">
      <section className="w-full max-w-md bg-paper p-6 px-frame sm:p-8" aria-labelledby="auth-title">
        <a href="/" className="font-pixel text-4xl font-bold">MuGuard</a>
        <h1 id="auth-title" className="mt-8 text-3xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-2 text-quiet">{mode === "login" ? "Log in to work with your documents." : "Just your email and a password. No verification email."}</p>
        <form className="mt-6 flex flex-col gap-5" onSubmit={async (event) => {
          event.preventDefault();
          if (busy) return;
          setBusy(true);
          setError(null);
          try {
            const account = await api[mode](email, password);
            setPassword("");
            setUser(account);
          } catch (e) {
            setError(e instanceof Error ? e.message : "Unable to sign in. Try again.");
          } finally { setBusy(false); }
        }}>
          <label className="flex flex-col gap-2" htmlFor="auth-email">Email
            <Input id="auth-email" name="email" type="email" autoComplete="email" required maxLength={254}
              value={email} disabled={busy} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <div className="flex flex-col gap-2">
            <label htmlFor="auth-password">Password</label>
            <Input id="auth-password" name="password" type="password" required minLength={8} maxLength={128}
              autoComplete={mode === "login" ? "current-password" : "new-password"} aria-describedby="password-hint"
              value={password} disabled={busy} onChange={(e) => setPassword(e.target.value)} />
            <span id="password-hint" className="text-sm text-quiet">At least 8 characters.</span>
          </div>
          {error && <p role="alert" className="text-signal-deep">{error}</p>}
          <Button type="submit" variant="primary" loading={busy} className="w-full">
            {mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>
        <div className="mt-6 flex flex-wrap items-center gap-2 text-sm">
          <span>{mode === "login" ? "New to MuGuard?" : "Already have an account?"}</span>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => {
            setMode(mode === "login" ? "register" : "login"); setError(null); setPassword("");
          }}>{mode === "login" ? "Create account" : "Log in"}</Button>
        </div>
      </section>
    </main>
  );
}
