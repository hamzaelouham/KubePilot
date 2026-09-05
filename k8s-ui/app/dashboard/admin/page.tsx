import { redirect } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { AdminUsersView } from "@/components/admin-users-view";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  let actor: { role?: string } | null = null;
  try {
    const response = await fetch("/api/auth/context", { cache: "no-store" });
    actor = response.ok ? ((await response.json()) as { identifier: string; role: string }) : null;
  } catch {
    actor = null;
  }

  if (actor?.role !== "admin") {
    redirect("/dashboard");
  }

  const navigate = (resource: string, namespace: string) => {
    const url = new URL("/dashboard", window.location.origin);
    url.searchParams.set("resource", resource);
    url.searchParams.set("namespace", namespace);
    window.location.assign(url.toString());
  };

  return (
    <DashboardShell activeResource="admin" activeNamespace="default" onNavigate={navigate}>
      <AdminUsersView />
    </DashboardShell>
  );
}