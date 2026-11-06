//! Resident recovery: when the native resident is lost, restart it and turn
//! the same Desktop and Browser access back on.
//!
//! The supervisor remembers the last status poll that no person's action
//! could have overtaken. After a restart it replays those surface choices
//! with ordinary `surface.configure` commands, exactly like an update, unless
//! a person acted after that observation. Standing policy is not operator
//! consent and is never captured.
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Mutex, OnceLock,
};
use std::time::{Duration, Instant};

static SEQUENCE: AtomicU64 = AtomicU64::new(0);
static LAST: Mutex<Option<Observed>> = Mutex::new(None);
#[cfg_attr(target_os = "macos", allow(dead_code))]
static BACKOFF: Mutex<Option<(Instant, usize)>> = Mutex::new(None);
static STARTED: OnceLock<Instant> = OnceLock::new();
/// A resident always starts with no stops counted.
static STOPS: Mutex<Option<u64>> = Mutex::new(Some(0));
/// A status snapshot older than this is not a live observation.
const OBSERVATION_AGE_MS: u64 = 3_000;

struct Observed {
    state: Value,
    at: u64,
    sequence: u64,
}

#[cfg_attr(target_os = "macos", allow(dead_code))]
/// Restart delays. A resident lost again soon after a restart waits longer.
const DELAYS: [u64; 5] = [1, 2, 5, 15, 60];
#[cfg_attr(target_os = "macos", allow(dead_code))]
const BACKOFF_RESET: Duration = Duration::from_secs(5 * 60);

/// A person acted: an operator command other than a read, or Stop. A
/// restart never restores access observed before this.
pub fn person_acted() {
    SEQUENCE.fetch_add(1, Ordering::AcqRel);
}

/// Taken before dispatching a status poll; see `observe`.
pub fn ticket() -> u64 {
    SEQUENCE.load(Ordering::Acquire)
}

/// A supervised restart produced a fresh resident, whose count starts at 0.
#[cfg_attr(target_os = "macos", allow(dead_code))]
pub fn resident_started() {
    if let Ok(mut stops) = STOPS.lock() {
        *stops = Some(0);
    }
}

/// Called once at startup.
pub fn started() {
    let _ = STARTED.set(Instant::now());
}

/// Remember a status poll unless a person acted while it was in flight. A
/// resident without its policy process shows access off but decides nothing.
///
/// Residents also report a live count of stops, including those a person
/// made inside the resident (hotkey, native notice) and safety revocations.
/// One newer than the last poll counts as a person's action even when the
/// rest of the snapshot is stale. A lower count can only be a new resident
/// observed before `resident_started` reset the baseline.
pub fn observe(state: &Value, ticket: u64) {
    if !state.is_object() {
        return;
    }
    if let Some(stops) = state["stops"].as_u64() {
        let Ok(mut last) = STOPS.lock() else {
            return;
        };
        if last.replace(stops).is_some_and(|previous| stops > previous) {
            person_acted();
            return;
        }
    }
    if state["accessPolicy"]["available"] == false
        || state["stateAgeMs"]
            .as_u64()
            .is_some_and(|age| age > OBSERVATION_AGE_MS)
    {
        return;
    }
    if let Ok(mut last) = LAST.lock() {
        if SEQUENCE.load(Ordering::Acquire) == ticket {
            *last = Some(Observed {
                state: state.clone(),
                at: crate::update_resume::now(),
                sequence: ticket,
            });
        }
    }
}

/// The access to restore after losing the resident now, if any.
pub fn plan(version: &str) -> Option<Value> {
    let observed = LAST.lock().ok()?.take()?;
    if observed.sequence != SEQUENCE.load(Ordering::Acquire)
        || crate::update_resume::standing(&observed.state)
    {
        return None;
    }
    let mut plan = crate::update_resume::capture(&observed.state, version, observed.at)?;
    plan["sequence"] = json!(observed.sequence);
    plan["reason"] = json!(crate::update_resume::RESIDENT_RESTART);
    Some(plan)
}

#[cfg_attr(target_os = "macos", allow(dead_code))]
/// Whether no person acted since the plan's observation.
pub fn current(plan: &Value) -> bool {
    plan["sequence"].as_u64() == Some(SEQUENCE.load(Ordering::Acquire))
}

#[cfg_attr(target_os = "macos", allow(dead_code))]
/// The next restart delay. Escalates while losses recur within five minutes.
pub fn backoff() -> Duration {
    let now = Instant::now();
    let Ok(mut state) = BACKOFF.lock() else {
        return Duration::from_secs(DELAYS[DELAYS.len() - 1]);
    };
    let index = match *state {
        Some((last, index)) if now.duration_since(last) < BACKOFF_RESET => {
            (index + 1).min(DELAYS.len() - 1)
        }
        _ => 0,
    };
    *state = Some((now, index));
    Duration::from_secs(DELAYS[index])
}

#[cfg_attr(target_os = "macos", allow(dead_code))]
/// Restore a plan after the resident restarted in this process.
pub fn restore(app: tauri::AppHandle, plan: Value) {
    let version = app.package_info().version.to_string();
    let Some(entries) =
        crate::update_resume::validate(&plan, &version, crate::update_resume::now())
    else {
        crate::diagnostics::record("resident.access.restore_skipped");
        return;
    };
    crate::update_resume::restore(app, entries, true, move || current(&plan));
}

#[cfg(target_os = "macos")]
const RESTART_COOLDOWN_SECONDS: u64 = 10 * 60;

/// macOS hosts the resident in this process. Its policy process cannot be
/// rebound in place, so restart the app with the access to restore recorded
/// like an update's. Never within a minute of starting or ten minutes of the
/// previous such restart, so a failing policy never restarts the app in a loop.
#[cfg(target_os = "macos")]
pub fn restart_after_policy_loss(app: &tauri::AppHandle) {
    use std::sync::atomic::AtomicBool;
    use tauri::Manager;
    static RESTARTING: AtomicBool = AtomicBool::new(false);
    // An update owns the restart and its plan file.
    if crate::updates::is_installing()
        || STARTED
            .get()
            .is_none_or(|started| started.elapsed() < Duration::from_secs(60))
        || RESTARTING.swap(true, Ordering::AcqRel)
    {
        return;
    }
    crate::diagnostics::record("resident.policy_lost");
    // At most one restart per ten minutes across launches; a policy that
    // keeps failing leaves Machine Control running with access off.
    let marker = app
        .path()
        .app_local_data_dir()
        .map(|directory| directory.join("resident-restart.json"));
    let now = crate::update_resume::now();
    if let Ok(marker) = &marker {
        let recent = std::fs::read_to_string(marker)
            .ok()
            .and_then(|text| serde_json::from_str::<Value>(&text).ok())
            .and_then(|value| value["at"].as_u64())
            .is_some_and(|at| at <= now && now - at < RESTART_COOLDOWN_SECONDS);
        if recent {
            crate::diagnostics::record("resident.restart_failed");
            return;
        }
        let _ = std::fs::create_dir_all(marker.parent().unwrap_or(marker));
        if std::fs::write(marker, json!({"at":now}).to_string()).is_err() {
            return;
        }
    } else {
        return;
    }
    if let Some(plan) = plan(&app.package_info().version.to_string()) {
        if crate::update_resume::save(app, &plan).is_err() {
            crate::diagnostics::record("resident.access.restore_failed");
        }
    }
    let handle = app.clone();
    let scheduled = crate::schedule_native(app, move || {
        let _ = crate::native_command(json!({"method":"prepare_exit"}));
        if crate::restart::request(&handle).is_err() {
            crate::diagnostics::record("resident.restart_failed");
        }
    });
    if scheduled.is_err() {
        crate::diagnostics::record("resident.restart_failed");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(mode: &str) -> Value {
        json!({"deployment":{"grant":null, "policy":{"grantMode":"approval"}},
            "accessPolicy":{"schema":"machine-control-admission/v2",
                "surfaces":{"desktop":{"mode":mode, "expired":false,
                    "consentRemainingSeconds":null, "profileIds":[]},
                "browser":{"mode":"off", "expired":false,
                    "consentRemainingSeconds":0, "profileIds":[]}}}})
    }

    // One test owns the process-wide sequence to avoid parallel interference.
    #[test]
    fn restores_only_access_no_person_overtook() {
        observe(&state("automatic"), ticket());
        let captured = plan("1.0.0").expect("live access is captured");
        assert_eq!(captured["surfaces"][0]["surface"], "desktop");
        assert_eq!(captured["reason"], "resident_restart");
        assert!(current(&captured));
        person_acted();
        assert!(!current(&captured), "a later action cancels the restore");

        // A poll in flight while a person acted is not remembered.
        let issued = ticket();
        person_acted();
        observe(&state("automatic"), issued);
        assert!(plan("1.0.0").is_none());

        // Access that was off restores nothing.
        observe(&state("off"), ticket());
        assert!(plan("1.0.0").is_none());

        // A resident without its policy process does not replace the last
        // observation.
        observe(&state("automatic"), ticket());
        let mut lost = state("off");
        lost["accessPolicy"]["available"] = json!(false);
        observe(&lost, ticket());
        assert!(plan("1.0.0").is_some());

        // A stop counted inside the resident cancels a pending restore even
        // when the snapshot is stale; a lower count is a new resident.
        resident_started();
        let mut counted = state("automatic");
        counted["stops"] = json!(1);
        observe(&counted, ticket());
        assert!(
            plan("1.0.0").is_none(),
            "a fresh resident's first stop counts"
        );
        counted["stops"] = json!(4);
        observe(&counted, ticket());
        observe(&counted, ticket());
        let captured = plan("1.0.0").expect("an unchanged count is observed");
        observe(&counted, ticket());
        counted["stops"] = json!(5);
        counted["stateAgeMs"] = json!(60_000);
        observe(&counted, ticket());
        assert!(!current(&captured));
        counted["stops"] = json!(0);
        counted["stateAgeMs"] = json!(0);
        observe(&counted, ticket());
        assert!(
            plan("1.0.0").is_some(),
            "a new resident's lower count is a baseline"
        );

        // A stale snapshot is not a live observation.
        let mut stale = state("automatic");
        stale["stateAgeMs"] = json!(10_000);
        observe(&stale, ticket());
        assert!(plan("1.0.0").is_none());

        // Standing policy is not operator consent.
        let mut standing = state("automatic");
        standing["deployment"]["policy"]["grantMode"] = json!("standing");
        observe(&standing, ticket());
        assert!(plan("1.0.0").is_none());
    }
}
