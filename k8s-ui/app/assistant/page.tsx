import { requireUsableBackendUser } from "@/lib/auth";
import { AssistantView } from "@/components/assistant/view";
import { agentIdSchema, contextSchema } from "@/lib/assistant/schemas";
import { assistantModeSchema } from "@/lib/assistant/mode";

export default async function AssistantPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const user = await requireUsableBackendUser();
  const query = await searchParams;
  const initial = Object.fromEntries(Object.entries(contextSchema.shape).flatMap(([key, schema]) => {
    const result = schema.safeParse(query[key]);
    return result.success && result.data ? [[key, result.data]] : [];
  }));
  const agentId = agentIdSchema.safeParse(query.agent).data;
  const modelId = agentIdSchema.safeParse(query.model).data;
  const requestedMode = assistantModeSchema.safeParse(query.mode).data;
  const mode = agentId && requestedMode !== "direct" ? "agent" : requestedMode ?? "direct";
  return <AssistantView user={user} initial={contextSchema.partial().parse(initial)} mode={mode} modelId={mode === "direct" ? modelId : undefined} agentId={mode === "agent" ? agentId : undefined} />;
}
