"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { UsersManagement } from "@/components/users-management";
import { useClusterStatus } from "@/lib/use-cluster-status";
import type { BackendUser } from "@/lib/auth";

export function UserSettingsView({ user }: { user: BackendUser }) {
  const router = useRouter();
  const cluster = useClusterStatus();

  const handleNav = (resource: string, namespace: string) => {
    const params = new URLSearchParams({ resource, namespace });
    if (cluster) params.set("cluster", cluster);
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <DashboardShell
      user={user}
      activeResource="users"
      activeNamespace="default"
      activeCluster={cluster}
      onNavigate={handleNav}
    >
      <div>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Users</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Provision accounts and assign roles. Permissions are enforced by the backend.
            </p>
          </div>
          <Link
            href="/settings/password"
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          >
            Change my password
          </Link>
        </div>
        <UsersManagement currentUserEmail={user.email} />
      </div>
    </DashboardShell>
  );
}