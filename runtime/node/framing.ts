/** The Chrome native-messaging format, also used on the private fixture IPC. */
import { Buffer } from "node:buffer";
import type { Writable } from "node:stream";
import { TextDecoder } from "node:util";
import type { NativeFrame } from "../src/extension-provider.ts";

export const MAXIMUM_FRAME = 1024 * 1024;

export function encodeFrame(frame: NativeFrame): Buffer {
  const body = Buffer.from(JSON.stringify(frame), "utf8");
  if (!body.length || body.length > MAXIMUM_FRAME)
    throw new Error("native_frame_size");
  const header = Buffer.alloc(4);
  header.writeUInt32LE(body.length);
  return Buffer.concat([header, body]);
}

export function writeFrame(stream: Writable, frame: NativeFrame): void {
  const encoded = encodeFrame(frame);
  if (
    stream.destroyed ||
    !stream.writable ||
    stream.writableLength + encoded.length > 2 * MAXIMUM_FRAME
  ) {
    throw new Error("native_output_unavailable");
  }
  stream.write(encoded);
}

export class FrameDecoder {
  #buffer: Buffer = Buffer.alloc(0);
  readonly #receive: (frame: NativeFrame) => void;
  readonly #utf8 = new TextDecoder("utf-8", { fatal: true });

  constructor(receive: (frame: NativeFrame) => void) {
    this.#receive = receive;
  }

  push(chunk: Uint8Array): void {
    if (this.#buffer.length + chunk.length > 2 * MAXIMUM_FRAME + 8)
      throw new Error("native_input_capacity");
    this.#buffer = Buffer.concat([this.#buffer, chunk]);
    while (this.#buffer.length >= 4) {
      const size = this.#buffer.readUInt32LE(0);
      if (!size || size > MAXIMUM_FRAME) throw new Error("native_frame_size");
      if (this.#buffer.length < size + 4) return;
      const body = this.#buffer.subarray(4, size + 4);
      this.#buffer = this.#buffer.subarray(size + 4);
      const frame: unknown = JSON.parse(this.#utf8.decode(body));
      if (!frame || typeof frame !== "object" || Array.isArray(frame))
        throw new Error("native_frame_object");
      this.#receive(frame as NativeFrame);
    }
  }

  end(): void {
    if (this.#buffer.length) throw new Error("native_frame_truncated");
  }
}
