import assert from "node:assert/strict";
import test from "node:test";
import { NextRequest } from "next/server";
import { config, proxy } from "../proxy.ts";

test("every API mutation passes the shared origin gate before upstream access", async () => {
  assert.ok(config.matcher.includes("/api/:path*"));
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error("unexpected upstream access"); };
  try {
    for (const path of ["/api/clusters", "/api/users", "/api/auth/login", "/api/settings/credentials", "/api/cluster/manage-resources/pods"]) {
      for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
        const rejected = await proxy(new NextRequest(`https://app.example.com${path}`, { method, headers: { host: "app.example.com", origin: "https://evil.example.com" } }));
        assert.equal(rejected.status, 403);
        const allowed = await proxy(new NextRequest(`https://app.example.com${path}`, { method, headers: { host: "app.example.com", origin: "https://app.example.com" } }));
        assert.equal(allowed.headers.get("x-middleware-next"), "1");
      }
    }
    const missing = await proxy(new NextRequest("https://app.example.com/api/clusters", { method: "POST", headers: { host: "app.example.com" } }));
    assert.equal(missing.status, 403);
    const read = await proxy(new NextRequest("https://app.example.com/api/clusters"));
    assert.equal(read.headers.get("x-middleware-next"), "1");
  } finally {
    globalThis.fetch = original;
  }
});
