import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronDown,
  Command,
  Monitor,
  Settings2,
  ShieldCheck,
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
  controlPolicy?: {
    supported: boolean;
    mode: "when_idle" | "announce";
    noticeSeconds: number;
  };
  admission?: {
    active: number;
    waiting: number;
    requests: {
      intentId: string;
      state: string;
      reason: string;
      noticeRemainingSeconds: number | null;
      maximumDurationSeconds: number;
      ownerAssurance?: string;
      caller?: string;
    }[];
  };
  desktopCallerTrust?: {
    supported: boolean;
    enabled: boolean;
    suspended: boolean;
    storageInvalid: boolean;
    scopes?: Scope[];
  };
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
  uac?: {
    installed: boolean;
    enabled: boolean;
    setupState: string;
    setupError?: string | null;
  };
  lockedUse?: {
    permissionReady: boolean;
    helperApproval: string;
    supported: boolean;
    enabled: boolean;
    phase: string;
    setupState: string;
    setupError: string | null;
    helperHealthy: boolean;
    helperNote?: string | null;
    unlockRulePeers?: string[];
    pausedUntilManualUnlock: boolean;
    controlSessionId: string | null;
  };
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
    setupPending?: boolean;
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
  const [actionBusy, setBusy] = useState(false);
  const busy = actionBusy || state?.uac?.setupState === "pending";
  const [scopes, setScopes] = useState<Scope[]>(["observe", "control"]);
  const [yaChoice, setYaChoice] = useState(false);
  const [pauseMenu, setPauseMenu] = useState(false);
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
  useEffect(() => {
    if (!pauseMenu) return;
    const close = () => setPauseMenu(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [pauseMenu]);
  const navigate = (next: string) => {
    setPage(next);
    setNotice("");
  };
  const refresh = async () => {
    try {
      const r = await native({ method: "state" });
      if (r.setupPending) {
        setState(
          (previous) =>
            previous && {
              ...previous,
              uac: { ...previous.uac!, setupState: "pending", enabled: false },
            },
        );
        setNotice("Finish helper setup in the Windows dialogs.");
        return;
      }
      setState(r.state);
      setNotice((previous) =>
        previous === "Finish helper setup in the Windows dialogs."
          ? ""
          : previous,
      );
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
  const updateInstallBlockedReason = update?.installing
    ? "Installing the update. Wait for the app to restart."
    : update?.checking
      ? "Wait for the update check to finish before installing."
      : busy
        ? "Wait for the current operation to finish before installing."
        : state?.pending
          ? "Resolve the pending access request before installing the update."
          : standing
            ? "Updates for appliances with standing access are managed by your administrator."
            : grant
              ? "Stop access before installing the update. The app will restart."
              : undefined;
  const trustedAccess = state?.desktopCallerTrust?.enabled === true;
  const availability = state?.deployment.availability;
  const blocks = availability?.blockingReasons ?? [];
  const on = !!grant || trustedAccess;
  // Physical activity only delays a waiting agent; these hold access itself.
  const paused =
    (on || standing) &&
    blocks.some((reason) =>
      [
        "manual",
        "local_use_episode",
        "operator_deferral",
        "physical_takeover",
      ].includes(reason),
    );
  const agentWaiting =
    on && !paused && (state?.admission?.waiting ?? 0) > 0 && blocks.length > 0;
  const trustSupported =
    mac && !standing && state?.desktopCallerTrust?.supported === true;
  // Experimental: verified YepAnywhere desktop sessions under separate trust.
  const yaOnly = grant ? false : trustedAccess || (trustSupported && yaChoice);
  const trustScopes: Scope[] = ["observe", "control"];
  const shownScopes = grant
    ? grant.scopes
    : trustedAccess
      ? (state?.desktopCallerTrust?.scopes ?? trustScopes)
      : scopes;
  const armScopes = yaOnly
    ? scopes.filter((s) => trustScopes.includes(s))
    : scopes;
  const lockedOff = "Turn access off to change this";
  const switchReason = standing
    ? "Managed by appliance policy"
    : on
      ? "Turn access off"
      : armScopes.length === 0
        ? "Choose at least one permission"
        : yaOnly && state?.admission?.active
          ? "Wait for the current agent to finish"
          : "Turn access on";
  const lockedUse =
    (mac || windows) && state?.deployment.policy.grantMode === "approval"
      ? state.lockedUse
      : undefined;
  const accessTitle = !state
    ? "Connecting…"
    : !on && !standing
      ? "Access is off"
      : paused
        ? "Access paused"
        : (state.admission?.active ?? 0) > 0
          ? "Agent in control"
          : standing
            ? "Access always on"
            : "Access is on";
  const accessDetail = standing
    ? "Managed by appliance policy"
    : paused
      ? blocks.includes("operator_deferral")
        ? "Agents wait 1 minute."
        : blocks.includes("local_use_episode")
          ? "Agents wait while you use the computer."
          : blocks.includes("physical_takeover")
            ? "Control stopped when you used the keyboard or mouse. Agents wait for the locked screen to be quiet, or choose Resume access."
            : "No agent can start or continue."
      : grant
        ? [
            grant.requester === "local operator"
              ? "Any app running as you"
              : grant.requester,
            grant.lifetime === "until_stopped"
              ? "until you turn it off"
              : `${Math.ceil((grant.remainingSeconds ?? 0) / 60)} min left`,
            ...(trustedAccess ? ["plus YepAnywhere sessions"] : []),
          ].join(" · ")
        : trustedAccess
          ? "YepAnywhere app only (experimental) · until you turn it off"
          : "";
  const ready =
    state?.permissions.accessibility && state?.permissions.screenRecording;
  const selected = (values: Scope[], setter: (v: Scope[]) => void, s: Scope) =>
    setter(values.includes(s) ? values.filter((v) => v !== s) : [...values, s]);
  if (new URLSearchParams(window.location.search).has("control-notice")) {
    const request = state?.admission?.requests.find(
      (value) => value.state === "announcing",
    );
    return (
      <main className="control-notice" aria-live="polite">
        <h2>Computer control is about to start</h2>
        <p>{request?.reason ?? "Waiting for the current request…"}</p>
        <p className="note">
          {request?.ownerAssurance === "verified_desktop_integration"
            ? "Verified YepAnywhere session"
            : "Same-user caller; identity unverified."}
        </p>
        {request && (
          <p>
            Starts in {Math.ceil(request.noticeRemainingSeconds ?? 0)}s ·
            Maximum control time {request.maximumDurationSeconds}s
          </p>
        )}
        <div className="group-footer">
          <button
            disabled={busy || !request}
            onClick={() =>
              request &&
              void act({ method: "start_control", intentId: request.intentId })
            }
          >
            Start now
          </button>
          <button
            disabled={busy}
            onClick={() => void act({ method: "defer_control" })}
          >
            Wait 1 minute
          </button>
          <button disabled={busy} onClick={() => void act({ method: "pause" })}>
            Pause until I resume
          </button>
        </div>
        {error && <p role="alert">{error}</p>}
      </main>
    );
  }
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
                    className={
                      "status-dot " +
                      (paused ? "paused" : on || standing ? "on" : "")
                    }
                  />
                  {accessTitle}
                </h1>
                {accessDetail && <p className="grant-detail">{accessDetail}</p>}
                {agentWaiting && (
                  <p className="grant-detail">
                    {blocks.includes("activity_unknown")
                      ? "An agent is waiting because local activity cannot be verified."
                      : blocks.includes("relock_pending")
                        ? "An agent is waiting for the screen to lock safely."
                        : "An agent is waiting for you to stop using the computer."}
                  </p>
                )}
                {state?.lockedUse?.pausedUntilManualUnlock && (
                  <p className="grant-detail">
                    Locked-screen access paused. Unlock your Mac manually to
                    continue.
                  </p>
                )}
              </div>
              <div className="access-actions">
                {(on || standing) &&
                  state?.pauseSupported &&
                  (paused ? (
                    <button
                      disabled={busy}
                      onClick={() => void act({ method: "resume" })}
                    >
                      Resume access
                    </button>
                  ) : (
                    <div className="split-button">
                      <button
                        disabled={busy}
                        onClick={() => void act({ method: "pause" })}
                      >
                        Pause access
                      </button>
                      <button
                        aria-label="Pause options"
                        aria-haspopup="menu"
                        aria-expanded={pauseMenu}
                        disabled={busy}
                        onClick={() => setPauseMenu(!pauseMenu)}
                      >
                        <ChevronDown size={13} />
                      </button>
                      {pauseMenu && (
                        <div className="menu" role="menu">
                          {(
                            [
                              [60, "Pause for 1 minute"],
                              [300, "Pause for 5 minutes"],
                            ] as const
                          ).map(([seconds, label]) => (
                            <button
                              key={seconds}
                              role="menuitem"
                              onClick={() =>
                                void act({ method: "pause", duration: seconds })
                              }
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                <button
                  className={"switch " + (on || standing ? "on" : "")}
                  aria-label={
                    standing
                      ? "Access managed by appliance policy"
                      : on
                        ? "Stop access"
                        : "Enable access"
                  }
                  title={switchReason}
                  disabled={
                    busy ||
                    !state ||
                    standing ||
                    (!on &&
                      (armScopes.length === 0 ||
                        (yaOnly && !!state.admission?.active)))
                  }
                  onClick={() =>
                    void act(
                      on
                        ? { method: "stop" }
                        : yaOnly
                          ? {
                              method: "desktop_caller_trust",
                              enabled: true,
                              scopes: armScopes,
                            }
                          : {
                              method: "arm",
                              scopes: armScopes,
                              duration,
                              lifetime:
                                duration === 0 ? "until_stopped" : "timed",
                            },
                    )
                  }
                >
                  <span className="knob" />
                </button>
              </div>
            </div>
            {state?.admission && state.admission.requests.length > 0 && (
              <section className="group requests" aria-label="Agent requests">
                {state.admission.requests.slice(0, 4).map((request) => (
                  <div className="control-request" key={request.intentId}>
                    <p>{request.reason}</p>
                    <p className="note">
                      {request.state.replaceAll("_", " ")}
                      {request.state === "announcing"
                        ? ` · starts in ${Math.ceil(request.noticeRemainingSeconds ?? 0)}s`
                        : ""}{" "}
                      · Maximum {request.maximumDurationSeconds}s
                    </p>
                    <div className="request-actions">
                      {request.state === "announcing" && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            void act({
                              method: "start_control",
                              intentId: request.intentId,
                            })
                          }
                        >
                          Start now
                        </button>
                      )}
                      <button
                        disabled={busy}
                        onClick={() => void act({ method: "defer_control" })}
                      >
                        Wait 1 minute
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void act({
                            method: "cancel_control",
                            intentId: request.intentId,
                          })
                        }
                      >
                        Cancel request
                      </button>
                    </div>
                  </div>
                ))}
              </section>
            )}
            {!standing && (
              <fieldset
                className="group access-config"
                aria-label="Access scopes"
                disabled={on || !state}
              >
                <div className="scope-list">
                  {availableScopes.map((s) => {
                    const unavailable = yaOnly && !trustScopes.includes(s);
                    return (
                      <label
                        className="scope"
                        key={s}
                        title={
                          on
                            ? lockedOff
                            : unavailable
                              ? "Not available with YepAnywhere-only access"
                              : undefined
                        }
                      >
                        <input
                          type="checkbox"
                          checked={!unavailable && shownScopes.includes(s)}
                          disabled={unavailable}
                          onChange={() => selected(scopes, setScopes, s)}
                        />
                        {labels[s]}
                      </label>
                    );
                  })}
                </div>
                {windows &&
                  shownScopes.some(
                    (s) => s === "browser" || s === "devtools",
                  ) && (
                    <p className="note group-note">
                      Browser access can attach local files to websites.
                    </p>
                  )}
                {lockedUse && (
                  <div className="lock-row">
                    <label
                      className="scope"
                      title={
                        on
                          ? lockedOff
                          : !lockedUse.supported
                            ? windows
                              ? "Requires Windows 10 version 2004 or later and one display"
                              : "Requires macOS 14 or later"
                            : yaOnly
                              ? "Not available with YepAnywhere-only access"
                              : state?.pending
                                ? "Answer the pending request first"
                                : lockedUse.enabled
                                  ? undefined
                                  : lockedUse.setupState === "approval"
                                    ? "Finish approving the helper in System Settings"
                                    : lockedUse.setupState !== "idle"
                                      ? "Helper setup is in progress"
                                      : !lockedUse.permissionReady
                                        ? "Set up the Machine Control helper first"
                                        : undefined
                      }
                    >
                      <input
                        type="checkbox"
                        checked={lockedUse.enabled && !yaOnly}
                        disabled={
                          busy ||
                          yaOnly ||
                          !lockedUse.supported ||
                          (!lockedUse.enabled &&
                            (!lockedUse.permissionReady ||
                              lockedUse.setupState !== "idle")) ||
                          !!state?.pending
                        }
                        onChange={(e) =>
                          void act({
                            method: "locked_use",
                            enabled: e.target.checked,
                          })
                        }
                      />
                      Also while the screen is locked
                    </label>
                    <span className="row-status">
                      {!lockedUse.supported
                        ? windows
                          ? "Requires one display and active desktop composition"
                          : "Requires macOS 14 or later"
                        : yaOnly
                          ? "Not with YepAnywhere-only"
                          : lockedUse.setupState === "approval"
                            ? "Approve in System Settings"
                            : lockedUse.setupState === "capture"
                              ? "Approve the screen capture prompt"
                              : lockedUse.setupState !== "idle"
                                ? "Preparing…"
                                : lockedUse.enabled
                                  ? windows
                                    ? "Locked-screen tasks run behind an opaque cover"
                                    : "Keep your Mac awake, lid open"
                                  : ""}
                    </span>
                    {!on &&
                      lockedUse.supported &&
                      !lockedUse.permissionReady &&
                      !yaOnly &&
                      ["idle", "approval"].includes(lockedUse.setupState) && (
                        <button
                          aria-label={
                            lockedUse.setupState === "approval"
                              ? "Open Machine Control helper settings"
                              : "Set up Machine Control helper"
                          }
                          disabled={
                            busy ||
                            (windows && !state?.uac?.installed) ||
                            !!lockedUse.controlSessionId ||
                            !!state?.pending
                          }
                          onClick={() =>
                            void act({
                              method: "permission",
                              permission: "lockedUse",
                            })
                          }
                        >
                          {lockedUse.setupState === "approval"
                            ? "Open Settings"
                            : "Set up…"}
                        </button>
                      )}
                  </div>
                )}
                {lockedUse?.setupError && !yaOnly && (
                  <p className="note group-note">{lockedUse.setupError}</p>
                )}
                {windows && lockedUse && (
                  <p className="note group-note">
                    An approved controller supplies your password once per task.
                    Locked-screen tasks use an opaque cover on one display and
                    relock before removing it. Tasks that start unlocked stay
                    unlocked when they finish. No password is saved. Install the
                    helper in Permissions, then choose the controller's public
                    approval.
                  </p>
                )}
                {trustSupported && (
                  <div className="ya-row">
                    <label className="scope" title={on ? lockedOff : undefined}>
                      <input
                        type="checkbox"
                        aria-label="Only the YepAnywhere app (experimental)"
                        checked={yaOnly}
                        onChange={(e) => setYaChoice(e.target.checked)}
                      />
                      Only the YepAnywhere app
                      <span className="badge">Experimental</span>
                    </label>
                    {yaOnly && (
                      <ul className="note caveats">
                        <li>
                          Only agents started by the YepAnywhere desktop app in
                          /Applications. Not the YepAnywhere CLI or other
                          servers.
                        </li>
                        <li>
                          View and control the unlocked screen only. No browser
                          access or locked-screen use.
                        </li>
                        <li>
                          No time limit: stays on until you turn access off.
                        </li>
                        <li>
                          Restart YepAnywhere sessions after changing this.
                        </li>
                      </ul>
                    )}
                  </div>
                )}
                {!on && (
                  <div className="group-footer">
                    {yaOnly ? (
                      <span className="note">Until you turn access off</span>
                    ) : (
                      <label className="duration">
                        For
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
                    )}
                  </div>
                )}
              </fieldset>
            )}
            {!standing && (on || !yaOnly) && (
              <p className="note">
                {on
                  ? "Turn access off to change these."
                  : "Any agent or script running as your user can use this access."}
              </p>
            )}
            {state?.desktopCallerTrust?.storageInvalid && (
              <p className="note">
                YepAnywhere trust storage needs attention. YepAnywhere access is
                blocked.
              </p>
            )}
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
                    <span className="row-label">UAC and elevated apps</span>
                    <span className="row-status">
                      {state?.uac?.installed ? "Installed" : "Not installed"}
                    </span>
                    <button
                      disabled={busy || !!grant || !!state?.pending}
                      onClick={() =>
                        void act({
                          method: "permission.uac",
                          remove: !!state?.uac?.installed,
                        })
                      }
                    >
                      {state?.uac?.installed
                        ? "Remove helper…"
                        : "Install helper…"}
                    </button>
                  </div>
                  <p className="note">
                    Windows asks for administrator approval. Installation leaves
                    UAC control off.
                  </p>
                  {state?.uac?.setupError && (
                    <p className="note">{state.uac.setupError}</p>
                  )}
                  <div className="setting-row">
                    <span className="row-label">
                      Other users and cold login
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
                        aria-label={`Open ${title} settings`}
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
              {mac &&
                state?.lockedUse?.supported &&
                state.deployment.policy.grantMode === "approval" && (
                  <>
                    <div className="setting-row">
                      <span
                        className={
                          "permission-icon " +
                          (state.lockedUse.permissionReady ? "done" : "")
                        }
                      >
                        {state.lockedUse.permissionReady ? (
                          <Check size={15} />
                        ) : (
                          <ShieldCheck size={15} />
                        )}
                      </span>
                      <span className="row-label">Machine Control helper</span>
                      <span className="row-status">
                        {state.lockedUse.permissionReady
                          ? "Granted"
                          : state.lockedUse.setupState === "approval"
                            ? "Awaiting approval"
                            : state.lockedUse.setupState !== "idle"
                              ? "Preparing"
                              : "Required for locked use"}
                      </span>
                      <button
                        aria-label={
                          state.lockedUse.setupState === "approval"
                            ? "Open Machine Control helper settings"
                            : state.lockedUse.permissionReady
                              ? "Repair Machine Control helper"
                              : "Set up Machine Control helper"
                        }
                        disabled={
                          busy ||
                          !!state.lockedUse.controlSessionId ||
                          !!state.pending ||
                          !["idle", "approval"].includes(
                            state.lockedUse.setupState,
                          )
                        }
                        onClick={() =>
                          void act({
                            method: "permission",
                            permission: "lockedUse",
                          })
                        }
                      >
                        {state.lockedUse.setupState === "approval"
                          ? "Open Settings"
                          : state.lockedUse.permissionReady
                            ? "Repair"
                            : "Set up"}
                      </button>
                      {["granted", "requires_approval"].includes(
                        state.lockedUse.helperApproval,
                      ) && (
                        <button
                          aria-label="Remove Machine Control helper"
                          disabled={
                            busy ||
                            !!state.lockedUse.controlSessionId ||
                            !!state.pending ||
                            !["idle", "approval"].includes(
                              state.lockedUse.setupState,
                            )
                          }
                          onClick={() =>
                            void act({
                              method: "permission.remove",
                              permission: "lockedUse",
                            })
                          }
                        >
                          Remove
                        </button>
                      )}
                    </div>
                    <p className="note">
                      Needed for locked-screen access. Approve Machine Control
                      in macOS Login Items &amp; Extensions.
                    </p>
                    {state.lockedUse.setupState === "capture" && (
                      <p className="note">
                        Preparing screen capture… Approve any macOS capture
                        prompt.
                      </p>
                    )}
                    {state.lockedUse.setupError && (
                      <p className="note">{state.lockedUse.setupError}</p>
                    )}
                    {state.lockedUse.helperNote && (
                      <p className="note">{state.lockedUse.helperNote}</p>
                    )}
                    {!!state.lockedUse.unlockRulePeers?.length && (
                      <p className="note">
                        Other lock screen plug-ins can also unlock this Mac:{" "}
                        {state.lockedUse.unlockRulePeers.join(", ")}
                      </p>
                    )}
                  </>
                )}
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
                    aria-label="Set up browser extension"
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
            {state?.controlPolicy?.supported && (
              <section className="group" aria-label="Polite computer control">
                <h2 className="group-title">When an agent wants control</h2>
                <label className="setting-row">
                  <span className="row-label">Takeover</span>
                  <select
                    aria-label="Takeover policy"
                    value={state.controlPolicy.mode}
                    disabled={busy || !!state.admission?.active}
                    onChange={(event) =>
                      void act({
                        method: "control_policy",
                        mode: event.target.value,
                        noticeSeconds: state.controlPolicy?.noticeSeconds ?? 10,
                      })
                    }
                  >
                    <option value="when_idle">
                      Wait for quiet, then announce
                    </option>
                    <option value="announce">
                      Announce even when I’m using the computer
                    </option>
                  </select>
                </label>
                <label className="setting-row">
                  <span className="row-label">Notice countdown</span>
                  <select
                    aria-label="Notice countdown"
                    value={state.controlPolicy.noticeSeconds}
                    disabled={busy || !!state.admission?.active}
                    onChange={(event) =>
                      void act({
                        method: "control_policy",
                        mode: state.controlPolicy?.mode ?? "when_idle",
                        noticeSeconds: Number(event.target.value),
                      })
                    }
                  >
                    <option value={5}>5 seconds</option>
                    <option value={10}>10 seconds</option>
                    <option value={30}>30 seconds</option>
                    <option value={60}>1 minute</option>
                  </select>
                </label>
                <p className="note group-note">
                  Using the keyboard or mouse interrupts an agent. On a locked
                  screen, displays stay covered and agents start once the
                  computer is quiet.
                </p>
              </section>
            )}
            {windows && state?.uac && (
              <section className="group" aria-label="UAC control">
                <label className="setting-row">
                  <span className="row-label">
                    Allow UAC and elevated app control
                  </span>
                  <input
                    type="checkbox"
                    checked={state.uac.enabled}
                    disabled={busy || !state.uac.installed || !!state.pending}
                    onChange={(e) =>
                      void act({
                        method: "uac.enable",
                        enabled: e.target.checked,
                      })
                    }
                  />
                </label>
                <p className="note">
                  Approved tasks can approve or cancel UAC consent prompts and
                  control elevated apps. Changing this setting stops access. It
                  starts off each time Machine Control opens.
                </p>
                {!state.uac.installed && (
                  <button
                    className="text-button"
                    onClick={() => navigate("setup")}
                  >
                    Install the helper in Permissions <ArrowUpRight size={13} />
                  </button>
                )}
                <p className="note">
                  Password prompts and lock/login control are unavailable.
                </p>
              </section>
            )}
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
                      disabled={!!updateInstallBlockedReason}
                      aria-describedby={
                        updateInstallBlockedReason
                          ? "update-install-blocked-reason"
                          : undefined
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
              {update?.availableVersion &&
                state?.updateInstallSupported !== false &&
                updateInstallBlockedReason && (
                  <div className="group-footer">
                    <p
                      className="note"
                      id="update-install-blocked-reason"
                      role="status"
                    >
                      {updateInstallBlockedReason}
                    </p>
                    {grant && !standing && !state?.pending && (
                      <button onClick={() => navigate("access")}>
                        Go to Access
                      </button>
                    )}
                  </div>
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
            {windows &&
              pendingScopes.some(
                (s) => s === "browser" || s === "devtools",
              ) && (
                <p className="note">
                  Browser access can attach local files to websites.
                </p>
              )}
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
