"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

type Role = "admin" | "operator" | "viewer";
type UserItem = { id: string; email: string; role: Role; isActive: boolean; createdAt: string };
type UsersState =
  | { status: "loading" }
  | { status: "ready"; users: UserItem[] }
  | { status: "error"; message: string };

const ROLES: Role[] = ["admin", "operator", "viewer"];

async function readBody(response: Response): Promise<{ message?: string }> {
  try {
    return (await response.json()) as { message?: string };
  } catch {
    return {};
  }
}

export function AdminUsersView() {
  const [state, setState] = useState<UsersState>({ status: "loading" });
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState<UserItem | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<Role>("viewer");
  const [creating, setCreating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const response = await fetch("/api/users", { signal: controller.signal, cache: "no-store" });
      const body = (await response.json()) as { items?: UserItem[]; message?: string };
      if (!response.ok) throw new Error(body.message ?? "Unable to load users");
      setState({ status: "ready", users: body.items ?? [] });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load users" });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    void Promise.resolve().then(load);
    return () => abortRef.current?.abort();
  }, [load]);

  const reload = async () => {
    await load();
  };

  const changeRole = async (user: UserItem, role: Role) => {
    if (role === user.role) return;
    setPendingId(user.id);
    setActionError(null);
    try {
      const response = await fetch(`/api/users/${user.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ role }),
        cache: "no-store",
      });
      const body = await readBody(response);
      if (!response.ok) {
        setActionError(body.message ?? "Unable to update the role.");
        return;
      }
      await reload();
    } catch {
      setActionError("Unable to update the role.");
    } finally {
      setPendingId(null);
    }
  };

  const confirmDeactivate = async () => {
    if (!deactivating) return;
    setPendingId(deactivating.id);
    setActionError(null);
    try {
      const response = await fetch(`/api/users/${deactivating.id}/deactivate`, {
        method: "POST",
        cache: "no-store",
      });
      const body = await readBody(response);
      if (!response.ok) {
        setActionError(body.message ?? "Unable to deactivate the user.");
        return;
      }
      await reload();
    } catch {
      setActionError("Unable to deactivate the user.");
    } finally {
      setDeactivating(null);
      setPendingId(null);
    }
  };

  const createUser = async () => {
    setCreating(true);
    setActionError(null);
    try {
      const response = await fetch("/api/users", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: newEmail, password: newPassword, role: newRole }),
        cache: "no-store",
      });
      const body = await readBody(response);
      if (!response.ok) {
        setActionError(body.message ?? "Unable to create the user.");
        return;
      }
      setNewEmail("");
      setNewPassword("");
      setNewRole("viewer");
      setDialogOpen(false);
      await reload();
    } catch {
      setActionError("Unable to create the user.");
    } finally {
      setCreating(false);
    }
  };

  const columns: DataTableColumn<UserItem>[] = [
    {
      accessorKey: "email",
      header: "Email",
      cell: ({ row }) => <span className="font-medium">{row.original.email}</span>,
    },
    {
      accessorKey: "role",
      header: "Role",
      cell: ({ row }) => (
        <Select
          value={row.original.role}
          onValueChange={(value) => changeRole(row.original, value as Role)}
          disabled={pendingId === row.original.id}
        >
          <SelectTrigger className="w-40" aria-label={`Role for ${row.original.email}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((role) => (
              <SelectItem key={role} value={role}>
                {role}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) =>
        row.original.isActive ? (
          <Badge>Active</Badge>
        ) : (
          <Badge variant="secondary">Deactivated</Badge>
        ),
    },
    {
      accessorKey: "createdAt",
      header: "Created",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {new Date(row.original.createdAt).toLocaleDateString()}
        </span>
      ),
    },
    {
      accessorKey: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => (
        <Button
          variant="destructive"
          size="sm"
          disabled={!row.original.isActive || pendingId === row.original.id}
          onClick={() => setDeactivating(row.original)}
        >
          Deactivate
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Admin</p>
          <h2 className="text-3xl font-semibold text-slate-700">Users</h2>
        </div>
        <div className="flex items-center gap-3">
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger
              render={
                <Button variant="header" size="header-lg" />
              }
            >
              New user
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create user</DialogTitle>
                <DialogDescription>
                  Provision a new KubePilot account with a role.
                </DialogDescription>
              </DialogHeader>
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void createUser();
                }}
              >
                <div className="space-y-2">
                  <label htmlFor="new-user-email" className="text-sm font-medium">
                    Email address
                  </label>
                  <Input
                    id="new-user-email"
                    type="email"
                    required
                    value={newEmail}
                    onChange={(event) => setNewEmail(event.target.value)}
                    placeholder="user@example.com"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="new-user-password" className="text-sm font-medium">
                    Initial password
                  </label>
                  <Input
                    id="new-user-password"
                    type="password"
                    required
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="new-user-role" className="text-sm font-medium">
                    Role
                  </label>
                  <Select value={newRole} onValueChange={(value) => setNewRole(value as Role)}>
                    <SelectTrigger id="new-user-role" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ROLES.map((role) => (
                        <SelectItem key={role} value={role}>
                          {role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" disabled={creating} onClick={() => setDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={creating}>
                    {creating ? "Creating…" : "Create user"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {actionError ? (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">
          {actionError}
        </p>
      ) : null}

      {state.status === "loading" ? (
        <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading users...</p>
      ) : null}
      {state.status === "error" ? (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">
          {state.message}
        </p>
      ) : null}
      {state.status === "ready" ? (
        <DataTable
          columns={columns}
          data={state.users}
          placeholder="No users found."
          searchPlaceholder="Filter users…"
        />
      ) : null}

      <AlertDialog open={deactivating !== null} onOpenChange={(open) => !open && setDeactivating(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Deactivate {deactivating?.email ?? "this user"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The user will no longer be able to sign in, and their active
              sessions will be invalidated immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmDeactivate()} disabled={pendingId !== null}>
              Deactivate user
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}