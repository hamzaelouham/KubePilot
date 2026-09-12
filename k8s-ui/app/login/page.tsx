import { signInAction } from "./actions";
import { Boxes } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }>;
}) {
  const resolvedParams = searchParams ? await searchParams : {};
  const error = resolvedParams.error;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Boxes aria-hidden="true" className="size-5" />
          </span>
          <h1 className="text-2xl font-semibold text-foreground">KubePilot</h1>
        </div>

        <h2 className="text-3xl font-semibold text-foreground">Sign in</h2>

        <form action={signInAction} className="mt-8 space-y-5">
          <div className="flex flex-col gap-2">
            <label htmlFor="email" className="text-sm font-medium">
              Email address
            </label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <Input
              id="password"
              name="password"
              type="password"
              placeholder="••••••••••"
              required
            />
          </div>

          {error === "invalid" || error === "backend" ? (
            <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error === "backend" ? "Authentication service is unavailable." : "Invalid email or password."}
            </div>
          ) : null}

          <Button type="submit" className="w-full">Sign in</Button>
        </form>
      </div>
    </main>
  );
}
