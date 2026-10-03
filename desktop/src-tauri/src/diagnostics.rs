//! Supervisor diagnostics contain closed event codes, never raw stderr/errors.
use serde_json::json;
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::PathBuf,
    sync::{Mutex, OnceLock},
    time::{SystemTime, UNIX_EPOCH},
};
static ROOT: OnceLock<PathBuf> = OnceLock::new();
static WRITER: Mutex<Option<PathBuf>> = Mutex::new(None);
fn micros() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_micros()
}
fn private_dir(path: &std::path::Path) -> std::io::Result<()> {
    if fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink()) {
        return Err(std::io::Error::other("Unsafe log directory"));
    }
    fs::create_dir_all(path)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    }
    Ok(())
}
pub fn start() {
    #[cfg(target_os = "macos")]
    let root = std::env::var_os("HOME")
        .map(PathBuf::from)
        .map(|p| p.join("Library/Logs/MachineControl"));
    #[cfg(target_os = "windows")]
    let root = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|p| p.join("MachineControl/logs"));
    #[cfg(target_os = "linux")]
    let root = std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|p| p.join(".local/state"))
        })
        .map(|p| p.join("machine-control/logs"));
    if let Some(root) = root {
        let _ = ROOT.set(root);
    }
    record("supervisor.start");
}
pub fn record(code: &str) {
    if !matches!(
        code,
        "supervisor.start"
            | "supervisor.stop"
            | "companion.stderr"
            | "companion.exited"
            | "companion.protocol_error"
            | "companion.timeout"
            | "resident.unavailable"
            | "update.check.ok"
            | "update.check.failed"
            | "update.install.ok"
            | "update.install.failed"
    ) {
        return;
    }
    let Some(root) = ROOT.get() else {
        return;
    };
    let Ok(mut writer) = WRITER.lock() else {
        return;
    };
    let result = (|| -> std::io::Result<()> {
        private_dir(root)?;
        let dir = root.join("diagnostics");
        private_dir(&dir)?;
        // Native readers enforce the same segment bound; share the total cap.
        let mut files: Vec<_> = fs::read_dir(&dir)?
            .filter_map(Result::ok)
            .filter(|f| f.path().extension().is_some_and(|e| e == "jsonl"))
            .collect();
        files.sort_by_key(|f| f.file_name());
        let mut total: u64 = files
            .iter()
            .filter_map(|f| f.metadata().ok())
            .map(|m| m.len())
            .sum();
        for f in files {
            let m = f.metadata()?;
            let expired = m.modified()?.elapsed().unwrap_or_default().as_secs() > 7 * 86400;
            if !expired && total <= 52_428_800 - 4096 {
                break;
            }
            total = total.saturating_sub(m.len());
            fs::remove_file(f.path())?;
        }
        if writer
            .as_ref()
            .is_none_or(|p| fs::metadata(p).map_or(true, |m| m.len() >= 1_048_576))
        {
            *writer = Some(dir.join(format!(
                "{:020}-supervisor-{}.jsonl",
                micros(),
                std::process::id()
            )));
        }
        let path = writer.as_ref().unwrap();
        if fs::symlink_metadata(path).is_ok_and(|m| m.file_type().is_symlink()) {
            return Err(std::io::Error::other("Unsafe log file"));
        }
        let mut options = OpenOptions::new();
        options.create(true).append(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options
                .mode(0o600)
                .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC);
        }
        let mut file = options.open(path)?;
        let at = micros();
        let value = json!({"schema":"machine-control-desktop-event/v0", "stream":"diagnostics", "component":"desktop.supervisor", "version":env!("CARGO_PKG_VERSION"), "atUnixMs":at / 1000, "at":iso_time(at / 1_000_000), "eventId":format!("{}-{at}", std::process::id()), "phase":"event", "operation":code, "errorCode":if code.ends_with("failed") || code.starts_with("companion.") || code == "resident.unavailable" { Some(code) } else { None }});
        writeln!(file, "{value}")?;
        file.sync_data()
    })();
    if result.is_err() { /* Diagnostics must never disable emergency Stop. */ }
}
// Gregorian UTC conversion keeps this logger independent of runtime payloads.
fn iso_time(seconds: u128) -> String {
    let days = (seconds / 86400) as i64 + 719468;
    let era = days / 146097;
    let doe = days - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let mut year = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    if month <= 2 {
        year += 1;
    }
    let time = seconds % 86400;
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        time / 3600,
        time / 60 % 60,
        time % 60
    )
}
#[cfg(any(target_os = "windows", target_os = "linux"))]
pub fn drain(mut stderr: impl std::io::Read + Send + 'static) {
    std::thread::spawn(move || {
        let mut buffer = [0u8; 4096];
        let mut last = 0;
        while let Ok(n) = stderr.read(&mut buffer) {
            if n == 0 {
                break;
            }
            let now = micros() / 1_000_000;
            if now > last {
                record("companion.stderr");
                last = now;
            }
        }
    });
}
