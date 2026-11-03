import test from "node:test";
import assert from "node:assert/strict";
import { ResidentCore } from "../../runtime/src/core.ts";
import { Profiles } from "../../runtime/src/profiles.ts";
import { Streams } from "../../runtime/src/streams.ts";
import { ManualClock } from "../../runtime/testing/reference-provider.ts";
import { ReferenceBrowser } from "../../runtime/testing/reference-browser.ts";
import { dispatchToProvider } from "../../runtime/src/provider-dispatch.ts";

function setup(devtools = false) {
  const clock = new ManualClock(),
    core = new ResidentCore(clock);
  const work = new ReferenceBrowser(core.connect("work", "fixture.browser"));
  const personal = new ReferenceBrowser(
    core.connect("personal", "fixture.browser"),
  );
  const approval = core.approve([work.connection, personal.connection], null, {
    devtools,
  }).approval;
  let id = 0;
  function call(provider, operation, params = {}) {
    const effects = core.request(approval, {
      requestId: `request-${++id}`,
      profileId: provider.connection.profileId,
      connection: provider.connection,
      operation,
      params,
      timeoutMs: 1000,
    });
    const command = effects.find(
      (effect) => effect.type === "provider.dispatch",
    )?.command;
    if (!command)
      return effects.find((effect) => effect.type === "request.finished")
        .result;
    dispatchToProvider(core, provider, command, () => {});
    return core
      .complete(provider.connection, command, provider.reply(command))
      .effects.find((effect) => effect.type === "request.finished").result;
  }
  return { clock, core, work, personal, approval, call };
}

test("reference browser implements ordinary effects behind the same policy", () => {
  const f = setup();
  assert.equal(
    f.call(f.work, "browser.navigate", {
      tabId: 1,
      url: "https://fixture.invalid/",
    }).accepted,
    true,
  );
  const snap = f.call(f.work, "browser.snapshot", { tabId: 1 }).data;
  f.call(f.work, "browser.click", { reference: snap.elements[0].reference });
  f.call(f.work, "browser.type", {
    reference: snap.elements[1].reference,
    text: "fixture message",
  });
  f.call(f.work, "browser.key", { tabId: 1, key: "Enter" });
  f.call(f.work, "browser.upload", { tabId: 1, files: ["fixture.txt"] });
  assert.equal(f.work.observe().clicks, 1);
  assert.equal(f.work.observe().saved, "fixture message");
  assert.deepEqual(f.work.observe().uploads, ["fixture.txt"]);
  assert.equal(f.personal.observe().clicks, 0);
  assert.equal(f.call(f.work, "browser.wait", { tabId: 1 }).data.ready, true);
  assert.deepEqual(
    f.call(f.work, "browser.capture", { tabId: 1 }).data.fixturePixels,
    [1, 15, 1],
  );
  assert.equal(
    f.call(f.work, "browser.dialog", { tabId: 1 }).data.dialog,
    null,
  );
  f.call(f.work, "browser.release", { tabId: 1 });
  assert.equal(
    f.call(f.work, "browser.click", { reference: snap.elements[0].reference })
      .delivery,
    "refused",
  );
  assert.equal(
    f.call(f.work, "browser.eval", {}).errorCode,
    "scope_not_approved",
  );
});

test("indefinite consent, native safety ceilings and profile withdrawal compose", () => {
  const f = setup(true);
  f.clock.advance(100_000_000);
  assert.equal(f.call(f.work, "browser.eval", {}).accepted, true);
  const workFence = f.core.fence(f.approval, f.work.connection, "browser.cdp");
  const personalFence = f.core.fence(
    f.approval,
    f.personal.connection,
    "browser.cdp",
  );
  f.core.withdraw(f.work.connection);
  assert.equal(f.core.validFence(workFence, "browser.cdp"), false);
  assert.equal(f.core.validFence(personalFence, "browser.cdp"), true);
  assert.equal(
    f.call(f.work, "browser.tabs").errorCode,
    "profile_not_approved",
  );
  f.core.availability(true, false, "prompt");
  assert.equal(f.call(f.personal, "browser.tabs").accepted, true);
  assert.equal(f.call(f.personal, "browser.eval").errorCode, "access_paused");
  f.core.availability(true, true, "resumed");
  assert.equal(f.core.validFence(personalFence, "browser.cdp"), false);
  assert.equal(f.call(f.personal, "browser.cdp").accepted, true);
  assert.equal(
    f.call(f.work, "browser.tabs").errorCode,
    "profile_not_approved",
  );
});

test("endpoint and stream policy scopes numeric tab collisions and late results", () => {
  const f = setup(true),
    streams = new Streams(f.core, f.clock);
  const endpoint = (provider, token) =>
    streams.endpoint(
      f.core.fence(f.approval, provider.connection, "browser.cdp"),
      "native-owner",
      token.repeat(64),
    );
  const work = endpoint(f.work, "a"),
    personal = endpoint(f.personal, "b");
  assert.equal(streams.lookup("a".repeat(64)), work);
  const ws = streams.open(work, 7, "work-stream"),
    ps = streams.open(personal, 7, "personal-stream");
  assert.throws(() => streams.open(work, 7, "duplicate"), /capacity/);
  assert.equal(streams.opened(ws), true);
  assert.equal(streams.opened(ps), true);
  streams.command(ws, 1, "child-session");
  assert.equal(streams.complete(ws, 1, "foreign-session"), false);
  assert.equal(streams.complete(ps, 1, "child-session"), false);
  assert.equal(streams.complete(ws, 1, "child-session"), true);
  assert.equal(streams.active({ ...ws }), false);
  streams.command(ps, 2);
  f.clock.advance(45_000);
  assert.deepEqual(streams.sweep(), [ps]);
  assert.equal(streams.complete(ps, 2), false);
  f.core.stop();
  assert.deepEqual(streams.sweep(), [ws]);
  assert.equal(streams.lookup("a".repeat(64)), undefined);
});

test("profiles retain exact offline selection and reject copied live identity", () => {
  const profiles = new Profiles(),
    f = setup();
  const extension = "a".repeat(32);
  const metadata = (id, name = "Work") => ({
    protocolVersion: 1,
    installationId: id,
    name,
    enabled: true,
  });
  const workId = "00000000-0000-4000-8000-000000000001",
    personalId = "00000000-0000-4000-8000-000000000002";
  const work = profiles.announce(extension, metadata(workId));
  work.connection = f.work.connection;
  const personal = profiles.announce(extension, metadata(personalId));
  personal.connection = f.personal.connection;
  assert.throws(
    () => profiles.announce(extension, metadata(workId)),
    /conflict/,
  );
  assert.throws(() => profiles.select("Work", []), /ambiguous/);
  assert.equal(profiles.select(undefined, [work.profileId]), work);
  profiles.disconnected(work, work.connection);
  assert.throws(
    () => profiles.select(undefined, [work.profileId]),
    /unavailable/,
  );
  assert.throws(
    () => profiles.select(undefined, [work.profileId, personal.profileId]),
    /required/,
  );
  assert.throws(
    () => profiles.update(personal, metadata(workId)),
    /identity_changed/,
  );
  assert.equal(profiles.get(work.profileId), work);
  assert.equal(profiles.get(personal.profileId), personal);
});

test("transport retirement releases bounded correlation without rewriting uncertainty", () => {
  const f = setup();
  const command = f.core.request(f.approval, {
    requestId: "held",
    profileId: "work",
    connection: f.work.connection,
    operation: "browser.navigate",
    params: { tabId: 1, url: "https://fixture.invalid/" },
    timeoutMs: 1000,
  })[0].command;
  dispatchToProvider(f.core, f.work, command, () => {});
  assert.throws(() => f.core.retire(f.work.connection));
  const result = f.core
    .disconnect(f.work.connection)
    .find((effect) => effect.type === "request.finished").result;
  assert.equal(result.delivery, "unknown");
  f.core.retire(f.work.connection);
  assert.equal(f.core.inspect().retainedRequests, 0);
  assert.equal(
    f.core.complete(f.work.connection, command, f.work.reply(command)).applied,
    false,
  );
  assert.equal(result.delivery, "unknown");
});
