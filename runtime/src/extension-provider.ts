/** Typed adapter for the existing extension protocol; the core owns authority. */
import { parameters } from "./browser-contract.ts";
import { ResidentCore } from "./core.ts";
import type {
  DispatchCommand,
  Effect,
  ProviderAdapter,
  ProviderConnection,
} from "./core.ts";

export type NativeFrame = Readonly<Record<string, unknown>>;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid_provider_data");
  return value as Record<string, unknown>;
}

function text(value: unknown, limit: number): string {
  if (typeof value !== "string" || value.length > limit)
    throw new Error("invalid_provider_data");
  return value;
}

function tabId(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1)
    throw new Error("invalid_provider_data");
  return value;
}

/** Strip undeclared fields and bound observations before returning them. */
function observation(command: DispatchCommand, value: unknown): unknown {
  const data = record(value);
  if ("params" in command) return parameters(data, 48 * 1024 * 1024);
  if (command.operation === "browser.tabs") {
    if (!Array.isArray(data.tabs) || data.tabs.length > 256)
      throw new Error("invalid_provider_data");
    const tabs = data.tabs.map((value) => {
      const tab = record(value);
      return Object.freeze({
        tabId: tabId(tab.tabId),
        title: text(tab.title, 512),
        url: text(tab.url, 8192),
      });
    });
    const info = record(data.providerInfo);
    if (
      info.protocolVersion !== 1 ||
      typeof info.operationsSha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(info.operationsSha256)
    )
      throw new Error("invalid_provider_data");
    return Object.freeze({
      tabs: Object.freeze(tabs),
      providerInfo: Object.freeze({
        extensionId: text(info.extensionId, 64),
        extensionVersion: text(info.extensionVersion, 32),
        protocolVersion: 1,
        operationsSha256: info.operationsSha256,
      }),
    });
  }
  if (command.operation === "browser.snapshot") {
    if (
      tabId(record(data.tab).tabId) !== command.tabId ||
      !Array.isArray(data.elements) ||
      data.elements.length > 64
    ) {
      throw new Error("invalid_provider_data");
    }
    return Object.freeze({
      tabId: command.tabId,
      elements: Object.freeze(
        data.elements.map((value) => {
          const element = record(value);
          return Object.freeze({
            reference: text(element.reference, 512),
            role: text(element.role, 128),
            name: text(element.name, 256),
          });
        }),
      ),
      truncated: data.truncated === true,
    });
  }
  return Object.freeze({ tabId: tabId(data.tabId) });
}

export class ExtensionProvider implements ProviderAdapter {
  readonly connection: ProviderConnection;
  readonly #core: ResidentCore;
  readonly #send: (frame: NativeFrame, command?: DispatchCommand) => void;
  readonly #effects: (effects: readonly Effect[]) => void;
  readonly #fault: () => void;
  readonly #pending = new Map<string, DispatchCommand>();
  #sequence = 0;
  #active = true;
  #published = "";

  get pendingCount(): number {
    return this.#pending.size;
  }

  constructor(
    core: ResidentCore,
    connection: ProviderConnection,
    transport: {
      send(frame: NativeFrame, command?: DispatchCommand): void;
      effects(effects: readonly Effect[]): void;
      fault(): void;
    },
  ) {
    this.#core = core;
    this.connection = connection;
    this.#send = transport.send;
    this.#effects = transport.effects;
    this.#fault = transport.fault;
  }

  /** Project the core's exact-profile state; this adapter cannot approve it. */
  synchronize(): void {
    if (!this.#active) return;
    const state = this.#core.inspect();
    const browser = state.approvedProfiles.includes(this.connection.profileId);
    const grantGeneration = `shared:${state.authorizationGeneration}:${this.connection.generation}`;
    const devtools = browser && state.devtools;
    const key = `${browser}:${devtools}:${grantGeneration}`;
    if (key === this.#published) return;
    this.#published = key;
    this.#write({ type: "grant", browser, devtools, grantGeneration });
  }

  execute(command: DispatchCommand, timeoutMs: number): void {
    if (!this.#active || command.connection !== this.connection) return;
    const params =
      "params" in command
        ? command.params
        : command.operation === "browser.click"
          ? { reference: command.target }
          : command.operation === "browser.snapshot"
            ? { tabId: command.tabId, maxElements: 64, interactiveOnly: true }
            : {};
    const id = `${this.connection.generation}:${++this.#sequence}`;
    if (timeoutMs < 100) {
      // The worker's minimum budget is 100 ms. Refuse rather than dispatch
      // with authority lasting longer than the remaining core deadline.
      this.#effects(
        this.#core.complete(this.connection, command, {
          ok: false,
          delivery: "refused",
        }).effects,
      );
    } else {
      this.#pending.set(id, command);
      this.#write(
        {
          type: "request",
          id,
          operation: command.operation,
          params,
          timeoutMs: Math.min(30_000, timeoutMs),
        },
        command,
      );
    }
  }

  cancel(command: DispatchCommand): void {
    if (!this.#active) return;
    for (const [id, pending] of this.#pending) {
      if (pending === command) {
        this.#write({ type: "cancel", id });
        return;
      }
    }
  }

  receive(frame: NativeFrame): boolean {
    if (frame.type !== "response" || typeof frame.id !== "string") return false;
    const command = this.#pending.get(frame.id);
    if (!command) return false;
    if (frame.ok !== true && frame.ok !== false) {
      this.#fail();
      return false;
    }
    try {
      const reply = frame.ok
        ? { ok: true as const, data: observation(command, frame.data) }
        : {
            ok: false as const,
            ...(typeof frame.errorCode === "string" && /^[a-z][a-z0-9_]{0,100}$/.test(frame.errorCode) ? { errorCode: frame.errorCode } : {}),
            ...(typeof frame.message === "string" ? { message: frame.message.slice(0, 512) } : {}),
            delivery:
              frame.delivery === "refused"
                ? ("refused" as const)
                : ("unknown" as const),
          };
      this.#pending.delete(frame.id);
      const completed = this.#core.complete(this.connection, command, reply);
      this.#effects(completed.effects);
      return completed.applied;
    } catch {
      this.#fail();
      return false;
    }
  }

  disconnected(): void {
    if (!this.#active) return;
    this.#active = false;
    this.#effects(this.#core.disconnect(this.connection));
  }

  #write(frame: NativeFrame, command?: DispatchCommand): void {
    try {
      this.#send(frame, command);
    } catch {
      this.#fail();
    }
  }

  #fail(): void {
    if (!this.#active) return;
    this.disconnected();
    this.#fault();
  }
}
