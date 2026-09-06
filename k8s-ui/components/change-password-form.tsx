"use client";

import { useState } from "react";

type ChangePasswordFormProps = {
  forced: boolean;
};

export function ChangePasswordForm({ forced }: ChangePasswordFormProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
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
        window.location.href = "/login";
        return;
      }
      if (response.status === 503) {
        setError("The authentication service is currently unavailable. Please try again.");
        return;
      }
      if (!response.ok) {
        const body = (await response.json()) as { message?: string };
        setError(body.message ?? "The password could not be changed.");
        return;
      }

      setSuccess(true);
      reset();
      if (forced) {
        window.location.href = "/dashboard";
      }
    } catch {
      setError("The authentication service is currently unavailable. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "w-full rounded-xl border border-input bg-background px-4 py-3 text-foreground outline-none placeholder:text-muted-foreground focus:border-primary";

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <label htmlFor="current-password" className="mb-2 block text-sm text-muted-foreground">
          Current password
        </label>
        <input
          id="current-password"
          name="current-password"
          type="password"
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
          className={inputClass}
          required
        />
      </div>

      <div>
        <label htmlFor="new-password" className="mb-2 block text-sm text-muted-foreground">
          New password
        </label>
        <input
          id="new-password"
          name="new-password"
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          className={inputClass}
          required
        />
      </div>

      <div>
        <label htmlFor="confirm-password" className="mb-2 block text-sm text-muted-foreground">
          Confirm new password
        </label>
        <input
          id="confirm-password"
          name="confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          className={inputClass}
          required
        />
      </div>

      {error ? (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
          Your password has been updated.
        </div>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="flex w-full cursor-pointer items-center justify-center rounded-xl bg-primary px-4 py-3 font-medium text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}