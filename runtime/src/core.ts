import {
  browserOperations,
  parameters,
  observes,
  needsDevtools,
} from "./browser-contract.ts";
import type { BrowserOperation, Parameters } from "./browser-contract.ts";
export type { BrowserOperation } from "./browser-contract.ts";

/** Resident policy only: no OS, transport, interpreter, UI, or provider I/O. */
export interface Clock {
  /** Monotonic integer milliseconds, supplied independently of wall time. */
  now(): number;
}

/** Issued after a trusted host authenticates a provider. IDs are not authority. */
export interface ProviderConnection {
  readonly profileId: string;
  readonly generation: number;
  readonly route: string;
}

/** Internal operator authority; never accept a deserialized copy from a caller. */
export interface Approval {
  readonly generation: number;
  readonly profiles: readonly string[];
  readonly expiresAt: number;
  readonly devtools?: boolean;
}

interface RequestIdentity {
  readonly requestId: string;
  readonly profileId: string;
  readonly timeoutMs: number;
}

export interface ClickRequest extends RequestIdentity {
  readonly operation?: "browser.click";
  readonly reference: {
    readonly connection: ProviderConnection;
    readonly target: string;
  };
}

export interface OperationRequest extends RequestIdentity {
  readonly operation: BrowserOperation;
  readonly connection: ProviderConnection;
  readonly params: Parameters;
}

export interface AuthorityFence {
  readonly connection: ProviderConnection;
  readonly authorizationGeneration: number;
}

export type BrowserRequest =
  | OperationRequest
  | ClickRequest
  | (RequestIdentity &
      (
        | {
            readonly operation: "browser.tabs";
            readonly connection: ProviderConnection;
          }
        | {
            readonly operation: "browser.snapshot";
            readonly connection: ProviderConnection;
            readonly tabId: number;
          }
      ));

/** Immutable correlation handle, translated by a future authenticated adapter. */
interface DispatchIdentity {
  readonly requestId: string;
  readonly connection: ProviderConnection;
  readonly authorizationGeneration: number;
}

export type DispatchCommand = DispatchIdentity &
  (
    | { readonly operation: BrowserOperation; readonly params: Parameters }
    | { readonly operation: "browser.click"; readonly target: string }
    | { readonly operation: "browser.tabs" }
    | { readonly operation: "browser.snapshot"; readonly tabId: number }
  );

/** Effect sink behind the host's authenticated connection and dispatch check. */
export interface ProviderAdapter {
  readonly connection: ProviderConnection;
  execute(command: DispatchCommand, timeoutMs: number): void;
  cancel(command: DispatchCommand): void;
}

export type ProviderReply =
  | { readonly ok: true; readonly data?: unknown }
  | { readonly ok: false; readonly delivery: "refused" | "unknown"; readonly errorCode?: string; readonly message?: string };

export type RefusalCode =
  | "approval_required"
  | "profile_not_approved"
  | "profile_unavailable"
  | "stale_reference"
  | "request_conflict"
  | "capacity_exceeded"
  | "stopped"
  | "approval_replaced"
  | "approval_expired"
  | "provider_disconnected"
  | "request_timeout"
  | "provider_failed"
  | "access_paused"
  | "stale_generation"
  | "scope_not_approved";

interface ResultIdentity {
  readonly requestId: string;
  readonly operation: BrowserOperation;
  readonly profileId: string;
  readonly actualRoute: string;
  readonly providerGeneration: number | null;
}

/** Internal result using the common vocabulary; this is not a public envelope. */
export type ActionResult = ResultIdentity &
  (
    | {
        readonly accepted: true;
        readonly delivery: "confirmed";
        readonly effect: "unverifiable";
        readonly uncertainty: "application_effect_not_observed";
        readonly retrySafety: "observe_before_retry";
        readonly errorCode?: never;
        readonly data?: unknown;
      }
    | {
        readonly accepted: false;
        readonly delivery: "refused";
        readonly effect: "refused";
        readonly uncertainty: "none";
        readonly retrySafety: "safe_not_dispatched";
        readonly errorCode: string;
        readonly message?: string;
      }
    | {
        readonly accepted: false;
        readonly delivery: "unknown";
        readonly effect: "unknown";
        readonly uncertainty: "action_may_have_executed";
        readonly retrySafety: "observe_before_retry";
        readonly errorCode: string;
        readonly message?: string;
      }
  );

export type Effect =
  | { readonly type: "provider.dispatch"; readonly command: DispatchCommand }
  | { readonly type: "provider.cancel"; readonly command: DispatchCommand }
  | { readonly type: "request.finished"; readonly result: ActionResult };

export class CoreError extends Error {
  readonly code:
    | "invalid_request"
    | "profile_conflict"
    | "capacity_exceeded"
    | "clock_invalid";

  constructor(code: CoreError["code"]) {
    super(code);
    this.code = code;
  }
}

interface Pending {
  readonly command: DispatchCommand;
  readonly approval: Approval;
  readonly deadline: number;
  phase: "queued" | "dispatched";
}

function identifier(value: string): void {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(value)) {
    throw new CoreError("invalid_request");
  }
}

function duration(value: number, maximum: number): void {
  if (!Number.isSafeInteger(value) || value < 1 || value > maximum) {
    throw new CoreError("invalid_request");
  }
}

function boundedText(value: string, maximum: number): void {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximum ||
    value.trim() !== value ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new CoreError("invalid_request");
  }
}

/**
 * One serialized owner of portable browser policy. The host supplies trusted
 * facts, schedules tick() at deadlines, and executes returned effects.
 * No method calls into a provider or awaits external work.
 */
export class ResidentCore {
  readonly #clock: Clock;
  readonly #maxProviders: number;
  readonly #maxRequests: number;
  readonly #providers = new Map<string, ProviderConnection>();
  readonly #knownProfiles = new Set<string>();
  readonly #pending = new Map<DispatchCommand, Pending>();
  // Stop ends authority, not the physical provider call. Retain its slot until
  // that exact connection returns, even if a new approval has been issued.
  readonly #unsettled = new Set<DispatchCommand>();
  #approval: Approval | undefined;
  readonly #withdrawn = new Set<string>();
  readonly #fences = new WeakSet<AuthorityFence>();
  #availability = { readable: true, writable: true, generation: "initial" };
  #providerGeneration = 0;
  #authorizationGeneration = 0;
  #lastTime = 0;

  constructor(
    clock: Clock,
    limits: { providers?: number; requests?: number } = {},
  ) {
    this.#clock = clock;
    this.#maxProviders = limits.providers ?? 16;
    this.#maxRequests = limits.requests ?? 64;
    duration(this.#maxProviders, 256);
    duration(this.#maxRequests, 256);
    this.#now();
  }

  connect(profileId: string, route: string): ProviderConnection {
    identifier(profileId);
    boundedText(route, 128);
    if (this.#providers.has(profileId)) throw new CoreError("profile_conflict");
    if (this.#providers.size >= this.#maxProviders)
      throw new CoreError("capacity_exceeded");
    const connection = Object.freeze({
      profileId,
      route,
      generation: ++this.#providerGeneration,
    });
    if (!this.#knownProfiles.has(profileId) && this.#knownProfiles.size >= 256) throw new CoreError("capacity_exceeded");
    this.#knownProfiles.add(profileId);
    this.#providers.set(profileId, connection);
    return connection;
  }

  approve(
    connections: readonly ProviderConnection[],
    durationMs: number | null,
    options: { devtools?: boolean } = {},
  ): {
    readonly approval: Approval;
    readonly effects: readonly Effect[];
  } {
    if (durationMs !== null) duration(durationMs, 28_800_000);
    if (
      connections.length === 0 ||
      new Set(connections).size !== connections.length ||
      connections.some(
        (connection) =>
          this.#providers.get(connection.profileId) !== connection,
      )
    ) {
      throw new CoreError("invalid_request");
    }
    return this.approveKnownProfiles(connections.map((connection) => connection.profileId), durationMs, options);
  }

  /** Trusted operator selection of previously authenticated installation IDs. */
  approveKnownProfiles(profileIds: readonly string[], durationMs: number | null, options: { devtools?: boolean } = {}): { readonly approval: Approval; readonly effects: readonly Effect[] } {
    if (durationMs !== null) duration(durationMs, 28_800_000);
    if (!profileIds.length || profileIds.length > this.#maxProviders || new Set(profileIds).size !== profileIds.length ||
        profileIds.some((id) => !this.#knownProfiles.has(id))) throw new CoreError("invalid_request");
    const now = this.#now();
    if (durationMs !== null && !Number.isSafeInteger(now + durationMs))
      throw new CoreError("clock_invalid");
    const effects = this.#expire(now);
    this.#approval = undefined;
    this.#withdrawn.clear();
    for (const pending of this.#pending.values())
      this.#end(pending, "approval_replaced", effects);
    const approval = Object.freeze({
      generation: ++this.#authorizationGeneration,
      profiles: Object.freeze(
        [...profileIds],
      ),
      expiresAt: durationMs === null ? Infinity : now + durationMs,
      devtools: options.devtools === true,
    });
    this.#approval = approval;
    return { approval, effects };
  }

  request(approval: Approval, request: BrowserRequest): readonly Effect[] {
    identifier(request.requestId);
    identifier(request.profileId);
    duration(request.timeoutMs, 45_000);
    if ("params" in request) {
      if (!browserOperations.includes(request.operation))
        throw new CoreError("invalid_request");
    } else if (
      request.operation === undefined ||
      request.operation === "browser.click"
    ) {
      boundedText(request.reference.target, 512);
    } else if (request.operation === "browser.snapshot") {
      if (!Number.isSafeInteger(request.tabId) || request.tabId < 1)
        throw new CoreError("invalid_request");
    } else if (request.operation !== "browser.tabs") {
      throw new CoreError("invalid_request");
    }
    const now = this.#now();
    const effects = this.#expire(now);
    const connection = this.#providers.get(request.profileId);
    const reject = (errorCode: RefusalCode) => {
      effects.push({
        type: "request.finished",
        result: this.#refused(request, connection, errorCode),
      });
      return effects;
    };
    if (!this.#approval || this.#approval !== approval)
      return reject("approval_required");
    if (
      !approval.profiles.includes(request.profileId) ||
      this.#withdrawn.has(request.profileId)
    )
      return reject("profile_not_approved");
    if (!connection) return reject("profile_unavailable");
    const permission = this.#permission(request.operation ?? "browser.click");
    if (permission) return reject(permission);
    const requestedConnection =
      "reference" in request
        ? request.reference.connection
        : request.connection;
    if (requestedConnection !== connection) return reject("stale_reference");
    if (
      [...this.#pending.keys()].some(
        (command) => command.requestId === request.requestId,
      )
    ) {
      return reject("request_conflict");
    }
    if (this.#retained() >= this.#maxRequests)
      return reject("capacity_exceeded");
    if (!Number.isSafeInteger(now + request.timeoutMs))
      throw new CoreError("clock_invalid");
    const identity: DispatchIdentity = {
      requestId: request.requestId,
      connection,
      authorizationGeneration: this.#authorizationGeneration,
    };
    const command: DispatchCommand =
      "params" in request
        ? Object.freeze({
            ...identity,
            operation: request.operation,
            params: parameters(request.params),
          })
        : request.operation === "browser.tabs"
          ? Object.freeze({ ...identity, operation: "browser.tabs" })
          : request.operation === "browser.snapshot"
            ? Object.freeze({
                ...identity,
                operation: "browser.snapshot",
                tabId: request.tabId,
              })
            : Object.freeze({
                ...identity,
                operation: "browser.click",
                target: request.reference.target,
              });
    this.#pending.set(command, {
      command,
      approval,
      deadline: now + request.timeoutMs,
      phase: "queued",
    });
    effects.push({ type: "provider.dispatch", command });
    return effects;
  }

  /**
   * Recheck at actual dispatch, not just at enqueue. If started, the trusted
   * adapter must submit in this serialized turn with no intervening await.
   * An adapter with additional asynchronous preparation needs a fresh begin
   * boundary instead of retaining a previously successful authorization.
   */
  begin(command: DispatchCommand):
    | { readonly started: false; readonly effects: readonly Effect[] }
    | {
        readonly started: true;
        readonly effects: readonly Effect[];
        readonly timeoutMs: number;
      } {
    const effects = this.tick();
    const pending = this.#pending.get(command);
    if (!pending || pending.phase !== "queued")
      return { started: false, effects };
    if (
      this.#approval !== pending.approval ||
      command.authorizationGeneration !== this.#authorizationGeneration ||
      this.#withdrawn.has(command.connection.profileId) ||
      this.#permission(command.operation) !== null ||
      this.#providers.get(command.connection.profileId) !== command.connection
    ) {
      this.#end(pending, "approval_required", effects);
      return { started: false, effects };
    }
    pending.phase = "dispatched";
    this.#unsettled.add(command);
    return {
      started: true,
      effects,
      timeoutMs: pending.deadline - this.#lastTime,
    };
  }

  complete(
    connection: ProviderConnection,
    command: DispatchCommand,
    reply: ProviderReply,
  ): {
    readonly applied: boolean;
    readonly effects: readonly Effect[];
  } {
    if (
      reply.ok !== true &&
      (reply.ok !== false || !["refused", "unknown"].includes(reply.delivery))
    ) {
      throw new CoreError("invalid_request");
    }
    const effects = this.tick();
    // Object identity is intentional. A copied public connection/generation or
    // a reply from another provider cannot complete work or free its capacity.
    if (command.connection !== connection || !this.#unsettled.delete(command)) {
      return { applied: false, effects };
    }
    const pending = this.#pending.get(command);
    if (!pending) return { applied: false, effects };
    this.#pending.delete(command);
    const result: ActionResult = reply.ok
      ? Object.freeze({
          requestId: command.requestId,
          operation: command.operation,
          profileId: connection.profileId,
          actualRoute: connection.route,
          providerGeneration: connection.generation,
          accepted: true,
          delivery: "confirmed",
          effect: "unverifiable",
          uncertainty: "application_effect_not_observed",
          retrySafety: "observe_before_retry",
          ...(reply.data === undefined ? {} : { data: reply.data }),
        })
      : Object.freeze({ ...this.#failure(command, reply.errorCode ?? "provider_failed", reply.delivery === "unknown"), ...(reply.message ? { message: reply.message } : {}) });
    effects.push({ type: "request.finished", result });
    return { applied: true, effects };
  }

  disconnect(connection: ProviderConnection): readonly Effect[] {
    const effects = this.tick();
    if (this.#providers.get(connection.profileId) !== connection)
      return effects;
    this.#providers.delete(connection.profileId);
    for (const pending of this.#pending.values()) {
      if (pending.command.connection === connection)
        this.#end(pending, "provider_disconnected", effects);
    }
    return effects;
  }

  cancel(requestId: string): readonly Effect[] {
    const effects = this.tick();
    for (const pending of this.#pending.values())
      if (pending.command.requestId === requestId) this.#end(pending, "request_timeout", effects);
    return effects;
  }

  stop(): readonly Effect[] {
    const effects: Effect[] = [];
    this.#approval = undefined;
    ++this.#authorizationGeneration;
    for (const pending of this.#pending.values())
      this.#end(pending, "stopped", effects);
    return effects;
  }

  tick(): Effect[] {
    return this.#expire(this.#now());
  }

  /** Host scheduling hint only; begin/complete still enforce exact deadlines. */
  nextDeadline(): number | null {
    let deadline = this.#approval?.expiresAt ?? Infinity;
    for (const pending of this.#pending.values())
      deadline = Math.min(deadline, pending.deadline);
    return Number.isFinite(deadline) ? deadline : null;
  }

  inspect(): {
    readonly connectedProfiles: readonly string[];
    readonly approvedProfiles: readonly string[];
    readonly pendingRequests: number;
    readonly unsettledDispatches: number;
    readonly retainedRequests: number;
    readonly authorizationGeneration: number;
    readonly devtools: boolean;
    readonly selectedProfiles: readonly string[];
    readonly remainingMs: number | null;
  } {
    const now = this.#now();
    return {
      connectedProfiles: [...this.#providers.keys()],
      approvedProfiles:
        this.#approval && this.#approval.expiresAt > now
          ? this.#approval.profiles.filter(
              (id) => !this.#withdrawn.has(id) && this.#availability.readable,
            )
          : [],
      pendingRequests: this.#pending.size,
      unsettledDispatches: this.#unsettled.size,
      retainedRequests: this.#retained(),
      authorizationGeneration: this.#authorizationGeneration,
      devtools:
        this.#approval?.devtools === true && this.#availability.writable,
      selectedProfiles:
        this.#approval?.profiles.filter((id) => !this.#withdrawn.has(id)) ?? [],
      remainingMs:
        this.#approval && Number.isFinite(this.#approval.expiresAt)
          ? Math.max(0, this.#approval.expiresAt - now)
          : null,
    };
  }

  /** Native host confirms the disconnected transport is permanently disposed.
   * Releases correlation capacity, never changes the already-unknown result. */
  retire(connection: ProviderConnection): void {
    if (this.#providers.get(connection.profileId) === connection)
      throw new CoreError("invalid_request");
    for (const command of this.#unsettled)
      if (command.connection === connection) this.#unsettled.delete(command);
  }

  /** Withdraw one profile without invalidating unrelated live profiles. */
  withdraw(connection: ProviderConnection): readonly Effect[] {
    const effects = this.tick();
    if (this.#providers.get(connection.profileId) !== connection)
      return effects;
    this.#withdrawn.add(connection.profileId);
    for (const pending of this.#pending.values())
      if (pending.command.connection === connection)
        this.#end(pending, "profile_not_approved", effects);
    return effects;
  }

  /** Native safety is an input and a denial ceiling, never an approval. */
  availability(
    readable: boolean,
    writable: boolean,
    generation: string,
  ): readonly Effect[] {
    boundedText(generation, 128);
    if (typeof readable !== "boolean" || typeof writable !== "boolean")
      throw new CoreError("invalid_request");
    const effects = this.tick();
    if (
      readable !== this.#availability.readable ||
      writable !== this.#availability.writable ||
      generation !== this.#availability.generation
    ) {
      this.#availability = { readable, writable, generation };
      ++this.#authorizationGeneration;
      for (const pending of this.#pending.values())
        this.#end(pending, "stale_generation", effects);
    }
    return effects;
  }

  fence(
    approval: Approval,
    connection: ProviderConnection,
    operation: BrowserOperation,
  ): AuthorityFence | null {
    if (
      approval !== this.#approval ||
      approval.expiresAt <= this.#now() ||
      !approval.profiles.includes(connection.profileId) ||
      this.#withdrawn.has(connection.profileId) ||
      this.#providers.get(connection.profileId) !== connection ||
      this.#permission(operation)
    )
      return null;
    const fence = Object.freeze({
      connection,
      authorizationGeneration: this.#authorizationGeneration,
    });
    this.#fences.add(fence);
    return fence;
  }

  validFence(fence: AuthorityFence, operation: BrowserOperation): boolean {
    return (
      this.#fences.has(fence) &&
      fence.authorizationGeneration === this.#authorizationGeneration &&
      !!this.#approval &&
      this.#approval.expiresAt > this.#now() &&
      this.#approval.profiles.includes(fence.connection.profileId) &&
      !this.#withdrawn.has(fence.connection.profileId) &&
      this.#providers.get(fence.connection.profileId) === fence.connection &&
      !this.#permission(operation)
    );
  }

  #permission(operation: BrowserOperation): RefusalCode | null {
    if (
      !this.#availability.readable ||
      (!observes(operation) && !this.#availability.writable)
    )
      return "access_paused";
    if (needsDevtools(operation) && !this.#approval?.devtools)
      return "scope_not_approved";
    return null;
  }

  #now(): number {
    const now = this.#clock.now();
    if (!Number.isSafeInteger(now) || now < this.#lastTime)
      throw new CoreError("clock_invalid");
    this.#lastTime = now;
    return now;
  }

  #retained(): number {
    return new Set([...this.#pending.keys(), ...this.#unsettled]).size;
  }

  #expire(now: number): Effect[] {
    const effects: Effect[] = [];
    if (this.#approval && now >= this.#approval.expiresAt) {
      this.#approval = undefined;
      ++this.#authorizationGeneration;
      for (const pending of this.#pending.values())
        this.#end(pending, "approval_expired", effects);
    }
    for (const pending of this.#pending.values()) {
      if (now >= pending.deadline)
        this.#end(pending, "request_timeout", effects);
    }
    return effects;
  }

  #end(pending: Pending, code: RefusalCode, effects: Effect[]): void {
    this.#pending.delete(pending.command);
    if (pending.phase === "dispatched")
      effects.push({ type: "provider.cancel", command: pending.command });
    effects.push({
      type: "request.finished",
      result: this.#failure(
        pending.command,
        code,
        pending.phase === "dispatched",
      ),
    });
  }

  #failure(
    command: DispatchCommand,
    errorCode: string,
    uncertain: boolean,
  ): ActionResult {
    const identity: ResultIdentity = {
      requestId: command.requestId,
      operation: command.operation,
      profileId: command.connection.profileId,
      actualRoute: command.connection.route,
      providerGeneration: command.connection.generation,
    };
    if (uncertain)
      return Object.freeze({
        ...identity,
        accepted: false,
        delivery: "unknown",
        effect: "unknown",
        uncertainty: "action_may_have_executed",
        retrySafety: "observe_before_retry",
        errorCode,
      });
    return Object.freeze({
      ...identity,
      accepted: false,
      delivery: "refused",
      effect: "refused",
      uncertainty: "none",
      retrySafety: "safe_not_dispatched",
      errorCode,
    });
  }

  #refused(
    request: BrowserRequest,
    connection: ProviderConnection | undefined,
    errorCode: RefusalCode,
  ): ActionResult {
    return Object.freeze({
      requestId: request.requestId,
      operation: request.operation ?? "browser.click",
      profileId: request.profileId,
      actualRoute: connection?.route ?? "unavailable",
      providerGeneration: connection?.generation ?? null,
      accepted: false,
      delivery: "refused",
      effect: "refused",
      uncertainty: "none",
      retrySafety: "safe_not_dispatched",
      errorCode,
    });
  }
}
