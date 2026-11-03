/** Private native transport fixture. Policy and adapters live in the child. */
import { createServer } from "node:net";
import type { Server, Socket } from "node:net";
import { chmod } from "node:fs/promises";
import { join } from "node:path";
import type {
  ActionResult,
  Approval,
  BrowserRequest,
  ProviderConnection,
} from "../src/core.ts";
import type { NativeFrame } from "../src/extension-provider.ts";
import { FrameDecoder, writeFrame } from "../node/framing.ts";
import { ProcessClient } from "./process-client.ts";

interface Peer {
  socket: Socket;
  processId?: number;
  connectionId?: string;
  connection?: ProviderConnection;
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
  deliver?: () => Promise<boolean>;
}

export class BrowserHost {
  readonly nativeProcessIds = new Set<number>();
  readonly providerErrors: NativeFrame[] = [];
  readonly #endpoints = new Map<string, Endpoint>();
  readonly #peers = new Map<string, Peer>();
  readonly #early = new Map<string, NativeFrame[]>();
  readonly #waiting = new Map<
    string,
    { resolve(value: ActionResult): void; reject(error: Error): void }
  >();
  readonly #gates = new Map<string, Gate>();
  #client: ProcessClient;
  #closing = false;
  #wireRequests = 0;

  constructor() {
    this.#client = this.#newClient();
  }
  #newClient(): ProcessClient {
    return new ProcessClient(
      (frame) => this.#event(frame),
      () => {
        // Death must close the browser transport, even without a final grant.
        for (const endpoint of this.#endpoints.values())
          for (const peer of endpoint.peers) peer.socket.destroy();
        for (const waiting of this.#waiting.values())
          waiting.reject(new Error("fixture_policy_died"));
        this.#waiting.clear();
      },
    );
  }

  async listen(root: string, profiles: readonly string[]): Promise<void> {
    await this.#client.start();
    try {
      for (const profile of profiles) {
        const socketPath = join(root, `${profile}.sock`);
        const server = createServer((socket) => this.#accept(profile, socket));
        this.#endpoints.set(profile, { server, socketPath, peers: new Set() });
        await new Promise<void>((resolve, reject) => {
          server.once("error", reject);
          server.listen(socketPath, resolve);
        });
        await chmod(socketPath, 0o600);
      }
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  socketPath(profile: string): string {
    return this.#endpoints.get(profile)!.socketPath;
  }
  connection(profile: string): ProviderConnection | undefined {
    return this.#endpoints.get(profile)?.current?.connection;
  }
  get wireRequests(): number {
    return this.#wireRequests;
  }
  async inspect(): Promise<Record<string, unknown>> {
    return (await this.#client.call("state")) as Record<string, unknown>;
  }

  async approve(
    profiles: readonly string[],
    durationMs = 60_000,
  ): Promise<Approval> {
    const connectionIds = profiles.map((profile) => {
      const id = this.#endpoints.get(profile)?.current?.connectionId;
      if (!id) throw new Error("fixture_profile_unavailable");
      return id;
    });
    const result = (await this.#client.call("operator.approve", {
      connectionIds,
      durationMs,
    })) as { generation: number };
    return Object.freeze({
      generation: result.generation,
      profiles: Object.freeze([...profiles]),
      expiresAt: 0,
    });
  }
  async stop(): Promise<void> {
    await this.#client.call("operator.stop");
  }

  call(
    approval: Approval | undefined,
    request: BrowserRequest,
  ): Promise<ActionResult> {
    if (this.#waiting.has(request.requestId))
      return Promise.reject(new Error("fixture_request_conflict"));
    const peer = this.#endpoints.get(request.profileId)?.current;
    if (!peer?.connectionId)
      return Promise.reject(new Error("fixture_profile_unavailable"));
    const fields =
      "params" in request
        ? { params: request.params }
        : "reference" in request
          ? { reference: request.reference.target }
          : request.operation === "browser.snapshot"
            ? { tabId: request.tabId }
            : {};
    return new Promise((resolve, reject) => {
      this.#waiting.set(request.requestId, { resolve, reject });
      void this.#client
        .call("request", {
          connectionId: peer.connectionId,
          authorizationGeneration: approval?.generation,
          requestId: request.requestId,
          timeoutMs: request.timeoutMs,
          operation: request.operation ?? "browser.click",
          ...fields,
        })
        .catch((error: Error) => {
          this.#waiting.delete(request.requestId);
          reject(error);
        });
    });
  }

  holdNextReply(
    profile: string,
    operation: string,
  ): { captured: Promise<void>; release(): Promise<boolean> } {
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
        const deliver = gate.deliver;
        if (!deliver) throw new Error("fixture_reply_not_captured");
        delete gate.deliver;
        return deliver();
      },
    };
  }
  dropTransport(profile: string): void {
    this.#endpoints.get(profile)?.current?.socket.destroy();
  }
  killPolicy(): void {
    this.#client.kill();
  }

  async restartPolicy(): Promise<void> {
    await this.#client.close();
    this.#peers.clear();
    this.#early.clear();
    this.#client = this.#newClient();
    await this.#client.start();
  }

  async close(): Promise<void> {
    if (this.#closing) return;
    this.#closing = true;
    try {
      await this.stop();
    } catch {
      /* Failed child is already unarmed. */
    }
    for (const endpoint of this.#endpoints.values())
      for (const peer of endpoint.peers) peer.socket.destroy();
    await Promise.all(
      [...this.#endpoints.values()].map(
        (endpoint) =>
          new Promise<void>((resolve) => {
            if (endpoint.server.listening)
              endpoint.server.close(() => resolve());
            else resolve();
          }),
      ),
    );
    await this.#client.close();
  }

  #event(message: NativeFrame): void {
    if (message.type === "browser.state") return;
    if (message.type === "request.finished") {
      const result = message.result as ActionResult;
      this.#waiting.get(result.requestId)?.resolve(result);
      this.#waiting.delete(result.requestId);
      return;
    }
    const id = String(message.connectionId);
    const peer = this.#peers.get(id);
    if (!peer) {
      if (this.#early.size >= 16) throw new Error("fixture_early_capacity");
      const early = this.#early.get(id) ?? [];
      if (early.length >= 4) throw new Error("fixture_early_capacity");
      early.push(message);
      this.#early.set(id, early);
      return;
    }
    if (message.type === "provider.close") {
      peer.socket.destroy();
      return;
    }
    const frame = message.frame as NativeFrame;
    if (frame.type === "request") {
      this.#wireRequests++;
      peer.operations.set(String(frame.id), String(frame.operation));
    }
    if (!peer.socket.destroyed) writeFrame(peer.socket, frame);
  }

  #accept(profile: string, socket: Socket): void {
    if (this.#closing) {
      socket.destroy();
      return;
    }
    const endpoint = this.#endpoints.get(profile)!;
    const peer: Peer = { socket, operations: new Map() };
    endpoint.peers.add(peer);
    const timer = setTimeout(() => socket.destroy(), 5000);
    let chain = Promise.resolve();
    const decoder = new FrameDecoder((frame) => {
      chain = chain
        .then(async () => {
          if (!peer.processId) {
            if (
              frame.type !== "fixture.native-host" ||
              typeof frame.processId !== "number" ||
              !Number.isSafeInteger(frame.processId) ||
              frame.processId < 1
            )
              throw new Error("fixture_host_required");
            peer.processId = frame.processId;
            this.nativeProcessIds.add(frame.processId);
            return;
          }
          if (!peer.connectionId) {
            if (
              frame.type !== "hello" ||
              frame.protocolVersion !== 1 ||
              typeof frame.extensionVersion !== "string" ||
              frame.extensionVersion.length > 32
            )
              throw new Error("fixture_hello_required");
            const data = (await this.#client.call("provider.connect", {
              profileId: profile,
            })) as { connectionId: string; generation: number };
            peer.connectionId = data.connectionId;
            peer.connection = Object.freeze({
              profileId: profile,
              generation: data.generation,
              route: "chrome.extension/cdp",
            });
            this.#peers.set(data.connectionId, peer);
            endpoint.current = peer;
            const early = this.#early.get(data.connectionId) ?? [];
            this.#early.delete(data.connectionId);
            for (const message of early) this.#event(message);
            clearTimeout(timer);
            return;
          }
          const operation =
            typeof frame.id === "string"
              ? peer.operations.get(frame.id)
              : undefined;
          if (frame.type === "response" && frame.ok === false) {
            this.providerErrors.push({
              profile,
              operation,
              code: frame.errorCode,
            });
            if (this.providerErrors.length > 20) this.providerErrors.shift();
          }
          if (frame.type === "response" && typeof frame.id === "string")
            peer.operations.delete(frame.id);
          const connectionId = peer.connectionId;
          const deliver = async () => {
            const result = (await this.#client.call("provider.frame", {
              connectionId,
              frame,
            })) as { applied: boolean };
            return result.applied;
          };
          const gate = this.#gates.get(profile);
          if (
            gate &&
            frame.type === "response" &&
            operation === gate.operation
          ) {
            this.#gates.delete(profile);
            gate.deliver = deliver;
            gate.captured();
          } else await deliver();
        })
        .catch(() => {
          socket.destroy();
        });
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
      if (endpoint.current === peer) delete endpoint.current;
      void chain
        .then(async () => {
          if (peer.connectionId)
            await this.#client.call("provider.disconnect", {
              connectionId: peer.connectionId,
            });
        })
        .catch(() => {});
    });
  }
}
