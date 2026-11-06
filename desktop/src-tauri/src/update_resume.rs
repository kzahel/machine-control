//! Operator-initiated update continuity: stop live access before bundle
//! replacement, then restore the same surface choices in the updated client.
//!
//! The plan is a one-shot local record, bound to the installed version and a
//! short expiry. Restoration replays ordinary `surface.configure` operator
//! commands, so every native readiness gate (unlocked console, audit storage,
//! approval presentation) still applies. It never restores a pending approval
//! or an agent task; those end when access stops.
use serde_json::{json, Value};
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::Manager;

const SCHEMA: &str = "machine-control-update-resume/v0";
const FILE: &str = "update-access-resume.json";
/// Longest gap between stopping access and the updated client restoring it.
const MAX_AGE_SECONDS: u64 = 10 * 60;
/// Native surface durations are bounded to 60..=28800 seconds.
const MIN_SECONDS: u64 = 60;
const MAX_SECONDS: u64 = 28_800;
const RESTORE_WINDOW: Duration = Duration::from_secs(120);

pub(crate) fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Whether any operator consent is live and must stop before replacement.
pub fn access_on(state: &Value) -> bool {
    !state["deployment"]["grant"].is_null()
        || state["accessPolicy"]["surfaces"]
            .as_object()
            .is_some_and(|surfaces| surfaces.values().any(live))
}

fn live(surface: &Value) -> bool {
    matches!(surface["mode"].as_str(), Some("ask" | "automatic")) && surface["expired"] != true
}

pub fn standing(state: &Value) -> bool {
    state["deployment"]["policy"]["grantMode"] == "standing"
        || state["deployment"]["policy"]["protectedAdministration"] == true
}

/// Record the live surface choices; timed consent keeps its wall-clock end.
pub fn capture(state: &Value, target_version: &str, at: u64) -> Option<Value> {
    if state["accessPolicy"]["schema"] != "machine-control-admission/v2" {
        return None;
    }
    let surfaces: Vec<Value> = ["desktop", "browser"]
        .iter()
        .filter_map(|name| {
            let surface = &state["accessPolicy"]["surfaces"][*name];
            if !live(surface) {
                return None;
            }
            let expires_at = match surface["consentRemainingSeconds"].as_f64() {
                None => Value::Null,
                Some(remaining) => json!(at + remaining.max(0.0).floor() as u64),
            };
            Some(json!({"surface":name, "mode":surface["mode"],
                "expiresAt":expires_at, "profileIds":surface["profileIds"]}))
        })
        .collect();
    (!surfaces.is_empty()).then(|| {
        json!({"schema":SCHEMA, "createdAt":at, "targetVersion":target_version,
            "surfaces":surfaces})
    })
}

/// Accept only a fresh plan written for exactly this installed version.
pub fn validate(plan: &Value, version: &str, at: u64) -> Option<Vec<Value>> {
    let created = plan["createdAt"].as_u64()?;
    if plan["schema"] != SCHEMA
        || plan["targetVersion"] != version
        || created > at
        || at - created > MAX_AGE_SECONDS
    {
        return None;
    }
    let surfaces = plan["surfaces"].as_array()?;
    let valid = surfaces.len() <= 2
        && surfaces.iter().all(|entry| {
            matches!(entry["surface"].as_str(), Some("desktop" | "browser"))
                && matches!(entry["mode"].as_str(), Some("ask" | "automatic"))
                && (entry["expiresAt"].is_null() || entry["expiresAt"].as_u64().is_some())
                && entry["profileIds"]
                    .as_array()
                    .is_some_and(|ids| ids.iter().all(Value::is_string))
        });
    valid.then(|| surfaces.clone())
}

/// The operator command that recreates one surface, if consent remains.
pub fn configure_command(entry: &Value, at: u64) -> Option<Value> {
    let browser = entry["surface"] == "browser";
    let profiles = if browser {
        entry["profileIds"].clone()
    } else {
        json!([])
    };
    let (lifetime, duration) = match entry["expiresAt"].as_u64() {
        None => ("until_stopped", 0),
        Some(end) => {
            let remaining = end.checked_sub(at)?;
            if remaining < MIN_SECONDS {
                return None;
            }
            ("timed", remaining.min(MAX_SECONDS))
        }
    };
    Some(
        json!({"method":"surface.configure", "surface":entry["surface"],
        "mode":entry["mode"], "lifetime":lifetime, "duration":duration,
        "browserProfileIds":profiles}),
    )
}

fn path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join(FILE))
}

pub fn save(app: &tauri::AppHandle, plan: &Value) -> Result<(), String> {
    let path = path(app)?;
    let directory = path.parent().ok_or("Update state folder unavailable")?;
    std::fs::create_dir_all(directory).map_err(|e| e.to_string())?;
    let staging = path.with_extension("tmp");
    let _ = std::fs::remove_file(&staging);
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let write = || -> std::io::Result<()> {
        use std::io::Write;
        let mut file = options.open(&staging)?;
        file.write_all(plan.to_string().as_bytes())?;
        file.sync_all()?;
        std::fs::rename(&staging, &path)
    };
    write().map_err(|e| {
        let _ = std::fs::remove_file(&staging);
        format!("Could not record access to restore after updating: {e}")
    })
}

pub fn discard(app: &tauri::AppHandle) {
    if let Ok(path) = path(app) {
        let _ = std::fs::remove_file(path);
    }
}

/// Consume the plan exactly once, whether or not it is still valid.
fn take(app: &tauri::AppHandle) -> Option<Value> {
    let path = path(app).ok()?;
    let text = std::fs::read_to_string(&path).ok();
    let _ = std::fs::remove_file(&path);
    serde_json::from_str(&text?).ok()
}

/// Apply each still-off surface once; a person's newer choice wins.
pub fn apply(
    entries: &mut Vec<Value>,
    state: &Value,
    at: u64,
    mut send: impl FnMut(Value) -> Result<Value, String>,
) -> Result<(), String> {
    let mut last = Ok(());
    entries.retain(|entry| {
        let name = entry["surface"].as_str().unwrap_or("");
        let current = &state["accessPolicy"]["surfaces"][name];
        if current["mode"].as_str().is_some_and(|mode| mode != "off") {
            return false;
        }
        let Some(command) = configure_command(entry, at) else {
            return false;
        };
        match send(command) {
            Ok(_) => false,
            Err(error) => {
                last = Err(error);
                true
            }
        }
    });
    last
}

fn surfaces_label(entries: &[Value]) -> Vec<Value> {
    entries.iter().map(|e| e["surface"].clone()).collect()
}

/// The update did not replace this client: restore its access immediately.
pub fn restore_after_failure(
    app: &tauri::AppHandle,
    plan: &Value,
    mut send: impl FnMut(Value) -> Result<Value, String>,
) {
    discard(app);
    let Some(mut entries) = plan["surfaces"].as_array().cloned() else {
        return;
    };
    let restoring = surfaces_label(&entries);
    let state = send(json!({"method":"state", "fresh":true}))
        .map(|reply| reply["state"].clone())
        .unwrap_or(Value::Null);
    match apply(&mut entries, &state, now(), send) {
        Ok(()) => {
            crate::diagnostics::record("update.access.restored");
            crate::updates::set_access_resume(json!({"phase":"restored", "surfaces":restoring}));
        }
        Err(error) => {
            crate::diagnostics::record("update.access.restore_failed");
            crate::updates::set_access_resume(json!({"phase":"failed",
                "surfaces":surfaces_label(&entries), "error":error}));
        }
    }
}

/// Called once at startup. Waits for the resident to become ready.
pub fn resume(app: tauri::AppHandle) {
    let Some(plan) = take(&app) else {
        return;
    };
    let version = app.package_info().version.to_string();
    let Some(mut entries) = validate(&plan, &version, now()) else {
        crate::diagnostics::record("update.access.restore_skipped");
        return;
    };
    let restoring = surfaces_label(&entries);
    crate::updates::set_access_resume(json!({"phase":"restoring", "surfaces":restoring}));
    std::thread::spawn(move || {
        let deadline = Instant::now() + RESTORE_WINDOW;
        let mut error = String::from("Machine Control was not ready");
        loop {
            match crate::native_blocking(&app, json!({"method":"state", "fresh":true})) {
                Ok(reply) => {
                    let state = &reply["state"];
                    let result = apply(&mut entries, state, now(), |command| {
                        crate::native_blocking(&app, command)
                    });
                    if entries.is_empty() {
                        crate::diagnostics::record("update.access.restored");
                        crate::updates::set_access_resume(
                            json!({"phase":"restored", "surfaces":restoring}),
                        );
                        return;
                    }
                    if let Err(e) = result {
                        error = e;
                    }
                }
                Err(e) => error = e,
            }
            if Instant::now() >= deadline {
                crate::diagnostics::record("update.access.restore_failed");
                crate::updates::set_access_resume(json!({"phase":"failed",
                    "surfaces":surfaces_label(&entries), "error":error}));
                return;
            }
            std::thread::sleep(Duration::from_secs(2));
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(desktop: Value, browser: Value) -> Value {
        json!({"deployment":{"grant":null, "policy":{"grantMode":"approval"}},
            "accessPolicy":{"schema":"machine-control-admission/v2",
                "surfaces":{"desktop":desktop, "browser":browser}}})
    }
    fn off() -> Value {
        json!({"mode":"off", "expired":false, "consentRemainingSeconds":0, "profileIds":[]})
    }

    #[test]
    fn captures_live_surfaces_with_wall_clock_end() {
        let s = state(
            json!({"mode":"automatic", "expired":false, "consentRemainingSeconds":null, "profileIds":[]}),
            json!({"mode":"ask", "expired":false, "consentRemainingSeconds":899.6, "profileIds":["p1"]}),
        );
        assert!(access_on(&s));
        let plan = capture(&s, "0.7.2", 1000).unwrap();
        assert_eq!(plan["surfaces"][0]["surface"], "desktop");
        assert!(plan["surfaces"][0]["expiresAt"].is_null());
        assert_eq!(plan["surfaces"][1]["expiresAt"], 1899);
        assert_eq!(plan["surfaces"][1]["profileIds"], json!(["p1"]));
    }

    #[test]
    fn off_or_expired_access_records_nothing() {
        let expired =
            json!({"mode":"ask", "expired":true, "consentRemainingSeconds":0, "profileIds":[]});
        let s = state(off(), expired);
        assert!(!access_on(&s));
        assert!(capture(&s, "0.7.2", 1000).is_none());
    }

    #[test]
    fn plan_binds_version_age_and_shape() {
        let s = state(
            json!({"mode":"ask", "expired":false, "consentRemainingSeconds":null, "profileIds":[]}),
            off(),
        );
        let plan = capture(&s, "0.7.2", 1000).unwrap();
        assert!(validate(&plan, "0.7.2", 1000 + MAX_AGE_SECONDS).is_some());
        assert!(validate(&plan, "0.7.1", 1001).is_none());
        assert!(validate(&plan, "0.7.2", 1001 + MAX_AGE_SECONDS).is_none());
        assert!(validate(&plan, "0.7.2", 999).is_none());
        let mut forged = plan.clone();
        forged["surfaces"][0]["surface"] = json!("shell");
        assert!(validate(&forged, "0.7.2", 1001).is_none());
    }

    #[test]
    fn restore_uses_remaining_bounded_duration() {
        let manual =
            json!({"surface":"desktop", "mode":"automatic", "expiresAt":null, "profileIds":["x"]});
        let command = configure_command(&manual, 50).unwrap();
        assert_eq!(command["lifetime"], "until_stopped");
        assert_eq!(command["browserProfileIds"], json!([]));
        let timed =
            json!({"surface":"browser", "mode":"ask", "expiresAt":1000, "profileIds":["p"]});
        let command = configure_command(&timed, 400).unwrap();
        assert_eq!(command["lifetime"], "timed");
        assert_eq!(command["duration"], 600);
        assert_eq!(command["browserProfileIds"], json!(["p"]));
        assert!(configure_command(&timed, 941).is_none());
        let long = json!({"surface":"desktop", "mode":"ask", "expiresAt":100_000, "profileIds":[]});
        assert_eq!(
            configure_command(&long, 0).unwrap()["duration"],
            MAX_SECONDS
        );
    }

    #[test]
    fn apply_retries_failures_and_respects_newer_choice() {
        let mut entries = vec![
            json!({"surface":"desktop", "mode":"automatic", "expiresAt":null, "profileIds":[]}),
            json!({"surface":"browser", "mode":"ask", "expiresAt":null, "profileIds":["p"]}),
        ];
        let person_chose_browser = state(
            off(),
            json!({"mode":"automatic", "expired":false, "consentRemainingSeconds":null, "profileIds":["q"]}),
        );
        let mut sent = Vec::new();
        let result = apply(&mut entries, &person_chose_browser, 0, |command| {
            sent.push(command);
            Err("unlocked_operator_required".into())
        });
        assert_eq!(result.unwrap_err(), "unlocked_operator_required");
        assert_eq!(sent.len(), 1);
        assert_eq!(entries.len(), 1);
        assert!(apply(&mut entries, &state(off(), off()), 0, |_| Ok(
            json!({"ok":true})
        ))
        .is_ok());
        assert!(entries.is_empty());
    }
}
