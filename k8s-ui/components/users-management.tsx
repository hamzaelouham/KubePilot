"use client";

import { useEffect, useState } from "react";
import { Field } from "@base-ui/react/field";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type ManagedUser = {
  id: string;
  email: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  password_expires_at: string | null;
  password_expired: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

const roleOptions = [
  { value: "admin", label: "Admin" },
  { value: "operator", label: "Operator" },
  { value: "viewer", label: "Viewer" },
] as const;

const roleLabels: Record<string, string> = {
  admin: "Admin",
  operator: "Operator",
  viewer: "Viewer",
};

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function UserManagementCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{children}</div>
  );
}

async function fetchUsers(): Promise<{ items: ManagedUser[] } | "unauthorized" | "unavailable" | "error"> {
  const response = await fetch("/api/users", { cache: "no-store" });
  if (response.status === 401) return "unauthorized";
  if (response.status === 503) return "unavailable";
  if (!response.ok) return "error";
  return (await response.json()) as { items: ManagedUser[] };
}

export function UsersManagement({ currentUserEmail }: { currentUserEmail: string }) {
  const router = useRouter();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createEmail, setCreateEmail] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createRole, setCreateRole] = useState<ManagedUser["role"]>("viewer");

  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ManagedUser | null>(null);
  const [editRole, setEditRole] = useState<ManagedUser["role"]>("viewer");

  const [resetOpen, setResetOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<ManagedUser | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  const [forceTarget, setForceTarget] = useState<ManagedUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ManagedUser | null>(null);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      const result = await fetchUsers();
      if (!mounted) return;
      if (result === "unauthorized") {
        router.push("/login");
        return;
      }
      if (result === "unavailable") {
        setUsers([]);
        setError("The user management service is currently unavailable.");
        setLoading(false);
        return;
      }
      if (result === "error") {
        setUsers([]);
        setError("Could not load users.");
        setLoading(false);
        return;
      }
      setUsers(result.items);
      setError(null);
      setLoading(false);
    })();
    return () => {
      mounted = false;
    };
  }, [router]);

  const extractError = async (response: Response): Promise<string | null> => {
    if (response.status === 401) {
      router.push("/login");
      return null;
    }
    if (response.status === 503 || response.status === 0) {
      return "The user management service is currently unavailable.";
    }
    try {
      const body = (await response.json()) as { message?: string };
      return body.message ?? "The operation could not be completed.";
    } catch {
      return "The operation could not be completed.";
    }
  };

  const refresh = async (): Promise<void> => {
    const result = await fetchUsers();
    if (result === "unauthorized") {
      router.push("/login");
      return;
    }
    if (result === "unavailable") {
      setError("Could not refresh the user list.");
      return;
    }
    if (result === "error") {
      setError("Could not refresh the user list.");
      return;
    }
    setUsers(result.items);
  };

  const run = async (verb: string, url: string, body?: unknown, method = "PATCH"): Promise<string | null> => {
    setPending(verb);
    setError(null);
    try {
      const response = await fetch(url, {
        method,
        headers: body !== undefined ? { "content-type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        cache: "no-store",
      });
      if (response.status === 401) {
        router.push("/login");
        return null;
      }
      if (response.status === 503) {
        const message = "The user management service is currently unavailable.";
        toast.add({ type: "error", title: "User operation failed", description: message });
        return message;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) toast.add({ type: "error", title: "User operation failed", description: failure });
        return failure;
      }
      await refresh();
      const successTitles: Record<string, string> = {
        create: "User created",
        edit: "User updated",
        reset: "Password reset",
        force: "Password change required",
        toggle: "User status updated",
      };
      toast.add({ type: "success", title: successTitles[verb] ?? "User operation complete", description: "The user list is up to date." });
      return null;
    } catch {
      const message = "An unexpected error occurred.";
      toast.add({ type: "error", title: "User operation failed", description: message });
      setError(message);
      return message;
    } finally {
      setPending(null);
    }
  };

  const doCreate = async () => {
    const failure = await run(
      "create",
      "/api/users",
      { email: createEmail, password: createPassword, role: createRole },
      "POST",
    );
    if (failure) {
      setError(failure);
      return;
    }
    setCreateOpen(false);
    setCreateEmail("");
    setCreatePassword("");
    setCreateRole("viewer");
  };

  const doEditRole = async () => {
    if (!editTarget) return;
    const failure = await run("edit", `/api/users/${editTarget.id}`, { role: editRole });
    if (failure) {
      setError(failure);
      return;
    }
    setEditOpen(false);
    setEditTarget(null);
  };

  const doResetPassword = async () => {
    if (!resetTarget) return;
    const failure = await run("reset", `/api/users/${resetTarget.id}/reset-password`, {
      new_password: resetPassword,
    }, "POST");
    if (failure) {
      setError(failure);
      return;
    }
    setResetOpen(false);
    setResetTarget(null);
    setResetPassword("");
  };

  const doForceChange = async () => {
    if (!forceTarget) return;
    const failure = await run("force", `/api/users/${forceTarget.id}/force-password-change`, undefined, "POST");
    if (failure) {
      setError(failure);
      return;
    }
    setForceTarget(null);
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    setPending("delete");
    setError(null);
    try {
      const response = await fetch(`/api/users/${deleteTarget.id}`, { method: "DELETE", cache: "no-store" });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        const message = "The user management service is currently unavailable.";
        toast.add({ type: "error", title: "User deletion failed", description: message });
        setError(message);
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) {
          toast.add({ type: "error", title: "User deletion failed", description: failure });
          setError(failure);
        }
        return;
      }
      toast.add({ type: "success", title: "User deleted", description: deleteTarget.email });
      setDeleteTarget(null);
      await refresh();
    } catch {
      const message = "An unexpected error occurred.";
      toast.add({ type: "error", title: "User deletion failed", description: message });
      setError(message);
    } finally {
      setPending(null);
    }
  };

  const openEdit = (user: ManagedUser) => {
    setEditTarget(user);
    setEditRole(user.role);
    setEditOpen(true);
  };

  const toggleActive = async (user: ManagedUser) => {
    const failure = await run("toggle", `/api/users/${user.id}`, { is_active: !user.is_active });
    if (failure) setError(failure);
  };

  const isSelf = (user: ManagedUser) => user.email.toLowerCase() === currentUserEmail.toLowerCase();

  if (loading && users.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">Loading users…</p>;
  }

  return (
    <div className="space-y-4">
      {error ? <UserManagementCallout>{error}</UserManagementCallout> : null}

      <div className="flex items-center justify-end gap-2">
        <Button onClick={() => setCreateOpen(true)}>create user</Button>
      </div>

      <div className="rounded-md border border-border bg-surface-elevated p-2 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Password</TableHead>
              <TableHead>Last login</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>
                  <span className="font-medium">{user.email}</span>
                  {isSelf(user) ? <span className="ml-2 text-xs text-muted-foreground">(you)</span> : null}
                </TableCell>
                <TableCell>
                  <Badge variant={user.role === "admin" ? "default" : user.role === "operator" ? "secondary" : "outline"}>
                    {roleLabels[user.role] ?? user.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  {user.is_active ? (
                    <Badge variant="secondary">Active</Badge>
                  ) : (
                    <Badge variant="destructive">Inactive</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {user.must_change_password ? (
                    <Badge variant="destructive">Change required</Badge>
                  ) : user.password_expired ? (
                    <Badge variant="destructive">Expired</Badge>
                  ) : (
                    <span className="text-sm text-muted-foreground">
                      {user.password_expires_at ? `Expires ${new Date(user.password_expires_at).toLocaleDateString()}` : "Never"}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDateTime(user.last_login_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="inline-flex items-center gap-1.5">
                    <Button size="sm" variant="outline" onClick={() => openEdit(user)} disabled={isSelf(user)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant={user.is_active ? "destructive" : "secondary"}
                      onClick={() => void toggleActive(user)}
                      disabled={isSelf(user)}
                    >
                      {user.is_active ? "Deactivate" : "Reactivate"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => { setResetTarget(user); setResetPassword(""); setResetOpen(true); }} disabled={isSelf(user)}>
                      Reset password
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setForceTarget(user)} disabled={isSelf(user)}>
                      Force change
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => setDeleteTarget(user)} disabled={isSelf(user)}>
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  No users yet.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" showCloseButton={pending !== "create"}>
          <DialogHeader>
            <DialogTitle>New user</DialogTitle>
            <DialogDescription>Provision a new account. They sign in with this password immediately.</DialogDescription>
          </DialogHeader>
          <form className="flex min-w-0 flex-col gap-5" onSubmit={(event) => { event.preventDefault(); void doCreate(); }}>
            <Field.Root name="email" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="create-email">Email</Field.Label>
              <Input id="create-email" type="email" value={createEmail} onChange={(event) => setCreateEmail(event.target.value)} placeholder="you@example.com" />
            </Field.Root>
            <Field.Root name="password" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="create-password">Initial password</Field.Label>
              <Input id="create-password" type="text" value={createPassword} onChange={(event) => setCreatePassword(event.target.value)} placeholder="At least 10 characters" />
            </Field.Root>
            <Field.Root name="role" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium">Role</Field.Label>
              <Select value={createRole} onValueChange={(value) => setCreateRole(value as ManagedUser["role"])}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field.Root>
            <DialogFooter>
              <DialogCancelButton onClick={() => setCreateOpen(false)} disabled={pending === "create"} />
              <Button type="submit" disabled={!createEmail || createPassword.length < 6 || pending === "create"}>{pending === "create" ? "Creating…" : "Create user"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={(open) => { if (!open && pending !== "edit") setEditOpen(false); }}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" showCloseButton={pending !== "edit"}>
          <DialogHeader>
            <DialogTitle>Edit user</DialogTitle>
            <DialogDescription>
              Change {editTarget?.email ?? "this user"}&apos;s role. You cannot change your own role.
            </DialogDescription>
          </DialogHeader>
          <form className="flex min-w-0 flex-col gap-5" onSubmit={(event) => { event.preventDefault(); void doEditRole(); }}>
            <Field.Root name="role" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium">Role</Field.Label>
            <Select value={editRole} onValueChange={(value) => setEditRole(value as ManagedUser["role"])}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roleOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            </Field.Root>
            <DialogFooter>
              <DialogCancelButton onClick={() => setEditOpen(false)} disabled={pending === "edit"} />
              <Button type="submit" disabled={pending === "edit"}>{pending === "edit" ? "Saving…" : "Save role"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={resetOpen} onOpenChange={(open) => { if (!open && pending !== "reset") setResetOpen(false); }}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" showCloseButton={pending !== "reset"}>
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>
              Set a new temporary password for {resetTarget?.email ?? "this user"}. They will be asked to change it on next sign-in and all existing sessions are ended.
            </DialogDescription>
          </DialogHeader>
          <form className="flex min-w-0 flex-col gap-5" onSubmit={(event) => { event.preventDefault(); void doResetPassword(); }}>
            <Field.Root name="password" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="reset-password">Temporary password</Field.Label>
              <Input id="reset-password" type="text" value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} placeholder="At least 10 characters" />
            </Field.Root>
            <DialogFooter>
              <DialogCancelButton onClick={() => setResetOpen(false)} disabled={pending === "reset"} />
              <Button type="submit" disabled={resetPassword.length < 6 || pending === "reset"}>{pending === "reset" ? "Resetting…" : "Reset password"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={forceTarget !== null} onOpenChange={(open) => { if (!open) setForceTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Force password change</AlertDialogTitle>
            <AlertDialogDescription>
              {forceTarget?.email ?? "This user"} will be required to change their password at their next sign-in, and all of their existing sessions will be ended.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void doForceChange()}>Force change</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user</AlertDialogTitle>
            <AlertDialogDescription>
              Delete {deleteTarget?.email ?? "this user"} permanently. Users referenced by audit history cannot be deleted; deactivate them instead.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void doDelete()}>Delete user</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {pending ? <p className="text-sm text-muted-foreground">Working…</p> : null}
    </div>
  );
}

function DialogCancelButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <Button type="button" variant="outline" onClick={onClick} disabled={disabled}>
      Cancel
    </Button>
  );
}
