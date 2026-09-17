import { createAgentUIStreamResponse } from "ai";
import { z } from "zod";
import { createAssistant } from "@/lib/assistant/agent";
import { AssistantError, authenticate, boundedBody, errorResponse, sameOrigin, sessionCookie } from "@/lib/assistant/backend";
import { contextSchema, scrubHistory } from "@/lib/assistant/schemas";
import { resolveAssistantRuntime } from "@/lib/assistant/model-resolver";

export const runtime = "nodejs";
export const maxDuration = 120;

const messageSchema = z.object({ id: z.string().max(100), role: z.enum(["user", "assistant"]), parts: z.array(z.record(z.string(), z.unknown())).max(100) });
const requestSchema = z.object({
  context: contextSchema,
  modelId: z.string().uuid().optional(),
  id: z.string().max(100).optional(),
  trigger: z.enum(["submit-message", "regenerate-message"]).optional(),
  messageId: z.string().max(100).optional(),
  messages: z.array(messageSchema).min(1).max(60),
}).strict();

export async function POST(request: Request) {
  try {
    sameOrigin(request);
    const cookie = sessionCookie(request);
    const user = await authenticate(cookie);
    const body = requestSchema.parse(await boundedBody(request));
    // Do not allow files, data URLs, provider-executed tools or system messages from clients.
    for (const message of body.messages) for (const part of message.parts) {
      if (typeof part.type !== "string" || !(part.type === "text" || part.type === "step-start" || part.type.startsWith("tool-")) || part.providerExecuted === true) {
        throw new AssistantError(422, "invalid_message", "Only text and KubePilot tool results are supported.");
      }
    }
    const signal = AbortSignal.any([request.signal, AbortSignal.timeout(110000)]);
    const resolved = await resolveAssistantRuntime(cookie, body.modelId);
    const agent = createAssistant(resolved.model, cookie, body.context, user.role, signal, resolved.metadata.capabilities.tools);
    return await createAgentUIStreamResponse({ agent, uiMessages: body.messages.map(scrubHistory), abortSignal: signal, sendReasoning: false, sendSources: false,
      onError: () => "The AI provider could not complete the response. Check model availability or try a new conversation. No proposed action was approved by this error.",
    });
  } catch (error) { return errorResponse(error); }
}
