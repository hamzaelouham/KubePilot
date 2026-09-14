import { SettingsShell } from "@/components/settings-shell";
import { requireAdminSettingsUser } from "@/lib/auth";

export default async function AdminSettingsLayout({ children }: { children: React.ReactNode }) {
  const user = await requireAdminSettingsUser();
  return <SettingsShell user={user}>{children}</SettingsShell>;
}
