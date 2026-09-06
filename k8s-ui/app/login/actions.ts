"use server";

import { redirect } from "next/navigation";
import { createSession, isValidCredential } from "@/lib/auth";

export async function signInAction(formData: FormData) {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (!(await isValidCredential(email, password))) {
    redirect("/login?error=invalid");
  }

  const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${backendUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    redirect("/login?error=backend");
  }
  if (!response.ok) {
    redirect("/login?error=backend");
  }
  const session = (await response.json()) as { cookie: string; expires_at: number };
  await createSession(email, session.cookie, session.expires_at);
  redirect("/dashboard");
}
