import { randomUUID } from "node:crypto";
import { closeSync, constants, fstatSync, fsyncSync, mkdirSync, openSync, readSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute } from "node:path";
import type { AccessAdmission, Surface, SurfaceConfiguration } from "../src/admission.ts";

const schema = "machine-control-startup-access/v1";
const maximumBytes = 16 * 1024;
type Choice = { surface: Surface; mode: "ask" | "automatic"; profileIds: readonly string[] };
type Choices = Map<Surface, Choice>;

function readRecord(path: string): string | undefined {
  try {
    const fd = openSync(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    try {
      const info = fstatSync(fd);
      if (!info.isFile() || info.size > maximumBytes ||
        (process.getuid && (info.uid !== process.getuid() || (info.mode & 0o077) !== 0))) return;
      const bytes = Buffer.alloc(maximumBytes + 1);
      const count = readSync(fd, bytes);
      if (count <= maximumBytes) return bytes.toString("utf8", 0, count);
    } finally { closeSync(fd); }
  } catch { /* Unreadable state carries no authority. */ }
}

/** The trusted native parent supplies a per-instance private path. Only the
 * operator's indefinite choices are stored, never tasks or native authority. */
export class StartupAccess {
  readonly #path: string;
  #enabled = false;
  #saved: Choices = new Map();
  #pending: Choices = new Map();
  #record?: string;

  constructor(path: string, admission: AccessAdmission) {
    if (!isAbsolute(path)) throw new Error("invalid_startup_access_path");
    this.#path = path;
    const contents = readRecord(path);
    if (contents === undefined) return;
    try {
      const record = JSON.parse(contents);
      if (record?.schema !== schema || record.enabled !== true || !Array.isArray(record.surfaces) || record.surfaces.length > 2) return;
      const choices: Choices = new Map();
      for (const { surface, mode, profileIds } of record.surfaces) {
        if (choices.has(surface) || (mode !== "ask" && mode !== "automatic") || !Array.isArray(profileIds) ||
          (surface === "browser" && profileIds.length === 0)) return;
        admission.validateConfiguration(surface, { mode, durationMs: null, profileIds });
        choices.set(surface, { surface, mode, profileIds });
      }
      this.#enabled = true;
      this.#saved = choices;
      this.#pending = new Map(choices);
      this.#record = contents;
    } catch { /* Invalid state carries no authority. */ }
  }

  status() { return { enabled: this.#enabled, pending: [...this.#pending.keys()] }; }
  pending() {
    // A different local instance or the emergency Stop fallback may revoke
    // the file while this resident is still waiting for its console.
    if (this.#pending.size && readRecord(this.#path) !== this.#record) {
      this.#pending.clear();
      this.#saved.clear();
      this.#enabled = false;
    }
    return [...this.#pending.values()];
  }

  optIn(enabled: boolean, admission: AccessAdmission): void {
    if (enabled === this.#enabled) return;
    const choices: Choices = new Map();
    if (enabled) {
      const status = admission.status();
      for (const surface of ["desktop", "browser"] as const) {
        const view = status.surfaces[surface];
        if (view && view.mode !== "off" && view.consentRemainingSeconds === null && !view.pauses.some(pause => pause.reason === "manual")) {
          choices.set(surface, { surface, mode: view.mode, profileIds: view.profileIds });
        }
      }
    }
    this.#write(enabled, choices);
    this.#pending.clear();
  }

  configure(surface: Surface, configuration: SurfaceConfiguration, restoring: boolean): void {
    if (restoring) {
      this.pending();
      const choice = this.#pending.get(surface);
      if (!choice || configuration.durationMs !== null || configuration.mode !== choice.mode ||
        JSON.stringify(configuration.profileIds ?? []) !== JSON.stringify(choice.profileIds)) throw new Error("startup_access_changed");
    } else if (this.#enabled) {
      const choices = new Map(this.#saved);
      if (configuration.mode !== "off" && configuration.durationMs === null) {
        choices.set(surface, { surface, mode: configuration.mode, profileIds: configuration.profileIds ?? [] });
      } else choices.delete(surface);
      this.#write(true, choices);
    }
    this.#pending.delete(surface);
  }

  forget(surface: Surface | "all"): void {
    if (!this.#enabled) return;
    const choices = new Map(this.#saved);
    if (surface === "all") choices.clear();
    else choices.delete(surface);
    if (surface === "all") this.#pending.clear();
    else this.#pending.delete(surface);
    if (choices.size !== this.#saved.size) {
      try { this.#write(true, choices); }
      catch (error) {
        this.#enabled = false;
        this.#saved.clear();
        this.#pending.clear();
        throw error;
      }
    }
  }

  resume(surface: Surface | "all", admission: AccessAdmission): void {
    if (!this.#enabled) return;
    const choices = new Map(this.#saved);
    const status = admission.status();
    for (const name of ["desktop", "browser"] as const) {
      if (surface !== "all" && name !== surface) continue;
      const view = status.surfaces[name];
      if (!choices.has(name) && view && view.mode !== "off" && view.consentRemainingSeconds === null &&
        !view.pauses.some(pause => pause.reason === "manual")) {
        choices.set(name, { surface: name, mode: view.mode, profileIds: view.profileIds });
      }
    }
    if (choices.size !== this.#saved.size) this.#write(true, choices);
  }

  #write(enabled: boolean, choices: Choices): void {
    const staging = `${this.#path}.${randomUUID()}.tmp`;
    const contents = JSON.stringify({ schema, enabled, surfaces: [...choices.values()] });
    try {
      mkdirSync(dirname(this.#path), { recursive: true, mode: 0o700 });
      const fd = openSync(staging, "wx", 0o600);
      try {
        writeFileSync(fd, contents);
        fsyncSync(fd);
      } finally { closeSync(fd); }
      renameSync(staging, this.#path);
      if (process.platform !== "win32") {
        // POSIX filesystems can persist the rename as well as the file data.
        try {
          const directory = openSync(dirname(this.#path), constants.O_RDONLY | constants.O_DIRECTORY);
          try { fsyncSync(directory); } finally { closeSync(directory); }
        } catch { /* Directory fsync is unavailable on some filesystems. */ }
      }
    } catch {
      try { unlinkSync(staging); } catch { /* Best effort for an unused temporary file. */ }
      throw new Error("startup_access_storage_unavailable");
    }
    this.#record = contents;
    this.#enabled = enabled;
    this.#saved = choices;
  }
}
