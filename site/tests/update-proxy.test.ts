import test from "node:test";
import assert from "node:assert/strict";
import { proxyUpdate } from "../src/lib/update-proxy.ts";

const params = { target: "darwin", arch: "aarch64", version: "0.3.3" };
test("update proxy preserves protocol responses and limits forwarded headers", async () => {
  const request = new Request("https://machinecontrol.dev/updates/tauri/darwin/aarch64/0.3.3", {
    headers: { "X-Check-Reason": "manual", "Cookie": "private", "Authorization": "private" },
  });
  const fetcher = (async (url, options) => {
    assert.equal(url, "https://updates.graehlarts.com/machine-control/tauri/darwin/aarch64/0.3.3");
    const headers = new Headers(options?.headers);
    assert.equal(headers.get("X-Check-Reason"), "manual");
    assert.equal(headers.has("Cookie"), false);
    assert.equal(headers.has("Authorization"), false);
    assert.equal(options?.redirect, "manual");
    return Response.json({ version: "0.3.4", signature: "signed", url: "artifact" });
  }) as typeof fetch;
  const response = await proxyUpdate(params, request, fetcher);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).version, "0.3.4");
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  const current = await proxyUpdate(params, request, (async () => new Response(null, { status: 204 })) as typeof fetch);
  assert.equal(current.status, 204);
  assert.equal(await current.text(), "");
});
test("invalid targets and upstream failures fail closed", async () => {
  const request = new Request("https://machinecontrol.dev");
  const unavailable = (async () => new Response("bad", { status: 500 })) as typeof fetch;
  for (const invalid of [{ ...params, target: "linux" }, { ...params, arch: "../../evil" }, { ...params, version: "01.0.0" }]) {
    assert.equal((await proxyUpdate(invalid, request, unavailable)).status, 404);
  }
  assert.equal((await proxyUpdate(params, request, unavailable)).status, 503);
  assert.equal((await proxyUpdate(params, request, (async () => new Response(null, { status: 302, headers: { Location: "https://example.com" } })) as typeof fetch)).status, 503);
  assert.equal((await proxyUpdate(params, request, (async () => { throw new Error("offline"); }) as typeof fetch)).status, 503);
});

test("both Windows updater architectures use the existing product route", async () => {
  for (const arch of ["x86_64", "aarch64"]) {
    const response = await proxyUpdate({target: "windows", arch, version: "0.4.7"}, new Request("https://machinecontrol.dev"),
      (async (url) => {
        assert.equal(url, `https://updates.graehlarts.com/machine-control/tauri/windows/${arch}/0.4.7`);
        return Response.json({version: "0.4.8", signature: "signed", url: "installer"});
      }) as typeof fetch);
    assert.equal(response.status, 200);
  }
});
