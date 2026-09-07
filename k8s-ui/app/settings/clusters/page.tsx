import { requireBackendUser } from "@/lib/auth";
import { ClusterSettingsView } from "@/components/cluster-settings-view";

export default async function ClustersSettingsPage() {
  const user = await requireBackendUser();
  const canManage = user.role === "admin" || user.role === "operator";
  return <ClusterSettingsView user={user} canManage={canManage} />;
}