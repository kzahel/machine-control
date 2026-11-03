import type { AuthorityFence, Clock } from "./core.ts";
import { ResidentCore } from "./core.ts";

export interface Endpoint {
  readonly fence: AuthorityFence;
  readonly authorityId: string;
  readonly token: string;
}
export interface Stream {
  readonly endpoint: Endpoint;
  readonly id: string;
  readonly tabId: number;
}
interface LiveStream {
  readonly handle: Stream;
  readonly reservation: string;
  readonly started: number;
  opened: boolean;
  readonly pending: Map<
    number,
    { session: string | undefined; started: number }
  >;
}

/** Portable endpoint/stream lifetime and profile-scoped reservation policy. */
export class Streams {
  readonly #core: ResidentCore;
  readonly #clock: Clock;
  readonly #endpoints = new Map<string, Endpoint>();
  readonly #streams = new Map<Stream, LiveStream>();
  readonly #reservations = new Set<string>();

  constructor(core: ResidentCore, clock: Clock) {
    this.#core = core;
    this.#clock = clock;
  }
  valid(endpoint: Endpoint): boolean {
    return (
      this.#endpoints.get(endpoint.token) === endpoint &&
      this.#core.validFence(endpoint.fence, "browser.cdp")
    );
  }
  endpoint(
    fence: AuthorityFence,
    authorityId: string,
    token: string,
  ): Endpoint {
    if (
      !this.#core.validFence(fence, "browser.cdp") ||
      !authorityId ||
      !/^[a-f0-9]{64}$/.test(token)
    )
      throw new Error("approval_required");
    for (const [key, endpoint] of this.#endpoints) {
      if (!this.valid(endpoint)) this.#endpoints.delete(key);
      else if (
        endpoint.authorityId === authorityId &&
        endpoint.fence.connection === fence.connection &&
        endpoint.fence.authorizationGeneration === fence.authorizationGeneration
      )
        return endpoint;
    }
    if (this.#endpoints.size >= 16 || this.#endpoints.has(token))
      throw new Error("browser_stream_capacity");
    const endpoint = Object.freeze({ fence, authorityId, token });
    this.#endpoints.set(token, endpoint);
    return endpoint;
  }
  lookup(token: string): Endpoint | undefined {
    const endpoint = this.#endpoints.get(token);
    return endpoint && this.valid(endpoint) ? endpoint : undefined;
  }
  open(endpoint: Endpoint, tabId: number, id: string): Stream {
    if (!this.valid(endpoint)) throw new Error("approval_required");
    if (
      !Number.isSafeInteger(tabId) ||
      tabId < 0 ||
      !/^[A-Za-z0-9_-]{1,128}$/.test(id)
    )
      throw new Error("invalid_request");
    const connection = endpoint.fence.connection;
    const reservation = `${connection.profileId}:${connection.generation}:${tabId}`;
    if (this.#streams.size >= 8 || this.#reservations.has(reservation))
      throw new Error("browser_stream_capacity");
    const handle = Object.freeze({ endpoint, tabId, id });
    this.#streams.set(handle, {
      handle,
      reservation,
      started: this.#clock.now(),
      opened: false,
      pending: new Map(),
    });
    this.#reservations.add(reservation);
    return handle;
  }
  active(stream: Stream): boolean {
    return this.#streams.has(stream) && this.valid(stream.endpoint);
  }
  opened(stream: Stream): boolean {
    const state = this.#streams.get(stream);
    if (
      !state ||
      !this.active(stream) ||
      this.#clock.now() - state.started >= 5000
    )
      return false;
    state.opened = true;
    return true;
  }
  command(stream: Stream, id: number, session?: string): void {
    const state = this.#streams.get(stream);
    if (!state?.opened || !this.active(stream))
      throw new Error("approval_required");
    if (
      !Number.isSafeInteger(id) ||
      id < 0 ||
      (session !== undefined && !/^[A-Za-z0-9_-]{1,160}$/.test(session))
    )
      throw new Error("invalid_request");
    if (state.pending.has(id) || state.pending.size >= 16)
      throw new Error("browser_stream_capacity");
    state.pending.set(id, { session, started: this.#clock.now() });
  }
  complete(stream: Stream, id: number, session?: string): boolean {
    const state = this.#streams.get(stream),
      pending = state?.pending.get(id);
    if (
      !pending ||
      pending.session !== session ||
      !this.active(stream) ||
      this.#clock.now() - pending.started >= 45_000
    )
      return false;
    state!.pending.delete(id);
    return true;
  }
  close(stream: Stream): boolean {
    const state = this.#streams.get(stream);
    if (!state) return false;
    this.#streams.delete(stream);
    this.#reservations.delete(state.reservation);
    return true;
  }
  sweep(): readonly Stream[] {
    const expired: Stream[] = [];
    for (const state of this.#streams.values()) {
      const now = this.#clock.now();
      if (
        !this.active(state.handle) ||
        (!state.opened && now - state.started >= 5000) ||
        [...state.pending.values()].some(
          (pending) => now - pending.started >= 45_000,
        )
      ) {
        this.close(state.handle);
        expired.push(state.handle);
      }
    }
    return expired;
  }
  ownerEnded(authorityId: string): readonly Stream[] {
    for (const [token, endpoint] of this.#endpoints)
      if (endpoint.authorityId === authorityId) this.#endpoints.delete(token);
    return this.sweep();
  }
}
