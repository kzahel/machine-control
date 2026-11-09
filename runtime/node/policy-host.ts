import { CdpBridge } from "./cdp.ts";
import { Profiles } from "../src/profiles.ts";
import type { Profile } from "../src/profiles.ts";
import { Streams } from "../src/streams.ts";
import { parameters, validOwnership } from "../src/browser-contract.ts";
import type { BrowserOperation } from "../src/browser-contract.ts";
/** Inherited, trusted-native-host channel. Never expose this inlet to agents. */
import { randomUUID } from "node:crypto";
import { performance } from "node:perf_hooks";
import { ResidentCore, CoreError } from "../src/core.ts";
import type { Approval, ApprovalCheckpoint, BrowserRequest, Effect } from "../src/core.ts";
import type { Clock } from "../src/core.ts";
import { ExtensionProvider } from "../src/extension-provider.ts";
import type { NativeFrame } from "../src/extension-provider.ts";
import { dispatchToProvider } from "../src/provider-dispatch.ts";
import { AccessAdmission, backgroundOperations } from "../src/admission.ts";
import type { AdmissionOwner, AdmissionRequest, Surface, SurfaceConfiguration, SessionFence, HumanInput, AccessPreferences } from "../src/admission.ts";

function string(value: unknown): string {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(value))
    throw new Error("invalid_host_request");
  return value;
}

function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value))
    throw new Error("invalid_host_request");
  return value;
}

function object(value: unknown): NativeFrame {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid_host_request");
  return value as NativeFrame;
}

/**
 * One serialized owner of policy and runtime-local handles. The parent must
 * authenticate operator/provider inputs, enforce caller admission and close
 * all provider routes if this process dies. No listener or bearer authority.
 * This is an integration boundary under qualification, not installed yet.
 */
export class PolicyHost {
  readonly bootId = randomUUID();
  readonly core = new ResidentCore({
    now: () => Math.floor(performance.now()),
  });
  readonly access: AccessAdmission;
  readonly #accessOwners = new Map<string, AdmissionOwner>();
  readonly #send: (frame: NativeFrame) => void;
  readonly #providers = new Map<string, ExtensionProvider>();
  readonly #retired = new Set<string>();
  readonly #profiles = new Profiles();
  readonly #profileConnections = new Map<string, Profile>();
  readonly #transportTags = new Map<string, string>();
  readonly #waiters = new Map<string, (value: unknown) => void>();
  readonly #requestAuthorities = new Map<string, string>();
  readonly #requestOwners = new Map<string, string>();
  readonly #nativeWaiters = new Map<string, (accepted: boolean) => void>();
  readonly #streams = new Streams(this.core, {
    now: () => Math.floor(performance.now()),
  });
  #cdp: CdpBridge | undefined;
  #published = "";
  #approval: Approval | undefined;
  readonly #checkpoints = new Map<string, ApprovalCheckpoint>();
  #hello = false;
  #sequence = 0;
  #closed = false;

  constructor(send: (frame: NativeFrame) => void, admissionClock: Clock = { now: () => Math.floor(performance.now()) }) {
    this.#send = send;
    this.access = new AccessAdmission(admissionClock, event => this.#send({ type: "access.event", ...event }));
  }

  receive(frame: NativeFrame): void {
    if (this.#closed) throw new Error("host_closed");
    const id = string(frame.id);
    try {
      if (!this.#hello && frame.method !== "hello")
        throw new Error("host_handshake_required");
      const data = this.#invoke(frame);
      this.#publish();
      if (data instanceof Promise) {
        void data
          .then((result: unknown) => {
            if (!this.#closed)
              this.#send({ type: "reply", id, ok: true, data: result });
          })
          .catch((error: unknown) => {
            if (!this.#closed)
              this.#send({
                type: "reply",
                id,
                ok: false,
                errorCode: this.#error(error),
              });
          });
      } else this.#send({ type: "reply", id, ok: true, data });
    } catch (error) {
      // Never reflect input or stack/page data into diagnostics.
      const code = this.#error(error);
      this.#send({ type: "reply", id, ok: false, errorCode: code });
    }
  }

  tick(): void {
    if (this.#closed || !this.#hello) return;
    this.#consume(this.core.tick());
    this.access.tick();
    this.#synchronize();
    this.#publish();
  }

  wakeInMs(): number | null {
    const deadlines = [this.core.nextDeadline(), this.access.nextDeadline()].filter((value): value is number => value !== null);
    const deadline = deadlines.length ? Math.min(...deadlines) : null;
    return deadline === null
      ? null
      : Math.max(1, deadline - Math.floor(performance.now()));
  }

  close(): void {
    if (this.#closed) return;
    // Revoke before native cleanup. EOF never restores or serializes consent.
    this.#consume(this.core.stop());
    this.access.stop();
    this.#accessOwners.clear();
    this.#approval = undefined;
    this.#synchronize();
    this.#cdp?.close();
    this.#closed = true;
    for (const resolve of this.#nativeWaiters.values()) resolve(false);
    this.#nativeWaiters.clear();
    this.#providers.clear();
  }

  #provider(value: unknown): ExtensionProvider {
    const provider = this.#providers.get(string(value));
    if (!provider) throw new Error("unknown_connection");
    return provider;
  }

  #invoke(frame: NativeFrame): unknown {
    if (typeof frame.method === "string" && frame.method.startsWith("access.")) return this.#access(frame);
    switch (frame.method) {
      case "hello":
        if (this.#hello || frame.protocolVersion !== 2)
          throw new Error("host_protocol_mismatch");
        this.#hello = true;
        return { protocolVersion: 2, bootId: this.bootId, admissionSchema: "machine-control-admission/v2" };
      case "state":
        this.tick();
        return {
          bootId: this.bootId,
          ...this.core.inspect(),
          host: {
            engine: process.versions.bun ? "bun" : "node",
            version: process.versions.bun ?? process.versions.node,
            rssBytes: process.memoryUsage().rss,
          },
        };
      case "provider.connect": {
        this.#prune();
        if (this.#providers.size >= 80) throw new Error("host_capacity");
        const connection = this.core.connect(
          string(frame.profileId),
          "chrome.extension/cdp",
        );
        const connectionId = `${this.bootId}:${++this.#sequence}`;
        if (typeof frame.transportTag === "string") this.#transportTags.set(connectionId, string(frame.transportTag));
        const provider = new ExtensionProvider(this.core, connection, {
          namespace: connectionId,
          send: (payload, command) =>
            this.#send({
              type: "provider.send",
              connectionId,
              transportTag: this.#transportTags.get(connectionId),
              frame: payload,
              ...(command
                ? {
                    authorityId: this.#requestAuthorities.get(
                      command.requestId,
                    ),
                  }
                : {}),
            }),
          effects: (effects) => this.#consume(effects),
          fault: () => this.#send({ type: "provider.close", connectionId }),
        });
        this.#providers.set(connectionId, provider);
        if (frame.defer !== true) provider.synchronize();
        return { connectionId, generation: connection.generation };
      }
      case "provider.disconnect": {
        const provider = this.#provider(frame.connectionId);
        provider.disconnected();
        const profile = this.#profileConnections.get(
          string(frame.connectionId),
        );
        if (profile) this.#profiles.disconnected(profile, provider.connection);
        this.#cdp?.sweep();
        this.#retired.add(string(frame.connectionId));
        this.#prune();
        return {};
      }
      case "provider.frame": {
        const provider = this.#provider(frame.connectionId);
        const payload = object(frame.frame);
        const profile = this.#profileConnections.get(
          string(frame.connectionId),
        );
        if (profile && payload.type === "profile.update") {
          this.#profiles.update(profile, payload.profile);
          if (!profile.enabled)
            this.#consume(this.core.withdraw(provider.connection));
          this.#synchronize();
          return {};
        }
        const applied =
          typeof payload.type === "string" &&
          payload.type.startsWith("session.")
            ? (this.#cdp?.receive(provider.connection, payload) ?? false)
            : provider.receive(payload);
        this.#prune();
        return { applied };
      }
      case "operator.approve": {
        if (!Array.isArray(frame.connectionIds))
          throw new Error("invalid_host_request");
        const providers = frame.connectionIds.map((value) =>
          this.#provider(value),
        );
        const granted = this.core.approve(
          providers.map((provider) => provider.connection),
          integer(frame.durationMs),
        );
        this.#approval = granted.approval;
        this.#consume(granted.effects);
        this.#synchronize();
        return { generation: granted.approval.generation };
      }
      case "browser.attach": {
        const hello = object(frame.hello);
        if (
          hello.protocolVersion !== 1 ||
          typeof hello.extensionVersion !== "string" ||
          hello.extensionVersion.length > 32
        )
          throw new Error("browser_profile_protocol_required");
        const profile = this.#profiles.announce(
          string(frame.extensionId),
          hello.profile,
        );
        const data = this.#invoke({
          method: "provider.connect",
          profileId: profile.profileId,
          defer: true,
          transportTag: frame.transportTag,
        }) as { connectionId: string };
        const provider = this.#provider(data.connectionId);
        profile.connection = provider.connection;
        this.#profileConnections.set(data.connectionId, profile);
        if (!profile.enabled)
          this.#consume(this.core.withdraw(provider.connection));
        this.#send({
          type: "provider.send",
          connectionId: data.connectionId,
          transportTag: this.#transportTags.get(data.connectionId),
          frame: {
            type: "profile.accepted",
            protocolVersion: 1,
            profileId: profile.profileId,
          },
        });
        this.#synchronize();
        return { ...data, profileId: profile.profileId };
      }
      case "provider.retire": {
        const id = string(frame.connectionId),
          provider = this.#providers.get(id);
        if (!provider) return {};
        this.core.retire(provider.connection);
        this.#providers.delete(id);
        this.#retired.delete(id);
        this.#profileConnections.delete(id);
        this.#transportTags.delete(id);
        return {};
      }
      case "native.state":
        this.#consume(
          this.core.availability(
            frame.readable === true,
            frame.writable === true,
            string(frame.generation),
          ),
        );
        this.#synchronize();
        return {};
      case "native.reply": {
        const id = string(frame.nativeId),
          resolve = this.#nativeWaiters.get(id);
        if (resolve) {
          this.#nativeWaiters.delete(id);
          resolve(frame.accepted === true);
        }
        return {};
      }
      case "operator.configure": {
        if (!Array.isArray(frame.scopes) || !Array.isArray(frame.profileIds))
          throw new Error("invalid_host_request");
        if (
          !frame.scopes.includes("browser") &&
          !frame.scopes.includes("devtools")
        )
          {
            this.#consume(this.core.replaceWithoutApproval());
            this.#approval = undefined;
            this.#synchronize();
            return {};
          }
        if (!frame.profileIds.length)
          throw new Error("browser_profiles_required");
        const connections = frame.profileIds.map((id) => {
          const profile = this.#profiles.get(string(id));
          if (!profile?.enabled)
            throw new Error("profile_unavailable");
          return profile.profileId;
        });
        const granted = this.core.approveKnownProfiles(
          connections,
          frame.durationMs === null ? null : integer(frame.durationMs),
          { devtools: frame.scopes.includes("devtools") },
        );
        this.#approval = granted.approval;
        this.#consume(granted.effects);
        this.#synchronize();
        return this.core.inspect();
      }
      case "browser.call":
        return this.#browserCall(frame);
      case "browser.cancel":
        this.#consume(this.core.cancel(string(frame.requestId)));
        return {};
      case "operator.checkpoint": {
        const checkpoint = this.core.checkpoint();
        this.#checkpoints.clear();
        if (!checkpoint) return {};
        const checkpointId = randomUUID();
        this.#checkpoints.set(checkpointId, checkpoint);
        return { checkpointId };
      }
      case "operator.restore": {
        const id = string(frame.checkpointId), token = this.#checkpoints.get(id);
        this.#checkpoints.delete(id);
        if (!token) throw new Error("invalid_checkpoint");
        const restored = this.core.restore(token);
        this.#approval = restored.approval;
        this.#consume(restored.effects);
        this.#synchronize();
        return {};
      }
      case "operator.stop":
        this.#checkpoints.clear();
        this.#consume(this.core.stop());
        this.#approval = undefined;
        this.#synchronize();
        return {};
      case "request": {
        // Native caller admission precedes this trusted-host call. No incoming
        // JSON object is ever cast to a core Approval or ProviderConnection.
        const provider = this.#provider(frame.connectionId);
        const common = {
          requestId: string(frame.requestId),
          profileId: provider.connection.profileId,
          timeoutMs: integer(frame.timeoutMs),
        };
        if (frame.authorizationGeneration !== this.#approval?.generation) {
          this.#send({
            type: "request.finished",
            result: {
              ...common,
              operation: frame.operation,
              accepted: false,
              actualRoute: provider.connection.route,
              providerGeneration: provider.connection.generation,
              errorCode: "approval_required",
              delivery: "refused",
              effect: "refused",
              uncertainty: "none",
              retrySafety: "safe_not_dispatched",
            },
          });
          return {};
        }
        let request: BrowserRequest;
        if (frame.operation === "browser.tabs") {
          request = {
            ...common,
            operation: frame.operation,
            connection: provider.connection,
          };
        } else if (frame.operation === "browser.snapshot") {
          request = {
            ...common,
            operation: frame.operation,
            connection: provider.connection,
            tabId: integer(frame.tabId),
          };
        } else if (frame.operation === "browser.click") {
          const prefix = this.#referencePrefix(provider.connection.generation);
          if (
            typeof frame.reference !== "string" ||
            frame.reference.length > 768
          )
            throw new Error("invalid_host_request");
          if (!frame.reference.startsWith(prefix)) {
            this.#send({
              type: "request.finished",
              result: {
                ...common,
                operation: frame.operation,
                accepted: false,
                actualRoute: provider.connection.route,
                providerGeneration: provider.connection.generation,
                errorCode: "stale_reference",
                delivery: "refused",
                effect: "refused",
                uncertainty: "none",
                retrySafety: "safe_not_dispatched",
              },
            });
            return {};
          }
          request = {
            ...common,
            operation: frame.operation,
            reference: {
              connection: provider.connection,
              target: frame.reference.slice(prefix.length),
            },
          };
        } else throw new Error("invalid_host_request");
        // The core refuses an absent approval through the normal typed path.
        const approval =
          this.#approval ??
          Object.freeze({ generation: 0, profiles: [], expiresAt: 0 });
        this.#consume(this.core.request(approval, request));
        return {};
      }
      default:
        throw new Error("unknown_host_method");
    }
  }

  /** Only the authenticated native parent can reach this private inlet. */
  #access(frame: NativeFrame): unknown {
    const method = frame.method;
    if (method === "access.state") return this.access.status();
    if (method === "access.query") return this.access.query();
    if (method === "access.configure") {
      this.access.configure(string(frame.surface) as Surface, object(frame.configuration) as unknown as SurfaceConfiguration);
    } else if (method === "access.notice") this.access.notice(integer(frame.milliseconds));
    else if (method === "access.ready") {
      if (typeof frame.ready !== "boolean") throw new Error("invalid_host_request");
      if (frame.noticeVisible !== undefined && typeof frame.noticeVisible !== "boolean") throw new Error("invalid_host_request");
      this.access.ready(string(frame.surface) as Surface, frame.ready, frame.noticeVisible as boolean | undefined);
    } else if (method === "access.input-ready") {
      if (typeof frame.ready !== "boolean") throw new Error("invalid_host_request");
      this.access.inputReady(frame.ready);
    } else if (method === "access.pause") this.access.pause(string(frame.surface) as Surface | "all", string(frame.reason), frame.milliseconds === null ? null : integer(frame.milliseconds));
    else if (method === "access.resume") this.access.resume(string(frame.surface) as Surface | "all", string(frame.reason));
    else if (method === "access.input") this.access.input(string(frame.surface) as Surface, string(frame.kind) as HumanInput);
    else if (method === "access.preferences") this.access.preferences(object(frame.preferences) as unknown as AccessPreferences);
    else if (method === "access.hold") this.access.hold(string(frame.intentId));
    else if (method === "access.postpone") this.access.postpone(string(frame.intentId), integer(frame.milliseconds));
    else if (method === "access.approve") this.access.approve(string(frame.intentId), frame.milliseconds === undefined ? 0 : integer(frame.milliseconds));
    else if (method === "access.start") this.access.startNow(string(frame.intentId));
    else if (method === "access.deny") this.access.deny(string(frame.intentId));
    else if (method === "access.defer") this.access.defer(string(frame.intentId), frame.milliseconds === null ? null : integer(frame.milliseconds));
    else if (method === "access.stop") this.access.stop();
    else {
      const label = string(frame.owner);
      if (method === "access.open") {
        if (this.#accessOwners.has(label)) throw new Error("admission_owner_exists");
        this.#accessOwners.set(label, this.access.open());
      } else {
        const owner = this.#accessOwners.get(label);
        if (!owner) throw new Error("admission_owner_mismatch");
        if (method === "access.close") { this.access.close(owner); this.#accessOwners.delete(label); }
        else if (method === "access.submit") {
          const request = object(frame.request);
          const narrowed = request.operations ?? undefined;
          if (narrowed !== undefined && (!Array.isArray(narrowed) || narrowed.length < 1 || narrowed.length > 64)) throw new Error("invalid_host_request");
          const operations = (narrowed as unknown[] | undefined)?.map(string);
          return this.access.submit(owner, { ...request, operations, disruptive: !backgroundOperations(operations) } as unknown as AdmissionRequest);
        }
        else if (method === "access.inspect") return this.access.inspect(owner, string(frame.intentId), frame.heartbeat === true);
        else if (method === "access.accept") return this.access.accept(owner, string(frame.intentId), integer(frame.offerGeneration));
        else if (method === "access.renew") return this.access.renew(owner, object(frame.fence) as unknown as SessionFence, integer(frame.durationMs));
        else if (method === "access.authorize") return { refusal: this.access.authorize(owner, object(frame.fence) as unknown as SessionFence, frame.operation == null ? undefined : string(frame.operation)) };
        else if (method === "access.cancel") this.access.cancel(owner, string(frame.intentId), frame.reason === undefined ? undefined : string(frame.reason));
        else throw new Error("unknown_host_method");
      }
    }
    return ["access.input", "access.input-ready", "access.ready"].includes(method as string) ? this.access.query() : this.access.status();
  }

  #consume(effects: readonly Effect[]): void {
    for (const effect of effects) {
      if (effect.type === "request.finished") {
        let result = effect.result;
        if (result.accepted && result.operation === "browser.snapshot") {
          const data = object(result.data);
          if (!Array.isArray(data.elements))
            throw new Error("invalid_provider_data");
          const prefix = this.#referencePrefix(result.providerGeneration!, this.#requestOwners.get(result.requestId));
          result = {
            ...result,
            data: {
              ...data,
              elements: data.elements.map((element) => {
                const value = object(element);
                return { ...value, reference: prefix + value.reference };
              }),
            },
          };
        }
        this.#send({ type: "request.finished", result });
        const resolve = this.#waiters.get(result.requestId);
        if (resolve) {
          this.#waiters.delete(result.requestId);
          this.#requestAuthorities.delete(result.requestId);
          this.#requestOwners.delete(result.requestId);
          resolve(result);
        }
      } else {
        const provider = [...this.#providers.values()].find(
          (item) => item.connection === effect.command.connection,
        );
        if (!provider) continue;
        if (effect.type === "provider.dispatch")
          dispatchToProvider(this.core, provider, effect.command, (effects) =>
            this.#consume(effects),
          );
        else provider.cancel(effect.command);
      }
    }
  }

  #synchronize(): void {
    for (const provider of this.#providers.values()) provider.synchronize();
    this.#cdp?.sweep();
  }

  #referencePrefix(connectionGeneration: number, ownerSession = "fixture"): string {
    return `${this.bootId}:${connectionGeneration}:${this.core.inspect().authorizationGeneration}:${ownerSession}:`;
  }

  #error(error: unknown): string {
    const message =
      error instanceof Error ? error.message : "invalid_host_request";
    return /^[a-z][a-z0-9_]{0,100}$/.test(message)
      ? message
      : "invalid_host_request";
  }

  #publish(): void {
    const state = this.core.inspect();
    const projection = {
      ...state,
      profiles: this.#profiles.state(),
      effectiveScopes: state.approvedProfiles.length
        ? state.devtools
          ? ["browser", "devtools"]
          : ["browser"]
        : [],
    };
    const serialized = JSON.stringify(projection);
    if (serialized === this.#published) return;
    this.#published = serialized;
    this.#send({ type: "browser.state", state: projection });
  }

  #native(
    phase: "check" | "begin" | "result",
    authorityId: string,
    auditId: string,
    delivery?: "confirmed" | "unknown",
  ): Promise<boolean> {
    if (this.#closed || this.#nativeWaiters.size >= 256)
      return Promise.resolve(false);
    const nativeId = `native:${++this.#sequence}`;
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.#nativeWaiters.delete(nativeId);
        resolve(false);
      }, 3000);
      this.#nativeWaiters.set(nativeId, (accepted) => {
        clearTimeout(timer);
        resolve(accepted);
      });
      this.#send({
        type: "native.check",
        nativeId,
        phase,
        authorityId,
        auditId,
        ...(delivery ? { delivery } : {}),
      });
    });
  }

  #browserCall(frame: NativeFrame): unknown {
    this.tick();
    const request = object(frame.request),
      requestId = string(frame.requestId),
      authorityId = string(frame.authorityId);
    const operation = string(request.operation);
    if (operation === "browser.profiles")
      return {
        accepted: true,
        delivery: "confirmed",
        effect: "not_applicable",
        data: { profiles: this.#profiles.state(), approvedProfiles: this.core.inspect().selectedProfiles },
      };
    const ownerSession = string(frame.ownerSession);
    if (!Array.isArray(frame.ownerProfileIds) || frame.ownerProfileIds.length > 64)
      throw new Error("invalid_host_request");
    const ownerProfiles = frame.ownerProfileIds.map(string);
    const selector =
      request.browserProfileId === undefined
        ? undefined
        : request.browserProfileId;
    if (
      selector !== undefined &&
      (typeof selector !== "string" ||
        selector.length < 1 ||
        selector.length > 128 ||
        /[\u0000-\u001f\u007f]/.test(selector))
    )
      throw new Error("invalid_request");
    const profile = this.#profiles.select(
      selector,
      ownerProfiles,
    );
    if (!ownerProfiles.includes(profile.profileId)) throw new Error("profile_not_permitted_by_control_channel");
    const connection = profile.connection!;
    const common = {
      requestId,
      profileId: profile.profileId,
      operation,
      actualRoute: connection.route,
      providerGeneration: connection.generation,
    };
    const refuse = (errorCode: string) => ({
      ...common,
      accepted: false,
      delivery: "refused",
      effect: "refused",
      uncertainty: "none",
      retrySafety: "safe_not_dispatched",
      errorCode,
    });
    if (!validOwnership(operation, request)) return refuse("invalid_request");
    if (operation === "browser.endpoint") {
      const fence =
        this.#approval &&
        this.core.fence(this.#approval, connection, "browser.cdp");
      if (!fence) return refuse("approval_required");
      this.#cdp ??= new CdpBridge(
        this.#streams,
        (phase, owner, audit, delivery) =>
          this.#native(phase, owner, audit, delivery),
        (target, payload, owner) => {
          const id = [...this.#providers].find(
            ([, adapter]) => adapter.connection === target,
          )?.[0];
          if (id)
            this.#send({
              type: "provider.send",
              connectionId: id,
              transportTag: this.#transportTags.get(id),
              frame: payload,
              ...(owner ? { authorityId: owner } : {}),
            });
        },
      );
      return this.#cdp
        .endpoint(fence, authorityId)
        .then((data) => ({
          ...common,
          accepted: true,
          delivery: "confirmed",
          effect: "not_applicable",
          uncertainty: "none",
          retrySafety: "safe_observation",
          data,
        }));
    }
    if (this.#waiters.size >= 64 || this.#waiters.has(requestId))
      return refuse("capacity_exceeded");
    const payload = { ...request };
    for (const key of [
      "operation",
      "requestId",
      "expectedGeneration",
      "browserProfileId",
      "scopes",
      "reason",
    ])
      delete payload[key];
    if (payload.reference !== undefined) {
      const prefix = this.#referencePrefix(connection.generation, ownerSession);
      if (
        typeof payload.reference !== "string" ||
        !payload.reference.startsWith(prefix)
      )
        return refuse("stale_reference");
      payload.reference = payload.reference.slice(prefix.length);
    }
    const params = parameters(payload);
    const timeoutMs =
      request.timeoutMs === undefined ? 45000 : integer(request.timeoutMs);
    return new Promise((resolve, reject) => {
      this.#waiters.set(requestId, resolve);
      this.#requestAuthorities.set(requestId, authorityId);
      this.#requestOwners.set(requestId, ownerSession);
      try {
        this.#consume(
          this.core.request(this.#approval!, {
            requestId,
            profileId: profile.profileId,
            connection,
            operation: operation as BrowserOperation,
            params,
            timeoutMs,
          }),
        );
      } catch (error) {
        this.#waiters.delete(requestId);
        this.#requestAuthorities.delete(requestId);
        this.#requestOwners.delete(requestId);
        reject(error);
      }
    });
  }

  #prune(): void {
    for (const id of this.#retired) {
      if (this.#providers.get(id)?.pendingCount === 0) {
        this.#providers.delete(id);
        this.#profileConnections.delete(id);
        this.#transportTags.delete(id);
        this.#retired.delete(id);
      }
    }
  }
}
