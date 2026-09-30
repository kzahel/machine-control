import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";
import {
  Activity,
  ArrowUpRight,
  Check,
  Circle,
  Clock3,
  Command,
  Monitor,
  Settings2,
  ShieldCheck,
  Square,
  Zap,
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
};
const labels: Record<Scope, string> = {
  observe: "View the desktop",
  control: "Control apps and input",
  browser: "Use browser tabs",
  devtools: "Browser developer access",
};
async function native(command: Record<string, unknown>) {
  return invoke<{ state?: State; extensionPath?: string }>("operator_command", {
    command,
  });
}
function App() {
  const [state, setState] = useState<State>();
  const [page, setPage] = useState("overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [scopes, setScopes] = useState<Scope[]>(["observe", "control"]);
  const [duration, setDuration] = useState(900);
  const [pendingScopes, setPendingScopes] = useState<Scope[]>([]);
  const [pendingDuration, setPendingDuration] = useState(900);
  const [update, setUpdate] = useState<Awaited<ReturnType<typeof check>>>(null);
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
      <aside>
        <div className="brand">
          <div className="mark">
            <Command size={21} />
          </div>
          <div>
            Machine Control<small>YOUR COMPUTER. YOUR CALL.</small>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {[
            ["overview", "Overview", Monitor],
            ["setup", "Setup", ShieldCheck],
            ["activity", "Activity", Activity],
            ["settings", "Settings", Settings2],
          ].map(([id, label, Icon]) => {
            const I = Icon as typeof Monitor;
            return (
              <button
                key={id as string}
                className={page === id ? "selected" : ""}
                onClick={() => setPage(id as string)}
              >
                <I size={18} />
                {label as string}
                {id === "setup" && !ready && <span className="dot" />}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <span className={"status-dot " + (grant || standing ? "on" : "")} />
          {grant
            ? "Access active"
            : standing
              ? "Standing access"
              : "Access off"}
          <small>macOS preview · {state?.version ?? "connecting"}</small>
        </div>
      </aside>
      <main>
        <header>
          <div className="eyebrow">LOCAL WORKSPACE</div>
          <div className="header-row">
            <h1>{page[0].toUpperCase() + page.slice(1)}</h1>
            <span className="badge">
              <Circle size={7} fill="currentColor" /> This Mac
            </span>
          </div>
          <p className="subtitle">
            {page === "overview"
              ? "Give agents a hand. Keep yourself in control."
              : page === "setup"
                ? "A few permissions, then you’re ready."
                : page === "activity"
                  ? "See what Machine Control has been asked to do."
                  : "Make Machine Control work your way."}
          </p>
        </header>
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
        {page === "overview" && (
          <>
            <section className={"hero " + (grant || standing ? "active" : "")}>
              <div className="hero-icon">
                <ShieldCheck size={28} />
              </div>
              <div>
                <div className="eyebrow">
                  {standing
                    ? "APPLIANCE POLICY"
                    : grant
                      ? "APPROVED ACCESS"
                      : "YOU’RE IN CONTROL"}
                </div>
                <h2>
                  {standing
                    ? "Standing access is enabled"
                    : grant
                      ? "Access is active"
                      : "Your computer is yours."}
                </h2>
                <p>
                  {standing
                    ? "This test appliance allows standing access under its installed policy."
                    : grant
                      ? `${grant.requester} · ${Math.ceil(grant.remainingSeconds / 60)} min remaining`
                      : "Agents need your approval before they can view or control this Mac."}
                </p>
              </div>
              {grant && (
                <button
                  className="danger"
                  disabled={busy}
                  onClick={() => void act({ method: "stop" })}
                >
                  <Square size={14} /> Stop access
                </button>
              )}
            </section>
            <div className="section-heading">
              <h3>Allow access</h3>
              <span>Temporary, visible, revocable</span>
            </div>
            <section className="card">
              <p className="card-intro">
                Choose what an agent can do, and for how long.
              </p>
              <div className="scope-grid">
                {(Object.keys(labels) as Scope[]).map((s) => (
                  <label
                    className={"scope " + (scopes.includes(s) ? "checked" : "")}
                    key={s}
                  >
                    <input
                      type="checkbox"
                      checked={scopes.includes(s)}
                      onChange={() => selected(scopes, setScopes, s)}
                    />
                    <span>
                      {labels[s]}
                      <small>
                        {s === "observe"
                          ? "Screenshots and app information"
                          : s === "control"
                            ? "Keyboard, pointer and app actions"
                            : s === "browser"
                              ? "Navigate, read and interact with tabs"
                              : "Scripts and raw DevTools commands"}
                      </small>
                    </span>
                  </label>
                ))}
              </div>
              <div className="card-footer">
                <label className="duration">
                  <Clock3 size={16} /> For{" "}
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
                  <Zap size={15} /> Allow selected access
                </button>
              </div>
            </section>
            <p className="footnote">
              Preview: an approval currently allows all callers running as your
              user. Access ends on expiry, Stop, lock, or app restart.
            </p>
            <div className="section-heading">
              <h3>Ready when you are</h3>
              <button className="text-button" onClick={() => setPage("setup")}>
                Review setup <ArrowUpRight size={14} />
              </button>
            </div>
            <div className="readiness">
              <div>
                <span className={"status-dot " + (ready ? "on" : "")} />
                <strong>
                  {ready ? "Desktop permissions ready" : "Finish desktop setup"}
                </strong>
                <small>Accessibility + Screen Recording</small>
              </div>
              <div>
                <span
                  className={
                    "status-dot " + (state?.browser.connected ? "on" : "")
                  }
                />
                <strong>
                  {state?.browser.connected
                    ? "Browser connected"
                    : "Browser optional"}
                </strong>
                <small>Connect the Chrome extension for tab control</small>
              </div>
            </div>
          </>
        )}
        {page === "setup" && (
          <section className="card setup-card">
            {[
              [
                "accessibility",
                "Accessibility",
                "Read application controls and deliver keyboard and pointer input.",
              ],
              [
                "screenRecording",
                "Screen Recording",
                "Capture the screen and application windows.",
              ],
            ].map(([id, title, description]) => (
              <div className="setup-row" key={id}>
                <div
                  className={
                    "step-icon " +
                    (state?.permissions[id as keyof State["permissions"]]
                      ? "done"
                      : "")
                  }
                >
                  {state?.permissions[id as keyof State["permissions"]] ? (
                    <Check size={18} />
                  ) : (
                    <Monitor size={18} />
                  )}
                </div>
                <div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                  <small>
                    {state?.permissions[id as keyof State["permissions"]]
                      ? "Granted"
                      : "Permission required"}
                  </small>
                </div>
                <button
                  disabled={busy}
                  onClick={() =>
                    void act({ method: "permission", permission: id })
                  }
                >
                  Open Settings <ArrowUpRight size={14} />
                </button>
              </div>
            ))}
            <div className="setup-row">
              <div
                className={
                  "step-icon " + (state?.browser.connected ? "done" : "")
                }
              >
                <Command size={18} />
              </div>
              <div>
                <h3>
                  Browser extension <span className="optional">Optional</span>
                </h3>
                <p>
                  Control Chrome tabs through the Machine Control extension.
                </p>
                <small>
                  {state?.browser.connected
                    ? "Connected"
                    : "Developer preview: load the bundled extension unpacked."}
                </small>
              </div>
              <button
                disabled={busy}
                onClick={async () => {
                  try {
                    const result = await native({ method: "browser.setup" });
                    setNotice(
                      `Extension path copied. In Chrome, open chrome://extensions, enable Developer mode, choose Load unpacked, and paste ${result.extensionPath}.`,
                    );
                  } catch (e) {
                    setError(String(e));
                  }
                }}
              >
                Set up browser
              </button>
            </div>
            <div className="setup-note">
              After enabling Screen Recording, restart Machine Control so it
              sees the new permission. Choose Later in macOS’s Quit & Reopen
              dialog if you have already restarted.
            </div>
            <button onClick={() => void relaunch()}>
              Restart Machine Control
            </button>
          </section>
        )}
        {page === "activity" && (
          <section className="card activity-card">
            {!state?.activity.length ? (
              <div className="empty">
                <Activity size={32} />
                <h3>No recent activity</h3>
                <p>Requests will appear here while this app is running.</p>
              </div>
            ) : (
              state.activity.map((entry, i) => (
                <div className="activity-row" key={i}>
                  <span
                    className={"status-dot " + (entry.accepted ? "on" : "")}
                  />
                  <div>
                    <strong>{entry.operation}</strong>
                    <small>
                      {entry.accepted
                        ? "Accepted"
                        : (entry.errorCode ?? "Refused")}
                    </small>
                  </div>
                  <time>{new Date(entry.at).toLocaleTimeString()}</time>
                </div>
              ))
            )}
          </section>
        )}
        {page === "settings" && (
          <>
            <section className="card">
              <h3>Updates</h3>
              <p>
                Signed desktop packages. Installation restarts the app and ends
                access.
              </p>
              <div className="settings-actions">
                <button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const candidate = await check();
                      setUpdate(candidate);
                      setNotice(
                        candidate
                          ? `Version ${candidate.version} is available.`
                          : "You’re up to date.",
                      );
                    } catch {
                      setNotice(
                        "The public update feed is not available for this preview. Use a verified CI package.",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
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
            <section className="card details">
              <h3>About this installation</h3>
              <dl>
                <dt>Version</dt>
                <dd>{state?.version}</dd>
                <dt>Policy</dt>
                <dd>{state?.deployment.policy.preset}</dd>
                <dt>Resident connection</dt>
                <dd>{state?.socket}</dd>
              </dl>
              <p>
                Closing this window keeps Machine Control in the menu bar. Quit
                from the menu bar to stop the app.
              </p>
            </section>
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
            <ShieldCheck size={32} />
            <div className="eyebrow">APPROVAL REQUEST</div>
            <h2 id="approval-title">An agent wants to use this Mac</h2>
            <p className="request-reason">{state.pending.reason}</p>
            <p className="caller">
              {state.pending.caller}
              <small>Caller identity is unverified</small>
            </p>
            <div className="approval-scopes">
              {state.pending.scopes.map((s) => (
                <label key={s}>
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
              Allow for{" "}
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
                      {v / 60} minutes
                    </option>
                  ))}
              </select>
            </label>
            <div className="approval-actions">
              <button
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
            <small>
              Input through Machine Control is paused while this request is
              open.
            </small>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
