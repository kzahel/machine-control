/** Bounded target-loopback transport over shared stream policy and native owner checks. */
import { createServer } from "node:http";
import type { Socket } from "node:net";
import { randomBytes, randomUUID } from "node:crypto";
import { WebSocketServer, WebSocket } from "ws";
import type { RawData } from "ws";
import type { AuthorityFence, ProviderConnection } from "../src/core.ts";
import { Streams } from "../src/streams.ts";
import type { Stream } from "../src/streams.ts";
import type { NativeFrame } from "../src/extension-provider.ts";
import { strictObject } from "./strict-json.ts";
import { parameters } from "../src/browser-contract.ts";

export type NativeCheck = (
  phase: "check" | "begin" | "result",
  authorityId: string,
  auditId: string,
  delivery?: "confirmed" | "unknown",
) => Promise<boolean>;
interface Pending {
  original: number;
  session?: string;
  auditId: string;
}
interface Client {
  socket: WebSocket;
  stream: Stream;
  nextCommand: number;
  pending: Map<number, Pending>;
  openAudit: string;
  opened: boolean;
  closed: boolean;
  queuedBytes: number;
  queue: Promise<void>;
  inbound: RawData[];
  checking: boolean;
}

export class CdpBridge {
  readonly #streams: Streams;
  readonly #native: NativeCheck;
  readonly #send: (
    connection: ProviderConnection,
    frame: NativeFrame,
    authorityId?: string,
  ) => void;
  readonly #clients = new Map<string, Client>();
  readonly #server = createServer(
    { maxHeaderSize: 8192 },
    (_request, response) => response.writeHead(404).end(),
  );
  readonly #ws = new WebSocketServer({
    noServer: true,
    maxPayload: 1024 * 1024,
    perMessageDeflate: false,
  });
  readonly #start: Promise<void>;
  #port = 0;
  #monitor: ReturnType<typeof setTimeout> | undefined;
  #closed = false;

  constructor(
    streams: Streams,
    native: NativeCheck,
    send: (
      connection: ProviderConnection,
      frame: NativeFrame,
      authorityId?: string,
    ) => void,
  ) {
    this.#streams = streams;
    this.#native = native;
    this.#send = send;
    this.#server.requestTimeout = 5000;
    this.#server.headersTimeout = 5000;
    this.#server.maxConnections = 16;
    this.#server.on("connection", (socket) => {
      socket.setTimeout(5000, () => socket.destroy());
    });
    this.#server.on("upgrade", (request, socket, head) => {
      const match =
        /^\/devtools\/(?:page\/([1-9][0-9]*)|browser)\?token=([a-f0-9]{64})$/.exec(
          request.url ?? "",
        );
      const names = request.rawHeaders.filter((_value, index) => index % 2 === 0).map(name => name.toLowerCase());
      if (
        new Set(names).size !== names.length || request.httpVersion !== "1.1" ||
        request.headers.upgrade?.toLowerCase() !== "websocket" ||
        !request.headers.connection?.toLowerCase().split(",").map(value => value.trim()).includes("upgrade") ||
        request.headers["sec-websocket-version"] !== "13" ||
        typeof request.headers["sec-websocket-key"] !== "string" || !/^[A-Za-z0-9+/]{22}==$/.test(request.headers["sec-websocket-key"]) ||
        request.headers["sec-websocket-protocol"] !== undefined ||
        !match ||
        request.method !== "GET" ||
        request.headers.host !== `127.0.0.1:${this.#port}` ||
        request.headers.origin !== undefined ||
        request.headers["content-length"] !== undefined ||
        request.headers["transfer-encoding"] !== undefined ||
        this.#clients.size >= 8 ||
        this.#closed
      ) {
        socket.destroy();
        return;
      }
      const endpoint = this.#streams.lookup(match[2]!);
      if (!endpoint) {
        socket.destroy();
        return;
      }
      const tabId = match[1] ? Number(match[1]) : 0;
      const auditId = randomUUID().replaceAll("-", "");
      void this.#native("begin", endpoint.authorityId, auditId)
        .then((allowed) => {
          if (
            !allowed ||
            socket.destroyed ||
            !this.#streams.valid(endpoint) ||
            this.#closed
          ) {
            if (allowed) void this.#native("result", endpoint.authorityId, auditId, "unknown");
            socket.destroy();
            return;
          }
          let stream: Stream;
          try {
            stream = this.#streams.open(
              endpoint,
              tabId,
              randomUUID().replaceAll("-", ""),
            );
          } catch {
            void this.#native(
              "result",
              endpoint.authorityId,
              auditId,
              "unknown",
            );
            socket.destroy();
            return;
          }
          let adopted = false;
          const abandoned = () => {
            if (adopted) return;
            this.#streams.close(stream);
            void this.#native("result", endpoint.authorityId, auditId, "unknown");
          };
          socket.once("close", abandoned);
          try {
            this.#ws.handleUpgrade(request, socket, head, (ws) => {
              adopted = true;
              socket.removeListener("close", abandoned);
              (socket as Socket).setTimeout(0);
              const client: Client = {
                socket: ws,
                stream,
                nextCommand: 0,
                pending: new Map(),
                openAudit: auditId,
                opened: false,
                closed: false,
                queuedBytes: 0,
                queue: Promise.resolve(),
                inbound: [],
                checking: false,
              };
              this.#clients.set(stream.id, client);
              ws.on("error", () => this.#close(client));
              ws.on("close", () => this.#close(client));
              ws.on("message", (data, binary) => {
                if (binary) {
                  this.#close(client);
                  return;
                }
                if (!client.opened) {
                  if (client.inbound.length >= 16) {
                    this.#close(client);
                    return;
                  }
                  client.inbound.push(data);
                  return;
                }
                void this.#command(client, data).catch(() =>
                  this.#close(client),
                );
              });
              this.#send(
                endpoint.fence.connection,
                { type: "session.open", id: stream.id, tabId },
                endpoint.authorityId,
              );
              this.#schedule();
            });
          } catch {
            socket.destroy();
          }
        })
        .catch(() => socket.destroy());
    });
    this.#server.on("clientError", (_error, socket) => socket.destroy());
    this.#start = new Promise((resolve, reject) => {
      this.#server.once("error", reject);
      this.#server.listen(0, "127.0.0.1", () => {
        const address = this.#server.address();
        if (!address || typeof address === "string") {
          reject(new Error("browser_stream_unavailable"));
          return;
        }
        this.#port = address.port;
        resolve();
      });
    });
  }

  async endpoint(fence: AuthorityFence, authorityId: string): Promise<object> {
    await this.#start;
    if (this.#closed) throw new Error("browser_stream_unavailable");
    const endpoint = this.#streams.endpoint(
      fence,
      authorityId,
      randomBytes(32).toString("hex"),
    );
    return {
      devtoolsEndpoint: `ws://127.0.0.1:${this.#port}/devtools/page/<tabId>?token=${endpoint.token}`,
      browserEndpoint: `ws://127.0.0.1:${this.#port}/devtools/browser?token=${endpoint.token}`,
      browserContext: "existing_default_profile",
      binding: "live_devtools_owner",
      retainedOwnerRequired: true,
      maximumConnections: 8,
      maximumCommandBytes: 1024 * 1024,
      maximumOutstandingCommands: 16,
      commandTimeoutMs: 45000,
      applicationEffect: "not_independently_observed",
    };
  }

  async #command(client: Client, data: RawData): Promise<void> {
    const bytes = Array.isArray(data)
      ? Buffer.concat(data)
      : Buffer.isBuffer(data)
        ? data
        : Buffer.from(new Uint8Array(data));
    if (bytes.byteLength > 1024 * 1024 || client.closed)
      throw new Error("invalid_cdp_command");
    const command = strictObject(bytes.toString());
    if (
      !command ||
      typeof command !== "object" ||
      Array.isArray(command) ||
      Object.keys(command).some(
        (key) => !["id", "method", "params", "sessionId"].includes(key),
      ) ||
      !Number.isSafeInteger(command.id) ||
      (command.id as number) < 0 ||
      typeof command.method !== "string" ||
      command.method.length > 160 ||
      !/^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*$/.test(command.method) ||
      (command.sessionId !== undefined &&
        (typeof command.sessionId !== "string" ||
          !/^[A-Za-z0-9_-]{1,160}$/.test(command.sessionId)))
    )
      throw new Error("invalid_cdp_command");
    const params = parameters(command.params ?? {});
    const session = command.sessionId as string | undefined;
    this.#streams.command(client.stream, command.id as number, session);
    const wireId = ++client.nextCommand,
      auditId = randomUUID().replaceAll("-", "");
    if (wireId > 2_000_000_000) throw new Error("browser_stream_capacity");
    const pending: Pending = {
      original: command.id as number,
      auditId,
      ...(session === undefined ? {} : { session }),
    };
    client.pending.set(wireId, pending);
    const allowed = await this.#native(
      "begin",
      client.stream.endpoint.authorityId,
      auditId,
    );
    if (!allowed || client.closed || !this.#streams.active(client.stream))
      throw new Error("approval_required");
    this.#send(
      client.stream.endpoint.fence.connection,
      {
        type: "session.command",
        id: client.stream.id,
        cmdId: wireId,
        method: command.method,
        params,
        ...(session === undefined ? {} : { sessionId: session }),
      },
      client.stream.endpoint.authorityId,
    );
  }

  receive(connection: ProviderConnection, frame: NativeFrame): boolean {
    const client =
      typeof frame.id === "string" ? this.#clients.get(frame.id) : undefined;
    if (
      !client ||
      client.stream.endpoint.fence.connection !== connection ||
      client.closed
    )
      return false;
    const size = Buffer.byteLength(JSON.stringify(frame));
    client.queuedBytes += size;
    if (client.queuedBytes > 16 * 1024 * 1024) {
      this.#close(client);
      return false;
    }
    client.queue = client.queue
      .then(async () => {
        if (!this.#streams.active(client.stream) || client.closed) {
          this.#close(client);
          return;
        }
        if (frame.type === "session.opened") {
          if (
            !this.#streams.opened(client.stream) ||
            !(await this.#native(
              "result",
              client.stream.endpoint.authorityId,
              client.openAudit,
              "confirmed",
            ))
          ) {
            this.#close(client);
            return;
          }
          client.opened = true;
          for (const data of client.inbound.splice(0))
            void this.#command(client, data).catch(() => this.#close(client));
        } else if (
          frame.type === "session.failed" ||
          frame.type === "session.closed"
        )
          this.#close(client);
        else if (frame.type === "session.result") {
          const pending = client.pending.get(frame.cmdId as number);
          if (
            !pending ||
            frame.sessionId !== pending.session ||
            !this.#streams.complete(
              client.stream,
              pending.original,
              pending.session,
            )
          ) {
            this.#close(client);
            return;
          }
          client.pending.delete(frame.cmdId as number);
          if (
            !(await this.#native(
              "result",
              client.stream.endpoint.authorityId,
              pending.auditId,
              "confirmed",
            ))
          ) {
            this.#close(client);
            return;
          }
          this.#write(client, {
            id: pending.original,
            ...(pending.session === undefined
              ? {}
              : { sessionId: pending.session }),
            ...(frame.error
              ? { error: frame.error }
              : { result: frame.result ?? {} }),
          });
        } else if (frame.type === "session.event") {
          if (
            typeof frame.method !== "string" ||
            frame.method.length > 160 ||
            !(await this.#native(
              "check",
              client.stream.endpoint.authorityId,
              "",
            ))
          ) {
            this.#close(client);
            return;
          }
          this.#write(client, {
            method: frame.method,
            params: frame.params ?? {},
            ...(frame.sessionId === undefined
              ? {}
              : { sessionId: frame.sessionId }),
          });
        }
      })
      .catch(() => this.#close(client))
      .finally(() => {
        client.queuedBytes -= size;
      });
    return true;
  }

  #write(client: Client, frame: NativeFrame): void {
    if (
      !this.#streams.active(client.stream) ||
      client.closed ||
      client.socket.bufferedAmount > 2 * 1024 * 1024
    ) {
      this.#close(client);
      return;
    }
    client.socket.send(JSON.stringify(frame), (error) => {
      if (error) this.#close(client);
    });
  }
  sweep(): void {
    for (const stream of this.#streams.sweep()) {
      const client = this.#clients.get(stream.id);
      if (client) this.#close(client);
    }
  }
  #schedule(): void {
    if (this.#monitor || !this.#clients.size || this.#closed) return;
    this.#monitor = setTimeout(() => {
      this.#monitor = undefined;
      this.sweep();
      for (const client of this.#clients.values()) {
        if (!client.checking) {
          client.checking = true;
          void this.#native("check", client.stream.endpoint.authorityId, "")
            .then((allowed) => {
              if (!allowed) this.#close(client);
            })
            .finally(() => {
              client.checking = false;
            });
        }
      }
      this.#schedule();
    }, 100);
  }
  #close(client: Client): void {
    if (client.closed) return;
    client.closed = true;
    this.#clients.delete(client.stream.id);
    this.#streams.close(client.stream);
    if (!client.opened)
      void this.#native(
        "result",
        client.stream.endpoint.authorityId,
        client.openAudit,
        "unknown",
      );
    for (const pending of client.pending.values())
      void this.#native(
        "result",
        client.stream.endpoint.authorityId,
        pending.auditId,
        "unknown",
      );
    client.pending.clear();
    try {
      this.#send(client.stream.endpoint.fence.connection, {
        type: "session.close",
        id: client.stream.id,
      });
    } catch {
      /* Transport already ended. */
    }
    client.socket.terminate();
  }
  close(): void {
    if (this.#closed) return;
    this.#closed = true;
    if (this.#monitor) clearTimeout(this.#monitor);
    for (const client of this.#clients.values()) this.#close(client);
    this.#ws.close();
    this.#server.close();
    this.#server.closeAllConnections();
  }
}
