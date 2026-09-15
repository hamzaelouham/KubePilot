import { backendUnavailable, backendUrl, proxyResponse } from "@/lib/backend";
import { sessionCookie } from "@/lib/assistant/backend";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/assistant/models`, {
      headers: { cookie: sessionCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The Assistant model service is unavailable");
  }
}
