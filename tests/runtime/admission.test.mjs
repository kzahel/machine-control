import test from "node:test";
import assert from "node:assert/strict";
import { AccessAdmission, admissionSchema } from "../../runtime/src/admission.ts";
import { ProcessClient } from "../../runtime/testing/process-client.ts";

function fixture(desktop = "automatic", browser = "automatic") {
  let now = 0, sequence = 0;
  const policy = new AccessAdmission({ now: () => now });
  policy.configure("desktop", { mode: desktop, durationMs: null });
  policy.configure("browser", { mode: browser, durationMs: null, profileIds: ["work", "personal"] });
  policy.ready("desktop", true); policy.ready("browser", true); policy.inputReady(true);
  const owner = policy.open();
  const request = (surface = "desktop", extras = {}, client = owner) => policy.submit(client, {
    requestId: `request:${++sequence}`, surfaces: [surface], profileIds: surface === "browser" ? ["work"] : [],
    disruptive: surface === "desktop", reason: "Synthetic task", waitMs: 300_000, durationMs: 120_000, ...extras,
  });
  const advance = ms => { now += ms; policy.tick(); };
  const inspect = (intent, client = owner, heartbeat = false) => policy.inspect(client, intent.intentId, heartbeat);
  const activate = (intent, client = owner) => {
    let view = inspect(intent, client);
    if (view.state === "announcing") policy.startNow(view.intentId);
    view = inspect(intent, client);
    return policy.accept(client, view.intentId, view.offerGeneration);
  };
  return { policy, owner, request, advance, inspect, activate };
}

for (const desktop of ["off", "ask", "automatic"]) for (const browser of ["off", "ask", "automatic"])
  test(`independent modes: Desktop ${desktop}, Browser ${browser}`, () => {
    const f = fixture(desktop, browser);
    for (const [surface, mode] of [["desktop", desktop], ["browser", browser]]) {
      const intent = f.request(surface);
      assert.equal(intent.schema, admissionSchema);
      assert.equal(intent.state, mode === "off" ? "ended" : mode === "ask" ? "waiting_for_approval" : surface === "desktop" ? "announcing" : "offered");
      if (mode === "off") assert.equal(intent.terminalReason, "surface_disabled");
      else {
        if (mode === "ask") f.policy.approve(intent.intentId);
        const active = f.activate(intent);
        assert.equal(f.policy.authorize(f.owner, active), null);
      }
    }
  });

test("typing during countdown does not defer; movement never interrupts; takeover uses a fixed surface cooldown", () => {
  const f = fixture(), intent = f.request();
  for (let i = 0; i < 10; ++i) { f.policy.input("desktop", "key"); f.advance(1000); }
  const offer = f.inspect(intent);
  assert.equal(offer.state, "offered");
  const active = f.activate(intent);
  f.policy.input("desktop", "movement");
  assert.equal(f.policy.authorize(f.owner, active), null);
  f.policy.input("desktop", "button");
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  const replacement = f.request("desktop", {}, f.policy.open());
  assert.equal(replacement.state, "paused");
  for (let i = 0; i < 12; ++i) {
    f.advance(5000); f.inspect(intent, f.owner, true); f.policy.input("desktop", "scroll");
  }
  assert.equal(f.inspect(intent).state, "announcing");
  assert.equal(f.inspect(intent).noticeRemainingSeconds, 10);
  const fresh = f.activate(intent);
  assert.notEqual(fresh.sessionId, active.sessionId);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  f.policy.input("desktop", "key");
  assert.equal(f.inspect(intent).state, "paused");
});

test("late takeover gets a fresh bounded wait and warning after the initial wait expired", () => {
  const f = fixture(), intent = f.request("desktop", { waitMs: 30_000 });
  f.advance(10_000);
  const active = f.activate(intent);
  for (let i = 0; i < 35; ++i) { f.advance(1000); f.inspect(intent, f.owner, true); }
  assert.equal(f.inspect(intent).waitRemainingSeconds, 0);
  f.policy.input("desktop", "key");
  assert.equal(f.inspect(intent).state, "paused");
  assert.equal(f.inspect(intent).waitRemainingSeconds, 85, "cooldown, warning and offer fit within the task ceiling");
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  for (let i = 0; i < 60; ++i) { f.advance(1000); f.inspect(intent, f.owner, true); }
  assert.equal(f.inspect(intent).state, "announcing");
  f.advance(10_000);
  const fresh = f.activate(intent);
  assert.notEqual(fresh.sessionId, active.sessionId);
  for (let i = 0; i < 35; ++i) { f.advance(1000); f.inspect(intent, f.owner, true); }
  assert.equal(f.inspect(intent).terminalReason, "duration_expired", "resuming never extends the task ceiling");
});

test("Ask first approval survives a pause only for the same live task and does not extend consent", () => {
  const f = fixture("ask");
  f.policy.configure("desktop", { mode: "ask", durationMs: 90_000 });
  const secondOwner = f.policy.open();
  const first = f.request(), second = f.request("desktop", {}, secondOwner);
  assert.equal(first.state, "waiting_for_approval");
  assert.equal(second.state, "waiting_for_approval", "unapproved tasks hold no resources");
  f.policy.approve(first.intentId);
  const active = f.activate(first);
  f.policy.pause("desktop", "manual", 30_000);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  f.advance(30_000);
  assert.equal(f.inspect(second, secondOwner).state, "waiting_for_approval", "yielded ownership does not grant the successor approval");
  f.policy.deny(second.intentId);
  assert.equal(f.inspect(first).state, "announcing");
  const resumed = f.activate(first);
  for (let i = 0; i < 12; ++i) { f.advance(4000); f.inspect(first, f.owner, true); }
  f.advance(12_000);
  assert.equal(f.inspect(first).terminalReason, "consent_expired");
  assert.equal(f.policy.authorize(f.owner, resumed), "stale_control_session");
});

test("Start now acknowledges warning input without exempting the next key", () => {
  const f = fixture(), intent = f.request();
  f.policy.input("desktop", "button");
  f.policy.startNow(intent.intentId);
  const active = f.activate(intent);
  assert.equal(f.policy.authorize(f.owner, active), null);
  f.policy.input("desktop", "key");
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
});

test("Start now tolerates the countdown boundary and never revives a retired session", () => {
  const f = fixture(), intent = f.request();
  f.advance(10_000);
  f.policy.startNow(intent.intentId);
  const active = f.activate(intent);
  f.policy.startNow(intent.intentId);
  assert.equal(f.policy.authorize(f.owner, active), null);
  f.policy.input("desktop", "button");
  f.policy.startNow(intent.intentId);
  const fresh = f.activate(intent);
  assert.notEqual(fresh.sessionId, active.sessionId);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  f.policy.pause("desktop", "manual", null);
  assert.throws(() => f.policy.startNow(intent.intentId), /stale_activation_notice/);
  assert.equal(f.inspect(intent).state, "paused");
});

test("queue and owner budgets refuse excess work without borrowing another channel", () => {
  const f = fixture(), owners = [f.owner];
  while (owners.length < 64) owners.push(f.policy.open());
  for (const owner of owners) for (let i = 0; i < 4; ++i) f.request("desktop", {}, owner);
  assert.equal(f.policy.status().waiting, 256);
  assert.throws(() => f.request(), /admission_queue_full/);
  f.policy.close(owners[1]);
  const newcomer = f.policy.open();
  assert.equal(f.request("desktop", {}, newcomer).state, "waiting_for_resource");
});

test("surface pauses and Off leave unrelated background browser work available", () => {
  const f = fixture("off"), browser = f.request("browser");
  const active = f.activate(browser);
  f.policy.pause("desktop", "manual", null);
  assert.equal(f.policy.authorize(f.owner, active), null);
  f.policy.input("browser", "key");
  assert.equal(f.policy.authorize(f.owner, active), null, "background work does not own human input");
  f.policy.pause("all", "manual", null);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  f.policy.resume("browser", "manual");
  assert.equal(f.inspect(browser).state, "paused", "surface Resume cannot clear a global Pause");
  f.policy.resume("all", "manual");
  assert.equal(f.inspect(browser).state, "offered");
});

test("unapproved Desktop and compound tasks do not hold back automatic Browser work", () => {
  const f = fixture("ask");
  const desktop = f.request();
  assert.equal(desktop.state, "waiting_for_approval");
  const browser = f.request("browser", { disruptive: true });
  assert.equal(browser.state, "announcing", "full CDP impact still proceeds under Browser Automatic");
  f.policy.cancel(f.owner, browser.intentId);
  const compound = f.request("browser", { surfaces: ["desktop", "browser"], disruptive: true });
  assert.equal(compound.state, "waiting_for_approval");
  assert.equal(f.request("browser").state, "offered", "an unapproved compound intent holds no profile reservation");
});

test("compound work acquires all resources atomically under both modes", () => {
  const f = fixture("ask"), compound = f.request("browser", { surfaces: ["browser", "desktop"], disruptive: true });
  assert.equal(compound.state, "waiting_for_approval");
  const other = f.request("browser", { profileIds: ["personal"] });
  assert.equal(other.state, "offered");
  f.policy.pause("desktop", "manual", null);
  assert.equal(f.inspect(compound).state, "paused");
  const background = f.request("browser");
  assert.equal(background.state, "offered", "blocked compound task holds no partial resource");
  f.policy.approve(compound.intentId);
  f.policy.resume("desktop", "manual");
  assert.equal(f.inspect(compound).state, "announcing");
  assert.equal(f.inspect(background).state, "waiting_for_resource");
});

test("exact profile sets, object owner binding, idempotency and generation fences", () => {
  const f = fixture(), owner = f.policy.open();
  assert.throws(() => f.policy.submit({ ...owner }, {}), /owner_mismatch/);
  const wrong = f.request("browser", { profileIds: ["new-profile"] });
  assert.equal(wrong.terminalReason, "profile_not_approved");
  const intent = f.request("browser", { requestId: "same" });
  assert.equal(f.request("browser", { requestId: "same" }).intentId, intent.intentId);
  assert.throws(() => f.request("browser", { requestId: "same", durationMs: 20_000 }), /idempotency/);
  assert.throws(() => f.inspect(intent, owner), /owner_mismatch/);
  const active = f.activate(intent);
  assert.equal(f.policy.authorize(f.owner, { ...active, resourceGenerations: {} }), "stale_generation");
  f.policy.close(f.owner);
  assert.throws(() => f.policy.authorize(f.owner, active), /owner_mismatch/);
});

test("provider work completing after takeover cannot publish success or replay an effect", () => {
  const f = fixture(), intent = f.request(), active = f.activate(intent);
  const target = { counter: 0 };
  const dispatched = () => { ++target.counter; return () => f.policy.authorize(f.owner, active) === null ? "observed" : "unknown_after_dispatch"; };
  const completion = dispatched();
  f.policy.input("desktop", "scroll");
  assert.equal(completion(), "unknown_after_dispatch");
  assert.equal(target.counter, 1);
  f.advance(59_000); f.inspect(intent, f.owner, true); f.advance(1000);
  f.activate(intent);
  assert.equal(target.counter, 1, "new ownership performs no automatic replay");
});

test("health, liveness, notice rechecks and cancellation do not mint authority", () => {
  const f = fixture(), intent = f.request();
  f.policy.ready("desktop", false); f.advance(10_000);
  assert.equal(f.inspect(intent).state, "paused");
  f.policy.ready("desktop", true);
  assert.equal(f.inspect(intent).noticeRemainingSeconds, 10);
  f.policy.deny(intent.intentId);
  assert.equal(f.inspect(intent).terminalReason, "denied_by_person");
  const next = f.request(); f.advance(60_000);
  assert.equal(f.inspect(next).terminalReason, "queue_lease_expired");
  const active = f.activate(f.request()); f.advance(5000);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
});

test("configuration replacement and restart cannot restore tasks or old Ask approvals", () => {
  const f = fixture("ask"), intent = f.request();
  f.policy.approve(intent.intentId); f.activate(intent);
  f.policy.configure("desktop", { mode: "automatic", durationMs: null });
  assert.equal(f.inspect(intent).terminalReason, "consent_replaced");
  const fresh = new AccessAdmission({ now: () => 0 });
  assert.equal(fresh.status().surfaces.desktop.mode, "off");
  assert.equal(fresh.status().active, 0);
  assert.equal(fresh.nextDeadline(), null);
});

test("changing clients or surfaces cannot bypass a disruptive resource deferral", () => {
  const f = fixture(), first = f.request();
  f.policy.defer(first.intentId, 30_000);
  const other = f.policy.open();
  assert.equal(f.request("browser", { disruptive: true }, other).state, "paused");
  assert.equal(f.request("browser", { profileIds: ["personal"] }, other).state, "offered", "independent background work remains available");
  assert.equal(f.policy.status().deferrals.find(pause => pause.resource === "human-input").remainingSeconds, 30);
  f.policy.resume("desktop", "operator_deferral");
  assert.equal(f.inspect(first).state, "announcing");
});

test("deliberate takeover cooldown spans disruptive surfaces and preserves background owners", () => {
  const f = fixture(), active = f.activate(f.request());
  const background = f.activate(f.request("browser", { profileIds: ["personal"] }));
  f.policy.input("desktop", "button");
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  assert.equal(f.policy.authorize(f.owner, background), null);
  assert.equal(f.request("browser", { disruptive: true }).state, "paused");
  assert.equal(f.policy.status().handoffCooldownRemainingSeconds, 60);
});

test("an explicitly ready locked route skips an invisible warning but keeps impact reservations and Ask", () => {
  const f = fixture();
  f.policy.ready("desktop", true, false);
  const first = f.request();
  assert.equal(first.state, "offered");
  const active = f.activate(first);
  assert.ok(Object.hasOwn(active.resourceGenerations, "human-input"));
  const competing = f.request("browser", { disruptive: true });
  assert.equal(competing.state, "waiting_for_resource");
  f.policy.cancel(f.owner, competing.intentId);
  f.policy.configure("desktop", { mode: "ask", durationMs: null });
  assert.equal(f.request().state, "waiting_for_approval", "a locked native fact never supplies task approval");
});

test("production process inlet carries independent owners and negotiates v2 without restoring authority after EOF", async () => {
  const process = new ProcessClient(() => {}, () => {});
  await process.start();
  try {
    const call = (method, fields = {}) => process.call(`access.${method}`, fields);
    await call("configure", { surface: "desktop", configuration: { mode: "ask", durationMs: null } });
    await call("configure", { surface: "browser", configuration: { mode: "automatic", durationMs: null, profileIds: ["work"] } });
    for (const surface of ["desktop", "browser"]) await call("ready", { surface, ready: true });
    await call("input-ready", { ready: true });
    for (const owner of ["one", "two"]) await call("open", { owner });
    const request = { requestId: "task", surfaces: ["desktop"], disruptive: true, reason: "Process fixture", waitMs: 30_000, durationMs: 30_000 };
    const desktop = await call("submit", { owner: "one", request });
    assert.equal(desktop.state, "waiting_for_approval");
    const browser = await call("submit", { owner: "two", request: { ...request, surfaces: ["browser"], profileIds: ["work"], operations: ["browser.tabs"], disruptive: false } });
    assert.equal(browser.state, "offered");
    const active = await call("accept", { owner: "two", intentId: browser.intentId, offerGeneration: browser.offerGeneration });
    assert.equal((await call("authorize", { owner: "two", fence: active })).refusal, null);
    await assert.rejects(call("inspect", { owner: "one", intentId: browser.intentId }), /owner_mismatch/);
    await call("close", { owner: "two" });
    assert.equal((await call("state")).active, 0);
    await call("stop");
    assert.equal((await call("state")).surfaces.desktop.mode, "off");
  } finally { await process.close(); }
});

test("unknown human-input observation fences disruptive Browser but preserves background work", () => {
  const f = fixture();
  const active = f.activate(f.request("browser", { disruptive: true }));
  const background = f.activate(f.request("browser", { profileIds: ["personal"] }));
  f.policy.inputReady(false);
  assert.equal(f.policy.authorize(f.owner, active), "stale_control_session");
  assert.equal(f.policy.authorize(f.owner, background), null);
  const request = f.request("desktop");
  assert.ok(request.blockingReasons.includes("activity_unknown"));
  f.policy.inputReady(true);
  assert.equal(f.inspect(request).state, "waiting_for_resource", "restored readiness preserves resource arbitration");
  f.policy.cancel(f.owner, active.intentId);
  assert.equal(f.inspect(request).state, "announcing");
});

test("common authority enforces narrowed operations and surfaces", () => {
  const f = fixture(), active = f.activate(f.request("browser", { operations: ["browser.tabs"] }));
  assert.equal(f.policy.authorize(f.owner, active, "browser.tabs"), null);
  assert.equal(f.policy.authorize(f.owner, active, "browser.eval"), "operation_not_permitted_by_control_channel");
  assert.equal(f.policy.authorize(f.owner, active, "click"), "operation_not_permitted_by_control_channel");
  assert.equal(f.policy.authorize(f.owner, active, "capabilities"), null);
  assert.throws(() => f.request("browser", { operations: ["browser.eval"] }), /invalid_admission_impact/);
});

test("global and surface pauses, deferrals and cooldowns keep their own resume scope", () => {
  const f = fixture(), first = f.request();
  f.policy.pause("desktop", "manual", null);
  f.policy.pause("all", "manual", null);
  f.policy.resume("all", "manual");
  assert.equal(f.inspect(first).state, "paused", "global Resume preserves the independent surface pause");
  f.policy.resume("desktop", "manual");
  f.activate(first);
  f.policy.input("desktop", "key");
  f.policy.resume("browser", "physical_takeover");
  assert.equal(f.inspect(first).state, "paused", "Browser Resume cannot clear Desktop takeover");
  f.policy.defer(first.intentId, null);
  f.policy.resume("browser", "operator_deferral");
  f.policy.resume("desktop", "physical_takeover");
  assert.equal(f.inspect(first).state, "paused", "Browser Resume cannot clear Desktop deferral");
  f.policy.stop();
  f.policy.configure("desktop", { mode: "automatic", durationMs: null });
  assert.equal(f.request().state, "announcing", "Stop clears task deferrals before fresh consent");
});

test("admission emits closed transition metadata without request or page text", () => {
  const events = [], policy = new AccessAdmission({ now: () => 0 }, event => events.push(event));
  policy.configure("desktop", { mode: "ask", durationMs: null });
  policy.ready("desktop", true); policy.inputReady(true);
  const owner = policy.open(), intent = policy.submit(owner, { requestId: "private-request-id", surfaces: ["desktop"],
    disruptive: true, reason: "PRIVATE TASK AND PAGE CONTENT", waitMs: 300_000, durationMs: 120_000 });
  policy.approve(intent.intentId); policy.startNow(intent.intentId);
  const offer = policy.inspect(owner, intent.intentId), active = policy.accept(owner, intent.intentId, offer.offerGeneration);
  policy.input("desktop", "key"); policy.authorize(owner, active); policy.cancel(owner, intent.intentId);
  const names = events.map(event => event.event);
  for (const expected of ["requested", "waiting_for_approval", "approved", "announcing", "start_now", "offered", "active", "takeover", "yielded", "paused", "rejected", "ended"])
    assert.ok(names.includes(expected), expected);
  assert.equal(events.findLast(event => event.event === "ended").reason, "cancelled");
  assert.ok(!JSON.stringify(events).includes("PRIVATE"));
  assert.ok(!JSON.stringify(events).includes("private-request-id"));
});
