import { test } from "node:test";
import assert from "node:assert/strict";
import { GET, POST } from "../app/api/assistant/agents/route.ts";
import { PUT, DELETE } from "../app/api/assistant/agents/[agentId]/route.ts";
import { agentWriteSchema, validateAgent, draftOf, filterAgents, agentRequest, AgentRequestError, agentListSchema } from "../lib/assistant/agents.ts";

const id = "11111111-1111-4111-8111-111111111111";
const draft = { name: "Investigator", description: "Workload health", instructions: "Read evidence.\nExplain findings.", model_id: id, enabled: false };
const model = { id, friendly_name: "Test", provider_name: "OpenAI", enabled: true, availability: "available", capabilities: { streaming: true, tools: true } };
const agent = { ...draft, id, model, created_by_id: id, updated_by_id: id, created_at: "2026-09-29T00:00:00Z", updated_at: "2026-09-29T00:00:00Z" };
const context = { params: Promise.resolve({ agentId: id }) };
function request(method = "POST", body = draft, origin = "http://localhost:3000") {
  return new Request("http://localhost:3000/api/assistant/agents", { method, headers: { host: "localhost:3000", origin, cookie: "kubepilot_session=signed; unrelated=secret", "content-type": "application/json" }, body: ["GET", "DELETE"].includes(method) ? undefined : JSON.stringify(body) });
}

test("agent bridges forward the signed cookie only and never cache", async t => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return Response.json(options.method === "GET" ? { agents: [agent] } : agent); });
  assert.equal((await GET(request("GET"))).status, 200);
  assert.equal((await POST(request())).status, 200);
  assert.equal((await PUT(request("PUT"), context)).status, 200);
  assert.equal((await DELETE(request("DELETE"), context)).status, 200);
  for (const { options } of calls) {
    assert.equal(options.headers.cookie, "kubepilot_session=signed");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.authorization, undefined);
  }
  assert.ok(calls[2].url.endsWith(`/assistant/agents/${id}`));
});

test("mutations reject foreign origins, forged fields, oversized payloads and invalid ids before fetching", async t => {
  t.mock.method(globalThis, "fetch", () => { throw new Error("must not fetch"); });
  assert.equal((await POST(request("POST", draft, "https://attacker.test"))).status, 403);
  assert.equal((await DELETE(request("DELETE", draft, "https://attacker.test"), context)).status, 403);
  assert.equal((await POST(request("POST", { ...draft, created_by_id: id }))).status, 422);
  assert.equal((await PUT(request("PUT"), { params: Promise.resolve({ agentId: "../settings" }) })).status, 422);
  assert.equal((await POST(request("POST", { ...draft, instructions: "a".repeat(256001) }))).status, 413);
  assert.equal(globalThis.fetch.mock.callCount(), 0);
});

test("bridge preserves denied and missing response status without leaking upstream errors", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ code: "insufficient_permissions", message: "Denied" }, { status: 403 }));
  assert.equal((await PUT(request("PUT"), context)).status, 403);
  globalThis.fetch.mock.mockImplementation(async () => Response.json({ code: "agent_not_found", message: "Missing" }, { status: 404 }));
  assert.equal((await DELETE(request("DELETE"), context)).status, 404);
  globalThis.fetch.mock.mockImplementation(async () => new Response("private stack trace", { status: 500 }));
  const result = await POST(request());
  assert.equal(result.status, 503);
  assert.ok(!(await result.text()).includes("private stack"));
});

test("wizard validation allows basic stage without a model and requires it before review", () => {
  assert.deepEqual(validateAgent({ ...draft, model_id: null }, null, [], 0), {});
  assert.ok(validateAgent({ ...draft, model_id: null }, null, [], 1).model_id);
  assert.deepEqual(validateAgent(draft, null, [model], 2), {});
  assert.ok(validateAgent({ ...draft, name: " " }, null, [model]).name);
  assert.ok(validateAgent({ ...draft, name: "x".repeat(129) }, null, [model]).name);
  assert.equal(agentWriteSchema.safeParse({ ...draft, enabled: "true" }).success, false);
  assert.equal(agentWriteSchema.parse({ ...draft, name: "  Name  " }).name, "Name");
  assert.equal(agentWriteSchema.parse(draft).instructions, draft.instructions);
});

test("outages and deleted models permit editing disabled definitions but not re-enabling", () => {
  const unavailable = { ...model, availability: "unavailable" };
  assert.deepEqual(validateAgent(draft, agent, [unavailable]), {});
  assert.ok(validateAgent({ ...draft, enabled: true }, agent, [unavailable]).model_id);
  assert.deepEqual(validateAgent({ ...draft, enabled: true }, { ...agent, enabled: true }, [unavailable]), {});
  const missing = { ...agent, model_id: null, model: null };
  assert.deepEqual(validateAgent(draftOf(missing), missing, []), {});
  assert.ok(validateAgent({ ...draftOf(missing), enabled: true }, missing, []).model_id);
});

test("draft serialization excludes server identity; search preserves exact saved values", () => {
  assert.deepEqual(draftOf(agent), draft);
  assert.equal(filterAgents([agent], "  HEALTH ").length, 1);
  assert.equal(filterAgents([agent], "absent").length, 0);
  assert.equal(agent.name, "Investigator");
});

test("client distinguishes access denial, unexpected data, and uncertain mutation without retry", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ code: "insufficient_permissions", message: "Denied" }, { status: 403 }));
  await assert.rejects(agentRequest("/test", agentListSchema), error => error instanceof AgentRequestError && error.status === 403);
  globalThis.fetch.mock.mockImplementation(async () => Response.json({ notAgents: [] }));
  await assert.rejects(agentRequest("/test", agentListSchema), error => error.code === "invalid_response");
  globalThis.fetch.mock.mockImplementation(async () => { throw new TypeError("network"); });
  const before = globalThis.fetch.mock.callCount();
  await assert.rejects(agentRequest("/test", agentListSchema, "POST", draft), error => error.status === 0 && error.message.includes("Refresh stored state"));
  assert.equal(globalThis.fetch.mock.callCount(), before + 1);
});
