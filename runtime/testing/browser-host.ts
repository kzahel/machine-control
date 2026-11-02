/** Private fixture composition of the real core, protocol adapter and sockets.
 * No agent RPC, native peer identity claim, or installed registration. */
import { createServer } from "node:net";
import type { Server, Socket } from "node:net";
import { chmod } from "node:fs/promises";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { ResidentCore } from "../src/core.ts";
import type {
  ActionResult,
  Approval,
  BrowserRequest,
  Effect,
  ProviderConnection,
} from "../src/core.ts";
import { ExtensionProvider } from "../src/extension-provider.ts";
import { dispatchToProvider } from "../src/provider-dispatch.ts";
import { FrameDecoder, writeFrame } from "../node/framing.ts";

interface Peer {
  socket: Socket;
  adapter?: ExtensionProvider;
  processId?: number;
  operations: Map<string, string>;
}
interface Endpoint {
  server: Server;
  socketPath: string;
  peers: Set<Peer>;
  current?: Peer;
}
interface Gate {
  operation: string;
  captured(): void;
  deliver?: () => boolean;
}

export class BrowserHost {
  readonly core = new ResidentCore({
    now: () => Math.floor(performance.now()),
  });
  readonly nativeProcessIds = new Set<number>();
  readonly providerErrors: {
    profile: string;
    operation: string;
    code: unknown;
    message: unknown;
  }[] = [];
  readonly #endpoints = new Map<string, Endpoint>();
  readonly #adapters = new Map<ProviderConnection, ExtensionProvider>();
  readonly #waiting = new Map<string, (result: ActionResult) => void>();
  readonly #gates = new Map<string, Gate>();
  #timer: ReturnType<typeof setInterval> | undefined;
  #closing = false;
  #wireRequests = 0;

  async listen(root: string, profiles: readonly string[]): Promise<void> {
    try {
      for (const profile of profiles) {
        if (!/^[a-z]{1,24}$/.test(profile) || this.#endpoints.has(profile))
          throw new Error("invalid_fixture_profile");
        const socketPath = join(root, `${profile}.sock`);
        const server = createServer((socket) => this.#accept(profile, socket));
        server.maxConnections = 4;
        const endpoint: Endpoint = { server, socketPath, peers: new Set() };
        this.#endpoints.set(profile, endpoint);
        await new Promise<void>((resolve, reject) => {
          server.once("error", reject);
          server.listen(socketPath, () => {
            server.removeListener("error", reject);
            resolve();
          });
        });
        await chmod(socketPath, 0o600);
      }
      this.#timer = setInterval(() => {
        this.#consume(this.core.tick());
        this.#synchronize();
      }, 10);
      this.#timer.unref();
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  socketPath(profile: string): string {
    const endpoint = this.#endpoints.get(profile);
    if (!endpoint) throw new Error("unknown_fixture_profile");
    return endpoint.socketPath;
  }

  connection(profile: string): ProviderConnection | undefined {
    return this.#endpoints.get(profile)?.current?.adapter?.connection;
  }

  get wireRequests(): number {
    return this.#wireRequests;
  }

  approve(profiles: readonly string[], durationMs = 60_000): Approval {
    const connections = profiles.map((profile) => {
      const connection = this.connection(profile);
      if (!connection) throw new Error("fixture_profile_unavailable");
      return connection;
    });
    const result = this.core.approve(connections, durationMs);
    this.#synchronize();
    this.#consume(result.effects);
    return result.approval;
  }

  stop(): void {
    const effects = this.core.stop();
    this.#synchronize();
    this.#consume(effects);
  }

  call(approval: Approval, request: BrowserRequest): Promise<ActionResult> {
    if (this.#waiting.has(request.requestId))
      return Promise.reject(new Error("fixture_request_conflict"));
    return new Promise((resolve, reject) => {
      this.#waiting.set(request.requestId, resolve);
      try {
        this.#consume(this.core.request(approval, request));
      } catch (error) {
        this.#waiting.delete(request.requestId);
        reject(error);
      }
    });
  }

  holdNextReply(
    profile: string,
    operation: string,
  ): { captured: Promise<void>; release(): boolean } {
    if (this.#gates.has(profile))
      throw new Error("fixture_gate_already_exists");
    let captured!: () => void;
    const promise = new Promise<void>((resolve) => {
      captured = resolve;
    });
    const gate: Gate = { operation, captured };
    this.#gates.set(profile, gate);
    return {
      captured: promise,
      release: () => {
        if (!gate.deliver) throw new Error("fixture_reply_not_captured");
        const deliver = gate.deliver;
        delete gate.deliver;
        return deliver();
      },
    };
  }

  dropTransport(profile: string): void {
    const peer = this.#endpoints.get(profile)?.current;
    if (!peer) throw new Error("fixture_profile_unavailable");
    peer.socket.destroy();
  }

  async close(): Promise<void> {
    if (this.#closing) return;
    this.#closing = true;
    if (this.#timer) clearInterval(this.#timer);
    this.stop();
    for (const endpoint of this.#endpoints.values()) {
      for (const peer of endpoint.peers) peer.socket.destroy();
    }
    await Promise.all(
      [...this.#endpoints.values()].map(
        (endpoint) =>
          new Promise<void>((resolve) => {
            if (!endpoint.server.listening) {
              resolve();
              return;
            }
            endpoint.server.close(() => resolve());
          }),
      ),
    );
  }

  #consume(effects: readonly Effect[]): void {
    for (const effect of effects) {
      if (effect.type === "request.finished") {
        const resolve = this.#waiting.get(effect.result.requestId);
        this.#waiting.delete(effect.result.requestId);
        resolve?.(effect.result);
      } else {
        const adapter = this.#adapters.get(effect.command.connection);
        if (effect.type === "provider.dispatch" && adapter)
          dispatchToProvider(this.core, adapter, effect.command, (effects) =>
            this.#consume(effects),
          );
        else adapter?.cancel(effect.command);
      }
    }
  }

  #synchronize(): void {
    for (const adapter of this.#adapters.values()) adapter.synchronize();
  }

  #accept(profile: string, socket: Socket): void {
    if (this.#closing) {
      socket.destroy();
      return;
    }
    const endpoint = this.#endpoints.get(profile)!;
    const peer: Peer = { socket, operations: new Map() };
    endpoint.peers.add(peer);
    const timer = setTimeout(() => socket.destroy(), 5_000);
    const decoder = new FrameDecoder((frame) => {
      if (!peer.processId) {
        if (
          frame.type !== "fixture.native-host" ||
          typeof frame.processId !== "number" ||
          !Number.isSafeInteger(frame.processId) ||
          frame.processId < 1
        )
          throw new Error("fixture_host_required");
        peer.processId = frame.processId;
        this.nativeProcessIds.add(frame.processId); // observation only, never a kill target
        return;
      }
      if (!peer.adapter) {
        if (
          frame.type !== "hello" ||
          frame.protocolVersion !== 1 ||
          typeof frame.extensionVersion !== "string" ||
          frame.extensionVersion.length > 32
        )
          throw new Error("fixture_hello_required");
        const connection = this.core.connect(profile, "chrome.extension/cdp");
        const adapter = new ExtensionProvider(this.core, connection, {
          send: (message) => {
            if (message.type === "request") {
              this.#wireRequests++;
              peer.operations.set(
                String(message.id),
                String(message.operation),
              );
            }
            writeFrame(socket, message);
          },
          effects: (effects) => this.#consume(effects),
          fault: () => socket.destroy(),
        });
        peer.adapter = adapter;
        endpoint.current = peer;
        this.#adapters.set(connection, adapter);
        clearTimeout(timer);
        adapter.synchronize();
        return;
      }
      const operation =
        typeof frame.id === "string"
          ? peer.operations.get(frame.id)
          : undefined;
      if (frame.type === "response" && frame.ok === false) {
        this.providerErrors.push({
          profile,
          operation: operation ?? "unknown",
          code: frame.errorCode,
          message: frame.message,
        });
        if (this.providerErrors.length > 20) this.providerErrors.shift();
      }
      if (frame.type === "response" && typeof frame.id === "string")
        peer.operations.delete(frame.id);
      const gate = this.#gates.get(profile);
      if (gate && frame.type === "response" && operation === gate.operation) {
        this.#gates.delete(profile);
        const adapter = peer.adapter;
        gate.deliver = () => adapter.receive(frame);
        gate.captured();
      } else peer.adapter.receive(frame);
    });
    socket.on("data", (chunk) => {
      try {
        decoder.push(chunk);
      } catch {
        socket.destroy();
      }
    });
    socket.on("error", () => {});
    socket.on("close", () => {
      clearTimeout(timer);
      endpoint.peers.delete(peer);
      if (peer.adapter) {
        peer.adapter.disconnected();
        this.#adapters.delete(peer.adapter.connection);
      }
      if (endpoint.current === peer) delete endpoint.current;
    });
  }
}
