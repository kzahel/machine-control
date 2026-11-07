import React, { useEffect, useRef, useState } from "react";

type Surface = "desktop" | "browser";
type Mode = "off" | "ask" | "automatic";
export type SurfacePolicy = {
  schema: string;
  experienceVersion?: number;
  preferences?: AccessPreferences;
  available?: boolean;
  humanInputReady?: boolean;
  handoffCooldownSurfaces?: Surface[];
  handoffCooldownRemainingSeconds?: number;
  globalPauses?: { reason: string; remainingSeconds: number | null }[];
  deferrals?: {
    resource: string;
    surfaces: Surface[];
    remainingSeconds: number | null;
  }[];
  noticeSeconds: number;
  surfaces: Record<
    Surface,
    {
      mode: Mode;
      expired: boolean;
      consentRemainingSeconds: number | null;
      profileIds: string[];
      ready: boolean;
      pauses: {
        reason: string;
        scope?: Surface | "all";
        remainingSeconds: number | null;
      }[];
    }
  >;
};
type Profile = {
  profileId: string;
  name: string;
  enabled: boolean;
  connected: boolean;
};
export type ControlRequest = {
  intentId: string;
  state: string;
  reason: string;
  surfaces?: string[];
  profileIds?: string[];
  noticeRemainingSeconds: number | null;
  blockingReasons?: string[];
  terminalReason?: string | null;
  scheduledRemainingSeconds?: number;
  taskRemainingSeconds?: number;
  waitRemainingSeconds?: number;
  held?: boolean;
  caller?: string;
};
type Act = (command: Record<string, unknown>) => Promise<boolean>;
type AccessPreferences = {
  desktopNoticeSeconds: number;
  browserNoticeSeconds: number;
  yieldWaitSeconds: number;
  yieldReapprove: boolean;
};
type Choices = AccessPreferences & {
  desktop: "ask" | "automatic";
  browser: "ask" | "automatic";
  duration: number;
  profileIds: string[];
  enabled: Surface[];
  noticeSeconds: number;
};
const surfaces = ["desktop", "browser"] as const;
const key = "machine-control.surface-choices.v3";
function choices(policy: SurfacePolicy): Choices {
  let saved: Partial<Choices> = {};
  try {
    saved = JSON.parse(
      localStorage.getItem(key) ??
        localStorage.getItem("machine-control.surface-choices.v2") ??
        "{}",
    );
    if (!saved || typeof saved !== "object") saved = {};
  } catch {
    /* Preferences never authorize access. */
  }
  return {
    desktop: saved.desktop === "ask" ? "ask" : "automatic",
    browser: saved.browser === "ask" ? "ask" : "automatic",
    duration: [0, 900, 3600, 28800].includes(saved.duration!)
      ? saved.duration!
      : 0,
    profileIds: Array.isArray(saved.profileIds)
      ? [
          ...new Set(
            saved.profileIds.filter(
              (id) =>
                typeof id === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(id),
            ),
          ),
        ].slice(0, 64)
      : [],
    enabled: Array.isArray(saved.enabled)
      ? surfaces.filter((s) => saved.enabled!.includes(s))
      : [],
    noticeSeconds: policy.noticeSeconds,
    desktopNoticeSeconds:
      typeof saved.desktopNoticeSeconds === "number" &&
      Number.isInteger(saved.desktopNoticeSeconds) &&
      saved.desktopNoticeSeconds >= 0 &&
      saved.desktopNoticeSeconds <= 60
        ? saved.desktopNoticeSeconds
        : (policy.preferences?.desktopNoticeSeconds ?? policy.noticeSeconds),
    browserNoticeSeconds:
      typeof saved.browserNoticeSeconds === "number" &&
      Number.isInteger(saved.browserNoticeSeconds) &&
      saved.browserNoticeSeconds >= 0 &&
      saved.browserNoticeSeconds <= 60
        ? saved.browserNoticeSeconds
        : (policy.preferences?.browserNoticeSeconds ?? policy.noticeSeconds),
    yieldWaitSeconds: [10, 30, 60, 300].includes(saved.yieldWaitSeconds!)
      ? saved.yieldWaitSeconds!
      : (policy.preferences?.yieldWaitSeconds ?? 60),
    yieldReapprove:
      typeof saved.yieldReapprove === "boolean"
        ? saved.yieldReapprove
        : (policy.preferences?.yieldReapprove ?? false),
  };
}
const enabled = (policy: SurfacePolicy, surface: Surface) =>
  policy.surfaces[surface].mode !== "off" && !policy.surfaces[surface].expired;
function liveChoices(policy: SurfacePolicy, saved: Choices): Choices {
  return {
    ...saved,
    ...(policy.preferences ?? {}),
    noticeSeconds: policy.noticeSeconds,
    desktop: enabled(policy, "desktop")
      ? (policy.surfaces.desktop.mode as Choices["desktop"])
      : saved.desktop,
    browser: enabled(policy, "browser")
      ? (policy.surfaces.browser.mode as Choices["browser"])
      : saved.browser,
    profileIds: enabled(policy, "browser")
      ? [...policy.surfaces.browser.profileIds]
      : saved.profileIds,
  };
}
const signature = (policy: SurfacePolicy) =>
  JSON.stringify([
    policy.noticeSeconds,
    policy.preferences,
    ...surfaces.map((s) => [
      policy.surfaces[s].mode,
      policy.surfaces[s].expired,
      [...policy.surfaces[s].profileIds].sort(),
    ]),
  ]);
const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
function Switch({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={checked}
      disabled={disabled}
      className={"access-switch" + (checked ? " checked" : "")}
      onClick={onChange}
    >
      <span aria-hidden="true" className="switch-thumb" />
      <span className="switch-word">{checked ? "On" : "Off"}</span>
    </button>
  );
}

type BrowserConnection = {
  connected: boolean;
  problems?: { reason: string }[];
};

/** Explains why no profile is selectable and offers the store/registration
 * action (`browser.setup` also re-registers the native host). */
function BrowserProfileHelp({
  profiles,
  browser,
  disabled,
  act,
}: {
  profiles: Profile[];
  browser?: BrowserConnection;
  disabled: boolean;
  act: Act;
}) {
  const [opened, setOpened] = useState(false);
  const problems = browser?.problems ?? [];
  const outdated = problems.some((p) => p.reason.includes("protocol_required"));
  const refused = problems.length > 0 && !outdated;
  const enabled = profiles.some((p) => p.enabled);
  const installed = profiles.length > 0 || !!browser?.connected;
  async function openStore() {
    setOpened(false);
    if (await act({ method: "browser.setup" })) setOpened(true);
  }
  const storeButton = (label: string) => (
    <button
      type="button"
      className="browser-store"
      disabled={disabled}
      onClick={openStore}
    >
      {label}
    </button>
  );
  return (
    <div className="browser-help">
      {outdated ? (
        <>
          <p className="note" role="alert">
            Your Machine Control extension is too old to share profiles. Update
            it, then turn on Enable this profile in its side panel.
          </p>
          {storeButton("Update Chrome extension")}
        </>
      ) : refused ? (
        <p className="note" role="alert">
          A browser profile connection was refused. In that Chrome profile,
          click the Machine Control toolbar icon, choose Reset profile identity,
          then approve the profile here again.
        </p>
      ) : enabled ? null : installed ? (
        <p className="note">
          In Chrome, click the Machine Control toolbar icon and turn on Enable
          this profile in its side panel.
        </p>
      ) : (
        <>
          <p className="note">
            No browser extension is connected. Install Machine Control in
            Chrome, then click its toolbar icon and turn on Enable this profile.
          </p>
          {storeButton("Install Chrome extension")}
        </>
      )}
      {opened && (
        <p className="note" role="status">
          Chrome Web Store opened. Install or update Machine Control there.
        </p>
      )}
      <details className="browser-troubleshooting">
        <summary>Troubleshooting</summary>
        <ul className="note">
          <li>
            Install the extension in each Chrome profile you want to share and
            enable each one in its side panel.
          </li>
          <li>
            Keep one Machine Control extension per Chrome profile. A Developer
            mode copy and the Web Store copy are separate extensions.
          </li>
          <li>
            To update now, open chrome://extensions, turn on Developer mode and
            click Update.
          </li>
          <li>
            Still not connected? Re-register Machine Control with Chrome, then
            reload the extension from chrome://extensions.
          </li>
        </ul>
        <button
          type="button"
          className="browser-store"
          disabled={disabled}
          onClick={openStore}
        >
          Re-register and open Web Store
        </button>
      </details>
    </div>
  );
}

export function SurfaceAccess({
  visible = true,
  policy,
  profiles,
  busy,
  act,
  protectedAccess,
  lockedBrowser,
  browser,
}: {
  visible?: boolean;
  policy: SurfacePolicy;
  profiles: Profile[];
  browser?: BrowserConnection;
  busy: boolean;
  act: Act;
  lockedBrowser?: { supported: boolean; enabled: boolean };
  protectedAccess?: {
    supported: boolean;
    enabled: boolean;
    permissionReady: boolean;
    credentialSource?: string;
    controlSessionId: string | null;
    setupState: string;
    setupError: string | null;
  };
}) {
  const [saved, setSaved] = useState(() => choices(policy));
  const [draft, setDraft] = useState(() => liveChoices(policy, saved));
  const [baseline, setBaseline] = useState(draft);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);
  const observed = useRef(signature(policy));
  const policyRef = useRef(policy);
  policyRef.current = policy;
  const dirty = !same(draft, baseline);
  const blocked = busy || working || policy.available === false;
  const modern = policy.experienceVersion === 1 && !!policy.preferences;
  const optionFields = [
    "desktopNoticeSeconds",
    "browserNoticeSeconds",
    "yieldWaitSeconds",
    "yieldReapprove",
  ] as const;
  async function applyOptions(selected: readonly Surface[]) {
    if (!modern) return true;
    const value = { ...policyRef.current.preferences! };
    if (selected.includes("desktop")) {
      value.desktopNoticeSeconds = draft.desktopNoticeSeconds;
      value.yieldWaitSeconds = draft.yieldWaitSeconds;
      value.yieldReapprove = draft.yieldReapprove;
    }
    if (selected.includes("browser"))
      value.browserNoticeSeconds = draft.browserNoticeSeconds;
    return act({ method: "access_preferences", preferences: value });
  }
  const selection = draft.profileIds;
  const validProfiles =
    selection.length > 0 &&
    selection.every((id) =>
      profiles.some((p) => p.profileId === id && p.enabled),
    );
  const external = signature(policy);
  useEffect(() => {
    if (external === observed.current) return;
    observed.current = external;
    if (working) return;
    if (dirty) setConflict(true);
    else {
      const next = liveChoices(policy, saved);
      setDraft(next);
      setBaseline(next);
    }
  }, [external, working, dirty, policy, saved]);
  function remember(next: Choices) {
    setSaved(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* Optional form preferences. */
    }
  }
  function reset() {
    const next = liveChoices(policyRef.current, saved);
    setDraft(next);
    setBaseline(next);
    setConflict(false);
    setMessage("");
  }
  async function configure(surface: Surface, on: boolean) {
    return act({
      method: "surface.configure",
      surface,
      mode: on ? draft[surface] : "off",
      duration: draft.duration,
      lifetime: draft.duration === 0 ? "until_stopped" : "timed",
      browserProfileIds: surface === "browser" ? selection : [],
    });
  }
  async function toggle(surface?: Surface) {
    if (working) return;
    setWorking(true);
    setMessage("");
    const current = policyRef.current;
    const turningOff = surface
      ? enabled(current, surface)
      : surfaces.some((s) => enabled(current, s));
    const selected = surface ? [surface] : saved.enabled;
    if (!turningOff && !selected.length) {
      setMessage("Turn on Desktop or Browser below to choose access.");
      setWorking(false);
      return;
    }
    if (!turningOff && selected.includes("browser") && !validProfiles) {
      setMessage("Choose an enabled browser profile first.");
      setWorking(false);
      return;
    }
    if (turningOff) {
      const wasOn = surfaces.filter((s) => enabled(current, s));
      const ok = surface
        ? await configure(surface, false)
        : await act({ method: "stop" });
      if (ok)
        remember({
          ...saved,
          enabled: surface
            ? wasOn.length > 1
              ? wasOn.filter((s) => s !== surface)
              : [surface]
            : wasOn,
        });
    } else {
      if (!(await applyOptions(selected))) {
        setMessage("Start settings were not applied. Access remains off.");
        setWorking(false);
        return;
      }
      let applied: Surface[] = [];
      for (const s of selected) {
        if (!(await configure(s, true))) {
          setMessage(
            applied.length
              ? "Some access was enabled. Review the switches before trying again."
              : "Access was not enabled.",
          );
          break;
        }
        applied.push(s);
      }
      if (applied.length) {
        remember({
          ...draft,
          enabled: [
            ...new Set([
              ...surfaces.filter((s) => enabled(current, s)),
              ...applied,
            ]),
          ],
        });
        setBaseline((previous) => ({
          ...previous,
          duration: surfaces.some(
            (s) => enabled(current, s) && !applied.includes(s),
          )
            ? previous.duration
            : draft.duration,
          ...Object.fromEntries(applied.map((s) => [s, draft[s]])),
          ...(modern && applied.includes("desktop")
            ? {
                desktopNoticeSeconds: draft.desktopNoticeSeconds,
                yieldWaitSeconds: draft.yieldWaitSeconds,
                yieldReapprove: draft.yieldReapprove,
              }
            : {}),
          ...(modern && applied.includes("browser")
            ? { browserNoticeSeconds: draft.browserNoticeSeconds }
            : {}),
          ...(applied.includes("browser")
            ? { profileIds: [...selection] }
            : {}),
        }));
      }
    }
    setWorking(false);
  }
  async function apply() {
    if (working || conflict) return;
    setWorking(true);
    setMessage("");
    const current = policyRef.current;
    const changed = surfaces.filter(
      (s) =>
        enabled(current, s) &&
        (draft[s] !== baseline[s] ||
          draft.duration !== baseline.duration ||
          (s === "browser" &&
            !same([...selection].sort(), [...baseline.profileIds].sort()))),
    );
    let count = 0,
      ok = true;
    if (
      modern &&
      optionFields.some((field) => draft[field] !== baseline[field])
    ) {
      ok = await applyOptions(surfaces);
      if (ok) ++count;
    }
    for (const surface of ok ? changed : []) {
      if (!(await configure(surface, true))) {
        ok = false;
        break;
      }
      ++count;
    }
    if (ok && !modern && draft.noticeSeconds !== baseline.noticeSeconds)
      ok = await act({
        method: "control_notice",
        noticeSeconds: draft.noticeSeconds,
      });
    if (ok) {
      remember({ ...draft, enabled: saved.enabled });
      setBaseline(draft);
      setConflict(false);
    } else {
      setConflict(true);
      setMessage(
        count
          ? "Some changes were applied. Discard remaining edits to reload the current settings."
          : "Changes were not applied. Reload the current settings before trying again.",
      );
    }
    setWorking(false);
  }
  const willConfigure = surfaces.filter(
    (s) =>
      enabled(policy, s) &&
      (draft[s] !== baseline[s] ||
        draft.duration !== baseline.duration ||
        (s === "browser" &&
          !same([...selection].sort(), [...baseline.profileIds].sort()))),
  );
  // Keep the draft hooks alive without a hidden subtree in WebKit's AX tree.
  if (!visible) return null;
  return (
    <div className="access-form">
      <div className="access-status access-heading">
        <h1>Agent access</h1>
        <Switch
          label="Agent access"
          checked={surfaces.some((s) => enabled(policy, s))}
          disabled={
            working ||
            (!surfaces.some((s) => enabled(policy, s)) &&
              (busy || policy.available === false))
          }
          onChange={() => void toggle()}
        />
      </div>
      {policy.available === false && (
        <p role="alert" className="message">
          Access is unavailable. Restart Machine Control to reconnect.
        </p>
      )}
      {message && (
        <p role="alert" className="message">
          {message}
        </p>
      )}
      {surfaces.map((surface) => {
        const state = policy.surfaces[surface],
          on = enabled(policy, surface),
          label = surface === "desktop" ? "Desktop" : "Browser";
        return (
          <section
            className="group surface-access"
            aria-label={`${label} access`}
            key={surface}
          >
            <div className="surface-heading">
              <h2>{label}</h2>
              <Switch
                label={`${label} access`}
                checked={on}
                disabled={
                  working ||
                  (!on && (busy || policy.available === false)) ||
                  (!on && surface === "browser" && !validProfiles)
                }
                onChange={() => void toggle(surface)}
              />
            </div>
            <label className="setting-row">
              <span>Before starting</span>
              <select
                aria-label={`${label} before starting`}
                disabled={blocked}
                value={
                  modern &&
                  draft[surface] === "automatic" &&
                  draft[
                    surface === "desktop"
                      ? "desktopNoticeSeconds"
                      : "browserNoticeSeconds"
                  ] === 0
                    ? "immediate"
                    : draft[surface]
                }
                onChange={(e) => {
                  const field =
                    surface === "desktop"
                      ? "desktopNoticeSeconds"
                      : "browserNoticeSeconds";
                  setDraft({
                    ...draft,
                    [surface]: e.target.value === "ask" ? "ask" : "automatic",
                    ...(modern
                      ? {
                          [field]:
                            e.target.value === "immediate"
                              ? 0
                              : draft[field] || 10,
                        }
                      : {}),
                  });
                }}
              >
                {modern && <option value="immediate">Start immediately</option>}
                <option value="automatic">Give me a heads-up</option>
                <option value="ask">Wait for my approval</option>
              </select>
            </label>
            {modern &&
              draft[surface] === "automatic" &&
              draft[
                surface === "desktop"
                  ? "desktopNoticeSeconds"
                  : "browserNoticeSeconds"
              ] > 0 && (
                <label className="setting-row">
                  <span>Heads-up</span>
                  <select
                    aria-label={`${label} heads-up duration`}
                    disabled={blocked}
                    value={
                      draft[
                        surface === "desktop"
                          ? "desktopNoticeSeconds"
                          : "browserNoticeSeconds"
                      ]
                    }
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        [surface === "desktop"
                          ? "desktopNoticeSeconds"
                          : "browserNoticeSeconds"]: Number(e.target.value),
                      })
                    }
                  >
                    {[
                      ...new Set([
                        draft[
                          surface === "desktop"
                            ? "desktopNoticeSeconds"
                            : "browserNoticeSeconds"
                        ],
                        5,
                        10,
                        30,
                        60,
                      ]),
                    ]
                      .sort((a, b) => a - b)
                      .map((seconds) => (
                        <option value={seconds} key={seconds}>
                          {seconds === 60 ? "1 minute" : `${seconds} seconds`}
                        </option>
                      ))}
                  </select>
                </label>
              )}
            {modern && surface === "desktop" && (
              <details className="yield-options">
                <summary>When you take control</summary>
                <label className="setting-row">
                  <span>Wait before trying again</span>
                  <select
                    aria-label="Desktop yield wait"
                    value={draft.yieldWaitSeconds}
                    disabled={blocked}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        yieldWaitSeconds: Number(e.target.value),
                      })
                    }
                  >
                    {[10, 30, 60, 300].map((seconds) => (
                      <option value={seconds} key={seconds}>
                        {seconds < 60
                          ? `${seconds} seconds`
                          : `${seconds / 60} minute${seconds > 60 ? "s" : ""}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="setting-row">
                  <span>Then</span>
                  <select
                    aria-label="After Desktop yields"
                    value={draft.yieldReapprove ? "ask" : "continue"}
                    disabled={blocked}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        yieldReapprove: e.target.value === "ask",
                      })
                    }
                  >
                    <option value="continue">Continue after a heads-up</option>
                    <option value="ask">Ask for approval again</option>
                  </select>
                </label>
              </details>
            )}
            {state.expired && <p className="note">Access expired</p>}
            {on && !state.ready && (
              <p role="status" className="note">
                {label} is temporarily unavailable.
              </p>
            )}
            {on && state.consentRemainingSeconds !== null && (
              <p className="note">
                {Math.ceil(state.consentRemainingSeconds / 60)} min remaining
              </p>
            )}
            {surface === "browser" && (
              <div className="browser-profile-list">
                <h3>Browser profiles</h3>
                {profiles
                  .filter((p) => p.enabled)
                  .map((profile) => (
                    <label className="scope" key={profile.profileId}>
                      <input
                        type="checkbox"
                        aria-label={`Allow profile ${profile.name}`}
                        checked={selection.includes(profile.profileId)}
                        disabled={blocked}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            profileIds: e.target.checked
                              ? [...selection, profile.profileId]
                              : selection.filter(
                                  (id) => id !== profile.profileId,
                                ),
                          })
                        }
                      />
                      {profile.name}
                      <span className="profile-state">
                        {profile.connected ? "Connected" : "Disconnected"}
                      </span>
                    </label>
                  ))}
                <BrowserProfileHelp
                  profiles={profiles}
                  browser={browser}
                  disabled={busy || working}
                  act={act}
                />
                {selection
                  .filter(
                    (id) =>
                      !profiles.some((p) => p.profileId === id && p.enabled),
                  )
                  .map((id) => (
                    <label className="scope" key={id}>
                      <input
                        type="checkbox"
                        checked
                        disabled={blocked}
                        onChange={() =>
                          setDraft({
                            ...draft,
                            profileIds: selection.filter(
                              (value) => value !== id,
                            ),
                          })
                        }
                      />
                      Unavailable profile · {id.slice(-8)}
                    </label>
                  ))}
              </div>
            )}
          </section>
        );
      })}
      <details className="group access-options">
        <summary>More options</summary>
        {!modern && (
          <>
            <label className="setting-row">
              <span>Heads-up duration</span>
              <select
                aria-label="Notice countdown"
                value={draft.noticeSeconds}
                disabled={blocked}
                onChange={(e) =>
                  setDraft({ ...draft, noticeSeconds: Number(e.target.value) })
                }
              >
                <option value={5}>5 seconds</option>
                <option value={10}>10 seconds</option>
                <option value={30}>30 seconds</option>
                <option value={60}>1 minute</option>
              </select>
            </label>
            <p className="note">Applies to Desktop and Browser.</p>
          </>
        )}
        <label className="setting-row">
          <span>Access duration</span>
          <select
            aria-label="Access lifetime"
            value={draft.duration}
            disabled={blocked}
            onChange={(e) =>
              setDraft({ ...draft, duration: Number(e.target.value) })
            }
          >
            <option value={0}>Until I turn it off</option>
            <option value={900}>15 minutes</option>
            <option value={3600}>1 hour</option>
            <option value={28800}>8 hours</option>
          </select>
        </label>
        {protectedAccess && (
          <section
            className="group surface-access"
            aria-label="Covered desktop access"
          >
            <h2 className="group-title">Covered desktop while locked</h2>
            <label className="scope">
              <input
                type="checkbox"
                checked={protectedAccess.enabled}
                disabled={
                  busy ||
                  !protectedAccess.supported ||
                  !protectedAccess.permissionReady ||
                  !!protectedAccess.controlSessionId
                }
                onChange={(event) =>
                  void act({
                    method: "locked_use",
                    enabled: event.target.checked,
                  })
                }
              />
              Allow prepared tasks behind an opaque cover
            </label>
            <p className="note">
              The computer relocks when the task ends. Changing this setting
              turns access off. Browser-only work can stay locked using its
              separate setting.
            </p>
            {(!protectedAccess.permissionReady ||
              (protectedAccess.credentialSource !== undefined &&
                protectedAccess.credentialSource !==
                  "service_enrolled_password")) && (
              <button
                disabled={
                  busy ||
                  !!protectedAccess.controlSessionId ||
                  !["idle", "approval"].includes(protectedAccess.setupState)
                }
                onClick={() =>
                  void act({ method: "permission", permission: "lockedUse" })
                }
              >
                Set up covered desktop access
              </button>
            )}
            {protectedAccess.setupError && (
              <p role="alert" className="note">
                {protectedAccess.setupError}
              </p>
            )}
          </section>
        )}
        {lockedBrowser?.supported && (
          <section
            className="group surface-access"
            aria-label="Browser while locked"
          >
            <label className="scope">
              <input
                type="checkbox"
                checked={lockedBrowser.enabled}
                disabled={busy}
                onChange={(event) =>
                  void act({
                    method: "browser_while_locked",
                    enabled: event.target.checked,
                  })
                }
              />
              Allow approved Browser work while locked
            </label>
            <p className="note">
              Keeps the computer locked. This setting grants no access by
              itself; Browser mode, exact profiles and a live task still apply.
            </p>
          </section>
        )}
      </details>
      {dirty && (
        <footer className="apply-footer" aria-label="Unsaved settings">
          <div>
            <strong>Unsaved changes</strong>
            {conflict && (
              <p role="status">
                Access changed elsewhere. Discard edits to reload.
              </p>
            )}
            {!!willConfigure.length && (
              <p>
                Applying ends current {willConfigure.join(" and ")} tasks
                {draft.duration === 0
                  ? " and enables access until turned off"
                  : ` and renews access for ${draft.duration >= 3600 ? `${draft.duration / 3600} hour${draft.duration > 3600 ? "s" : ""}` : `${draft.duration / 60} minutes`}`}
                .
              </p>
            )}
          </div>
          <div className="footer-actions">
            <button disabled={working} onClick={reset}>
              Discard
            </button>
            <button
              className="primary"
              disabled={
                blocked ||
                conflict ||
                (willConfigure.includes("browser") && !validProfiles)
              }
              onClick={() => void apply()}
            >
              Apply changes
            </button>
          </div>
        </footer>
      )}
    </div>
  );
}

export function SurfaceActivity({
  policy,
  requests,
  profiles,
  busy,
  act,
}: {
  policy: SurfacePolicy;
  requests: ControlRequest[];
  profiles: Profile[];
  busy: boolean;
  act: Act;
}) {
  const holding = surfaces.filter(
    (s) =>
      policy.surfaces[s].pauses.some((p) => p.scope !== "all") ||
      policy.deferrals?.some((p) => p.surfaces.includes(s)),
  );
  const resumable = (surface: Surface) =>
    policy.deferrals?.some((p) => p.surfaces.includes(surface)) ||
    policy.surfaces[surface].pauses.some(
      (p) =>
        p.scope !== "all" &&
        [
          "manual",
          "operator_deferral",
          "local_use_episode",
          "physical_takeover",
        ].includes(p.reason),
    );
  return (
    <section className="group live-tasks" aria-label="Current tasks">
      <h2>Current tasks</h2>
      {!!policy.globalPauses?.length && (
        <div className="task-row">
          <span>Access on hold</span>
          <button
            disabled={busy}
            onClick={() => void act({ method: "resume" })}
          >
            Resume access
          </button>
        </div>
      )}
      {holding.map((surface) => (
        <div className="task-row" key={surface}>
          <span>
            {surface === "desktop" ? "Desktop" : "Browser"}{" "}
            {resumable(surface) ? "on hold" : "waiting for system readiness"}
          </span>
          {resumable(surface) && (
            <button
              disabled={busy}
              onClick={() => void act({ method: "resume_surface", surface })}
            >
              Resume {surface}
            </button>
          )}
        </div>
      ))}
      {(policy.handoffCooldownRemainingSeconds ?? 0) > 0 &&
        requests.some(
          (request) =>
            request.state === "paused" &&
            request.blockingReasons?.includes("physical_takeover"),
        ) && (
          <p className="note">
            Yielded to you ·{" "}
            {policy.preferences?.yieldReapprove
              ? "Can ask for approval in"
              : "Can try again in"}{" "}
            {Math.ceil(policy.handoffCooldownRemainingSeconds!)}s
          </p>
        )}
      {enabled(policy, "desktop") && policy.humanInputReady === false && (
        <p className="note">
          Desktop is waiting for input monitoring to recover.
        </p>
      )}
      {!requests.length && !holding.length && !policy.globalPauses?.length && (
        <p className="note">No tasks running</p>
      )}
      {requests.map((request) => (
        <div className="task-row" key={request.intentId}>
          <div>
            <strong>{request.reason}</strong>
            {!!request.profileIds?.length && (
              <p className="note">
                {request.profileIds
                  .map((id) => {
                    const profile = profiles.find((p) => p.profileId === id);
                    return `${profile?.name ?? "Unavailable profile"} · …${id.slice(-8)}`;
                  })
                  .join(", ")}
              </p>
            )}
            <details className="task-details">
              <summary>Details</summary>
              <p className="note">
                {request.caller ?? "Local process"} · Identity unverified
              </p>
            </details>
            <p className="note">
              {request.surfaces
                ?.map((s) => (s === "desktop" ? "Desktop" : "Browser"))
                .join(" + ")}{" "}
              ·{" "}
              {request.state === "active"
                ? "Running"
                : request.state === "waiting_for_approval"
                  ? "Needs your approval"
                  : request.state === "announcing"
                    ? `Starts in ${Math.ceil(request.noticeRemainingSeconds ?? 0)}s`
                    : request.state === "paused"
                      ? request.held
                        ? "Paused"
                        : (request.scheduledRemainingSeconds ?? 0) > 0
                          ? `Can start in ${Math.ceil(request.scheduledRemainingSeconds!)}s`
                          : request.blockingReasons?.includes(
                                "physical_takeover",
                              )
                            ? "Yielded to you"
                            : "Waiting"
                      : request.state === "offered"
                        ? "Starting"
                        : "Queued"}
            </p>
          </div>
          <div className="request-actions">
            {policy.experienceVersion === 1 &&
              request.state === "paused" &&
              !!request.blockingReasons?.length &&
              request.blockingReasons.every((reason) =>
                ["task_held", "scheduled", "physical_takeover"].includes(
                  reason,
                ),
              ) && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void act({
                      method: "continue_control",
                      intentId: request.intentId,
                    })
                  }
                >
                  Continue now
                </button>
              )}
            {policy.experienceVersion === 1 &&
              ["active", "announcing", "offered"].includes(request.state) && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void act({
                      method: "hold_control",
                      intentId: request.intentId,
                    })
                  }
                >
                  Pause task
                </button>
              )}
            {policy.experienceVersion === 1 &&
              ["waiting_for_approval", "announcing"].includes(
                request.state,
              ) && (
                <select
                  aria-label={`Delay ${request.reason}`}
                  value=""
                  disabled={busy}
                  onChange={(e) => {
                    const seconds = Number(e.target.value);
                    if (seconds)
                      void act({
                        method:
                          request.state === "waiting_for_approval"
                            ? "approve_control"
                            : "postpone_control",
                        intentId: request.intentId,
                        duration: seconds,
                      });
                  }}
                >
                  <option value="">
                    {request.state === "waiting_for_approval"
                      ? "Allow in…"
                      : "More time…"}
                  </option>
                  {[30, 60, 300].map((seconds) => (
                    <option
                      value={seconds}
                      key={seconds}
                      disabled={
                        seconds + 65 >=
                        (request.taskRemainingSeconds ??
                          request.waitRemainingSeconds ??
                          0)
                      }
                    >
                      {seconds < 60
                        ? "30 seconds"
                        : `${seconds / 60} minute${seconds > 60 ? "s" : ""}`}
                    </option>
                  ))}
                </select>
              )}
            {request.state === "waiting_for_approval" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  void act({
                    method: "approve_control",
                    intentId: request.intentId,
                  })
                }
              >
                {policy.experienceVersion === 1 ? "Allow now" : "Allow task"}
              </button>
            )}
            {request.state === "announcing" && (
              <button
                className="primary"
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
              onClick={() =>
                void act({
                  method: "cancel_control",
                  intentId: request.intentId,
                })
              }
            >
              {request.state === "active" ? "Stop task" : "Cancel"}
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
