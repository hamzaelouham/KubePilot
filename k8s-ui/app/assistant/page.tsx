import { requireUsableBackendUser } from "@/lib/auth";
import { AssistantView } from "@/components/assistant/view";
import { contextSchema } from "@/lib/assistant/schemas";

export default async function AssistantPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const user = await requireUsableBackendUser();
  const query = await searchParams;
  const initial = Object.fromEntries(Object.entries(contextSchema.shape).flatMap(([key, schema]) => {
    const result = schema.safeParse(query[key]);
    return result.success && result.data ? [[key, result.data]] : [];
  }));
  return <AssistantView user={user} initial={contextSchema.partial().parse(initial)} />;
}
