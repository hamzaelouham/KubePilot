import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHmac, timingSafeEqual } from "node:crypto";
import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";
import { backendUrl } from "@/lib/backend";
import { ADMIN_ROLE, type BackendUser } from "@/lib/auth-client";

export { ADMIN_ROLE, ROLE_LABELS } from "@/lib/auth-client";
export type { BackendUser } from "@/lib/auth-client";

export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 12;

export const SESSION_REDIRECT_PATHS = ["/settings/password"];

const SESSION_SECRET = process.env.KUBEPILOT_AUTH_SECRET ?? "local-development-secret-change-me";

type SessionData = {
  email: string;
  expiresAt: number;
};

function sign(payload: string) {
  return createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
}

function parseSession(value: string): SessionData | null {
  const [payload, signature] = value.split(".");
  if (!payload || !signature) return null;

  const expected = sign(payload);
  const actualBuffer = Buffer.from(signature);
  const expectedBuffer = Buffer.from(expected);
  if (actualBuffer.length !== expectedBuffer.length || !timingSafeEqual(actualBuffer, expectedBuffer)) {
    return null;
  }

  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as SessionData;
    if (!parsed.email || !Number.isFinite(parsed.expiresAt) || parsed.expiresAt <= Date.now()) return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function getSession(): Promise<SessionData | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!sessionCookie) {
    return null;
  }

  return parseSession(sessionCookie);
}

export async function setBackendSession(cookieValue: string, expiresAt?: number) {
  const cookieStore = await cookies();
  const maxAge = expiresAt
    ? Math.max(1, Math.round((expiresAt - Date.now()) / 1000))
    : SESSION_MAX_AGE_SECONDS;
  cookieStore.set(SESSION_COOKIE_NAME, cookieValue, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  });
}

export async function clearSession() {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

export async function fetchBackendUser(): Promise<BackendUser | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!sessionCookie) {
    return null;
  }

  try {
    const response = await fetch(`${backendUrl()}/api/v1/auth/me`, {
      headers: { cookie: `${SESSION_COOKIE_NAME}=${sessionCookie}` },
      cache: "no-store",
    });
    if (response.status !== 200) {
      return null;
    }
    return (await response.json()) as BackendUser;
  } catch {
    return null;
  }
}

export async function requireBackendUser(): Promise<BackendUser> {
  const user = await fetchBackendUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}

export function requiresPasswordChange(user: BackendUser) {
  return user.mustChangePassword || user.passwordExpired;
}

export async function requireUsableBackendUser(): Promise<BackendUser> {
  const user = await requireBackendUser();
  if (requiresPasswordChange(user)) {
    redirect("/settings/password?forced=1");
  }
  return user;
}