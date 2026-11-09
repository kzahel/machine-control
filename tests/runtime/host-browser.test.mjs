import test from "node:test";
import assert from "node:assert/strict";
import { PolicyHost } from "../../runtime/node/policy-host.ts";
import { ReferenceBrowser } from "../../runtime/testing/reference-browser.ts";

test(
  "production host uses profile identity, exact selection and shared reference effects",
  { timeout: 5000 },
  async () => {
    const replies = new Map(),
      providers = new Map(),
      forwarded = [];
    let sequence = 0;
    const host = new PolicyHost((message) => {
      if (message.type === "reply") {
        const pending = replies.get(message.id);
        replies.delete(message.id);
        if (message.ok) pending?.resolve(message.data);
        else pending?.reject(new Error(message.errorCode));
      } else if (message.type === "native.check") {
        queueMicrotask(
          () =>
            void call("native.reply", {
              nativeId: message.nativeId,
              accepted: true,
            }),
        );
      } else if (
        message.type === "provider.send" &&
        message.frame.type === "request"
      ) {
        const provider = providers.get(message.connectionId);
        forwarded.push(message.frame);
        const command = {
          connection: provider.connection,
          operation: message.frame.operation,
          params: message.frame.params,
          requestId: message.frame.id,
          authorizationGeneration: 0,
        };
        provider.execute(command);
        const reply = provider.reply(command);
        queueMicrotask(
          () =>
            void call("provider.frame", {
              connectionId: message.connectionId,
              frame: { type: "response", id: message.frame.id, ...reply },
            }),
        );
      }
    });
    function call(method, fields = {}) {
      const id = `rpc-${++sequence}`;
      return new Promise((resolve, reject) => {
        replies.set(id, { resolve, reject });
        host.receive({ id, method, ...fields });
      });
    }
    try {
      await call("hello", { protocolVersion: 2 });
      const attach = async (name, suffix) => {
        const metadata = {
          protocolVersion: 1,
          installationId: `00000000-0000-4000-8000-00000000000${suffix}`,
          name,
          enabled: true,
        };
        const data = await call("browser.attach", {
          extensionId: "a".repeat(32),
          hello: {
            protocolVersion: 1,
            extensionVersion: "fixture",
            profile: metadata,
          },
        });
        providers.set(
          data.connectionId,
          new ReferenceBrowser({
            profileId: data.profileId,
            generation: data.generation,
            route: "fixture.browser",
          }),
        );
        return { ...data, metadata };
      };
      const work = await attach("Work profile", 1),
        personal = await attach("Personal profile", 2);
      await assert.rejects(attach("Copied", 1), /profile_conflict/);
      let ownerSession = "fixture-owner-1";
      let ownerProfiles;
      const request = (operation, fields = {}) =>
        call("browser.call", {
          requestId: `action-${++sequence}`,
          authorityId: "fixture-native-owner",
          ownerSession,
          ownerProfileIds: ownerProfiles ?? host.core.inspect().selectedProfiles,
          request: { operation, ...fields },
        });
      await call("operator.configure", {
        scopes: ["browser"],
        profileIds: [work.profileId],
        durationMs: null,
      });
      assert.equal((await request("browser.tabs")).accepted, true);
      // Claim attribution passes to the extension unchanged; malformed
      // ownership is refused before dispatch.
      const owner = { claimId: `c-${"a1".repeat(12)}`, leaseSeconds: 600, sessionRef: "fixture-session" };
      const dispatched = forwarded.length;
      assert.equal((await request("browser.tabs", { owner })).accepted, true);
      assert.deepEqual({ ...forwarded.at(-1).params.owner }, owner);
      for (const invalid of [
        { ...owner, leaseSeconds: 0 },
        { ...owner, leaseSeconds: 1.5 },
        { ...owner, claimId: "c-short" },
        { ...owner, sessionRef: "has space" },
        { ...owner, label: "extra" },
        "c-not-an-object",
      ]) {
        const refused = await request("browser.tabs", { owner: invalid });
        assert.equal(refused.errorCode, "invalid_request");
        assert.equal(refused.retrySafety, "safe_not_dispatched");
      }
      assert.equal((await request("browser.tabs", { ownerClaimId: owner.claimId })).errorCode, "invalid_request",
        "only release is scoped to a claim");
      assert.equal((await request("browser.endpoint", { owner: "c-not-an-object" })).errorCode, "invalid_request",
        "the endpoint route validates ownership too");
      assert.equal((await request("browser.release", { ownerClaimId: "c-short" })).errorCode, "invalid_request");
      assert.equal(forwarded.length, dispatched + 1, "refused ownership is never dispatched");
      assert.equal((await request("browser.release", { ownerClaimId: owner.claimId })).accepted, true);
      assert.equal(forwarded.at(-1).params.ownerClaimId, owner.claimId);
      assert.equal((await request("browser.tabs", { owner: null, ownerClaimId: null })).accepted, true,
        "null means absent, matching the typed Windows relay");
      const snap = await request("browser.snapshot", {
        browserProfileId: "Work profile",
        tabId: 1,
      });
      const reference = snap.data.elements[0].reference;
      assert.equal(
        (await request("browser.click", { reference })).accepted,
        true,
      );
      assert.equal(providers.get(work.connectionId).observe().clicks, 1);
      assert.equal(providers.get(personal.connectionId).observe().clicks, 0);
      ownerSession = "fixture-owner-2";
      assert.equal((await request("browser.click", { reference })).errorCode, "stale_reference", "a new owner cannot reuse the previous owner's observation");
      assert.equal(providers.get(work.connectionId).observe().clicks, 1);
      ownerSession = "fixture-owner-1";
      assert.equal(
        (await request("browser.eval")).errorCode,
        "scope_not_approved",
      );
      await call("operator.configure", {
        scopes: ["browser", "devtools"],
        profileIds: [work.profileId, personal.profileId],
        durationMs: 60_000,
      });
      ownerProfiles = [work.profileId];
      await assert.rejects(request("browser.tabs", { browserProfileId: personal.profileId }), /profile_not_permitted_by_control_channel/);
      ownerProfiles = undefined;
      await assert.rejects(request("browser.tabs"), /browser_profile_required/);
      assert.equal(
        (
          await request("browser.click", {
            browserProfileId: personal.profileId,
            reference,
          })
        ).errorCode,
        "stale_reference",
      );
      assert.equal(
        (
          await request("browser.eval", {
            browserProfileId: personal.profileId,
          })
        ).accepted,
        true,
      );
      await call("provider.frame", {
        connectionId: work.connectionId,
        frame: {
          type: "profile.update",
          profile: { ...work.metadata, enabled: false },
        },
      });
      assert.equal(
        (await request("browser.tabs")).profileId,
        personal.profileId,
      );
      await call("provider.frame", {
        connectionId: work.connectionId,
        frame: { type: "profile.update", profile: work.metadata },
      });
      assert.equal(
        (await request("browser.tabs")).profileId,
        personal.profileId,
        "re-enable cannot restore withdrawn approval",
      );
      await call("operator.configure", { scopes: ["browser", "devtools"], profileIds: [work.profileId, personal.profileId], durationMs: 60_000 });
      const checkpoint = await call("operator.checkpoint");
      await call("operator.configure", { scopes: [], profileIds: [], durationMs: 1000 });
      await assert.rejects(request("browser.tabs"), /approval_required/);
      await call("provider.frame", { connectionId: personal.connectionId, frame: { type: "profile.update", profile: { ...personal.metadata, enabled: false } } });
      await call("provider.frame", { connectionId: personal.connectionId, frame: { type: "profile.update", profile: personal.metadata } });
      await call("operator.restore", checkpoint);
      assert.equal((await request("browser.tabs")).profileId, work.profileId);
      await assert.rejects(request("browser.tabs", { browserProfileId: personal.profileId }), /profile_not_permitted_by_control_channel/, "restoration cannot undo withdrawal");
      const stoppedCheckpoint = await call("operator.checkpoint");
      await call("operator.stop");
      await assert.rejects(call("operator.restore", stoppedCheckpoint), /invalid_checkpoint/);
      await assert.rejects(request("browser.tabs"), /approval_required/);
    } finally {
      host.close();
    }
  },
);
