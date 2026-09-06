import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="w-full max-w-xl rounded-3xl border border-border bg-card p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-lg text-primary">
            ☸
          </span>
          <h1 className="text-2xl font-semibold text-foreground">KubePilot</h1>
        </div>
        <p className="mt-6 text-base leading-7 text-muted-foreground">
          A production-ready control plane for cluster health, workload visibility, and platform operations.
        </p>

        <div className="mt-8 space-y-3">
          <Link
            href="/login"
            className="flex w-full items-center justify-center rounded-xl bg-primary px-4 py-3 font-medium text-primary-foreground transition hover:bg-primary/90"
          >
            Go to login
          </Link>
          <Link
            href="/dashboard"
            className="flex w-full items-center justify-center rounded-xl border border-border bg-background px-4 py-3 font-medium text-foreground transition hover:bg-muted"
          >
            Open dashboard preview
          </Link>
        </div>
      </div>
    </main>
  );
}