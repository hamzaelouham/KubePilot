import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHmac, timingSafeEqual } from "node:crypto";
import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";

export const SESSION_SECRET = process.env.KUBEPILOT_AUTH_SECRET ?? "local-development-secret-change-me";

export type SessionData = {
  email: string;
  expiresAt: number;
};

function encode(value: string) {
  return Buffer.from(value).toString("base64url");
}

function sign(payload: string) {
  return createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
}

function serializeSession(session: SessionData) {
  const payload = encode(JSON.stringify(session));
  return `${payload}.${sign(payload)}`;
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

  try {
    return parseSession(sessionCookie);
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

export async function createSession(email: string, cookieValue?: string, sessionExpiresAt?: number) {
  const cookieStore = await cookies();
  const expiresAt = sessionExpiresAt ?? Date.now() + 1000 * 60 * 60 * 12;
  const session: SessionData = { email, expiresAt };

  cookieStore.set(SESSION_COOKIE_NAME, cookieValue ?? serializeSession(session), {
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
