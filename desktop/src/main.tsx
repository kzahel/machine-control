import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  Activity,
  ArrowUpRight,
  Check,
  Command,
  Monitor,
  Settings2,
  ShieldCheck,
  Square,
} from "lucide-react";
import "./style.css";

type Scope = "observe" | "control" | "browser" | "devtools";
type UpdateState = {
  phase: string;
  checking: boolean;
  installing: boolean;
  availableVersion: string | null;
  notes: string | null;
  reason: string | null;
  error: string | null;
};
type State = {
  updates?: UpdateState;
  platform?: string;
  supportedScopes?: Scope[];
  stopShortcut?: string;
  startOnLogin?: boolean;
  deployment: {
    policy: { preset: string; grantMode: string };
    grant: null | {
      remainingSeconds: number | null;
      lifetime?: "timed" | "until_stopped";
      scopes: Scope[];
      requester: string;
      reason: string;
    };
    pendingRequest: unknown;
    availability?: { paused: boolean; blockingReasons: string[] };
  };
  permissions: { accessibility: boolean; screenRecording: boolean };
  portal?: {
    state: string;
    error?: string;
    pointer: boolean;
    keyboard: boolean;
  };
  browser: { connected: boolean; available?: boolean };
  pending?: {
    id: string;
    reason: string;
    caller: string;
    scopes: Scope[];
    duration: number;
  };
  activity: {
    at: string;
    operation: string;
    accepted: boolean;
    errorCode: string | null;
  }[];
  logging?: {
    available: boolean;
    errorCode?: string;
    debugRemainingSeconds?: number;
  };
  version: string;
  socket: string;
  stopShortcutAvailable: boolean;
  manualUntilStoppedSupported?: boolean;
  pauseSupported?: boolean;
  updateInstallSupported?: boolean;
};
type AuditEvent = {
  eventId: string;
  at: string;
  phase: string;
  operation: string;
  accepted?: boolean;
  errorCode?: string;
  delivery?: string;
  effect?: string;
  uncertainty?: string;
  elapsedMs?: number;
  [key: string]: unknown;
};
type History = {
  entries: AuditEvent[];
  hasMore: boolean;
  offset: number;
  earliestAt?: string;
  health: { available: boolean; errorCode?: string; historyGap?: boolean };
};
const labels: Record<Scope, string> = {
  observe: "View desktop",
  control: "Control apps and input",
  browser: "Browser tabs",
  devtools: "Browser scripts and DevTools",
};
async function native(command: Record<string, unknown>) {
  return invoke<{
    state?: State;
    extensionPath?: string;
    history?: History;
    preview?: unknown;
    path?: string;
  }>("operator_command", {
    command,
  });
}
function App() {
  const [state, setState] = useState<State>();
  const [platform, setPlatform] = useState<string>();
  const [page, setPage] = useState("access");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [scopes, setScopes] = useState<Scope[]>(["observe", "control"]);
  const [pauseDuration, setPauseDuration] = useState(60);
  const [duration, setDuration] = useState(900);
  const [pendingScopes, setPendingScopes] = useState<Scope[]>([]);
  const [pendingDuration, setPendingDuration] = useState(900);
  const [history, setHistory] = useState<History>();
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyOperation, setHistoryOperation] = useState("");
  const [historyOutcome, setHistoryOutcome] = useState("");
  const [historyStream, setHistoryStream] = useState("audit");
  const [exportPreview, setExportPreview] = useState<unknown>();
  const loadHistory = async () => {
    try {
      const r = await native({
        method: "logs.query",
        offset: historyOffset,
        operation: historyOperation,
        outcome: historyOutcome,
        stream: historyStream,
      });
      setHistory(r.history);
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    if (page === "activity") void loadHistory();
  }, [page, historyOffset, historyOperation, historyOutcome, historyStream]);
  const update = state?.updates;
  const checkUpdates = async () => {
    try {
      await invoke("check_update");
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    const listener = listen<string>("tray-command", ({ payload }) => {
      setPage(payload === "open" ? "access" : "settings");
      setNotice("");
    });
    return () => {
      void listener.then((unlisten) => unlisten());
    };
  }, []);
  const navigate = (next: string) => {
    setPage(next);
    setNotice("");
  };
  const refresh = async () => {
    try {
      const r = await native({ method: "state" });
      setState(r.state);
      if (r.state?.platform) setPlatform(r.state.platform);
    } catch (e) {
      setState(undefined);
      setError(String(e));
    }
  };
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (state?.pending) {
      setPendingScopes(state.pending.scopes);
      setPendingDuration(state.pending.duration);
    }
  }, [state?.pending?.id]);
  const act = async (command: Record<string, unknown>) => {
    setBusy(true);
    setError("");
    try {
      await native(command);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const windows = platform === "windows";
  const linux = platform === "linux";
  const mac = !windows && !linux;
  const availableScopes =
    state?.supportedScopes ?? (Object.keys(labels) as Scope[]);
  const grant = state?.deployment.grant;
  const standing = state?.deployment.policy.grantMode === "standing";
  const availability = state?.deployment.availability;
  const manuallyPaused = availability?.blockingReasons.some((reason) =>
    ["manual", "local_use_episode"].includes(reason),
  );
  const ready =
    state?.permissions.accessibility && state?.permissions.screenRecording;
  const selected = (values: Scope[], setter: (v: Scope[]) => void, s: Scope) =>
    setter(values.includes(s) ? values.filter((v) => v !== s) : [...values, s]);
  return (
    <div className="shell">
      <nav aria-label="Sections" inert={!!state?.pending}>
        {[
          ["access", "Access", Monitor],
          ["setup", "Permissions", ShieldCheck],
          ["activity", "Activity", Activity],
          ["settings", "Settings", Settings2],
        ].map(([id, label, Icon]) => {
          const I = Icon as typeof Monitor;
          return (
            <button
              key={id as string}
              className={page === id ? "selected" : ""}
              aria-current={page === id ? "page" : undefined}
              onClick={() => navigate(id as string)}
            >
              <I size={16} />
              {label as string}
              {id === "settings" && update?.availableVersion && (
                <span
                  className="dot"
                  aria-hidden="true"
                  title="Update available"
                />
              )}
              {id === "setup" && state && !ready && <span className="dot" />}
            </button>
          );
        })}
      </nav>
      <main inert={!!state?.pending}>
        {error && (
          <div role="alert" className="message error">
            {error}
          </div>
        )}
        {notice && (
          <div role="status" className="message">
            {notice}
          </div>
        )}
        {page === "access" && (
          <>
            <div className="access-status">
              <div>
                <h1>
                  <span
                    className={"status-dot " + (grant || standing ? "on" : "")}
                  />
                  {!state
                    ? "Connecting…"
                    : standing
                      ? "Standing access"
                      : grant
                        ? availability?.paused
                          ? "Access paused"
                          : "Access active"
                        : "Access off"}
                </h1>
                {grant && (
                  <p className="grant-detail">
                    {grant.requester} ·{" "}
                    {grant.lifetime === "until_stopped"
                      ? "Until you turn it off"
                      : `${Math.ceil((grant.remainingSeconds ?? 0) / 60)} min left`}
                  </p>
                )}
                {standing && <p className="grant-detail">Appliance policy</p>}
              </div>
              {grant && (
                <button
                  className="danger"
                  disabled={busy}
                  onClick={() => void act({ method: "stop" })}
                >
                  <Square size={12} /> Stop access
                </button>
              )}
            </div>
            {state?.pauseSupported && (
              <section className="group" aria-label="Pause agent access">
                <div className="group-footer">
                  <label className="duration">
                    Pause for
                    <select
                      aria-label="Pause duration"
                      value={pauseDuration}
                      onChange={(event) =>
                        setPauseDuration(Number(event.target.value))
                      }
                    >
                      <option value={60}>1 minute</option>
                      <option value={300}>5 minutes</option>
                      <option value={0}>Until I resume</option>
                    </select>
                  </label>
                  {manuallyPaused ? (
                    <button
                      disabled={busy}
                      onClick={() => void act({ method: "resume" })}
                    >
                      Resume access
                    </button>
                  ) : (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void act({
                          method: "pause",
                          ...(pauseDuration > 0
                            ? { duration: pauseDuration }
                            : {}),
                        })
                      }
                    >
                      Pause access
                    </button>
                  )}
                </div>
                <p className="note">
                  {availability?.paused
                    ? `Waiting: ${availability.blockingReasons.map((reason) => reason.replaceAll("_", " ")).join(", ")}.`
                    : "Pause keeps your access approval. Stop access turns it off."}
                </p>
              </section>
            )}
            <section className="group" aria-label="Access scopes">
              <div className="scope-list">
                {availableScopes.map((s) => (
                  <label className="scope" key={s}>
                    <input
                      type="checkbox"
                      checked={scopes.includes(s)}
                      onChange={() => selected(scopes, setScopes, s)}
                    />
                    {labels[s]}
                  </label>
                ))}
              </div>
              <div className="group-footer">
                <label className="duration">
                  Duration
                  <select
                    aria-label="Access duration"
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                  >
                    <option value={60}>1 minute</option>
                    <option value={300}>5 minutes</option>
                    <option value={900}>15 minutes</option>
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 hour</option>
                    {state?.manualUntilStoppedSupported && (
                      <option value={0}>Until I turn it off</option>
                    )}
                  </select>
                </label>
                <button
                  className="primary"
                  disabled={busy || !state || standing || scopes.length === 0}
                  onClick={() =>
                    void act({
                      method: "arm",
                      scopes,
                      duration,
                      lifetime: duration === 0 ? "until_stopped" : "timed",
                    })
                  }
                >
                  Enable access
                </button>
              </div>
            </section>
            <p className="note">Applies to all callers running as your user.</p>
            {state && !ready && (
              <button className="text-button" onClick={() => navigate("setup")}>
                Permissions needed <ArrowUpRight size={13} />
              </button>
            )}
          </>
        )}
        {page === "setup" && (
          <>
            <section className="group" aria-label="Permissions">
              {windows && (
                <>
                  <div className="setting-row">
                    <span className="row-label">Desktop session</span>
                    <span className="row-status">
                      {ready ? "Available" : "Unavailable"}
                    </span>
                  </div>
                  <div className="setting-row">
                    <span className="row-label">
                      Elevated apps and lock screen
                    </span>
                    <span className="row-status">Unavailable</span>
                  </div>
                </>
              )}
              {linux && (
                <>
                  <div className="setting-row">
                    <span className="row-label">Accessibility</span>
                    <span className="row-status">
                      {state?.permissions.accessibility
                        ? "Available"
                        : "Unavailable"}
                    </span>
                  </div>
                  <div className="setting-row">
                    <span className="row-label">Screen and input</span>
                    <span className="row-status">
                      {state?.portal?.state === "pending"
                        ? "Awaiting consent"
                        : state?.portal?.state === "ready"
                          ? "Shared"
                          : "Off"}
                    </span>
                    <button
                      disabled={
                        busy ||
                        !!grant ||
                        !!state?.pending ||
                        state?.portal?.state === "pending"
                      }
                      onClick={() =>
                        void act({
                          method:
                            state?.portal?.state === "ready"
                              ? "permission.disconnect"
                              : "permission",
                        })
                      }
                    >
                      {state?.portal?.state === "ready"
                        ? "Disconnect"
                        : "Share…"}
                    </button>
                  </div>
                  {state?.portal?.error && (
                    <p className="note">{state.portal.error}</p>
                  )}
                  <div className="setting-row">
                    <span className="row-label">
                      Lock screen and other users
                    </span>
                    <span className="row-status">Unavailable</span>
                  </div>
                </>
              )}
              {mac &&
                [
                  ["accessibility", "Accessibility"],
                  ["screenRecording", "Screen Recording"],
                ].map(([id, title]) => {
                  const granted =
                    state?.permissions[id as keyof State["permissions"]];
                  return (
                    <div className="setting-row" key={id}>
                      <span
                        className={"permission-icon " + (granted ? "done" : "")}
                      >
                        {granted ? <Check size={15} /> : <Monitor size={15} />}
                      </span>
                      <span className="row-label">{title}</span>
                      <span className="row-status">
                        {!state ? "—" : granted ? "Granted" : "Required"}
                      </span>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void act({ method: "permission", permission: id })
                        }
                      >
                        Open Settings
                      </button>
                    </div>
                  );
                })}
              {state?.browser.available !== false && (
                <div className="setting-row">
                  <span
                    className={
                      "permission-icon " +
                      (state?.browser.connected ? "done" : "")
                    }
                  >
                    <Command size={15} />
                  </span>
                  <span className="row-label">
                    Browser extension{" "}
                    <span className="optional">(optional)</span>
                  </span>
                  <span className="row-status">
                    {state?.browser.connected ? "Connected" : "Not connected"}
                  </span>
                  <button
                    disabled={busy}
                    onClick={async () => {
                      try {
                        await native({ method: "browser.setup" });
                        setNotice(
                          "Path copied. In Chrome extensions, enable Developer mode, then Load unpacked.",
                        );
                      } catch (e) {
                        setError(String(e));
                      }
                    }}
                  >
                    Set up
                  </button>
                </div>
              )}
            </section>
            {mac && (
              <div className="restart-row">
                <p className="note">Restart after changing Screen Recording.</p>
                <button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      await invoke("restart_application");
                    } catch (e) {
                      setError(String(e));
                      setBusy(false);
                    }
                  }}
                >
                  Restart
                </button>
              </div>
            )}
          </>
        )}
        {page === "activity" && (
          <>
            <section
              className="group history-controls"
              aria-label="Activity filters"
            >
              <select
                aria-label="History type"
                value={historyStream}
                onChange={(e) => {
                  setHistoryStream(e.target.value);
                  setHistoryOffset(0);
                }}
              >
                <option value="audit">Activity</option>
                <option value="diagnostics">Diagnostics</option>
              </select>
              <input
                aria-label="Filter operation"
                placeholder="Filter operation"
                value={historyOperation}
                onChange={(e) => {
                  setHistoryOperation(e.target.value);
                  setHistoryOffset(0);
                }}
              />
              <select
                aria-label="Filter outcome"
                value={historyOutcome}
                onChange={(e) => {
                  setHistoryOutcome(e.target.value);
                  setHistoryOffset(0);
                }}
              >
                <option value="">All outcomes</option>
                <option value="accepted">Accepted</option>
                <option value="refused">Refused</option>
              </select>
              <button onClick={() => void loadHistory()}>Refresh</button>
            </section>
            <p className="row-status">
              Audit: 30 days / 100 MB. Diagnostics: 7 days / 50 MB. Oldest
              entries are removed when either limit is reached.
            </p>
            {(history?.health.available === false ||
              state?.logging?.available === false) && (
              <p role="alert">
                Logging needs attention:{" "}
                {history?.health.errorCode ?? state?.logging?.errorCode}. New
                control is paused; Stop remains available.
              </p>
            )}
            {history?.earliestAt && (
              <p className="row-status">
                Retained history starts{" "}
                {new Date(history.earliestAt).toLocaleString()}.
              </p>
            )}
            {history?.health.historyGap && (
              <p role="status">
                Some retained history is incomplete. Outcomes without a result
                remain unknown.
              </p>
            )}
            <section
              className="group activity-list"
              aria-label="Retained activity"
            >
              {!history?.entries.length ? (
                <p className="empty">No retained activity</p>
              ) : (
                history.entries.map((entry) => (
                  <details className="history-entry" key={entry.eventId}>
                    <summary>
                      <strong>{entry.operation}</strong>
                      <span>
                        {entry.phase === "intent"
                          ? history.entries.some(
                              (result) =>
                                result.phase === "result" &&
                                result.requestId === entry.requestId &&
                                result.runtimeId === entry.runtimeId,
                            )
                            ? "Intent — result recorded"
                            : "Intent — outcome pending or unknown"
                          : entry.accepted === true
                            ? "Accepted"
                            : (entry.errorCode ?? entry.phase)}
                      </span>
                      <time>{new Date(entry.at).toLocaleString()}</time>
                    </summary>
                    <p>
                      Delivery: {entry.delivery ?? "unknown"} · Effect:{" "}
                      {entry.effect ?? "unknown"}
                    </p>
                    <pre>{JSON.stringify(entry, null, 2)}</pre>
                  </details>
                ))
              )}
            </section>
            <div className="history-controls">
              <button
                disabled={historyOffset === 0}
                onClick={() =>
                  setHistoryOffset(Math.max(0, historyOffset - 50))
                }
              >
                Newer
              </button>
              <button
                disabled={!history?.hasMore}
                onClick={() => setHistoryOffset(historyOffset + 50)}
              >
                Older
              </button>
              <button
                onClick={() =>
                  void native({
                    method: "logs.debug",
                    enabled: !state?.logging?.debugRemainingSeconds,
                  })
                    .then(() => refresh())
                    .catch((e) => setError(String(e)))
                }
              >
                {state?.logging?.debugRemainingSeconds
                  ? "End detailed diagnostics"
                  : "Detailed diagnostics for 15 minutes"}
              </button>
              <button
                onClick={() =>
                  void native({ method: "logs.open" }).catch((e) =>
                    setError(String(e)),
                  )
                }
              >
                Open log folder
              </button>
              <button
                onClick={() =>
                  void native({ method: "logs.preview" })
                    .then((r) => setExportPreview(r.preview))
                    .catch((e) => setError(String(e)))
                }
              >
                Preview diagnostic export
              </button>
            </div>
            {exportPreview !== undefined && (
              <section
                className="group history-export"
                aria-label="Diagnostic export preview"
              >
                <p>
                  Includes up to 500 recent events from each stream. Saved
                  locally; nothing is uploaded.
                </p>
                <pre>{JSON.stringify(exportPreview, null, 2)}</pre>
                <button
                  onClick={() =>
                    void native({ method: "logs.export" })
                      .then((r) => {
                        setNotice(`Diagnostics saved to ${r.path}`);
                        setExportPreview(undefined);
                      })
                      .catch((e) => setError(String(e)))
                  }
                >
                  Save diagnostics
                </button>
                <button onClick={() => setExportPreview(undefined)}>
                  Cancel
                </button>
              </section>
            )}
          </>
        )}
        {page === "settings" && (
          <>
            {(windows || linux) && (
              <section className="group" aria-label="Startup">
                {linux && (
                  <label className="setting-row">
                    <span className="row-label">Stop shortcut</span>
                    <input
                      type="checkbox"
                      checked={!!state?.stopShortcutAvailable}
                      disabled={busy || !state}
                      onChange={(e) =>
                        void act({
                          method: "shortcut",
                          enabled: e.target.checked,
                        })
                      }
                    />
                  </label>
                )}
                <label className="setting-row">
                  <span className="row-label">Start at login</span>
                  <input
                    type="checkbox"
                    checked={!!state?.startOnLogin}
                    disabled={busy || !state}
                    onChange={(e) =>
                      void act({ method: "startup", enabled: e.target.checked })
                    }
                  />
                </label>
                <div className="setting-row">
                  <span className="row-label">Restart</span>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void invoke("restart_application").catch((e) =>
                        setError(String(e)),
                      )
                    }
                  >
                    Restart
                  </button>
                </div>
              </section>
            )}
            <section className="group" aria-label="Updates">
              <div className="setting-row">
                <span className="row-label">Updates</span>
                <button
                  disabled={busy || update?.checking || update?.installing}
                  onClick={() => void checkUpdates()}
                >
                  Check for updates
                </button>
                {update?.availableVersion &&
                  state?.updateInstallSupported !== false && (
                    <button
                      disabled={
                        busy ||
                        update.checking ||
                        update.installing ||
                        !!grant ||
                        standing ||
                        !!state?.pending
                      }
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await invoke("install_update", {
                            version: update.availableVersion,
                          });
                        } catch (e) {
                          setError(String(e));
                          setBusy(false);
                        }
                      }}
                    >
                      Install and restart
                    </button>
                  )}
              </div>
              {linux && state?.updateInstallSupported === false && (
                <p className="note">
                  Install updates with the package manager.
                </p>
              )}
              {update?.checking && (
                <p className="note">Checking for updates…</p>
              )}
              {update?.availableVersion && (
                <p className="note">
                  Version {update.availableVersion} available.
                </p>
              )}
              {update?.phase === "up_to_date" && update.reason === "manual" && (
                <p className="note">Up to date.</p>
              )}
              {update?.phase === "error" && update.error && (
                <p className="note">{update.error}</p>
              )}
            </section>
            <section className="group details" aria-label="Installation">
              <dl>
                <dt>Version</dt>
                <dd>
                  {state?.version ?? "—"}{" "}
                  <span className="optional">(preview)</span>
                </dd>
                <dt>Policy</dt>
                <dd>{state?.deployment.policy.preset ?? "—"}</dd>
                <dt>Stop shortcut</dt>
                <dd>
                  {state?.stopShortcutAvailable
                    ? (state.stopShortcut ?? "⌃⌥⌘.")
                    : "Unavailable; use Stop access"}
                </dd>
                <dt>{windows ? "Endpoint" : "Socket"}</dt>
                <dd>{state?.socket ?? "—"}</dd>
              </dl>
            </section>
            <p className="note">
              Close hides the window. Quit from the{" "}
              {windows || linux ? "tray" : "menu bar"}.
            </p>
          </>
        )}
      </main>
      {state?.pending && (
        <div className="scrim">
          <section
            className="approval"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-title"
          >
            <h2 id="approval-title">Allow access?</h2>
            <p className="request-reason">{state.pending.reason}</p>
            <p className="caller">
              {state.pending.caller} <span>(unverified)</span>
            </p>
            <div className="approval-scopes">
              {state.pending.scopes.map((s) => (
                <label className="scope" key={s}>
                  <input
                    type="checkbox"
                    checked={pendingScopes.includes(s)}
                    onChange={() =>
                      selected(pendingScopes, setPendingScopes, s)
                    }
                  />
                  {labels[s]}
                </label>
              ))}
            </div>
            <label className="duration">
              Duration
              <select
                aria-label="Approval duration"
                value={pendingDuration}
                onChange={(e) => setPendingDuration(Number(e.target.value))}
              >
                {[60, 300, 900, 1800, 3600, state.pending.duration]
                  .filter(
                    (v, i, a) =>
                      v <= state.pending!.duration && a.indexOf(v) === i,
                  )
                  .sort((a, b) => a - b)
                  .map((v) => (
                    <option key={v} value={v}>
                      {v / 60} {v === 60 ? "minute" : "minutes"}
                    </option>
                  ))}
              </select>
            </label>
            <p className="note">
              Applies to all callers running as your user. Input is paused.
            </p>
            <div className="approval-actions">
              <button
                disabled={busy}
                autoFocus
                onClick={() =>
                  void act({
                    method: "decision",
                    id: state.pending!.id,
                    allow: false,
                  })
                }
              >
                Deny
              </button>
              <button
                className="primary"
                disabled={busy || !pendingScopes.length}
                onClick={() =>
                  void act({
                    method: "decision",
                    id: state.pending!.id,
                    allow: true,
                    scopes: pendingScopes,
                    duration: pendingDuration,
                  })
                }
              >
                Allow access
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
