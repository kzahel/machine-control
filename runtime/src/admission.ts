import type { Clock } from "./core.ts";

export const admissionSchema = "machine-control-admission/v2";
export type Surface = "desktop" | "browser";
export type AccessMode = "off" | "ask" | "automatic";
export type HumanInput = "movement" | "key" | "button" | "scroll";
/** Common conservative impact rule, coupled to the enforced operation set. */
export function backgroundOperations(operations: readonly string[] | undefined): boolean {
  return operations !== undefined && operations.length > 0 && operations.every(operation =>
    ["browser.tabs", "browser.snapshot", "browser.capture", "browser.wait", "browser.release"].includes(operation));
}
export interface SurfaceConfiguration {
  readonly mode: AccessMode;
  /** Null means until turned off. Restart never restores live authority. */
  readonly durationMs: number | null;
  readonly profileIds?: readonly string[];
}
export interface AdmissionRequest {
  readonly requestId: string;
  readonly surfaces: readonly Surface[];
  readonly profileIds?: readonly string[];
  readonly operations?: readonly string[];
  /** Supplied by the trusted operation router, never by an agent assertion. */
  readonly disruptive: boolean;
  readonly reason: string;
  readonly waitMs: number;
  readonly durationMs: number;
}
export interface AdmissionEvent {
  readonly event: "requested" | "approved" | "deferred" | "start_now" | "takeover" |
    "pause" | "resume" | "configured" | "stopped" | "yielded" | "rejected" | "renewed" |
    "waiting_for_resource" | "waiting_for_approval" | "paused" | "announcing" | "offered" | "active" | "ended";
  readonly surface?: Surface | "all";
  readonly intentId?: string;
  readonly sessionId?: string;
  readonly reason?: string;
}
export interface AdmissionOwner { readonly channel: number }
export interface SessionFence {
  readonly intentId: string;
  readonly sessionId: string;
  readonly resourceGenerations: Readonly<Record<string, number>>;
}
interface Configuration {
  mode: AccessMode;
  expiresAt: number;
  profiles: Set<string>;
  generation: number;
}
interface Availability {
  ready: boolean;
  noticeVisible: boolean;
  pauses: Map<string, number>;
}
interface Intent {
  readonly id: string;
  readonly owner: AdmissionOwner;
  readonly request: AdmissionRequest;
  readonly identity: string;
  readonly resources: readonly string[];
  deadline: number;
  taskDeadline: number;
  readonly approvals: Map<Surface, number>;
  heartbeat: number;
  state: string;
  terminal: string | null;
  offer: number;
  offerDeadline: number;
  noticeDeadline: number;
  announced: boolean;
  session: string | null;
  activeDeadline: number;
  generations: Record<string, number>;
}
const surfaces: readonly Surface[] = ["desktop", "browser"];
function duration(value: number, min: number, max: number): void {
  if (!Number.isSafeInteger(value) || value < min || value > max)
    throw new Error("invalid_admission_request");
}
function identifier(value: string): void {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(value))
    throw new Error("invalid_admission_request");
}

/**
 * Shared, synchronous policy. Adapters authenticate owners and operator input,
 * classify effects, and supply safety facts. Nothing here observes or drives an
 * OS. Public IDs are correlation only; owner objects are runtime-local authority.
 */
export class AccessAdmission {
  readonly #clock: Clock;
  readonly #owners = new Set<AdmissionOwner>();
  readonly #intents: Intent[] = [];
  readonly #configuration = new Map<Surface, Configuration>();
  readonly #availability = new Map<Surface, Availability>();
  readonly #resourceGenerations = new Map<string, number>();
  readonly #deferrals = new Map<string, Map<Surface, number>>();
  readonly #globalPauses = new Map<string, number>();
  readonly #takeoverSurfaces = new Set<Surface>();
  #inputReady = false;
  readonly #event: (event: AdmissionEvent) => void;
  #sequence = 0;
  #revision = 0;
  #noticeMs = 10_000;
  #humanCooldownUntil = 0;

  constructor(clock: Clock, event: (event: AdmissionEvent) => void = () => {}) {
    this.#clock = clock; this.#event = event;
    for (const surface of surfaces) {
      this.#configuration.set(surface, { mode: "off", expiresAt: 0, profiles: new Set(), generation: 0 });
      this.#availability.set(surface, { ready: false, noticeVisible: false, pauses: new Map() });
    }
  }
  open(): AdmissionOwner {
    if (this.#owners.size >= 256) throw new Error("admission_capacity");
    const owner = Object.freeze({ channel: ++this.#sequence });
    this.#owners.add(owner);
    return owner;
  }
  close(owner: AdmissionOwner): void {
    this.#owner(owner);
    for (const intent of this.#intents)
      if (intent.owner === owner && !intent.terminal) this.#finish(intent, "owner_disconnected");
    this.#owners.delete(owner);
    this.tick();
  }
  configure(surface: Surface, configuration: SurfaceConfiguration): void {
    const current = this.#config(surface);
    if (!["off", "ask", "automatic"].includes(configuration.mode)) throw new Error("invalid_access_mode");
    if (configuration.durationMs !== null) duration(configuration.durationMs, 1000, 86_400_000);
    const profiles = configuration.profileIds ?? [];
    if (!Array.isArray(profiles) || profiles.length > 64 || new Set(profiles).size !== profiles.length ||
        (surface === "desktop" && profiles.length > 0)) throw new Error("invalid_profile_selection");
    for (const profile of profiles) identifier(profile);
    // Configuration is a new consent ceiling, never an extension of an old task.
    for (const intent of this.#intents)
      if (!intent.terminal && intent.request.surfaces.includes(surface)) this.#finish(intent, "consent_replaced");
    current.mode = configuration.mode;
    current.expiresAt = configuration.mode === "off" ? 0 :
      configuration.durationMs === null ? Infinity : this.#now + configuration.durationMs;
    current.profiles = new Set(profiles);
    if (surface === "browser") {
      for (const resource of this.#deferrals.keys())
        if (resource.startsWith("browser:") && !current.profiles.has(resource.slice(8))) this.#deferrals.delete(resource);
      for (const resource of this.#resourceGenerations.keys())
        if (resource.startsWith("browser:") && !current.profiles.has(resource.slice(8))) this.#resourceGenerations.delete(resource);
    }
    ++current.generation;
    ++this.#revision;
    this.#event({ event: "configured", surface });
    this.tick();
  }
  notice(milliseconds: number): void {
    duration(milliseconds, 0, 60_000);
    this.#noticeMs = milliseconds;
  }
  ready(surface: Surface, ready: boolean, noticeVisible = ready): void {
    this.#available(surface).ready = ready;
    this.#available(surface).noticeVisible = noticeVisible;
    this.tick();
  }
  inputReady(ready: boolean): void {
    this.#inputReady = ready;
    this.tick();
  }
  pause(surface: Surface | "all", reason: string, milliseconds: number | null): void {
    identifier(reason);
    if (milliseconds !== null) duration(milliseconds, 1, 28_800_000);
    const pauses = surface === "all" ? this.#globalPauses : this.#available(surface).pauses;
    pauses.set(reason, milliseconds === null ? Infinity : this.#now + milliseconds);
    this.#event({ event: "pause", surface, reason });
    this.tick();
  }
  resume(surface: Surface | "all", reason: string): void {
    const pauses = surface === "all" ? this.#globalPauses : this.#available(surface).pauses;
    pauses.delete(reason);
    if (reason === "physical_takeover") {
      if (surface === "all") this.#takeoverSurfaces.clear(); else this.#takeoverSurfaces.delete(surface);
      if (this.#takeoverSurfaces.size === 0) this.#humanCooldownUntil = 0;
    }
    if (reason === "operator_deferral") for (const [resource, origins] of this.#deferrals) {
      if (surface === "all") origins.clear(); else origins.delete(surface);
      if (!origins.size) this.#deferrals.delete(resource);
    }
    this.#event({ event: "resume", surface, reason });
    this.tick();
  }
  input(surface: Surface, kind: HumanInput): void {
    if (!["movement", "key", "button", "scroll"].includes(kind)) throw new Error("invalid_input_kind");
    this.tick();
    if (kind === "movement") return;
    // Input during a warning acknowledges no takeover and changes no deadline.
    // A cooldown is attached to the surface, so a new caller cannot bypass it.
    if (!this.#intents.some(i => i.session && i.request.disruptive && i.request.surfaces.includes(surface))) return;
    if (this.#humanCooldownUntil <= this.#now) {
      this.#humanCooldownUntil = this.#now + 60_000;
      this.#takeoverSurfaces.clear();
    }
    this.#takeoverSurfaces.add(surface);
    this.#event({ event: "takeover", surface, reason: "physical_takeover" });
    this.tick();
  }
  submit(owner: AdmissionOwner, request: AdmissionRequest) {
    this.#owner(owner);
    this.tick();
    identifier(request.requestId);
    duration(request.waitMs, 1000, 14_400_000);
    duration(request.durationMs, 1000, 900_000);
    if (typeof request.disruptive !== "boolean" || typeof request.reason !== "string" ||
        !request.reason.trim() || request.reason.length > 240 ||
        !Array.isArray(request.surfaces) || request.surfaces.length < 1 || request.surfaces.length > 2 ||
        new Set(request.surfaces).size !== request.surfaces.length ||
        request.surfaces.some(surface => !surfaces.includes(surface))) throw new Error("invalid_admission_request");
    if (request.profileIds !== undefined && !Array.isArray(request.profileIds)) throw new Error("invalid_profile_selection");
    const profiles = [...(request.profileIds ?? [])].sort();
    if (new Set(profiles).size !== profiles.length || profiles.length > 64 ||
        (request.surfaces.includes("browser") ? profiles.length === 0 : profiles.length > 0))
      throw new Error("invalid_profile_selection");
    for (const profile of profiles) identifier(profile);
    const operations = request.operations === undefined ? undefined : [...request.operations];
    if (operations !== undefined) {
      if (!Array.isArray(request.operations) || operations.length < 1 || operations.length > 64 ||
          new Set(operations).size !== operations.length) throw new Error("invalid_admission_request");
      for (const operation of operations) identifier(operation);
      operations.sort();
      if (!request.disruptive && !backgroundOperations(operations)) throw new Error("invalid_admission_impact");
    }
    const copy = Object.freeze({ requestId: request.requestId, surfaces: Object.freeze([...request.surfaces].sort()),
      profileIds: Object.freeze(profiles), disruptive: request.disruptive, reason: request.reason,
      ...(operations === undefined ? {} : { operations: Object.freeze(operations) }),
      waitMs: request.waitMs, durationMs: request.durationMs });
    const identity = JSON.stringify(copy);
    const duplicate = this.#intents.find(i => i.owner === owner && i.request.requestId === request.requestId);
    if (duplicate) {
      if (duplicate.identity !== identity) throw new Error("admission_idempotency_conflict");
      return this.#view(duplicate);
    }
    if (this.#intents.filter(i => !i.terminal).length >= 256 ||
        this.#intents.filter(i => i.owner === owner && !i.terminal).length >= 4) throw new Error("admission_queue_full");
    const resources = [...(copy.surfaces.includes("desktop") ? ["desktop"] : []), ...profiles.map(id => `browser:${id}`),
      ...(copy.disruptive ? ["human-input"] : [])];
    const intent: Intent = {
      id: `intent:${++this.#sequence}`, owner, request: copy, identity, resources,
      deadline: this.#now + copy.waitMs, taskDeadline: this.#now + copy.waitMs + copy.durationMs,
      approvals: new Map(), heartbeat: this.#now + 60_000, state: "waiting_for_resource",
      terminal: null, offer: 0, offerDeadline: 0, noticeDeadline: 0, announced: false, session: null,
      activeDeadline: 0, generations: {},
    };
    this.#intents.push(intent);
    this.#emit(intent, "requested");
    this.tick();
    return this.#view(intent);
  }
  inspect(owner: AdmissionOwner, id: string, heartbeat = false) {
    this.tick();
    const intent = this.#owned(owner, id);
    if (heartbeat && !intent.terminal) intent.heartbeat = this.#now + (intent.session ? 5000 : 60_000);
    return this.#view(intent);
  }
  accept(owner: AdmissionOwner, id: string, offer: number) {
    this.tick();
    const intent = this.#owned(owner, id);
    if (intent.state !== "offered" || intent.offer !== offer) throw new Error("stale_activation_offer");
    intent.session = `session:${++this.#sequence}`;
    intent.state = "active";
    intent.activeDeadline = Math.min(this.#now + intent.request.durationMs, intent.taskDeadline);
    intent.heartbeat = this.#now + 5000;
    for (const resource of intent.resources) {
      const generation = (this.#resourceGenerations.get(resource) ?? 0) + 1;
      this.#resourceGenerations.set(resource, generation);
      intent.generations[resource] = generation;
    }
    ++this.#revision;
    this.#emit(intent, "active");
    return this.#view(intent);
  }
  authorize(owner: AdmissionOwner, fence: SessionFence, operation?: string): string | null {
    this.tick();
    const intent = this.#owned(owner, fence.intentId);
    const refuse = (reason: string) => { this.#emit(intent, "rejected", reason); return reason; };
    if (!intent.session || intent.session !== fence.sessionId || intent.state !== "active") return refuse("stale_control_session");
    if (Object.keys(fence.resourceGenerations).length !== intent.resources.length ||
        intent.resources.some(resource => fence.resourceGenerations[resource] !== intent.generations[resource])) return refuse("stale_generation");
    if (operation !== undefined && !["capabilities", "browser.profiles"].includes(operation)) {
      if (intent.request.operations && !intent.request.operations.includes(operation)) return refuse("operation_not_permitted_by_control_channel");
      if (!intent.request.surfaces.includes(operation.startsWith("browser.") ? "browser" : "desktop"))
        return refuse("operation_not_permitted_by_control_channel");
    }
    return null;
  }
  renew(owner: AdmissionOwner, fence: SessionFence, durationMs: number) {
    duration(durationMs, 1000, 900_000);
    const refusal = this.authorize(owner, fence);
    if (refusal) throw new Error(refusal);
    const intent = this.#owned(owner, fence.intentId);
    const consent = Math.min(...intent.request.surfaces.map(surface => this.#config(surface).expiresAt));
    intent.activeDeadline = Math.min(consent, Math.max(intent.activeDeadline, this.#now + durationMs));
    // Only this explicit live-owner operation can extend the task. Heartbeat,
    // pause and resumed waits leave its ceiling unchanged.
    intent.taskDeadline = Math.max(intent.taskDeadline, intent.activeDeadline);
    intent.heartbeat = this.#now + 5000;
    ++this.#revision;
    this.#emit(intent, "renewed");
    return this.#view(intent);
  }
  /** Operator approval is task-specific and stays within the original ceiling. */
  approve(id: string): void {
    this.tick();
    const intent = this.#live(id);
    for (const surface of intent.request.surfaces) {
      const config = this.#config(surface);
      if (config.mode === "ask") intent.approvals.set(surface, config.generation);
    }
    this.#emit(intent, "approved");
    this.tick();
  }
  startNow(id: string): void {
    this.tick();
    const intent = this.#live(id);
    // The countdown can finish between drawing the notice and its click.
    // Acknowledgement never revives the old session or overrides a manual,
    // protected/readiness block, missing approval or resource contention.
    if (intent.state === "paused" && intent.announced && this.#humanCooldownUntil > this.#now &&
        this.#blocks(intent).every(block => block === "physical_takeover") &&
        intent.request.surfaces.every(surface => {
          const available = this.#available(surface), config = this.#config(surface);
          return this.#inputReady && this.#globalPauses.size === 0 && available.ready && available.pauses.size === 0 &&
            (config.mode !== "ask" || intent.approvals.get(surface) === config.generation);
        })) {
      this.#humanCooldownUntil = 0;
      this.tick();
    }
    if (intent.state === "offered" || intent.state === "active") return;
    if (intent.state !== "announcing") throw new Error("stale_activation_notice");
    intent.noticeDeadline = this.#now;
    this.#emit(intent, "start_now");
    // Adapter drains/acknowledges the operator input before calling this method.
    this.tick();
  }
  cancel(owner: AdmissionOwner, id: string): void {
    this.tick();
    const intent = this.#owned(owner, id);
    if (!intent.terminal) this.#finish(intent, "cancelled");
    this.tick();
  }
  deny(id: string): void {
    this.tick();
    this.#finish(this.#live(id), "denied_by_person");
    this.tick();
  }
  defer(id: string, milliseconds: number | null): void {
    this.tick();
    if (milliseconds !== null) duration(milliseconds, 1, 28_800_000);
    const intent = this.#live(id);
    for (const resource of intent.resources) {
      const origins = this.#deferrals.get(resource) ?? new Map<Surface, number>();
      for (const surface of intent.request.surfaces)
        origins.set(surface, milliseconds === null ? Infinity : this.#now + milliseconds);
      this.#deferrals.set(resource, origins);
    }
    this.#emit(intent, "deferred");
    this.tick();
  }
  stop(reason = "stopped"): void {
    for (const intent of this.#intents) if (!intent.terminal) this.#finish(intent, reason);
    for (const config of this.#configuration.values()) { config.mode = "off"; config.expiresAt = 0; ++config.generation; }
    this.#deferrals.clear(); this.#takeoverSurfaces.clear(); this.#humanCooldownUntil = 0;
    ++this.#revision;
    this.#event({ event: "stopped" });
  }
  tick(): void {
    const now = this.#now;
    const yielded: Intent[] = [];
    for (const [resource, origins] of this.#deferrals) {
      for (const [surface, deadline] of origins) if (now >= deadline) origins.delete(surface);
      if (!origins.size) this.#deferrals.delete(resource);
    }
    for (const [reason, deadline] of this.#globalPauses) if (now >= deadline) this.#globalPauses.delete(reason);
    for (const availability of this.#availability.values())
      for (const [reason, deadline] of availability.pauses)
        if (now >= deadline) availability.pauses.delete(reason);
    for (const intent of this.#intents) {
      if (intent.terminal) continue;
      const denied = this.#denied(intent);
      if (denied) { this.#finish(intent, denied); continue; }
      if (now >= intent.heartbeat) { this.#finish(intent, intent.session ? "owner_disconnected" : "queue_lease_expired"); continue; }
      if (now >= intent.taskDeadline || (intent.session && now >= intent.activeDeadline)) { this.#finish(intent, "duration_expired"); continue; }
      if (intent.session && this.#blocks(intent).length > 0) {
        this.#release(intent, "paused");
        intent.heartbeat = now + 60_000;
        // Active work can outlive its original queue wait. Each yield receives
        // a new waiting period, including the handoff, under the task ceiling.
        intent.deadline = Math.min(intent.taskDeadline, now + Math.max(intent.request.waitMs,
          Math.max(0, this.#humanCooldownUntil - now) + this.#noticeMs + 15_000));
        intent.state = "paused";
        this.#emit(intent, "paused");
        yielded.push(intent);
      }
      if (!intent.session && now >= intent.deadline) { this.#finish(intent, "wait_deadline_exceeded"); continue; }
      if (intent.state === "offered" && now >= intent.offerDeadline) this.#finish(intent, "activation_offer_expired");
    }
    for (const intent of yielded) { this.#intents.splice(this.#intents.indexOf(intent), 1); this.#intents.push(intent); }
    const reserved = new Set(this.#intents.filter(i => i.session).flatMap(i => i.resources));
    for (const intent of this.#intents) {
      if (intent.terminal || intent.session) continue;
      const blocks = this.#blocks(intent);
      const approval = intent.request.surfaces.some(surface => this.#config(surface).mode === "ask" && intent.approvals.get(surface) !== this.#config(surface).generation);
      const state = blocks.length ? "paused" :
        intent.resources.some(resource => reserved.has(resource)) ? "waiting_for_resource" :
        approval ? "waiting_for_approval" : null;
      if (state) {
        if (intent.state !== state) { intent.state = state; intent.offer = 0; ++this.#revision; this.#emit(intent, state); }
        // Waiting for permission owns nothing. In particular Desktop Ask must
        // not prevent an independently automatic Browser task from warning.
        // Native presenters coalesce approval notices without reserving work.
        continue;
      }
      for (const resource of intent.resources) reserved.add(resource);
      if (!["announcing", "offered"].includes(intent.state)) {
        intent.noticeDeadline = now + (intent.request.disruptive && intent.request.surfaces.some(surface => this.#available(surface).noticeVisible) ? this.#noticeMs : 0);
        intent.announced ||= intent.noticeDeadline > now;
        intent.state = "announcing";
        ++this.#revision;
        this.#emit(intent, "announcing");
      }
      if (intent.state === "announcing" && now >= intent.noticeDeadline) {
        intent.state = "offered";
        intent.offerDeadline = now + 15_000;
        intent.offer = ++this.#revision;
        this.#emit(intent, "offered");
      }
    }
    const terminal = this.#intents.filter(i => i.terminal);
    for (const intent of terminal.slice(0, Math.max(0, terminal.length - 256)))
      this.#intents.splice(this.#intents.indexOf(intent), 1);
  }
  nextDeadline(): number | null {
    this.tick();
    const deadlines: number[] = [];
    for (const origins of this.#deferrals.values()) deadlines.push(...origins.values());
    deadlines.push(...this.#globalPauses.values());
    if (this.#humanCooldownUntil > this.#now) deadlines.push(this.#humanCooldownUntil);
    for (const config of this.#configuration.values()) if (config.expiresAt > this.#now) deadlines.push(config.expiresAt);
    for (const availability of this.#availability.values()) deadlines.push(...availability.pauses.values());
    for (const intent of this.#intents) {
      if (intent.terminal) continue;
      deadlines.push(intent.heartbeat, intent.taskDeadline, intent.session ? intent.activeDeadline : intent.deadline);
      if (intent.state === "announcing") deadlines.push(intent.noticeDeadline);
      if (intent.state === "offered") deadlines.push(intent.offerDeadline);
    }
    const finite = deadlines.filter(Number.isFinite);
    return finite.length ? Math.min(...finite) : null;
  }
  status() {
    this.tick();
    return {
      schema: admissionSchema, available: true, revision: this.#revision, ownerBinding: "admitted_channel", noticeSeconds: this.#noticeMs / 1000,
      handoffCooldownRemainingSeconds: Math.max(0, this.#humanCooldownUntil - this.#now) / 1000,
      humanInputReady: this.#inputReady,
      globalPauses: [...this.#globalPauses].map(([reason, until]) => ({ reason, remainingSeconds: Number.isFinite(until) ? Math.max(0, until - this.#now) / 1000 : null })),
      deferrals: [...this.#deferrals].map(([resource, origins]) => { const until = Math.max(...origins.values()); return ({ resource, remainingSeconds: Number.isFinite(until) ? Math.max(0, until - this.#now) / 1000 : null }); }),
      surfaces: this.#surfaceViews(),
      waiting: this.#intents.filter(i => !i.terminal && !i.session).length,
      active: this.#intents.filter(i => i.session).length,
      requests: this.#intents.filter(i => !i.terminal).map(i => this.#view(i)),
    };
  }
  /** Native dispatch/observation facts without task text or full intent views. */
  query() {
    this.tick();
    const requests = this.#intents.filter(i => !i.terminal);
    return { schema: admissionSchema, available: true, revision: this.#revision,
      humanInputReady: this.#inputReady, surfaces: this.#surfaceViews(),
      active: requests.filter(i => i.session).length,
      activeDesktop: requests.some(i => i.session && i.request.surfaces.includes("desktop")),
      requests: requests.map(i => ({ intentId: i.id, sessionId: i.session, state: i.state, surfaces: [...i.request.surfaces] })) };
  }
  #surfaceViews() {
    return Object.fromEntries(surfaces.map(surface => {
        const config = this.#config(surface), available = this.#available(surface);
        return [surface, {
          mode: config.mode, expired: config.mode !== "off" && this.#now >= config.expiresAt,
          consentRemainingSeconds: Number.isFinite(config.expiresAt) ? Math.max(0, config.expiresAt - this.#now) / 1000 : null,
          profileIds: [...config.profiles].sort(), ready: available.ready, noticeVisible: available.noticeVisible,
          pauses: [...available.pauses, ...this.#globalPauses].map(([reason, until]) => ({ reason, remainingSeconds: Number.isFinite(until) ? Math.max(0, until - this.#now) / 1000 : null })),
        }];
      }));
  }
  get #now(): number { return this.#clock.now(); }
  #config(surface: Surface): Configuration {
    const config = this.#configuration.get(surface);
    if (!config) throw new Error("unknown_surface");
    return config;
  }
  #available(surface: Surface): Availability {
    const available = this.#availability.get(surface);
    if (!available) throw new Error("unknown_surface");
    return available;
  }
  #owner(owner: AdmissionOwner): void {
    if (!this.#owners.has(owner)) throw new Error("admission_owner_mismatch");
  }
  #owned(owner: AdmissionOwner, id: string): Intent {
    this.#owner(owner);
    const intent = this.#intents.find(i => i.id === id && i.owner === owner);
    if (!intent) throw new Error("admission_owner_mismatch");
    return intent;
  }
  #live(id: string): Intent {
    const intent = this.#intents.find(i => i.id === id && !i.terminal);
    if (!intent) throw new Error("stale_activation_notice");
    return intent;
  }
  #denied(intent: Intent): string | null {
    for (const surface of intent.request.surfaces) {
      const config = this.#config(surface);
      if (config.mode === "off") return "surface_disabled";
      if (this.#now >= config.expiresAt) return "consent_expired";
      if (surface === "browser" && intent.request.profileIds?.some(id => !config.profiles.has(id))) return "profile_not_approved";
    }
    return null;
  }
  #blocks(intent: Intent): string[] {
    return [...new Set([...intent.request.surfaces.flatMap(surface => {
      const available = this.#available(surface);
      return [...available.pauses.keys(), ...(available.ready ? [] : ["resource_unavailable"])];
    }), ...this.#globalPauses.keys(), ...(intent.request.disruptive && !this.#inputReady ? ["activity_unknown"] : []), ...(intent.request.disruptive && this.#humanCooldownUntil > this.#now ? ["physical_takeover"] : []),
      ...(intent.resources.some(resource => this.#deferrals.has(resource)) ? ["operator_deferral"] : [])])].sort();
  }
  #release(intent: Intent, reason: string): void {
    if (!intent.session) return;
    this.#emit(intent, "yielded", reason);
    for (const resource of intent.resources) this.#resourceGenerations.set(resource, (this.#resourceGenerations.get(resource) ?? 0) + 1);
    intent.session = null;
    intent.generations = {};
    intent.offer = 0;
    ++this.#revision;
  }
  #finish(intent: Intent, reason: string): void {
    this.#release(intent, reason);
    intent.terminal = reason;
    intent.state = "ended";
    ++this.#revision;
    this.#emit(intent, "ended", reason);
  }
  #emit(intent: Intent, event: AdmissionEvent["event"], reason?: string): void {
    this.#event({ event, surface: intent.request.surfaces.length === 2 ? "all" : intent.request.surfaces[0]!, intentId: intent.id,
      ...(intent.session ? { sessionId: intent.session } : {}), ...(reason === undefined ? {} : { reason }) });
  }
  #view(intent: Intent) {
    return {
      schema: admissionSchema, revision: this.#revision, intentId: intent.id, state: intent.state,
      renewal: "owner_connection/v1",
      terminalReason: intent.terminal, offerGeneration: intent.offer, sessionId: intent.session,
      resourceGenerations: { ...intent.generations }, blockingReasons: this.#blocks(intent),
      surfaces: [...intent.request.surfaces], profileIds: [...(intent.request.profileIds ?? [])],
      waitRemainingSeconds: Math.max(0, intent.deadline - this.#now) / 1000,
      leaseRemainingSeconds: Math.max(0, intent.heartbeat - this.#now) / 1000,
      offerRemainingSeconds: intent.state === "offered" ? Math.max(0, intent.offerDeadline - this.#now) / 1000 : null,
      noticeRemainingSeconds: intent.state === "announcing" ? Math.max(0, intent.noticeDeadline - this.#now) / 1000 : null,
      activeRemainingSeconds: intent.session ? Math.max(0, intent.activeDeadline - this.#now) / 1000 : null,
      reason: intent.request.reason, maximumDurationSeconds: intent.request.durationMs / 1000,
    };
  }
}
