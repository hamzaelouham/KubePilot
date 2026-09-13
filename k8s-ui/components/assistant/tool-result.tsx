"use client";

import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Tool, ToolHeader, ToolContent, ToolInput } from "@/components/ai-elements/tool";
import type { ToolUIPart, DynamicToolUIPart } from "ai";
import { proposalSchema, type ActionProposal } from "@/lib/assistant/schemas";
import { ActionReview } from "./action-review";

const objectSchema = z.record(z.string(), z.unknown());
const resultSchema = z.object({ cluster: z.string(), namespace: z.string().nullable().optional(), resource_type: z.string().optional(), result: objectSchema });

function Results({ output, followUp, disabled }: { output: unknown; followUp: (text: string) => void; disabled: boolean }) {
  const parsed = resultSchema.safeParse(output);
  if (!parsed.success) return <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(output, null, 2)}</pre>;
  const { result, cluster, namespace, resource_type } = parsed.data;
  if (Array.isArray(result.lines)) return <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{result.lines.map(String).join("\n")}</pre>;
  const items = Array.isArray(result.items) ? result.items : result.name ? [result] : [];
  return <div className="flex flex-col gap-3">
    {result.truncated === true && <p className="text-sm text-muted-foreground">Bounded result; additional records may exist.</p>}
    {items.length ? items.slice(0, 8).map((raw, index) => {
      const item = objectSchema.safeParse(raw);
      if (!item.success) return null;
      const data = item.data;
      const type = typeof data.resource_type === "string" ? data.resource_type : resource_type;
      const name = typeof data.name === "string" ? data.name : undefined;
      const ns = typeof data.namespace === "string" ? data.namespace : namespace;
      return <Card key={index} size="sm"><CardHeader><CardTitle>{name ?? String(data.reason ?? "Observation")}</CardTitle><CardDescription>{cluster} / {ns ?? "cluster scope"}{type ? ` / ${type}` : ""}</CardDescription></CardHeader><CardContent><pre className="max-h-44 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(data, null, 2)}</pre></CardContent><CardFooter className="flex flex-wrap gap-2">{type && name ? <><Button variant="outline" size="sm" disabled={disabled} onClick={() => followUp(`Inspect ${type} ${name}${ns ? ` in namespace ${ns}` : ""}.`)}>Inspect</Button><Button variant="outline" size="sm" disabled={disabled} onClick={() => followUp(`Find the likely cause of problems with ${type} ${name}${ns ? ` in namespace ${ns}` : ""}. Gather evidence and suggest a fix.`)}>Suggest Fix</Button>{ns && <Button variant="outline" size="sm" disabled={disabled} onClick={() => followUp(`Show events for ${name} in namespace ${ns}.`)}>View Events</Button>}{type === "pods" && ns && <Button variant="outline" size="sm" disabled={disabled} onClick={() => followUp(`Read logs for pod ${name} in namespace ${ns}; inspect container statuses if necessary.`)}>View Logs</Button>}</> : <Badge variant="outline">Observation</Badge>}</CardFooter></Card>;
    }) : <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(result, null, 2)}</pre>}
    {items.length > 8 && <details><summary className="cursor-pointer text-sm">Show all {items.length} returned records</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(items, null, 2)}</pre></details>}
  </div>;
}

export function AssistantTool({ part, cluster, disabled, followUp, onResult }: { part: ToolUIPart | DynamicToolUIPart; cluster: string; disabled: boolean; followUp: (text: string) => void; onResult: (result: ActionProposal) => void }) {
  const output = part.state === "output-available" ? part.output : undefined;
  const proposal = proposalSchema.safeParse(output);
  const toolName = part.type === "dynamic-tool" ? part.toolName : part.type.slice(5);
  return <Tool defaultOpen={proposal.success}>
    <ToolHeader type="dynamic-tool" toolName={toolName} title={toolName} state={part.state} />
    <ToolContent>
      <ToolInput input={part.input} />
      {part.state === "output-error" ? <p role="alert" className="text-sm text-destructive">{part.errorText}</p> : null}
      {proposal.success ? <ActionReview id={proposal.data.proposal_id} cluster={cluster} disabled={disabled} onResult={onResult} /> : output !== undefined ? <Results output={output} followUp={followUp} disabled={disabled} /> : null}
    </ToolContent>
  </Tool>;
}
