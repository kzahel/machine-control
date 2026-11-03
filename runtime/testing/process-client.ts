/** Fixture-side parent for the inherited native-host integration inlet. */
import { spawn } from "node:child_process";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FrameDecoder, writeFrame } from "../node/framing.ts";
import type { NativeFrame } from "../src/extension-provider.ts";

export class ProcessClient {
  readonly #command: readonly string[];
  readonly #event: (frame: NativeFrame) => void;
  readonly #failed: () => void;
  readonly #waiting = new Map<string, { resolve(value: unknown): void; reject(error: Error): void; timer: ReturnType<typeof setTimeout> }>();
  #child: ChildProcessWithoutNullStreams | undefined;
  #exit: Promise<void> | undefined;
  #sequence = 0;
  #closed = false;

  constructor(event: (frame: NativeFrame) => void, failed: () => void) {
    const command: unknown = process.env.MC_POLICY_COMMAND ? JSON.parse(process.env.MC_POLICY_COMMAND) :
      [process.execPath, fileURLToPath(new URL("../node/main.ts", import.meta.url))];
    if (!Array.isArray(command) || !command.length || command.some((item) => typeof item !== "string"))
      throw new Error("invalid_fixture_policy_command");
    this.#command = command;
    this.#event = event;
    this.#failed = failed;
  }

  async start(): Promise<void> {
    const child = spawn(this.#command[0]!, this.#command.slice(1), { stdio: ["pipe", "pipe", "pipe"], env: {} });
    this.#child = child;
    child.stderr.resume();
    const decoder = new FrameDecoder((frame) => {
      if (frame.type !== "reply") { this.#event(frame); return; }
      const id = String(frame.id);
      const pending = this.#waiting.get(id);
      if (!pending) throw new Error("unexpected_host_reply");
      this.#waiting.delete(id);
      clearTimeout(pending.timer);
      if (frame.ok === true) pending.resolve(frame.data);
      else pending.reject(new Error(String(frame.errorCode)));
    });
    child.stdout.on("data", (chunk: Buffer) => { try { decoder.push(chunk); } catch { child.kill(); } });
    child.stdin.on("error", () => child.kill());
    this.#exit = new Promise((resolve) => {
      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        for (const pending of this.#waiting.values()) {
          clearTimeout(pending.timer);
          pending.reject(new Error("policy_host_closed"));
        }
        this.#waiting.clear();
        if (!this.#closed) this.#failed();
        resolve();
      };
      child.once("exit", finish);
      child.once("error", finish);
    });
    await this.call("hello", { protocolVersion: 2 });
  }

  call(method: string, fields: NativeFrame = {}): Promise<unknown> {
    const child = this.#child;
    if (!child || child.exitCode !== null || this.#closed || this.#waiting.size >= 64)
      return Promise.reject(new Error("policy_host_unavailable"));
    const id = String(++this.#sequence);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { child.kill(); }, 20_000);
      this.#waiting.set(id, { resolve, reject, timer });
      try { writeFrame(child.stdin, { id, method, ...fields }); } catch { child.kill(); }
    });
  }

  kill(): void { this.#child?.kill("SIGKILL"); }

  async close(): Promise<void> {
    if (this.#closed) return;
    this.#closed = true;
    const child = this.#child;
    if (!child) return;
    child.stdin.end();
    const timer = setTimeout(() => child.kill("SIGKILL"), 3000);
    try { await this.#exit; } finally { clearTimeout(timer); }
  }
}
