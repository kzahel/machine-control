/** Inherited, trusted-native-host channel. Never expose this inlet to agents. */
import { randomUUID } from "node:crypto";
import { performance } from "node:perf_hooks";
import { ResidentCore, CoreError } from "../src/core.ts";
import type { Approval, BrowserRequest, Effect } from "../src/core.ts";
import { ExtensionProvider } from "../src/extension-provider.ts";
import type { NativeFrame } from "../src/extension-provider.ts";
import { dispatchToProvider } from "../src/provider-dispatch.ts";

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
  readonly core = new ResidentCore({ now: () => Math.floor(performance.now()) });
  readonly #send: (frame: NativeFrame) => void;
  readonly #providers = new Map<string, ExtensionProvider>();
  readonly #retired = new Set<string>();
  #approval: Approval | undefined;
  #hello = false;
  #sequence = 0;
  #closed = false;

  constructor(send: (frame: NativeFrame) => void) {
    this.#send = send;
  }

  receive(frame: NativeFrame): void {
    if (this.#closed) throw new Error("host_closed");
    const id = string(frame.id);
    try {
      if (!this.#hello && frame.method !== "hello")
        throw new Error("host_handshake_required");
      const data = this.#invoke(frame);
      this.#send({ type: "reply", id, ok: true, data });
    } catch (error) {
      // Never reflect input or stack/page data into diagnostics.
      const code = error instanceof CoreError ? error.code : "invalid_host_request";
      this.#send({ type: "reply", id, ok: false, errorCode: code });
    }
  }

  tick(): void {
    if (this.#closed || !this.#hello) return;
    this.#consume(this.core.tick());
    this.#synchronize();
  }

  wakeInMs(): number | null {
    const deadline = this.core.nextDeadline();
    return deadline === null ? null : Math.max(1, deadline - Math.floor(performance.now()));
  }

  close(): void {
    if (this.#closed) return;
    // Revoke before native cleanup. EOF never restores or serializes consent.
    this.#consume(this.core.stop());
    this.#approval = undefined;
    this.#synchronize();
    this.#closed = true;
    this.#providers.clear();
  }

  #provider(value: unknown): ExtensionProvider {
    const provider = this.#providers.get(string(value));
    if (!provider) throw new Error("unknown_connection");
    return provider;
  }

  #invoke(frame: NativeFrame): unknown {
    switch (frame.method) {
      case "hello":
        if (this.#hello || frame.protocolVersion !== 1)
          throw new Error("host_protocol_mismatch");
        this.#hello = true;
        return { protocolVersion: 1, bootId: this.bootId };
      case "state":
        this.tick();
        return { bootId: this.bootId, ...this.core.inspect(), host: {
          engine: process.versions.bun ? "bun" : "node",
          version: process.versions.bun ?? process.versions.node,
          rssBytes: process.memoryUsage().rss,
        } };
      case "provider.connect": {
        this.#prune();
        if (this.#providers.size >= 80) throw new Error("host_capacity");
        const connection = this.core.connect(string(frame.profileId), "chrome.extension/cdp");
        const connectionId = `${this.bootId}:${++this.#sequence}`;
        const provider = new ExtensionProvider(this.core, connection, {
          send: (payload) => this.#send({ type: "provider.send", connectionId, frame: payload }),
          effects: (effects) => this.#consume(effects),
          fault: () => this.#send({ type: "provider.close", connectionId }),
        });
        this.#providers.set(connectionId, provider);
        provider.synchronize();
        return { connectionId, generation: connection.generation };
      }
      case "provider.disconnect": {
        const provider = this.#provider(frame.connectionId);
        provider.disconnected();
        this.#retired.add(string(frame.connectionId));
        this.#prune();
        return {};
      }
      case "provider.frame": {
        const provider = this.#provider(frame.connectionId);
        const applied = provider.receive(object(frame.frame));
        this.#prune();
        return { applied };
      }
      case "operator.approve": {
        if (!Array.isArray(frame.connectionIds)) throw new Error("invalid_host_request");
        const providers = frame.connectionIds.map((value) => this.#provider(value));
        const granted = this.core.approve(providers.map((provider) => provider.connection), integer(frame.durationMs));
        this.#approval = granted.approval;
        this.#consume(granted.effects);
        this.#synchronize();
        return { generation: granted.approval.generation };
      }
      case "operator.stop":
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
          this.#send({ type: "request.finished", result: {
            ...common, operation: frame.operation, accepted: false,
            actualRoute: provider.connection.route, providerGeneration: provider.connection.generation,
            errorCode: "approval_required", delivery: "refused", effect: "refused",
            uncertainty: "none", retrySafety: "safe_not_dispatched",
          } });
          return {};
        }
        let request: BrowserRequest;
        if (frame.operation === "browser.tabs") {
          request = { ...common, operation: frame.operation, connection: provider.connection };
        } else if (frame.operation === "browser.snapshot") {
          request = { ...common, operation: frame.operation, connection: provider.connection, tabId: integer(frame.tabId) };
        } else if (frame.operation === "browser.click") {
          const prefix = this.#referencePrefix(provider.connection.generation);
          if (typeof frame.reference !== "string" || frame.reference.length > 768)
            throw new Error("invalid_host_request");
          if (!frame.reference.startsWith(prefix)) {
            this.#send({ type: "request.finished", result: {
              ...common, operation: frame.operation, accepted: false,
              actualRoute: provider.connection.route, providerGeneration: provider.connection.generation,
              errorCode: "stale_reference", delivery: "refused", effect: "refused",
              uncertainty: "none", retrySafety: "safe_not_dispatched",
            } });
            return {};
          }
          request = { ...common, operation: frame.operation, reference: {
            connection: provider.connection, target: frame.reference.slice(prefix.length),
          } };
        } else throw new Error("invalid_host_request");
        // The core refuses an absent approval through the normal typed path.
        const approval = this.#approval ?? Object.freeze({ generation: 0, profiles: [], expiresAt: 0 });
        this.#consume(this.core.request(approval, request));
        return {};
      }
      default:
        throw new Error("unknown_host_method");
    }
  }

  #consume(effects: readonly Effect[]): void {
    for (const effect of effects) {
      if (effect.type === "request.finished") {
        const result = effect.result;
        if (result.accepted && result.operation === "browser.snapshot") {
          const data = object(result.data);
          if (!Array.isArray(data.elements)) throw new Error("invalid_provider_data");
          const prefix = this.#referencePrefix(result.providerGeneration!);
          this.#send({ type: "request.finished", result: { ...result, data: {
            ...data, elements: data.elements.map((element) => {
              const value = object(element);
              return { ...value, reference: prefix + value.reference };
            }),
          } } });
        } else this.#send({ type: "request.finished", result });
      } else {
        const provider = [...this.#providers.values()].find((item) => item.connection === effect.command.connection);
        if (!provider) continue;
        if (effect.type === "provider.dispatch")
          dispatchToProvider(this.core, provider, effect.command, (effects) => this.#consume(effects));
        else provider.cancel(effect.command);
      }
    }
  }

  #synchronize(): void {
    for (const provider of this.#providers.values()) provider.synchronize();
  }

  #referencePrefix(connectionGeneration: number): string {
    return `${this.bootId}:${connectionGeneration}:${this.#approval?.generation ?? 0}:`;
  }

  #prune(): void {
    for (const id of this.#retired) {
      if (this.#providers.get(id)?.pendingCount === 0) {
        this.#providers.delete(id);
        this.#retired.delete(id);
      }
    }
  }
}
