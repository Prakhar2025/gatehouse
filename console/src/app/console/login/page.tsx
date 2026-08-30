"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

/**
 * Client gate that pairs with the middleware: /api/me is the auth check,
 * and the login form posts to /api/auth. Kept tiny on purpose.
 */
export default function LoginPage() {
  const router = useRouter();
  const params = usePathname();
  void params;
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/me").then((r) => {
      if (r.ok) router.replace("/console");
    });
  }, [router]);

  return (
    <main className="flex min-h-svh items-center justify-center bg-bg px-6">
      <form
        className="w-full max-w-sm rounded-xl border border-line bg-card p-7"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(false);
          const r = await fetch("/api/auth", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password }),
          });
          setBusy(false);
          if (r.ok) router.replace("/console");
          else setError(true);
        }}
      >
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-fg-subtle">
          gatehouse
        </div>
        <h1 className="font-display mt-3 text-2xl font-medium">Guardian sign in</h1>
        <p className="mt-1.5 text-xs text-fg-muted">
          Household console. One password, set in the environment.
        </p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          aria-label="Console password"
          className="mt-5 w-full rounded border border-line bg-bg px-3 py-2.5 text-sm"
          placeholder="console password"
        />
        {error ? (
          <p className="mt-2 text-xs text-scam-fg" role="alert">
            Wrong password.
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy || password.length === 0}
          className="mt-4 w-full rounded bg-bone px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "..." : "Enter"}
        </button>
      </form>
    </main>
  );
}
