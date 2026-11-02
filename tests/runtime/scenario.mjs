import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { ResidentCore } from "../../runtime/src/core.ts";
import {
  ManualClock,
  ReferenceProvider,
} from "../../runtime/testing/reference-provider.ts";

export function finished(effects) {
  return effects
    .filter((effect) => effect.type === "request.finished")
    .map((effect) => effect.result);
}

export function queued(effects) {
  const commands = effects.filter(
    (effect) => effect.type === "provider.dispatch",
  );
  assert.equal(
    commands.length,
    1,
    "exactly one selected provider receives the request",
  );
  return commands[0].command;
}

export function click(provider, requestId, changes = {}) {
  return {
    requestId,
    profileId: provider.connection.profileId,
    reference: provider.reference(),
    timeoutMs: 1_000,
    ...changes,
  };
}

export function execute(core, provider, command) {
  const beginning = core.begin(command);
  assert.equal(beginning.started, true);
  assert.deepEqual(beginning.effects, []);
  // No await between the fresh dispatch check and submission to the provider.
  provider.execute(command);
}

/** Production policy, two stateful providers, independently observed counters. */
export function runScenario() {
  const clock = new ManualClock();
  const core = new ResidentCore(clock);
  const work = new ReferenceProvider(core.connect("work", "fixture.counter"));
  const personal = new ReferenceProvider(
    core.connect("personal", "fixture.counter"),
  );
  assert.deepEqual(core.inspect().connectedProfiles, ["work", "personal"]);
  const approval = core.approve([work.connection], 10_000).approval;

  const forbidden = finished(
    core.request(approval, click(personal, "unapproved")),
  );
  assert.equal(forbidden[0].errorCode, "profile_not_approved");
  assert.equal(personal.received.length, 0);

  const oldCommand = queued(core.request(approval, click(work, "click")));
  execute(core, work, oldCommand);
  assert.equal(
    work.readCounter(),
    1,
    "effect already happened before the held reply",
  );
  assert.equal(personal.readCounter(), 0, "the other profile was not affected");

  const stopped = core.stop();
  for (const effect of stopped) {
    if (effect.type === "provider.cancel") work.cancel(effect.command);
  }
  assert.deepEqual(work.cancelled, [oldCommand]);
  const interrupted = finished(stopped);
  assert.equal(interrupted.length, 1);
  assert.equal(interrupted[0].delivery, "unknown");
  assert.equal(interrupted[0].effect, "unknown");
  assert.deepEqual(core.inspect().approvedProfiles, []);
  assert.equal(
    work.readCounter(),
    1,
    "cancellation did not undo the page effect",
  );

  assert.deepEqual(core.disconnect(personal.connection), []);
  const reconnected = new ReferenceProvider(
    core.connect("personal", "fixture.counter"),
  );
  const freshApproval = core.approve([reconnected.connection], 10_000).approval;
  // Reuse the public request label deliberately: correlation is the exact
  // internal dispatch, not a public request/profile/generation string.
  const freshCommand = queued(
    core.request(freshApproval, click(reconnected, "click")),
  );
  execute(core, reconnected, freshCommand);

  const late = core.complete(
    work.connection,
    oldCommand,
    work.reply(oldCommand),
  );
  assert.equal(late.applied, false);
  assert.deepEqual(late.effects, []);
  assert.equal(
    core.inspect().pendingRequests,
    1,
    "late Work reply cannot complete Personal's request",
  );
  assert.deepEqual(core.inspect().approvedProfiles, ["personal"]);
  assert.equal(
    finished(core.request(approval, click(work, "stale-approval")))[0]
      .errorCode,
    "approval_required",
  );

  const completion = core.complete(
    reconnected.connection,
    freshCommand,
    reconnected.reply(freshCommand),
  );
  assert.equal(completion.applied, true);
  const success = finished(completion.effects)[0];
  assert.equal(success.accepted, true);
  assert.equal(success.delivery, "confirmed");
  assert.equal(
    success.effect,
    "unverifiable",
    "core does not claim the independent fixture oracle",
  );
  assert.equal(reconnected.readCounter(), 1);
  assert.equal(core.inspect().retainedRequests, 0);

  return {
    scenario: "two-providers-approval-action-stop-late-result",
    passed: true,
    independentEffects: {
      work: work.readCounter(),
      originalPersonal: personal.readCounter(),
      reconnectedPersonal: reconnected.readCounter(),
    },
    stoppedDelivery: interrupted[0].delivery,
    lateReplyApplied: late.applied,
    freshDelivery: success.delivery,
    freshEffectReportedByCore: success.effect,
    retainedRequests: core.inspect().retainedRequests,
  };
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  process.stdout.write(JSON.stringify(runScenario(), null, 2) + "\n");
}
