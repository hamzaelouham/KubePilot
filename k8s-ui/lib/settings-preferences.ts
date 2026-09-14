export const themeOptions = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
] as const;

export type ThemePreference = (typeof themeOptions)[number]["value"];

export type UserPreferences = {
  default_namespace: string | null;
  theme: ThemePreference;
};

export type UserPreferencesUpdate = Partial<UserPreferences>;

async function preferencesRequest<T>(init?: RequestInit): Promise<T> {
  const response = await fetch("/api/settings/preferences", {
    ...init,
    cache: "no-store",
    headers: {
      "content-type": "application/json",
      ...init?.headers,
    },
  });
  const body = (await response.json().catch(() => null)) as { message?: string } | T | null;
  if (!response.ok) {
    const message = body && typeof body === "object" && "message" in body ? body.message : undefined;
    throw new Error(message || "Unable to save preferences");
  }
  return body as T;
}

export function fetchUserPreferences() {
  return preferencesRequest<UserPreferences>();
}

export function updateUserPreferences(changes: UserPreferencesUpdate) {
  return preferencesRequest<UserPreferences>({
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}
