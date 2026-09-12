import { BackgroundJobsView } from "@/components/background-jobs-view";
import { requireUsableBackendUser } from "@/lib/auth";

export default async function BackgroundJobsPage() {
  const user = await requireUsableBackendUser();
  return <BackgroundJobsView user={user} />;
}
