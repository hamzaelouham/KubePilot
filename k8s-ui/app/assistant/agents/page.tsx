import { requireUsableBackendUser } from "@/lib/auth";
import { AgentsView } from "@/components/assistant/agents/view";
export default async function AgentsPage() {
  return <AgentsView user={await requireUsableBackendUser()} />;
}
