import assert from "node:assert/strict";
import { test } from "node:test";
import { CoreError, ResidentCore } from "../../runtime/src/core.ts";
import {
  ManualClock,
  ReferenceProvider,
} from "../../runtime/testing/reference-provider.ts";
import { click, execute, finished, queued, runScenario } from "./scenario.mjs";

function fixture(limits) {
  const clock = new ManualClock();
  const core = new ResidentCore(clock, limits);
  const work = new ReferenceProvider(core.connect("work", "fixture.counter"));
  const personal = new ReferenceProvider(
    core.connect("personal", "fixture.counter"),
  );
  return { clock, core, work, personal };
}

function rejects(code) {
  return (error) => error instanceof CoreError && error.code === code;
}

test("motivating scenario uses shared policy and independent stateful effects", () => {
  const result = runScenario();
  assert.equal(result.passed, true);
  assert.deepEqual(result.independentEffects, {
    work: 1,
    originalPersonal: 0,
    reconnectedPersonal: 1,
  });
});

test("two approved providers stay connected and operate independently", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve(
    [work.connection, personal.connection],
    10_000,
  );
  for (const [index, provider] of [work, personal, work].entries()) {
    const command = queued(
      core.request(approval, click(provider, `click-${index}`)),
    );
    execute(core, provider, command);
    const { applied, effects } = core.complete(
      provider.connection,
      command,
      provider.reply(command),
    );
    assert.equal(applied, true);
    assert.equal(finished(effects)[0].profileId, provider.connection.profileId);
  }
  assert.equal(work.readCounter(), 2);
  assert.equal(personal.readCounter(), 1);
  assert.deepEqual(core.inspect().connectedProfiles, ["work", "personal"]);
  assert.equal(core.inspect().retainedRequests, 0);
});

test("Stop fences queued work before dispatch without uncertain delivery", () => {
  const { core, work } = fixture();
  const { approval } = core.approve([work.connection], 10_000);
  const command = queued(core.request(approval, click(work, "queued")));
  const stopped = core.stop();
  assert.equal(
    stopped.some((effect) => effect.type === "provider.cancel"),
    false,
  );
  const result = finished(stopped)[0];
  assert.equal(result.delivery, "refused");
  assert.equal(result.retrySafety, "safe_not_dispatched");
  assert.equal(core.begin(command).started, false);
  assert.equal(work.readCounter(), 0);
  assert.equal(core.inspect().retainedRequests, 0);
  assert.deepEqual(core.stop(), []);
});

test("queued request snapshots are immutable and cannot change target or authority", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve([work.connection], 10_000);
  const request = click(work, "snapshot");
  const command = queued(core.request(approval, request));
  request.profileId = "personal";
  request.reference = personal.reference();
  assert.throws(() => {
    command.target = "different";
  }, TypeError);
  assert.throws(() => {
    approval.profiles.push("personal");
  }, TypeError);
  assert.throws(() => {
    work.connection.generation = 99;
  }, TypeError);
  execute(core, work, command);
  assert.equal(work.readCounter(), 1);
  assert.equal(personal.readCounter(), 0);
  assert.equal(
    core.begin(command).started,
    false,
    "the same dispatch cannot run twice",
  );
});

test("public handle copies and foreign replies cannot supply authority or release capacity", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve([work.connection], 10_000);
  assert.throws(
    () => core.approve([{ ...work.connection }], 100),
    rejects("invalid_request"),
  );
  assert.equal(
    finished(core.request({ ...approval }, click(work, "forged")))[0].errorCode,
    "approval_required",
  );
  const command = queued(core.request(approval, click(work, "genuine")));
  assert.equal(core.begin({ ...command }).started, false);
  assert.equal(
    core.complete(work.connection, command, { ok: true }).applied,
    false,
    "a queued request cannot complete",
  );
  execute(core, work, command);
  for (const [connection, candidate] of [
    [personal.connection, command],
    [{ ...work.connection }, command],
    [work.connection, { ...command }],
  ]) {
    assert.equal(
      core.complete(connection, candidate, { ok: true }).applied,
      false,
    );
    assert.equal(core.inspect().unsettledDispatches, 1);
    assert.equal(core.inspect().pendingRequests, 1);
  }
  const reply = work.reply(command);
  assert.equal(core.complete(work.connection, command, reply).applied, true);
  assert.equal(core.complete(work.connection, command, reply).applied, false);
  assert.equal(core.inspect().retainedRequests, 0);
});

test("matching public IDs from another runtime are not current handles", () => {
  const first = fixture();
  const second = fixture();
  const { approval } = first.core.approve([first.work.connection], 1_000);
  const other = second.core.approve([second.work.connection], 1_000).approval;
  assert.deepEqual(approval, other);
  assert.equal(
    finished(first.core.request(other, click(first.work, "foreign-runtime")))[0]
      .errorCode,
    "approval_required",
  );
  assert.equal(
    finished(
      first.core.request(approval, click(second.work, "foreign-reference")),
    )[0].errorCode,
    "stale_reference",
  );
});

test("profile references cannot cross routes even when both profiles are approved", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve(
    [work.connection, personal.connection],
    1_000,
  );
  const effects = core.request(
    approval,
    click(work, "foreign-reference", { reference: personal.reference() }),
  );
  assert.equal(finished(effects)[0].errorCode, "stale_reference");
  assert.equal(
    effects.some((effect) => effect.type === "provider.dispatch"),
    false,
  );
  assert.equal(work.readCounter() + personal.readCounter(), 0);
});

test("an additional connection cannot expand an approval or replace an incumbent", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve([work.connection], 1_000);
  const third = new ReferenceProvider(core.connect("third", "fixture.counter"));
  assert.throws(
    () => core.connect("work", "fixture.other"),
    rejects("profile_conflict"),
  );
  assert.deepEqual(core.inspect().connectedProfiles, [
    "work",
    "personal",
    "third",
  ]);
  assert.equal(
    finished(core.request(approval, click(third, "unapproved")))[0].errorCode,
    "profile_not_approved",
  );
  assert.deepEqual(core.inspect().approvedProfiles, ["work"]);
  const command = queued(core.request(approval, click(work, "incumbent")));
  execute(core, work, command);
  assert.equal(work.readCounter(), 1);
  assert.equal(personal.readCounter() + third.readCounter(), 0);
});

test("disconnect is profile-local, never fails over, and fences stale connections", () => {
  const { core, work, personal } = fixture();
  const { approval } = core.approve(
    [work.connection, personal.connection],
    1_000,
  );
  const workCommand = queued(
    core.request(approval, click(work, "work-pending")),
  );
  execute(core, work, workCommand);
  const personalCommand = queued(
    core.request(approval, click(personal, "personal-pending")),
  );
  const disconnected = finished(core.disconnect(work.connection));
  assert.equal(disconnected.length, 1);
  assert.equal(disconnected[0].errorCode, "provider_disconnected");
  assert.equal(disconnected[0].delivery, "unknown");
  assert.equal(
    finished(core.request(approval, click(work, "offline")))[0].errorCode,
    "profile_unavailable",
  );
  const replacement = new ReferenceProvider(
    core.connect("work", "fixture.counter"),
  );
  assert.notEqual(
    replacement.connection.generation,
    work.connection.generation,
  );
  assert.deepEqual(
    core.disconnect(work.connection),
    [],
    "old disconnect cannot remove the replacement",
  );
  assert.equal(
    finished(core.request(approval, click(work, "old-reference")))[0].errorCode,
    "stale_reference",
  );
  assert.equal(
    core.complete(work.connection, workCommand, work.reply(workCommand))
      .applied,
    false,
  );
  execute(core, personal, personalCommand);
  assert.equal(personal.readCounter(), 1);
  const newCommand = queued(
    core.request(approval, click(replacement, "fresh-reference")),
  );
  execute(core, replacement, newCommand);
  assert.equal(
    replacement.readCounter(),
    1,
    "remaining exact-profile approval permits fresh work",
  );
});

test("reapproval invalidates both queued and dispatched old work", () => {
  const { core, work, personal } = fixture();
  const old = core.approve([work.connection], 1_000).approval;
  const dispatched = queued(core.request(old, click(work, "sent")));
  execute(core, work, dispatched);
  const waiting = queued(core.request(old, click(work, "waiting")));
  const { approval, effects } = core.approve([personal.connection], 1_000);
  const results = finished(effects);
  assert.deepEqual(
    results.map((result) => result.errorCode),
    ["approval_replaced", "approval_replaced"],
  );
  assert.deepEqual(
    results.map((result) => result.delivery),
    ["unknown", "refused"],
  );
  assert.equal(core.begin(waiting).started, false);
  assert.equal(
    core.complete(work.connection, dispatched, work.reply(dispatched)).applied,
    false,
  );
  assert.equal(
    finished(core.request(old, click(work, "old")))[0].errorCode,
    "approval_required",
  );
  assert.equal(
    finished(core.request(approval, click(work, "new-wrong-profile")))[0]
      .errorCode,
    "profile_not_approved",
  );
});

test("approval expires at the exact boundary even if the provider replies successfully", () => {
  const { clock, core, work } = fixture();
  const { approval } = core.approve([work.connection], 10);
  const command = queued(core.request(approval, click(work, "expiry")));
  execute(core, work, command);
  clock.advance(10);
  const late = core.complete(work.connection, command, work.reply(command));
  assert.equal(late.applied, false);
  assert.equal(finished(late.effects)[0].errorCode, "approval_expired");
  assert.equal(finished(late.effects)[0].delivery, "unknown");
  assert.deepEqual(core.inspect().approvedProfiles, []);
  assert.deepEqual(core.tick(), []);
  assert.equal(work.readCounter(), 1);
  assert.equal(core.inspect().retainedRequests, 0);
});

test("dispatch checks expiry again after enqueue, before any effect", () => {
  const { clock, core, work } = fixture();
  const { approval } = core.approve([work.connection], 10);
  const command = queued(core.request(approval, click(work, "queued-expiry")));
  clock.advance(10);
  const start = core.begin(command);
  assert.equal(start.started, false);
  assert.equal(finished(start.effects)[0].errorCode, "approval_expired");
  assert.equal(finished(start.effects)[0].delivery, "refused");
  assert.equal(work.readCounter(), 0);
});

test("request deadlines distinguish queued and dispatched work without sleeps", () => {
  const { clock, core, work } = fixture();
  const { approval } = core.approve([work.connection], 10_000);
  const sent = queued(
    core.request(approval, click(work, "sent-timeout", { timeoutMs: 20 })),
  );
  execute(core, work, sent);
  const waiting = queued(
    core.request(approval, click(work, "queued-timeout", { timeoutMs: 20 })),
  );
  clock.advance(19);
  assert.deepEqual(core.tick(), []);
  clock.advance(1);
  const results = finished(core.tick());
  assert.deepEqual(
    results.map((result) => result.delivery),
    ["unknown", "refused"],
  );
  assert.equal(
    results.every((result) => result.errorCode === "request_timeout"),
    true,
  );
  assert.equal(core.begin(waiting).started, false);
  assert.deepEqual(core.tick(), []);
  const late = core.complete(work.connection, sent, work.reply(sent));
  assert.equal(late.applied, false);
  assert.deepEqual(late.effects, []);
  assert.equal(core.inspect().retainedRequests, 0);
});

test("Stop cannot free physical capacity until the exact outstanding callback settles", () => {
  const { core, work, personal } = fixture({ requests: 1 });
  const old = core.approve([work.connection], 1_000).approval;
  const command = queued(core.request(old, click(work, "held")));
  execute(core, work, command);
  core.stop();
  assert.equal(core.inspect().pendingRequests, 0);
  assert.equal(core.inspect().retainedRequests, 1);
  const fresh = core.approve([personal.connection], 1_000).approval;
  assert.equal(
    finished(core.request(fresh, click(personal, "blocked")))[0].errorCode,
    "capacity_exceeded",
  );
  assert.equal(
    core.complete(personal.connection, command, { ok: true }).applied,
    false,
  );
  assert.equal(core.inspect().retainedRequests, 1);
  assert.equal(
    core.complete(work.connection, command, work.reply(command)).applied,
    false,
  );
  assert.equal(core.inspect().retainedRequests, 0);
  const next = queued(core.request(fresh, click(personal, "after-settlement")));
  execute(core, personal, next);
  assert.equal(personal.readCounter(), 1);
});

test("capacity and active request-label conflicts refuse without disturbing existing work", () => {
  const { core, work } = fixture({ providers: 2, requests: 1 });
  assert.throws(
    () => core.connect("third", "fixture.counter"),
    rejects("capacity_exceeded"),
  );
  const { approval } = core.approve([work.connection], 1_000);
  const command = queued(core.request(approval, click(work, "one")));
  assert.equal(
    finished(core.request(approval, click(work, "one")))[0].errorCode,
    "request_conflict",
  );
  assert.equal(
    finished(core.request(approval, click(work, "two")))[0].errorCode,
    "capacity_exceeded",
  );
  assert.equal(core.inspect().pendingRequests, 1);
  execute(core, work, command);
  assert.equal(
    core.complete(work.connection, command, work.reply(command)).applied,
    true,
  );
  assert.equal(core.inspect().retainedRequests, 0);
});

test("provider refusal and uncertain failure preserve delivery distinctions", () => {
  for (const delivery of ["refused", "unknown"]) {
    const { core, work } = fixture();
    const { approval } = core.approve([work.connection], 1_000);
    const command = queued(
      core.request(approval, click(work, "provider-failure")),
    );
    assert.equal(core.begin(command).started, true);
    const result = finished(
      core.complete(work.connection, command, { ok: false, delivery }).effects,
    )[0];
    assert.equal(result.accepted, false);
    assert.equal(result.errorCode, "provider_failed");
    assert.equal(result.delivery, delivery);
    assert.equal(result.effect, delivery === "refused" ? "refused" : "unknown");
  }
});

test("malformed boundaries and non-monotonic time never dispatch work", () => {
  const { clock, core, work } = fixture();
  const { approval } = core.approve([work.connection], 1_000);
  for (const timeoutMs of [0, -1, 1.5, NaN, Infinity, true, 45_001]) {
    assert.throws(
      () => core.request(approval, click(work, "invalid", { timeoutMs })),
      rejects("invalid_request"),
    );
  }
  assert.throws(() => core.approve([], 1_000), rejects("invalid_request"));
  assert.throws(
    () => core.approve([work.connection, work.connection], 1_000),
    rejects("invalid_request"),
  );
  assert.throws(
    () => core.approve([work.connection], Infinity),
    rejects("invalid_request"),
  );
  assert.throws(
    () => core.connect("", "fixture.counter"),
    rejects("invalid_request"),
  );
  assert.throws(() => clock.advance(-1));
  assert.equal(core.inspect().retainedRequests, 0);
  assert.equal(work.readCounter(), 0);
  let now = 5;
  const invalidClock = new ResidentCore({ now: () => now });
  now = 4;
  assert.throws(() => invalidClock.tick(), rejects("clock_invalid"));
  assert.throws(
    () => new ResidentCore({ now: () => NaN }),
    rejects("clock_invalid"),
  );
});
