// Chrome starts this relay through a launcher in its scratch profile only.
// Its private fixture endpoint is not production native peer authentication.
import { readFile, stat } from "node:fs/promises";
import { createConnection } from "node:net";
import { FrameDecoder, writeFrame } from "../../runtime/node/framing.ts";

const [configPath, origin] = process.argv.slice(2);
if (origin !== "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/")
  throw new Error("fixture_origin_refused");
const metadata = await stat(configPath);
if (
  !metadata.isFile() ||
  (metadata.mode & 0o777) !== 0o600 ||
  metadata.size > 4096
)
  throw new Error("fixture_config_refused");
const config = JSON.parse(await readFile(configPath, "utf8"));
if (typeof config.socketPath !== "string")
  throw new Error("fixture_config_refused");
const socket = createConnection(config.socketPath);
let closing = false;
function close() {
  if (closing) return;
  closing = true;
  clearTimeout(timer);
  socket.destroy();
  process.stdin.destroy();
  process.stdout.end();
}
const timer = setTimeout(close, 5_000);
const inbound = new FrameDecoder((frame) => writeFrame(socket, frame));
const outbound = new FrameDecoder((frame) => writeFrame(process.stdout, frame));
socket.on("connect", () => {
  clearTimeout(timer);
  writeFrame(socket, { type: "fixture.native-host", processId: process.pid });
  process.stdin.on("data", (chunk) => {
    try {
      inbound.push(chunk);
    } catch {
      close();
    }
  });
});
socket.on("data", (chunk) => {
  try {
    outbound.push(chunk);
  } catch {
    close();
  }
});
socket.on("close", close);
socket.on("error", close);
process.stdin.on("end", close);
process.stdin.on("error", close);
process.stdout.on("error", close);
process.on("SIGTERM", close);
