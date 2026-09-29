import { requireUsableBackendUser } from "@/lib/auth";
import { AgentsView } from "@/components/assistant/agents/view";
export default async function CreateAgentPage() {
  return <AgentsView user={await requireUsableBackendUser()} creating />;
}
