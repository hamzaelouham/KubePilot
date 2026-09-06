import { ChangePasswordForm } from "@/components/change-password-form";
import { requireBackendUser } from "@/lib/auth";
import Link from "next/link";

export default async function PasswordSettingsPage({
  searchParams,
}: {
  searchParams?: Promise<{ forced?: string }> | { forced?: string };
}) {
  const user = await requireBackendUser();
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const forced = resolvedParams.forced === "1";

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#11243d_0%,_#0f172a_45%,_#020817_100%)] px-6 py-12 text-slate-100">
      <div className="w-full max-w-lg overflow-hidden rounded-3xl border border-slate-700 bg-slate-900/80 shadow-2xl shadow-slate-950/50 backdrop-blur-xl">
        <div className="p-8 lg:p-10">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-500/20 text-lg font-bold text-cyan-300">
              K
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Control plane</p>
              <h1 className="text-2xl font-semibold text-white">KubePilot</h1>
            </div>
          </div>

          <h2 className="text-3xl font-semibold text-white">Update password</h2>
          <p className="mt-2 text-base leading-7 text-slate-300">
            {forced || user.mustChangePassword || user.passwordExpired
              ? "Your password must be changed before you can continue."
              : "Choose a new password for your account."}
          </p>

          <div className="mt-8">
            <ChangePasswordForm forced={forced || user.mustChangePassword || user.passwordExpired} />
            {!forced && !user.mustChangePassword && !user.passwordExpired ? (
              <p className="mt-6 text-sm text-slate-400">
                <Link href="/dashboard" className="text-cyan-300 hover:text-cyan-200">
                  Back to dashboard
                </Link>
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </main>
  );
}