"use client";

import { useState } from "react";
import { Field } from "@base-ui/react/field";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";

type ChangePasswordFormProps = {
  forced: boolean;
};

export function ChangePasswordForm({ forced }: ChangePasswordFormProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  const reset = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      const message = "The new passwords do not match.";
      setError(message);
      toast.add({ type: "error", title: "Password change failed", description: message });
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        cache: "no-store",
      });

      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        const message = "The authentication service is currently unavailable. Please try again.";
        setError(message);
        toast.add({ type: "error", title: "Password change failed", description: message });
        return;
      }
      if (!response.ok) {
        const body = (await response.json()) as { message?: string };
        const message = body.message ?? "The password could not be changed.";
        setError(message);
        toast.add({ type: "error", title: "Password change failed", description: message });
        return;
      }

      toast.add({ type: "success", title: "Password updated", description: "Your password has been changed." });
      reset();
      if (forced) {
        router.push("/dashboard");
      }
    } catch {
      const message = "The authentication service is currently unavailable. Please try again.";
      setError(message);
      toast.add({ type: "error", title: "Password change failed", description: message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} aria-busy={submitting} className="flex min-w-0 flex-col gap-5">
      <Field.Root name="current-password" className="flex min-w-0 flex-col gap-2">
        <Field.Label className="text-sm font-medium" htmlFor="current-password">Current password</Field.Label>
        <Input
          id="current-password"
          name="current-password"
          type="password"
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </Field.Root>

      <Field.Root name="new-password" className="flex min-w-0 flex-col gap-2">
        <Field.Label className="text-sm font-medium" htmlFor="new-password">New password</Field.Label>
        <Input
          id="new-password"
          name="new-password"
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          autoComplete="new-password"
          required
        />
      </Field.Root>

      <Field.Root name="confirm-password" className="flex min-w-0 flex-col gap-2">
        <Field.Label className="text-sm font-medium" htmlFor="confirm-password">Confirm new password</Field.Label>
        <Input
          id="confirm-password"
          name="confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          autoComplete="new-password"
          required
        />
      </Field.Root>

      {error ? (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Button type="submit" disabled={submitting}>{submitting ? "Updating…" : "Update password"}</Button>
    </form>
  );
}
