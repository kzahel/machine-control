// Standalone real-browser integration. No installed resident or primary browser.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";
import { BrowserHost } from "../../runtime/testing/browser-host.ts";

const repository = fileURLToPath(new URL("../../", import.meta.url));
const extensionId = "ncbfifkjllmnkkjmomjohinigfgdocjc";
const shellQuote = (value) => "'" + value.replaceAll("'", "'\\''") + "'";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function poll(predicate, label, timeout = 10_000) {
  const deadline = performance.now() + timeout;
  while (performance.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await delay(25);
  }
  throw new Error(`Timed out: ${label}`);
}
async function within(promise, label, timeout = 10_000) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`Timed out: ${label}`)),
          timeout,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    throw error;
  }
}

export async function runBrowserAcceptance() {
  if (!["darwin", "linux"].includes(process.platform))
    throw new Error(
      "Scratch-profile native-host registration is implemented only on Mac/Linux",
    );
  const { chromium } = await import(
    "../../desktop/node_modules/playwright/index.mjs"
  );
  const browserExecutable = chromium.executablePath();
  assert.match(
    browserExecutable,
    /ms-playwright[\/]/,
    "Use the pinned separately identified test browser",
  );
  const started = performance.now();
  const root = await mkdtemp(join(tmpdir(), "mc-nb-"));
  const host = new BrowserHost();
  const contexts = [],
    checks = [],
    pages = {},
    panels = {};
  const counters = { work: 0, personal: 0 };
  const browserVersions = [];
  let extensionVersion;
  let server,
    failure,
    stage = "setup",
    result;
  const check = (name) => {
    checks.push(name);
    process.stderr.write(`PASS ${name}\n`);
  };
  let nextRequest = 0;
  async function call(
    approval,
    profile,
    operation,
    fields = {},
    requestId = `request-${++nextRequest}`,
  ) {
    const connection = host.connection(profile);
    assert.ok(connection, `Connected ${profile}`);
    return within(
      host.call(approval, {
        requestId,
        profileId: profile,
        operation,
        connection,
        timeoutMs: 4_000,
        ...fields,
      }),
      operation,
    );
  }
  async function accepted(
    approval,
    profile,
    operation,
    fields = {},
    requestId,
  ) {
    const result = await call(approval, profile, operation, fields, requestId);
    assert.equal(
      result.accepted,
      true,
      `${profile} ${operation}: ${result.errorCode}; ${JSON.stringify(host.providerErrors)}`,
    );
    return result;
  }
  async function button(approval, profile) {
    const tabs = await accepted(approval, profile, "browser.tabs");
    const tab = tabs.data.tabs.find((tab) =>
      tab.url.endsWith(`/fixture/${profile}`),
    );
    assert.ok(tab, `Find owned ${profile} fixture through extension discovery`);
    assert.equal(tabs.data.providerInfo.extensionId, extensionId);
    assert.equal(tabs.data.providerInfo.extensionVersion, extensionVersion);
    assert.match(tabs.data.providerInfo.operationsSha256, /^[a-f0-9]{64}$/);
    const snapshot = await accepted(approval, profile, "browser.snapshot", {
      tabId: tab.tabId,
    });
    const element = snapshot.data.elements.find(
      (element) =>
        element.role === "button" && element.name === "Increment fixture",
    );
    assert.ok(element, "Read a real provider reference from its AX snapshot");
    return { connection: host.connection(profile), target: element.reference };
  }
  async function panelAccess(profile, approved) {
    await poll(async () => {
      const text = await panels[profile]
        .locator("#access-summary")
        .textContent();
      return approved
        ? text?.startsWith("An agent may control")
        : text?.startsWith("No agent has browser access");
    }, `${profile} extension approval projection`);
    if (!approved)
      await poll(
        () => panels[profile].locator("#no-tabs").isVisible(),
        `${profile} controlled-tab cleanup`,
      );
  }

  try {
    await host.listen(root, ["work", "personal"]);
    const extension = join(root, "extension");
    execFileSync("python3", [
      "-B",
      join(repository, "providers/chrome-extension/package.py"),
      "--unpacked",
      extension,
    ]);
    const sourceWorker = await readFile(
      join(repository, "providers/chrome-extension/service_worker.js"),
    );
    assert.deepEqual(
      await readFile(join(extension, "service_worker.js")),
      sourceWorker,
    );
    const workerSha256 = createHash("sha256")
      .update(sourceWorker)
      .digest("hex");
    extensionVersion = JSON.parse(
      await readFile(join(extension, "manifest.json"), "utf8"),
    ).version;
    server = createServer((request, response) => {
      const match = /^\/(fixture|effect)\/(work|personal)$/.exec(
        request.url ?? "",
      );
      if (!match) {
        response.writeHead(404).end();
        return;
      }
      const [, route, profile] = match;
      if (route === "fixture" && request.method === "GET") {
        response.writeHead(200, {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store",
        });
        response.end(
          `<!doctype html><title>Fixture ${profile}</title><button onclick="fetch('/effect/${profile}',{method:'POST',body:String(event.isTrusted)})">Increment fixture</button>`,
        );
      } else if (route === "effect" && request.method === "POST") {
        let body = "";
        request.on("data", (chunk) => {
          body += chunk;
          if (body.length > 32) request.destroy();
        });
        request.on("end", () => {
          if (body !== "true") {
            response.writeHead(400).end();
            return;
          }
          counters[profile]++;
          response.writeHead(204).end();
        });
      } else response.writeHead(405).end();
    });
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolve);
    });
    const url = `http://127.0.0.1:${server.address().port}`;

    for (const profile of ["work", "personal"]) {
      stage = `launch ${profile}`;
      const directory = join(root, profile);
      const manifests = join(directory, "NativeMessagingHosts");
      await mkdir(manifests, { recursive: true });
      const config = join(root, `${profile}.json`),
        launcher = join(root, `${profile}.sh`);
      await writeFile(
        config,
        JSON.stringify({ socketPath: host.socketPath(profile) }),
        { mode: 0o600 },
      );
      await writeFile(
        launcher,
        `#!/bin/sh\nexec ${shellQuote(process.execPath)} ${shellQuote(join(repository, "tests/runtime/native-host.mjs"))} ${shellQuote(config)} "$@"\n`,
        { mode: 0o700 },
      );
      await writeFile(
        join(manifests, "org.machine_control.browser.json"),
        JSON.stringify({
          name: "org.machine_control.browser",
          description: "Shared-core isolated browser fixture",
          path: launcher,
          type: "stdio",
          allowed_origins: [`chrome-extension://${extensionId}/`],
        }),
      );
      const context = await chromium.launchPersistentContext(directory, {
        channel: "chromium",
        headless: true,
        chromiumSandbox: false,
        args: [
          `--disable-extensions-except=${extension}`,
          `--load-extension=${extension}`,
        ],
      });
      contexts.push(context);
      browserVersions.push(context.browser().version());
      const worker =
        context.serviceWorkers()[0] ??
        (await context.waitForEvent("serviceworker", { timeout: 10_000 }));
      assert.ok(worker.url().startsWith(`chrome-extension://${extensionId}/`));
      await poll(
        () => host.connection(profile),
        `${profile} real native hello`,
      );
      pages[profile] = context.pages()[0] ?? (await context.newPage());
      await pages[profile].goto(`${url}/fixture/${profile}`);
      panels[profile] = await context.newPage();
      await panels[profile].goto(
        `chrome-extension://${extensionId}/panel.html`,
      );
    }
    check("two headless real workers connect through scratch native hosts");
    const initial = [host.connection("work"), host.connection("personal")];
    const beforeOff = host.wireRequests;
    assert.equal(
      (await call(undefined, "work", "browser.tabs")).errorCode,
      "approval_required",
    );
    assert.equal(host.wireRequests, beforeOff);
    check("Off refuses before the native transport");

    stage = "Work-only approval";
    let approval = await host.approve(["work"]);
    await panelAccess("work", true);
    await panelAccess("personal", false);
    const beforeUnapproved = host.wireRequests;
    assert.equal(
      (await call(approval, "personal", "browser.tabs")).errorCode,
      "profile_not_approved",
    );
    assert.equal(host.wireRequests, beforeUnapproved);
    const workReference = await button(approval, "work");
    const workClick = await accepted(approval, "work", "browser.click", {
      reference: workReference,
    });
    assert.equal(workClick.effect, "unverifiable");
    await poll(() => counters.work === 1, "independent Work HTTP effect");
    assert.equal(counters.personal, 0);
    check(
      "Work-only approval, real snapshot/reference and trusted click effect",
    );

    stage = "both profiles";
    approval = await host.approve(["work", "personal"]);
    await panelAccess("personal", true);
    const personalReference = await button(approval, "personal");
    const crossCount = host.wireRequests;
    assert.equal(
      (
        await call(approval, "work", "browser.click", {
          reference: personalReference,
        })
      ).errorCode,
      "stale_reference",
    );
    assert.equal(host.wireRequests, crossCount);
    await accepted(approval, "personal", "browser.click", {
      reference: personalReference,
    });
    await poll(
      () => counters.personal === 1,
      "independent Personal HTTP effect",
    );
    assert.equal(counters.work, 1);
    assert.deepEqual(
      [host.connection("work"), host.connection("personal")],
      initial,
    );
    check(
      "both approved profiles preserve connections and reject foreign references",
    );

    stage = "Stop and late result";
    const heldReference = await button(approval, "work");
    const gate = host.holdNextReply("work", "browser.click");
    const held = call(
      approval,
      "work",
      "browser.click",
      { reference: heldReference },
      "reused-click",
    );
    await within(gate.captured, "held real Work response");
    await poll(() => counters.work === 2, "Work effect before Stop");
    await host.stop();
    const stopped = await held;
    assert.equal(stopped.delivery, "unknown");
    assert.equal(stopped.effect, "unknown");
    await panelAccess("work", false);
    await panelAccess("personal", false);
    const stoppedWireCount = host.wireRequests;
    assert.equal(
      (await call(approval, "work", "browser.tabs")).errorCode,
      "approval_required",
    );
    assert.equal(host.wireRequests, stoppedWireCount);
    check(
      "Stop reaches both real workers and preserves uncertain dispatched effects",
    );

    approval = await host.approve(["personal"]);
    const freshReference = await button(approval, "personal");
    const freshGate = host.holdNextReply("personal", "browser.click");
    const fresh = call(
      approval,
      "personal",
      "browser.click",
      { reference: freshReference },
      "reused-click",
    );
    await within(freshGate.captured, "held fresh Personal response");
    assert.equal(await gate.release(), false);
    assert.equal((await host.inspect()).pendingRequests, 1);
    assert.deepEqual((await host.inspect()).approvedProfiles, ["personal"]);
    assert.equal(await freshGate.release(), true);
    assert.equal((await fresh).accepted, true);
    await poll(() => counters.personal === 2, "fresh Personal effect");
    assert.equal((await host.inspect()).retainedRequests, 0);
    check(
      "late Work wire reply cannot complete a new Personal request with the same label",
    );

    stage = "native host loss";
    approval = await host.approve(["work", "personal"]);
    const oldWork = host.connection("work"),
      unchangedPersonal = host.connection("personal");
    const oldReference = await button(approval, "work");
    const unaffectedReference = await button(approval, "personal");
    const lossGate = host.holdNextReply("work", "browser.click");
    const lost = call(approval, "work", "browser.click", {
      reference: oldReference,
    });
    await within(lossGate.captured, "real Work reply before transport loss");
    await poll(() => counters.work === 3, "Work effect before transport loss");
    host.dropTransport("work");
    const disconnected = await lost;
    assert.equal(disconnected.errorCode, "provider_disconnected");
    assert.equal(disconnected.delivery, "unknown");
    await poll(
      () => host.connection("work")?.generation > oldWork.generation,
      "real native host and worker reconnection",
    );
    assert.equal(host.connection("personal"), unchangedPersonal);
    const beforeStale = host.wireRequests;
    assert.equal(
      (
        await call(approval, "work", "browser.click", {
          reference: oldReference,
        })
      ).errorCode,
      "stale_reference",
    );
    assert.equal(host.wireRequests, beforeStale);
    assert.equal(await lossGate.release(), false);
    await accepted(approval, "personal", "browser.click", {
      reference: unaffectedReference,
    });
    await poll(() => counters.personal === 3, "unaffected Personal effect");
    const newWorkReference = await button(approval, "work");
    await accepted(approval, "work", "browser.click", {
      reference: newWorkReference,
    });
    await poll(() => counters.work === 4, "fresh Work effect after reconnect");
    assert.equal((await host.inspect()).retainedRequests, 0);
    check(
      "native transport loss fences pending work, reconnects and leaves Personal usable",
    );
    await host.stop();
    await panelAccess("work", false);
    await panelAccess("personal", false);
    check("final Stop clears controlled tabs in both real extension panels");

    stage = "approval deadline across the process boundary";
    approval = await host.approve(["work"], 1000);
    const expiryReference = await button(approval, "work");
    const expiryGate = host.holdNextReply("work", "browser.click");
    const expiring = call(approval, "work", "browser.click", { reference: expiryReference });
    await within(expiryGate.captured, "real reply held until approval expiry");
    await poll(() => counters.work === 5, "independent effect before expiry");
    const expired = await expiring;
    assert.equal(expired.errorCode, "approval_expired");
    assert.equal(expired.delivery, "unknown");
    await panelAccess("work", false);
    assert.equal(await expiryGate.release(), false);
    check("scheduled expiry revokes the real worker and fences its held reply");

    stage = "policy process death and restart";
    approval = await host.approve(["work", "personal"]);
    const killedReference = await button(approval, "work");
    const killedGate = host.holdNextReply("work", "browser.click");
    const dying = call(approval, "work", "browser.click", { reference: killedReference });
    const rejected = assert.rejects(dying, /fixture_policy_died/);
    await within(killedGate.captured, "real effect before coordinator kill");
    await poll(() => counters.work === 6, "independent effect before policy death");
    host.killPolicy();
    await rejected;
    await poll(() => !host.connection("work") && !host.connection("personal"), "native routes close after policy death");
    await panelAccess("work", false);
    await panelAccess("personal", false);
    await host.restartPolicy();
    await poll(() => host.connection("work") && host.connection("personal"), "native routes reconnect to fresh Off policy");
    const restartRequests = host.wireRequests;
    assert.equal((await call(undefined, "work", "browser.tabs")).errorCode, "approval_required");
    assert.equal(host.wireRequests, restartRequests);
    approval = await host.approve(["work", "personal"]);
    assert.equal((await call(approval, "work", "browser.click", { reference: killedReference })).errorCode, "stale_reference");
    await assert.rejects(killedGate.release(), /unknown_connection/);
    const afterRestart = await button(approval, "personal");
    await accepted(approval, "personal", "browser.click", { reference: afterRestart });
    await poll(() => counters.personal === 4, "fresh independent effect after policy restart");
    assert.equal(counters.work, 6);
    await host.stop();
    await panelAccess("work", false);
    await panelAccess("personal", false);
    check("policy death closes real native ports; restart has no consent, stale refs or replay");
    result = {
      passed: true,
      platform: process.platform,
      architecture: process.arch,
      browserVersion: browserVersions[0],
      extensionWorkerSha256: workerSha256,
      extensionVersion,
      topology:
        "two persistent profiles in separate headless test-browser processes",
      browserSandbox: false,
      checks,
      independentEffects: counters,
    };
  } catch (error) {
    failure = new Error(`${stage}: ${error.message}`, { cause: error });
  } finally {
    try {
      await host.stop();
      const closed = await Promise.allSettled(
        contexts.map((context) => context.close()),
      );
      await host.close();
      if (server)
        await new Promise((resolve) => {
          server.close(resolve);
          server.closeAllConnections();
        });
      await poll(
        () => [...host.nativeProcessIds].every((pid) => !alive(pid)),
        "all owned native relay processes exited",
        5_000,
      );
      assert.equal(
        closed.every((value) => value.status === "fulfilled"),
        true,
        "Close all owned browser processes",
      );
      if (result) {
        result.nativeHostsReaped = true;
        result.elapsedMs = Math.round(performance.now() - started);
      }
    } catch (error) {
      failure ??= error;
    }
    await rm(root, { recursive: true, force: true });
  }
  if (failure) throw failure;
  return result;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  runBrowserAcceptance()
    .then((result) =>
      process.stdout.write(JSON.stringify(result, null, 2) + "\n"),
    )
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
