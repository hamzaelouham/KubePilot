"use server";

import { redirect } from "next/navigation";
import { backendUrl } from "@/lib/backend";
import { setBackendSession } from "@/lib/auth";

type LoginResult = {
  cookie: string;
  expires_at: number;
  change_required: boolean;
};

export async function signInAction(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    redirect("/login?error=backend");
  }

  if (response.status === 503) {
    redirect("/login?error=backend");
  }
  if (!response.ok) {
    redirect("/login?error=invalid");
  }

  const result = (await response.json()) as LoginResult;
  await setBackendSession(result.cookie, result.expires_at);

  if (result.change_required) {
    redirect("/settings/password?forced=1");
  }
  redirect("/dashboard");
}