export type Health = "healthy" | "warning" | "error" | "unknown";

export function healthTone(health: Health | undefined | null): { pill: string; short: string } {
  switch (health) {
    case "healthy":
      return { pill: "bg-green-100 text-green-700", short: "healthy" };
    case "warning":
      return { pill: "bg-amber-100 text-amber-700", short: "warning" };
    case "error":
      return { pill: "bg-red-100 text-red-700", short: "error" };
    default:
      return { pill: "bg-slate-200 text-slate-600", short: "unknown" };
  }
}
