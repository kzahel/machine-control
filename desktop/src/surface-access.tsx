import React, { useState } from "react";

type Surface = "desktop" | "browser";
type Mode = "off" | "ask" | "automatic";
export type SurfacePolicy = {
  schema: string;
  available?: boolean;
  handoffCooldownRemainingSeconds?: number;
  deferrals?: { resource: string; remainingSeconds: number | null }[];
  noticeSeconds: number;
  surfaces: Record<Surface, {
    mode: Mode;
    expired: boolean;
    consentRemainingSeconds: number | null;
    profileIds: string[];
    ready: boolean;
    pauses: { reason: string; remainingSeconds: number | null }[];
  }>;
};
type Profile = { profileId: string; name: string; enabled: boolean; connected: boolean };
type Request = { intentId: string; state: string; reason: string; surfaces?: string[]; noticeRemainingSeconds: number | null };
type Choices = { desktop: Exclude<Mode, "off">; browser: Exclude<Mode, "off">; duration: number; profileIds: string[] };
const key = "machine-control.surface-choices.v2";
function choices(): Choices {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? "null");
    if (saved && ["ask", "automatic"].includes(saved.desktop) && ["ask", "automatic"].includes(saved.browser) &&
      [0, 900, 3600, 28800].includes(saved.duration) && Array.isArray(saved.profileIds) && saved.profileIds.length <= 64 &&
      saved.profileIds.every((id: unknown) => typeof id === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(id))) return saved;
  } catch { /* A form preference never supplies authority. */ }
  return { desktop: "automatic", browser: "automatic", duration: 0, profileIds: [] };
}

export function SurfaceAccess({ policy, profiles, requests, busy, act, protectedAccess }: {
  policy: SurfacePolicy; profiles: Profile[]; requests: Request[]; busy: boolean;
  act: (command: Record<string, unknown>) => Promise<unknown>;
  protectedAccess?: { supported: boolean; enabled: boolean; permissionReady: boolean; credentialSource?: string; controlSessionId: string | null; setupState: string; setupError: string | null };
}) {
  const [saved, setSaved] = useState(choices);
  const [selection, setSelection] = useState(() => policy.surfaces.browser.mode === "off" ? saved.profileIds : policy.surfaces.browser.profileIds);
  function remember(next: Choices) {
    setSaved(next);
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* Preferences are optional. */ }
  }
  function configure(surface: Surface, mode: Mode) {
    if (mode !== "off") remember({ ...saved, [surface]: mode, profileIds: [...selection] });
    return act({ method: "surface.configure", surface, mode, duration: saved.duration,
      lifetime: saved.duration === 0 ? "until_stopped" : "timed", browserProfileIds: surface === "browser" ? selection : [] });
  }
  return <>
    {policy.available === false && <p role="alert">The control engine is unavailable. Access is off. Restart Machine Control to reconnect.</p>}
    <div className="access-status">
      <div><h1>Computer access</h1><p className="grant-detail">Choose how agents may use each surface.</p></div>
      <button disabled={busy} onClick={() => void act({ method: "stop" })}>Stop all access</button>
    </div>
    {(policy.handoffCooldownRemainingSeconds ?? 0) > 0 && <p role="status" className="note">
      Disruptive work waits {Math.ceil(policy.handoffCooldownRemainingSeconds!)}s before a fresh warning. Background browser work can continue.
    </p>}
    {!!policy.deferrals?.length && <p role="status" className="note">Control handoff paused · {policy.deferrals.some(pause => pause.remainingSeconds === null) ? "until Resume" : `${Math.ceil(Math.max(...policy.deferrals.map(pause => pause.remainingSeconds ?? 0)))}s remaining`}.</p>}
    <section className="group surface-lifetime" aria-label="Access lifetime">
      <label className="setting-row"><span className="row-label">Lifetime for new access</span>
        <select aria-label="Access lifetime" value={saved.duration} disabled={busy}
          onChange={event => remember({ ...saved, duration: Number(event.target.value) })}>
          <option value={0}>Until I turn it off</option><option value={900}>15 minutes</option>
          <option value={3600}>1 hour</option><option value={28800}>8 hours</option>
        </select>
      </label>
      <p className="note">Changing this choice applies when you enable access or choose Apply. Pausing never extends access.</p>
    </section>
    {(["desktop", "browser"] as const).map(surface => {
      const state = policy.surfaces[surface], enabled = state.mode !== "off" && !state.expired;
      const label = surface === "desktop" ? "Desktop" : "Browser";
      const validProfiles = surface !== "browser" || selection.length > 0 && selection.every(id => profiles.some(profile => profile.profileId === id && profile.enabled));
      return <section className="group surface-access" aria-label={`${label} access`} key={surface}>
        <h2 className="group-title">{label}</h2>
        {surface === "desktop" && <p className="note">Includes screen capture, app control, keyboard and pointer input.</p>}
        <label className="setting-row"><span className="row-label">Access mode</span>
          <select aria-label={`${label} access mode`} value={state.mode} disabled={busy || policy.available === false}
            onChange={event => void configure(surface, event.target.value as Mode)}>
            <option value="off">Off</option><option value="ask" disabled={!validProfiles}>Ask first</option>
            <option value="automatic" disabled={!validProfiles}>Automatic</option>
          </select>
        </label>
        <p role="status" className="note">{state.expired ? "Access expired. Enable it again to allow new work." : !enabled ? "Off. Agent requests are declined quietly." :
          `${state.mode === "ask" ? "Each task needs your approval." : "Agents can start after a warning when their work affects you."} ${state.consentRemainingSeconds === null ? "Until you turn it off." : `${Math.ceil(state.consentRemainingSeconds / 60)} minutes of access remain.`}`}</p>
        {surface === "browser" && <>
          <p className="note">Includes page actions, capture, CDP and JavaScript. Choose exactly which profiles agents may use.</p>
          <p className="note">Profile edits take effect when you choose Apply. Applying changes ends current tasks on this surface.</p>
          {profiles.filter(profile => profile.enabled).map(profile => <label className="scope" key={profile.profileId}>
            <input type="checkbox" aria-label={`Allow profile ${profile.name}`} checked={selection.includes(profile.profileId)} disabled={busy}
              onChange={event => setSelection(event.target.checked ? [...selection, profile.profileId] : selection.filter(id => id !== profile.profileId))} />
            {profile.name} · {profile.connected ? "Connected" : "Disconnected"}
          </label>)}
          {!profiles.some(profile => profile.enabled) && <p className="note">Enable and name a profile in its Machine Control browser extension.</p>}
          {selection.filter(id => !profiles.some(profile => profile.profileId === id && profile.enabled)).map(id =>
            <label className="scope" key={id}><input type="checkbox" checked disabled={busy}
              onChange={() => setSelection(selection.filter(value => value !== id))} />Unavailable profile · {id.slice(-8)}</label>)}
        </>}
        {state.pauses.map(pause => <p role="status" className="note" key={pause.reason}>
          Paused: {pause.reason.replaceAll("_", " ")}{pause.remainingSeconds === null ? " · until Resume" : ` · ${Math.ceil(pause.remainingSeconds)}s remaining`}
        </p>)}
        {enabled && !state.ready && <p role="status" className="note">Waiting for the {label.toLowerCase()} provider to become available.</p>}
        <div className="request-actions">
          <button disabled={busy || policy.available === false || !validProfiles} onClick={() => void configure(surface, enabled ? state.mode : saved[surface])}>
            {enabled ? `Apply ${label.toLowerCase()} choices` : `Enable ${saved[surface] === "ask" ? "Ask first" : "Automatic"} for ${label.toLowerCase()}`}
          </button>
          {enabled && <>
            <button disabled={busy} onClick={() => void act({ method: "pause_surface", surface, duration: 30 })}>Pause {label.toLowerCase()} 30s</button>
            <button disabled={busy} onClick={() => void act({ method: "pause_surface", surface, duration: 60 })}>Pause {label.toLowerCase()} 1m</button>
            <button disabled={busy} onClick={() => void act({ method: "pause_surface", surface })}>Pause {label.toLowerCase()} until Resume</button>
          </>}
          {(state.pauses.length > 0 || (policy.handoffCooldownRemainingSeconds ?? 0) > 0 || policy.deferrals?.some(pause => pause.resource === "human-input" || pause.resource === surface || pause.resource.startsWith(`${surface}:`))) && <button disabled={busy} onClick={() => void act({ method: "resume_surface", surface })}>Resume {label.toLowerCase()}</button>}
        </div>
      </section>;
    })}
    <section className="group surface-warnings" aria-label="Control warnings">
      <label className="setting-row"><span className="row-label">Warning before disruptive work</span>
        <select aria-label="Notice countdown" value={policy.noticeSeconds} disabled={busy}
          onChange={event => void act({ method: "control_notice", noticeSeconds: Number(event.target.value) })}>
          <option value={5}>5 seconds</option><option value={10}>10 seconds</option><option value={30}>30 seconds</option><option value={60}>1 minute</option>
        </select>
      </label>
      <p className="note">Keep working during the warning. Mouse movement does not interrupt an agent. A click, key or scroll takes control back; the agent can announce again after one minute.</p>
      <p className="note">Access applies to apps running as your user. A task label does not verify who operates that app.</p>
    </section>
    {protectedAccess && <section className="group surface-access" aria-label="Covered desktop access">
      <h2 className="group-title">Covered desktop while locked</h2>
      <label className="scope"><input type="checkbox" checked={protectedAccess.enabled}
        disabled={busy || !protectedAccess.supported || !protectedAccess.permissionReady || !!protectedAccess.controlSessionId}
        onChange={event => void act({ method: "locked_use", enabled: event.target.checked })} />Allow prepared tasks behind an opaque cover</label>
      <p className="note">Windows relocks when the task ends. Changing this setting turns access off. Browser-only work can stay locked using its separate setting.</p>
      {(!protectedAccess.permissionReady || protectedAccess.credentialSource !== "service_enrolled_password") &&
        <button disabled={busy || !!protectedAccess.controlSessionId || !["idle", "approval"].includes(protectedAccess.setupState)}
          onClick={() => void act({ method: "permission", permission: "lockedUse" })}>Set up covered desktop access</button>}
      {protectedAccess.setupError && <p role="alert" className="note">{protectedAccess.setupError}</p>}
    </section>}
    {requests.length > 0 && <section className="group requests" aria-label="Agent requests">
      {requests.slice(0, 8).map(request => <div className="control-request" key={request.intentId}>
        <p>{request.reason}</p><p className="note">{request.surfaces?.join(" + ")} · {request.state.replaceAll("_", " ")}
          {request.state === "announcing" ? ` · starts in ${Math.ceil(request.noticeRemainingSeconds ?? 0)}s` : ""}</p>
        <div className="request-actions">
          {request.state === "waiting_for_approval" && <button disabled={busy} onClick={() => void act({ method: "approve_control", intentId: request.intentId })}>Allow this task</button>}
          {request.state === "announcing" && <button disabled={busy} onClick={() => void act({ method: "start_control", intentId: request.intentId })}>Start now</button>}
          <button disabled={busy} onClick={() => void act({ method: "pause_request", intentId: request.intentId, duration: 30 })}>Pause 30 seconds</button>
          <button disabled={busy} onClick={() => void act({ method: "pause_request", intentId: request.intentId, duration: 60 })}>Pause 1 minute</button>
          <button disabled={busy} onClick={() => void act({ method: "pause_request", intentId: request.intentId })}>Pause until Resume</button>
          <button disabled={busy} onClick={() => void act({ method: "cancel_control", intentId: request.intentId })}>Deny task</button>
        </div>
      </div>)}
    </section>}
  </>;
}
