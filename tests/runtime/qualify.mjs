/** Exercise a packaged child, independently of a system-installed runtime. */
import assert from "node:assert/strict";
import { readFile, lstat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { resolve, relative, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { ProcessClient } from "../../runtime/testing/process-client.ts";

const nativeTarget = `${process.platform === "win32" ? "win" : process.platform}-${process.arch}`;
const root = process.argv.includes("--native") ? resolve(process.argv[2], nativeTarget) : resolve(process.argv[2]);
const manifest = JSON.parse(await readFile(resolve(root, "payload.json"), "utf8"));
assert.equal(manifest.schema, "machine-control-policy-payload/v1");
assert.ok(Object.hasOwn(manifest.files, manifest.executable));
for (const argument of manifest.arguments) assert.ok(Object.hasOwn(manifest.files, argument));
for (const [name, entry] of Object.entries(manifest.files)) {
  const path = resolve(root, name);
  assert.ok(!relative(root, path).startsWith("..") && !isAbsolute(name));
  assert.ok((await lstat(path)).isFile());
  const bytes = await readFile(path);
  assert.equal(bytes.length, entry.bytes);
  assert.equal(createHash("sha256").update(bytes).digest("hex"), entry.sha256);
}
const command = [resolve(root, manifest.executable), ...manifest.arguments.map((arg) => resolve(root, arg))];
process.env.MC_POLICY_COMMAND = JSON.stringify(command);
process.env.MC_POLICY_SLOW = manifest.target === nativeTarget ? "0" : "1";
const repository = fileURLToPath(new URL("../../", import.meta.url));
async function run(args) {
  const child = spawn(process.execPath, args, { cwd: repository, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
  let error = "";
  child.stdout.on("data", (chunk) => { error = (error + chunk).slice(-16_384); });
  child.stderr.on("data", (chunk) => { if (error.length < 8192) error += chunk; });
  const code = await new Promise((resolve, reject) => { child.once("exit", resolve); child.once("error", reject); });
  if (code !== 0) throw new Error(`payload_acceptance_failed: ${error}`);
}
await run(["--test", "tests/runtime/process.test.mjs"]);
if (process.argv.includes("--browser")) await run(["tests/runtime/browser-live.mjs"]);
const observations = [];
for (let iteration = 0; iteration < 8; iteration++) {
  const client = new ProcessClient(() => {}, () => {});
  const started = performance.now();
  try {
    await client.start();
    const ready = performance.now();
    const state = await client.call("state");
    assert.deepEqual(state.approvedProfiles, []);
    assert.equal(state.host.engine, manifest.engine);
    assert.equal(state.host.version, manifest.engineVersion);
    await client.close();
    observations.push({ startupMs: Math.round(ready - started), shutdownMs: Math.round(performance.now() - ready), rssBytes: state.host.rssBytes });
  } finally { await client.close(); }
}
console.log(JSON.stringify({
  schema: "machine-control-policy-qualification/v1", passed: true,
  engine: manifest.engine, version: manifest.engineVersion, target: manifest.target,
  executionPlatform: process.platform, executionArchitecture: process.arch,
  processChecks: 4, browserChecks: process.argv.includes("--browser") ? 10 : 0,
  observations,
}, null, 2));
