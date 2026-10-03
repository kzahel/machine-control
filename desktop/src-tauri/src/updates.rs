//! Native-owned discovery. Timers and CLI requests never focus, download or install.
use serde_json::{json, Value};
use std::sync::{Mutex, MutexGuard, OnceLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{menu::MenuItem, Emitter};
use tauri_plugin_updater::UpdaterExt;

pub const STARTUP_SECONDS: u64 = 5;
pub const PERIODIC_SECONDS: u64 = 24 * 60 * 60;
static STATE: OnceLock<Mutex<Core>> = OnceLock::new();

#[derive(Default)]
struct Core {
    current_version: String,
    checking: bool,
    installing: bool,
    phase: &'static str,
    reason: Option<String>,
    candidate: Option<(String, Option<String>)>,
    last_checked: Option<u64>,
    error: Option<String>,
}

impl Core {
    fn begin_check(&mut self, reason: &str) -> bool {
        if self.checking {
            // A manual caller joining a silent check still gets visible feedback.
            if reason == "manual" {
                self.reason = Some(reason.into());
            }
            return false;
        }
        if self.installing || (reason != "manual" && self.candidate.is_some()) {
            return false;
        }
        self.checking = true;
        self.phase = "checking";
        self.reason = Some(reason.into());
        self.error = None;
        true
    }

    fn finish_check(&mut self, result: Result<Option<(String, Option<String>)>, String>, now: u64) {
        self.checking = false;
        self.last_checked = Some(now);
        match result {
            Ok(candidate) => {
                // A later empty response must not erase an already discovered update.
                if candidate.is_some() {
                    self.candidate = candidate;
                }
                self.phase = if self.candidate.is_some() {
                    "available"
                } else {
                    "up_to_date"
                };
            }
            Err(error) => {
                self.error = Some(error);
                self.phase = if self.reason.as_deref() == Some("manual") {
                    "error"
                } else if self.candidate.is_some() {
                    "available"
                } else {
                    "idle"
                };
            }
        }
    }

    fn begin_install(&mut self, version: &str) -> Result<(), String> {
        if self.checking || self.installing {
            return Err("An update operation is already running".into());
        }
        if self.candidate.as_ref().map(|v| v.0.as_str()) != Some(version) {
            return Err("Update changed; check again before installing".into());
        }
        self.installing = true;
        self.phase = "downloading";
        self.error = None;
        Ok(())
    }

    fn snapshot(&self) -> Value {
        json!({"schema":"machine-control-update-status/v0", "currentVersion":self.current_version,
            "phase":if self.phase.is_empty() { "idle" } else { self.phase },
            "checking":self.checking, "installing":self.installing, "reason":self.reason,
            "availableVersion":self.candidate.as_ref().map(|v| &v.0),
            "notes":self.candidate.as_ref().and_then(|v| v.1.as_ref()),
            "lastCheckedAt":self.last_checked, "error":self.error,
            "startupDelaySeconds":STARTUP_SECONDS, "periodicIntervalSeconds":PERIODIC_SECONDS})
    }
}

fn state() -> MutexGuard<'static, Core> {
    STATE
        .get_or_init(|| Mutex::new(Core::default()))
        .lock()
        .expect("Update state poisoned")
}
pub fn status() -> Value {
    state().snapshot()
}
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

pub fn check(app: &tauri::AppHandle, reason: &str) -> Result<Value, String> {
    if !matches!(reason, "startup" | "periodic" | "manual") {
        return Err("Invalid check reason".into());
    }
    if state().begin_check(reason) {
        let app = app.clone();
        let reason = reason.to_owned();
        tauri::async_runtime::spawn(async move {
            let result = async {
                let candidate = app
                    .updater_builder()
                    .header("X-Check-Reason", &reason)
                    .map_err(|e| e.to_string())?
                    .timeout(Duration::from_secs(20))
                    .build()
                    .map_err(|e| e.to_string())?
                    .check()
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(candidate.map(|v| (v.version, v.body)))
            }
            .await;
            if reason != "manual" {
                if let Err(error) = &result {
                    eprintln!("Automatic {reason} update check failed: {error}");
                }
            }
            state().finish_check(result, now());
            let _ = app.emit("update-state", status());
        });
    }
    Ok(status())
}

pub fn begin_install(version: &str) -> Result<(), String> {
    state().begin_install(version)
}
pub fn installing() {
    state().phase = "installing";
}
pub fn finish_install(result: &Result<(), String>) {
    let mut core = state();
    core.installing = false;
    core.phase = if result.is_ok() { "installed" } else { "error" };
    core.error = result.as_ref().err().cloned();
}

struct Schedule {
    started: u64,
    periodic: u64,
    startup_pending: bool,
}
impl Schedule {
    fn new(now: u64) -> Self {
        Self {
            started: now,
            periodic: now,
            startup_pending: true,
        }
    }
    fn due(&mut self, now: u64) -> Option<&'static str> {
        if self.startup_pending && now.saturating_sub(self.started) >= STARTUP_SECONDS {
            self.startup_pending = false;
            self.periodic = now; // A wake before startup must not schedule two checks.
            return Some("startup");
        }
        if now.saturating_sub(self.periodic) >= PERIODIC_SECONDS {
            self.periodic = now; // One overdue check on wake, never a catch-up burst.
            return Some("periodic");
        }
        None
    }
}

pub fn start(app: &tauri::AppHandle, menu: MenuItem<tauri::Wry>) {
    state().current_version = app.package_info().version.to_string();
    let app = app.clone();
    std::thread::spawn(move || {
        let mut schedule = Schedule::new(now());
        let mut previous = Value::Null;
        loop {
            let snapshot = status();
            let (send, receive) = std::sync::mpsc::channel();
            if crate::schedule_native(&app, move || {
                let _ = send.send(crate::native_command(
                    json!({"method":"update_sync", "state":snapshot}),
                ));
            })
            .is_err()
            {
                break;
            }
            if let Ok(Ok(reply)) = receive.recv_timeout(Duration::from_secs(3)) {
                if reply["checkRequested"] == true {
                    let _ = check(&app, "manual");
                }
            }
            if let Some(reason) = schedule.due(now()) {
                let _ = check(&app, reason);
            }
            let snapshot = status();
            if snapshot != previous {
                let title = snapshot["availableVersion"]
                    .as_str()
                    .map(|v| format!("Update available ({v})…"))
                    .unwrap_or_else(|| "Check for Updates…".into());
                let _ = menu.set_text(title);
                let _ = app.emit("update-state", &snapshot);
                previous = snapshot;
            }
            std::thread::sleep(Duration::from_secs(1));
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn schedule_startup_daily_wake_and_clock_rollback() {
        let mut s = Schedule::new(100);
        assert_eq!(s.due(104), None);
        assert_eq!(s.due(105), Some("startup"));
        assert_eq!(s.due(106), None);
        assert_eq!(s.due(105 + PERIODIC_SECONDS), Some("periodic"));
        assert_eq!(s.due(100 + 4 * PERIODIC_SECONDS), Some("periodic"));
        assert_eq!(s.due(100 + 4 * PERIODIC_SECONDS), None);
        assert_eq!(s.due(0), None);
        let mut late_startup = Schedule::new(100);
        assert_eq!(
            late_startup.due(100 + 4 * PERIODIC_SECONDS),
            Some("startup")
        );
        assert_eq!(late_startup.due(100 + 4 * PERIODIC_SECONDS), None);
    }
    #[test]
    fn checks_coalesce_and_available_update_survives() {
        let mut c = Core::default();
        assert!(c.begin_check("startup"));
        assert!(!c.begin_check("manual"));
        c.finish_check(Ok(Some(("1.2.3".into(), Some("notes".into())))), 10);
        assert!(!c.begin_check("periodic"));
        assert!(c.begin_check("manual"));
        c.finish_check(Err("offline".into()), 11);
        assert_eq!(c.snapshot()["availableVersion"], "1.2.3");
        assert_eq!(c.phase, "error");
        assert!(c.begin_check("manual"));
        c.finish_check(Ok(None), 12);
        assert_eq!(c.phase, "available");
    }
    #[test]
    fn automatic_errors_are_quiet_and_install_excludes_checks() {
        let mut c = Core::default();
        assert!(c.begin_check("startup"));
        assert!(c.begin_install("1.2.3").is_err());
        c.finish_check(Err("offline".into()), 10);
        assert_eq!(c.phase, "idle");
        c.begin_check("manual");
        c.finish_check(Ok(Some(("1.2.3".into(), None))), 11);
        assert!(c.begin_install("other").is_err());
        c.begin_install("1.2.3").unwrap();
        assert!(!c.begin_check("manual"));
        assert!(c.begin_install("1.2.3").is_err());
    }
    #[test]
    fn manual_check_joining_startup_gets_visible_failure_without_second_request() {
        let mut c = Core::default();
        assert!(c.begin_check("startup"));
        assert!(!c.begin_check("manual"));
        c.finish_check(Err("offline".into()), 10);
        assert_eq!(c.phase, "error");
        assert_eq!(c.snapshot()["reason"], "manual");
    }
}
