import { test } from "node:test";
import assert from "node:assert/strict";
import { GET, POST } from "../app/api/assistant/agents/route.ts";
import { PUT, DELETE } from "../app/api/assistant/agents/[agentId]/route.ts";
import { GET as GETSkills, POST as POSTSkills } from "../app/api/assistant/agents/skills/route.ts";
import { GET as GETTemplates } from "../app/api/assistant/agents/templates/route.ts";
import { GET as GETNotifications, POST as POSTNotifications } from "../app/api/assistant/agents/[agentId]/notifications/route.ts";
import { PUT as PUTNotification, DELETE as DELETENotification } from "../app/api/assistant/agents/[agentId]/notifications/[destinationId]/route.ts";
import { POST as POSTNotificationTest } from "../app/api/assistant/agents/[agentId]/notifications/[destinationId]/test/route.ts";
import { agentWriteSchema, validateAgent, draftOf, applyTemplate, filterAgents, agentRequest, AgentRequestError, agentListSchema, agentTemplateListSchema } from "../lib/assistant/agents.ts";

const id = "11111111-1111-4111-8111-111111111111";
const draft = { name: "Investigator", description: "Workload health", instructions: "Read evidence.\nExplain findings.", model_id: id, enabled: false, skill_ids: [], tool_ids: [] };
const model = { id, friendly_name: "Test", provider_name: "OpenAI", enabled: true, availability: "available", capabilities: { streaming: true, tools: true } };
const agent = { ...draft, id, model, created_by_id: id, updated_by_id: id, created_at: "2026-09-29T00:00:00Z", updated_at: "2026-09-29T00:00:00Z" };
const context = { params: Promise.resolve({ agentId: id }) };
const destinationId = "22222222-2222-4222-8222-222222222222";
const notificationContext = { params: Promise.resolve({ agentId: id, destinationId }) };
const safeDestination = { id: destinationId, provider_id: "slack", label: "On-call", destination_hint: "…C123", enabled: true, connection_status: "connected", updated_at: "2026-09-30T00:00:00Z" };
const delivery = { delivery_id: destinationId, provider_id: "slack", event_type: "agent_notification_test", destination_hint: "…C123", status: "queued", attempt_count: 0, max_attempts: 3, next_attempt_at: "2026-09-30T00:00:00Z", last_error_code: null, created_at: "2026-09-30T00:00:00Z", started_at: null, completed_at: null, agent_id: id, agent_destination_id: destinationId, deduplicated: false };
function request(method = "POST", body = draft, origin = "http://localhost:3000") {
  return new Request("http://localhost:3000/api/assistant/agents", { method, headers: { host: "localhost:3000", origin, cookie: "kubepilot_session=signed; unrelated=secret", "content-type": "application/json" }, body: ["GET", "DELETE"].includes(method) ? undefined : JSON.stringify(body) });
}
function catalogRequest(method = "GET", body = { name: "Skill", description: "Read", instructions: "Read safely." }, origin = "http://localhost:3000") {
  return new Request("http://localhost:3000/api/assistant/agents/skills", { method, headers: { host: "localhost:3000", origin, cookie: "kubepilot_session=signed; unrelated=secret", "content-type": "application/json" }, body: method === "GET" ? undefined : JSON.stringify(body) });
}

function notificationRequest(method = "GET", body = { provider_id: "slack", label: "On-call", destination: "C123", enabled: true }, origin = "http://localhost:3000") {
  return new Request(`http://localhost:3000/api/assistant/agents/${id}/notifications`, { method, headers: { host: "localhost:3000", origin, cookie: "kubepilot_session=signed; unrelated=secret", "content-type": "application/json" }, body: method === "GET" ? undefined : JSON.stringify(body) });
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

test("skill and template bridges preserve the same trust boundary", async t => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return Response.json({ skills: [] }); });
  assert.equal((await GETSkills(catalogRequest())).status, 200);
  assert.equal((await POSTSkills(catalogRequest("POST"))).status, 200);
  assert.equal((await GETTemplates(catalogRequest())).status, 200);
  for (const { options } of calls) {
    assert.equal(options.headers.cookie, "kubepilot_session=signed");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.authorization, undefined);
  }
});

test("notification bridges expose safe destinations and preserve the delivery boundary", async t => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    if (String(url).endsWith("/test")) return Response.json(delivery);
    if (options.method === "DELETE") return Response.json({ id: destinationId });
    return Response.json(options.method === "GET" ? { destinations: [safeDestination] } : safeDestination);
  });
  assert.equal((await GETNotifications(notificationRequest(), { params: Promise.resolve({ agentId: id }) })).status, 200);
  assert.equal((await POSTNotifications(notificationRequest("POST"), { params: Promise.resolve({ agentId: id }) })).status, 200);
  assert.equal((await PUTNotification(notificationRequest("PUT"), notificationContext)).status, 200);
  assert.equal((await DELETENotification(notificationRequest("DELETE"), notificationContext)).status, 200);
  assert.equal((await POSTNotificationTest(new Request("http://localhost:3000/api/assistant/agents/x/notifications/y/test", { method: "POST", headers: { host: "localhost:3000", origin: "http://localhost:3000", cookie: "kubepilot_session=signed" } }), notificationContext)).status, 200);
  for (const { options } of calls) {
    assert.equal(options.headers.cookie, "kubepilot_session=signed");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.authorization, undefined);
  }
  assert.ok(calls.some(call => String(call.url).endsWith(`/assistant/agents/${id}/notifications/${destinationId}/test`)));
});

test("notification mutations reject foreign origins and invalid identifiers before fetching", async t => {
  t.mock.method(globalThis, "fetch", () => { throw new Error("must not fetch"); });
  assert.equal((await POSTNotifications(notificationRequest("POST", undefined, "https://attacker.test"), { params: Promise.resolve({ agentId: id }) })).status, 403);
  assert.equal((await POSTNotificationTest(new Request("http://localhost:3000/api/assistant/agents/x/notifications/y/test", { method: "POST", headers: { host: "localhost:3000", origin: "http://localhost:3000", cookie: "kubepilot_session=signed" } }), { params: Promise.resolve({ agentId: "not-a-uuid", destinationId }) })).status, 422);
  assert.equal(globalThis.fetch.mock.callCount(), 0);
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

test("template contracts apply safe values to a draft without persistence", () => {
  const template = { id: "workload-investigator", name: "Workload investigator", description: "Trace health", instructions: "Use live evidence.", tool_ids: ["listResources", "getEvents"] };
  assert.deepEqual(agentTemplateListSchema.parse({ templates: [template] }).templates[0], template);
  const applied = applyTemplate({ ...draft, name: "Existing", skill_ids: [id], tool_ids: [] }, template);
  assert.equal(applied.name, template.name);
  assert.equal(applied.instructions, template.instructions);
  assert.deepEqual(applied.skill_ids, []);
  assert.deepEqual(applied.tool_ids, template.tool_ids);
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
