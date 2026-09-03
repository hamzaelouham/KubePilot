import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const SESSION_COOKIE_NAME = "kubepilot_session";
export const DEFAULT_ADMIN_EMAIL = "ops@kubepilot.io";
export const DEFAULT_ADMIN_PASSWORD = "kubepilot";

export type SessionData = {
  email: string;
  expiresAt: number;
};

function normalizeCredential(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase();
}

export async function getSession(): Promise<SessionData | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!sessionCookie) {
    return null;
  }

  try {
    const parsed = JSON.parse(decodeURIComponent(sessionCookie)) as SessionData;

    if (!parsed.email || !parsed.expiresAt || parsed.expiresAt <= Date.now()) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

export async function requireSession() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  return session;
}

export async function getAdminCredentials() {
  return {
    email: normalizeCredential(process.env.KUBEPILOT_ADMIN_EMAIL ?? DEFAULT_ADMIN_EMAIL),
    password: process.env.KUBEPILOT_ADMIN_PASSWORD ?? DEFAULT_ADMIN_PASSWORD,
  };
}

export async function isValidCredential(email: string, password: string) {
  const credentials = await getAdminCredentials();
  const normalizedEmail = normalizeCredential(email);

  return normalizedEmail === credentials.email && password === credentials.password;
}

export async function createSession(email: string) {
  const cookieStore = await cookies();
  const expiresAt = Date.now() + 1000 * 60 * 60 * 12;
  const session: SessionData = { email, expiresAt };

  cookieStore.set(SESSION_COOKIE_NAME, encodeURIComponent(JSON.stringify(session)), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  });

  return session;
}

export async function clearSession() {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}
