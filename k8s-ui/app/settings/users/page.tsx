import { UsersManagement } from "@/components/users-management";
import { requireBackendUser, ADMIN_ROLE } from "@/lib/auth";
import { redirect } from "next/navigation";

export default async function UsersSettingsPage() {
  const user = await requireBackendUser();
  if (user.role !== ADMIN_ROLE) {
    redirect("/dashboard");
  }
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-4">
          <div className="flex items-center gap-3 text-[#3b4edb]">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8ebff] text-xl">◈</div>
            <div className="text-3xl font-semibold tracking-tight text-[#3f4fce]">kubernetes</div>
          </div>
          <div className="ml-auto text-sm text-muted-foreground">{user.email}</div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Users</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Provision accounts and assign roles. Permissions are enforced by the backend.
            </p>
          </div>
          <a
            href="/settings/password"
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          >
            Change my password
          </a>
        </div>
        <UsersManagement currentUserEmail={user.email} />
      </div>
    </main>
  );
}