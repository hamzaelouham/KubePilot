import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";

async function isAuthenticated(request: NextRequest) {
  const value = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const secret = process.env.KUBEPILOT_AUTH_SECRET;

  if (!value || !secret) {
    return false;
  }

  try {
    const [payload, signature] = value.split(".");
    if (!payload || !signature) return false;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
    const parsed = JSON.parse(decoded) as { expiresAt?: number };
    if (typeof parsed.expiresAt !== "number" || parsed.expiresAt <= Date.now()) return false;
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );
    const signatureBase64 = signature.replace(/-/g, "+").replace(/_/g, "/");
    const signatureBytes = Uint8Array.from(atob(signatureBase64 + "=".repeat((4 - (signatureBase64.length % 4)) % 4)), (character) => character.charCodeAt(0));
    return await crypto.subtle.verify("HMAC", key, signatureBytes, new TextEncoder().encode(payload));
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const authenticated = await isAuthenticated(request);

  if (pathname.startsWith("/dashboard")) {
    if (!authenticated) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
    return NextResponse.next();
  }

  if (pathname === "/login") {
    if (authenticated) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login"],
};
