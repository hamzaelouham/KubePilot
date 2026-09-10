type ApiErrorBody = {
  message?: unknown;
  detail?: unknown;
};

export function apiErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const error = body as ApiErrorBody;
  if (typeof error.message === "string") return error.message;
  if (typeof error.detail === "string") return error.detail;
  if (
    error.detail &&
    typeof error.detail === "object" &&
    "message" in error.detail &&
    typeof error.detail.message === "string"
  ) {
    return error.detail.message;
  }
  return fallback;
}
