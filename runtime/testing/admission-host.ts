/** Native contract fixture only. Excluded from production policy payloads. */
import { FrameDecoder, writeFrame } from "../node/framing.ts";
import { PolicyHost } from "../node/policy-host.ts";
let now = 0;
const send = (frame: Record<string, unknown>) => writeFrame(process.stdout, frame, 16 * 1024 * 1024);
const host = new PolicyHost(send, { now: () => now });
const decoder = new FrameDecoder(frame => {
  if (frame.method === "fixture.time") {
    if (typeof frame.milliseconds !== "number" || !Number.isSafeInteger(frame.milliseconds) || frame.milliseconds < now)
      throw new Error("invalid_fixture_time");
    now = frame.milliseconds; host.tick(); send({ type: "reply", id: frame.id, ok: true, data: {} });
  } else host.receive(frame);
}, 16 * 1024 * 1024);
process.stdin.on("data", (chunk: Buffer) => decoder.push(chunk));
process.stdin.on("end", () => { decoder.end(); host.close(); });
