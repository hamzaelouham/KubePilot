import { test } from "node:test";
import assert from "node:assert/strict";
import { GET as listCredentials } from "../app/api/settings/credentials/route.ts";
import { DELETE, PUT } from "../app/api/settings/credentials/[credentialKey]/route.ts";
import {
  credentialSchema,
  credentialsResponseSchema,
  deleteCredential,
  fetchCredentials,
  saveCredential,
} from "../lib/settings-credentials.ts";

const credential = {
  credential_key: "ai.provider.openai.api_key",
  display_name: "OpenAI API key",
  description: "API key used by KubePilot to access OpenAI.",
  category: "provider",
  configured: false,
  updated_at: null,
};

function request(method = "GET", body) {
  return new Request("http://localhost:3000/api/settings/credentials", {
    method,
    headers: {
      cookie: "kubepilot_session=signed; unrelated=private",
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    body,
  });
}

test("credential schemas accept safe metadata and reject secret-bearing responses", () => {
  assert.deepEqual(credentialSchema.parse(credential), credential);
  assert.deepEqual(credentialsResponseSchema.parse({ credentials: [credential] }), { credentials: [credential] });
  assert.throws(() => credentialSchema.parse({ ...credential, value: "secret" }));
  assert.throws(() => credentialSchema.parse({ ...credential, ciphertext: "encrypted" }));
  assert.throws(() => credentialSchema.parse({ ...credential, category: "arbitrary" }));
});

test("credential client uses metadata-only GET and write-only PUT/DELETE requests", async t => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls.push({ url: String(url), init });
    return Response.json(init.method === "GET" ? { credentials: [credential] } : { ...credential, configured: init.method === "PUT" });
  });

  assert.equal((await fetchCredentials()).credentials.length, 1);
  assert.equal((await saveCredential(credential.credential_key, "new-secret")).configured, true);
  assert.equal((await deleteCredential(credential.credential_key)).configured, false);
  assert.equal(calls[0].url, "/api/settings/credentials");
  assert.deepEqual(JSON.parse(calls[1].init.body), { value: "new-secret" });
  assert.equal(calls[2].init.body, undefined);
});

test("credential proxy forwards only the signed session cookie and exact methods", async t => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls.push({ url: String(url), init });
    return Response.json(init.method === "GET" || init.method === undefined ? { credentials: [credential] } : credential);
  });

  assert.equal((await listCredentials(request())).status, 200);
  const context = { params: Promise.resolve({ credentialKey: credential.credential_key }) };
  assert.equal((await PUT(request("PUT", JSON.stringify({ value: "new-secret" })), context)).status, 200);
  assert.equal((await DELETE(request("DELETE"), context)).status, 200);

  assert.ok(calls[0].url.endsWith("/api/v1/settings/credentials"));
  assert.ok(calls[1].url.endsWith(`/api/v1/settings/credentials/${credential.credential_key}`));
  assert.equal(calls[0].init.headers.cookie, "kubepilot_session=signed");
  assert.equal(calls[1].init.headers.cookie, "kubepilot_session=signed");
  assert.equal(calls[2].init.headers.cookie, "kubepilot_session=signed");
  assert.equal(calls[1].init.method, "PUT");
  assert.equal(calls[2].init.method, "DELETE");
  assert.equal(calls[2].init.body, undefined);
  assert.equal(calls[0].init.cache, "no-store");
});

test("credential client and proxy fail closed on malformed or unavailable responses", async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ credentials: [{ ...credential, value: "leak" }] }));
  await assert.rejects(fetchCredentials());

  globalThis.fetch.mock.mockImplementation(async () => { throw new Error("offline"); });
  await assert.rejects(fetchCredentials(), /unavailable/);
  const response = await listCredentials(request());
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { code: "backend_unavailable", message: "The credential service is unavailable" });
});
