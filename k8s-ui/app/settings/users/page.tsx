import { requireBackendUser, ADMIN_ROLE } from "@/lib/auth";
import { redirect } from "next/navigation";
import { UserSettingsView } from "@/components/user-settings-view";

export default async function UsersSettingsPage() {
  const user = await requireBackendUser();
  if (user.role !== ADMIN_ROLE) {
    redirect("/dashboard");
  }
  return <UserSettingsView user={user} />;
}