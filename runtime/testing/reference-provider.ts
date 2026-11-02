/** Stateful effect oracle, not a parallel authorization or routing engine. */
import type {
  Clock,
  DispatchCommand,
  ProviderAdapter,
  ProviderConnection,
  ProviderReply,
} from "../src/core.ts";

export class ManualClock implements Clock {
  #time = 0;

  now(): number {
    return this.#time;
  }

  advance(milliseconds: number): void {
    if (
      !Number.isSafeInteger(milliseconds) ||
      milliseconds < 0 ||
      !Number.isSafeInteger(this.#time + milliseconds)
    )
      throw new Error("Invalid clock advance");
    this.#time += milliseconds;
  }
}

/**
 * A tiny target with one increment button. Effects occur independently of
 * reply delivery. Cancellation deliberately does not roll back an effect.
 */
export class ReferenceProvider implements ProviderAdapter {
  readonly connection: ProviderConnection;
  readonly received: DispatchCommand[] = [];
  readonly cancelled: DispatchCommand[] = [];
  readonly #replies = new Map<DispatchCommand, ProviderReply>();
  #counter = 0;

  constructor(connection: ProviderConnection) {
    this.connection = connection;
  }

  reference(): {
    readonly connection: ProviderConnection;
    readonly target: string;
  } {
    return Object.freeze({
      connection: this.connection,
      target: "increment-button",
    });
  }

  execute(command: DispatchCommand): void {
    if (command.connection !== this.connection)
      throw new Error("Host routed command to the wrong provider");
    if (this.#replies.has(command))
      throw new Error("Host dispatched a command twice");
    this.received.push(command);
    if (
      command.operation !== "browser.click" ||
      command.target !== "increment-button"
    ) {
      this.#replies.set(command, { ok: false, delivery: "refused" });
      return;
    }
    this.#counter++;
    this.#replies.set(command, { ok: true });
  }

  cancel(command: DispatchCommand): void {
    this.cancelled.push(command);
  }

  reply(command: DispatchCommand): ProviderReply {
    const reply = this.#replies.get(command);
    if (!reply) throw new Error("No held provider reply");
    this.#replies.delete(command);
    return reply;
  }

  readCounter(): number {
    return this.#counter;
  }
}
