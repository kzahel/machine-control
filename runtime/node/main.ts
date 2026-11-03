/** Private child entry point: binary framed inherited stdin/stdout only. */
import { FrameDecoder, writeFrame } from "./framing.ts";
import { PolicyHost } from "./policy-host.ts";

if (process.stdin.isTTY || process.stdout.isTTY)
  throw new Error("inherited_host_channel_required");

const host = new PolicyHost((frame) =>
  writeFrame(process.stdout, frame, 16 * 1024 * 1024),
);
let closed = false;
let timer: ReturnType<typeof setTimeout> | undefined;
function schedule(): void {
  if (timer) clearTimeout(timer);
  const delay = host.wakeInMs();
  if (closed || delay === null) return;
  timer = setTimeout(() => {
    try {
      host.tick();
      schedule();
    } catch {
      shutdown(1);
    }
  }, delay);
}
function shutdown(code: number): void {
  if (closed) return;
  closed = true;
  if (timer) clearTimeout(timer);
  try {
    host.close();
  } catch {
    /* The broken parent channel is already revoked. */
  }
  process.stdin.destroy();
  process.exitCode = code;
  process.stdout.end();
}
const decoder = new FrameDecoder(
  (frame) => {
    host.receive(frame);
    schedule();
  },
  16 * 1024 * 1024,
);
process.stdin.on("data", (chunk: Buffer) => {
  try {
    decoder.push(chunk);
  } catch {
    shutdown(1);
  }
});
process.stdin.on("end", () => {
  try {
    decoder.end();
    shutdown(0);
  } catch {
    shutdown(1);
  }
});
process.stdin.on("error", () => shutdown(1));
process.stdout.on("error", () => shutdown(1));
process.on("SIGTERM", () => shutdown(0));
process.on("SIGINT", () => shutdown(0));
