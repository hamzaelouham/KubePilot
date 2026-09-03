"use server";

import { redirect } from "next/navigation";
import { createSession, isValidCredential } from "@/lib/auth";

export async function signInAction(formData: FormData) {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (!(await isValidCredential(email, password))) {
    redirect("/login?error=invalid");
  }

  await createSession(email);
  redirect("/dashboard");
}
