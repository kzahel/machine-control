import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";
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
type State = {
  deployment: {
    policy: { preset: string; grantMode: string };
    grant: null | {
      remainingSeconds: number;
      scopes: Scope[];
      requester: string;
      reason: string;
    };
    pendingRequest: unknown;
  };
  permissions: { accessibility: boolean; screenRecording: boolean };
  browser: { connected: boolean };
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
  version: string;
  socket: string;
  stopShortcutAvailable: boolean;
};
const labels: Record<Scope, string> = {
  observe: "View desktop",
  control: "Control apps and input",
  browser: "Browser tabs",
  devtools: "Browser scripts and DevTools",
};
async function native(command: Record<string, unknown>) {
  return invoke<{ state?: State; extensionPath?: string }>("operator_command", {
    command,
  });
}
function App() {
  const [state, setState] = useState<State>();
  const [page, setPage] = useState("access");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [scopes, setScopes] = useState<Scope[]>(["observe", "control"]);
  const [duration, setDuration] = useState(900);
  const [pendingScopes, setPendingScopes] = useState<Scope[]>([]);
  const [pendingDuration, setPendingDuration] = useState(900);
  const [update, setUpdate] = useState<Awaited<ReturnType<typeof check>>>(null);
  const checking = useRef(false);
  const checkUpdates = async () => {
    if (checking.current) return;
    checking.current = true;
    setBusy(true);
    setError("");
    setNotice("Checking…");
    try {
      const candidate = await check({
        timeout: 20000,
        headers: { "X-Check-Reason": "manual" },
      });
      setUpdate((previous) => {
        void previous?.close();
        return candidate;
      });
      setNotice(
        candidate ? `Version ${candidate.version} available.` : "Up to date.",
      );
    } catch {
      setNotice("Couldn’t check for updates. Try again.");
    } finally {
      checking.current = false;
      setBusy(false);
    }
  };
  const trayAction = useRef(checkUpdates);
  trayAction.current = checkUpdates;
  useEffect(() => {
    const listener = listen<string>("tray-command", ({ payload }) => {
      setPage(payload === "open" ? "access" : "settings");
      setNotice("");
      if (payload === "updates") void trayAction.current();
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
    } catch (e) {
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
  const grant = state?.deployment.grant;
  const standing = state?.deployment.policy.grantMode === "standing";
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
                        ? "Access active"
                        : "Access off"}
                </h1>
                {grant && (
                  <p className="grant-detail">
                    {grant.requester} · {Math.ceil(grant.remainingSeconds / 60)}{" "}
                    min left
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
            <section className="group" aria-label="Access scopes">
              <div className="scope-list">
                {(Object.keys(labels) as Scope[]).map((s) => (
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
                  </select>
                </label>
                <button
                  className="primary"
                  disabled={busy || !state || standing || scopes.length === 0}
                  onClick={() => void act({ method: "arm", scopes, duration })}
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
              {[
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
                  Browser extension <span className="optional">(optional)</span>
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
            </section>
            <div className="restart-row">
              <p className="note">Restart after changing Screen Recording.</p>
              <button onClick={() => void relaunch()}>Restart</button>
            </div>
          </>
        )}
        {page === "activity" && (
          <section className="group activity-list" aria-label="Recent activity">
            {!state?.activity.length ? (
              <p className="empty">No recent activity</p>
            ) : (
              state.activity.map((entry, i) => (
                <div className="activity-row" key={i}>
                  <span
                    className={"status-dot " + (entry.accepted ? "on" : "")}
                  />
                  <strong>{entry.operation}</strong>
                  <span className="row-status">
                    {entry.accepted
                      ? "Accepted"
                      : (entry.errorCode ?? "Refused")}
                  </span>
                  <time>{new Date(entry.at).toLocaleTimeString()}</time>
                </div>
              ))
            )}
          </section>
        )}
        {page === "settings" && (
          <>
            <section className="group" aria-label="Updates">
              <div className="setting-row">
                <span className="row-label">Updates</span>
                <button disabled={busy} onClick={() => void checkUpdates()}>
                  Check for updates
                </button>
                {update && (
                  <button
                    disabled={busy || !!grant || standing || !!state?.pending}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await invoke("install_update", {
                          version: update.version,
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
                    ? "⌃⌥⌘."
                    : "Unavailable; use Stop access"}
                </dd>
                <dt>Socket</dt>
                <dd>{state?.socket ?? "—"}</dd>
              </dl>
            </section>
            <p className="note">
              Close hides the window. Quit from the menu bar.
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
