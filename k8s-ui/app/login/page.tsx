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
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#11243d_0%,_#0f172a_45%,_#020817_100%)] px-6 py-12 text-slate-100">
      <div className="w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-700 bg-slate-900/80 shadow-2xl shadow-slate-950/50 backdrop-blur-xl">
        <div className="grid lg:grid-cols-[1.2fr_0.8fr]">
          <div className="p-10 lg:p-12">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-500/20 text-lg font-bold text-cyan-300">
                K
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Control plane</p>
                <h1 className="text-2xl font-semibold text-white">KubePilot</h1>
              </div>
            </div>

            <div className="max-w-lg">
              <p className="mb-3 text-sm font-medium uppercase tracking-[0.25em] text-cyan-300">
                Kubernetes management UI
              </p>
              <h2 className="text-4xl font-semibold leading-tight text-white">
                Secure operations for your production clusters.
              </h2>
              <p className="mt-4 text-base leading-7 text-slate-300">
                Monitor workloads, inspect pods, review events, and understand cluster health from one streamlined interface built for platform teams.
              </p>
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {[
                ["95%", "Cluster uptime"],
                ["18", "Connected nodes"],
                ["4.2s", "Avg. API latency"],
              ].map(([value, label]) => (
                <div key={label} className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">
                  <div className="text-2xl font-semibold text-white">{value}</div>
                  <div className="mt-1 text-sm text-slate-400">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-slate-700 bg-slate-950/70 p-8 lg:border-l lg:border-t-0">
            <div className="mb-8">
              <p className="text-sm text-slate-400">Welcome back</p>
              <h3 className="mt-1 text-3xl font-semibold text-white">Sign in</h3>
            </div>

            <form action={signInAction} className="space-y-5">
              <div>
                <label htmlFor="email" className="mb-2 block text-sm text-slate-300">
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  defaultValue="ops@kubepilot.io"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-0 placeholder:text-slate-500 focus:border-cyan-400"
                  required
                />
              </div>

              <div>
                <label htmlFor="password" className="mb-2 block text-sm text-slate-300">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  defaultValue="kubepilot"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none ring-0 focus:border-cyan-400"
                  required
                />
              </div>

              <div className="flex items-center justify-between text-sm text-slate-400">
                <label className="inline-flex items-center gap-2">
                  <input type="checkbox" className="h-4 w-4 rounded border-slate-600 bg-slate-900" />
                  Remember me
                </label>
                <a href="#" className="text-cyan-300 hover:text-cyan-200">
                  Forgot password?
                </a>
              </div>

              {error === "invalid" ? (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                  Invalid email or password.
                </div>
              ) : null}

              <button
                type="submit"
                className="flex w-full items-center justify-center rounded-xl bg-cyan-500 px-4 py-3 font-medium text-slate-950 transition hover:bg-cyan-400"
              >
                Sign in
              </button>
            </form>

            <div className="mt-6 rounded-xl border border-slate-700 bg-slate-900/80 p-3 text-sm text-slate-300">
              <p>
                Use the admin credential configured for the app to continue to the cluster dashboard.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
