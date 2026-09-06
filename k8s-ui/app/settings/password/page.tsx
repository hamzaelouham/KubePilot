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
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12 text-foreground">
      <div className="w-full max-w-md rounded-3xl border border-border bg-card p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-lg text-primary">
            ☸
          </span>
          <h1 className="text-2xl font-semibold text-foreground">KubePilot</h1>
        </div>

        <h2 className="text-3xl font-semibold text-foreground">Update password</h2>
        <p className="mt-2 text-base leading-7 text-muted-foreground">
          {forced || user.mustChangePassword || user.passwordExpired
            ? "Your password must be changed before you can continue."
            : "Choose a new password for your account."}
        </p>

        <div className="mt-8">
          <ChangePasswordForm forced={forced || user.mustChangePassword || user.passwordExpired} />
          {!forced && !user.mustChangePassword && !user.passwordExpired ? (
            <p className="mt-6 text-sm text-muted-foreground">
              <Link href="/dashboard" className="text-primary hover:text-primary/80">
                Back to dashboard
              </Link>
            </p>
          ) : null}
        </div>
      </div>
    </main>
  );
}