export const ADMIN_ROLE = "admin";

export type BackendUser = {
  id: string;
  email: string;
  role: "admin" | "operator" | "viewer";
  isActive: boolean;
  mustChangePassword: boolean;
  passwordExpired: boolean;
  lastLoginAt: string | null;
  createdAt: string;
};

export const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  operator: "Operator",
  viewer: "Viewer",
};