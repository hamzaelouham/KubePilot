import { redirect } from "next/navigation";
import { signInAction } from "./actions";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }> | { error?: string };
}) {
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const error = resolvedParams.error;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="w-full max-w-md rounded-3xl border border-border bg-card p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-lg text-primary">
            ☸
          </span>
          <h1 className="text-2xl font-semibold text-foreground">KubePilot</h1>
        </div>

        <h2 className="text-3xl font-semibold text-foreground">Sign in</h2>

        <form action={signInAction} className="mt-8 space-y-5">
          <div>
            <label htmlFor="email" className="mb-2 block text-sm text-muted-foreground">
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              placeholder="you@example.com"
              className="w-full rounded-xl border border-input bg-background px-4 py-3 text-foreground outline-none placeholder:text-muted-foreground focus:border-primary"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-2 block text-sm text-muted-foreground">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              placeholder="••••••••••"
              className="w-full rounded-xl border border-input bg-background px-4 py-3 text-foreground outline-none placeholder:text-muted-foreground focus:border-primary"
              required
            />
          </div>

          {error === "invalid" || error === "backend" ? (
            <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error === "backend" ? "Authentication service is unavailable." : "Invalid email or password."}
            </div>
          ) : null}

          <button
            type="submit"
            className="flex w-full cursor-pointer items-center justify-center rounded-xl bg-primary px-4 py-3 font-medium text-primary-foreground transition hover:bg-primary/90"
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  );
}