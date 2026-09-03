import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-12 text-slate-100">
      <div className="w-full max-w-xl rounded-3xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl shadow-slate-950/50">
        <p className="text-xs uppercase tracking-[0.3em] text-cyan-300">Kubernetes dashboard</p>
        <h1 className="mt-4 text-4xl font-semibold text-white">KubePilot</h1>
        <p className="mt-4 text-base leading-7 text-slate-300">
          A production-ready control plane for cluster health, workload visibility, and platform operations.
        </p>

        <div className="mt-8 space-y-3">
          <Link
            href="/login"
            className="flex w-full items-center justify-center rounded-xl bg-cyan-500 px-4 py-3 font-medium text-slate-950 transition hover:bg-cyan-400"
          >
            Go to login
          </Link>
          <Link
            href="/dashboard"
            className="flex w-full items-center justify-center rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 font-medium text-slate-100 transition hover:border-slate-500"
          >
            Open dashboard preview
          </Link>
        </div>
      </div>
    </main>
  );
}
