use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Read, Write},
    os::windows::{io::AsRawHandle, process::CommandExt},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicIsize, AtomicU32, AtomicU64, Ordering},
        mpsc, Arc, Mutex, OnceLock,
    },
    time::Duration,
};
use tauri::Manager;
use tauri_plugin_autostart::ManagerExt;
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, TerminateJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_BREAKAWAY_OK, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    },
};

static RUNTIME: Mutex<Option<Runtime>> = Mutex::new(None);
static APP: OnceLock<tauri::AppHandle> = OnceLock::new();
static UAC_SETUP: Mutex<Option<Child>> = Mutex::new(None);
static UAC_SETUP_ERROR: Mutex<Option<String>> = Mutex::new(None);
static STOP_WINDOW: AtomicIsize = AtomicIsize::new(0);
static STOP_PROCESS: AtomicU32 = AtomicU32::new(0);
static EPOCH: AtomicU64 = AtomicU64::new(0);
static JOB: Mutex<Option<Arc<Job>>> = Mutex::new(None);
static EXITING: AtomicBool = AtomicBool::new(false);
pub fn epoch() -> u64 {
    EPOCH.load(Ordering::Acquire)
}

/// Private inherited handshake identifies the native Stop message window.
/// Posting never waits for IPC, provider work, or a Tauri event-loop reply.
pub fn stop() -> Result<Value, String> {
    EPOCH.fetch_add(1, Ordering::AcqRel);
    let window = STOP_WINDOW.load(Ordering::Acquire);
    let mut owner = 0;
    if window != 0 {
        unsafe {
            windows_sys::Win32::UI::WindowsAndMessaging::GetWindowThreadProcessId(
                window as _,
                &mut owner,
            );
        }
    }
    if window == 0
        || owner == 0
        || owner != STOP_PROCESS.load(Ordering::Acquire)
        || unsafe {
            windows_sys::Win32::UI::WindowsAndMessaging::PostMessageW(window as _, 0x8001, 0, 0)
        } == 0
    {
        return Err("Native Stop unavailable; quit Machine Control to end its resident".into());
    }
    Ok(json!({"ok":true,"queued":true,"effect":"pending"}))
}
struct Job(HANDLE);
// Kernel job handles have no thread affinity; access is owned by RUNTIME.
unsafe impl Send for Job {}
unsafe impl Sync for Job {}
impl Drop for Job {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.0) };
    }
}
struct Runtime {
    child: Child,
    input: ChildStdin,
    replies: mpsc::Receiver<Result<Value, String>>,
    _job: Arc<Job>,
}
impl Runtime {
    fn call(&mut self, command: &Value) -> Result<Value, String> {
        if self.child.try_wait().map_err(|e| e.to_string())?.is_some() {
            crate::diagnostics::record("companion.exited");
            return Err("Resident stopped; restart Machine Control".into());
        }
        let line = serde_json::to_vec(command).map_err(|e| e.to_string())?;
        if line.len() > 65536 {
            return Err("Operator command is too large".into());
        }
        // Covers blocked writes as well as reads. Terminating our private job
        // closes the pipe; a late reply can never be reused for another call.
        let (finished, deadline) = mpsc::channel::<()>();
        let job = self._job.clone();
        std::thread::spawn(move || {
            if matches!(
                deadline.recv_timeout(Duration::from_secs(6)),
                Err(mpsc::RecvTimeoutError::Timeout)
            ) {
                unsafe {
                    TerminateJobObject(job.0, 1);
                }
            }
        });
        let _finished = finished;
        self.input.write_all(&line).map_err(|e| e.to_string())?;
        self.input.write_all(b"\n").map_err(|e| e.to_string())?;
        self.input.flush().map_err(|e| e.to_string())?;
        let reply = self
            .replies
            .recv_timeout(Duration::from_secs(5))
            .map_err(|_| {
                crate::diagnostics::record("companion.timeout");
                "Resident did not respond; restart Machine Control".to_string()
            })??;
        Ok(reply)
    }
}
impl Drop for Runtime {
    fn drop(&mut self) {
        // Kill-on-close covers descendants including the private Cua daemon.
        // Never target a PID obtained from a writable file.
        unsafe {
            TerminateJobObject(self._job.0, 0);
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn start(app: &tauri::AppHandle) -> Result<(), String> {
    APP.set(app.clone())
        .map_err(|_| "Operator already initialized")?;
    let app = app.clone();
    std::thread::spawn(move || {
        if spawn_runtime(&app).is_err() {
            crate::diagnostics::record("resident.unavailable");
        }
    });
    Ok(())
}

fn bundled_runtime(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    Ok(app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("runtime/machine-control-windows.exe"))
}

pub fn launch_option(name: &str) -> Option<String> {
    let args: Vec<_> = std::env::args().collect();
    args.iter()
        .position(|arg| arg == name)
        .and_then(|index| args.get(index + 1).cloned())
}

pub fn instance() -> String {
    launch_option("--instance").unwrap_or_else(|| "desktop".into())
}

fn spawn_runtime(app: &tauri::AppHandle) -> Result<(), String> {
    let bundled = bundled_runtime(app)?;
    let mut resolver = Command::new(&bundled)
        .arg("uac-resolve")
        .creation_flags(0x08000000)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| e.to_string())?;
    let until = std::time::Instant::now() + Duration::from_secs(3);
    while resolver.try_wait().map_err(|e| e.to_string())?.is_none() {
        if EXITING.load(Ordering::Acquire) || std::time::Instant::now() >= until {
            let _ = resolver.kill();
            let _ = resolver.wait();
            return Err("Companion resolution timed out or was cancelled".into());
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    let resolved = resolver.wait_with_output().map_err(|e| e.to_string())?;
    if !resolved.status.success() {
        return Err("Could not verify the UAC companion installation".into());
    }
    let executable = std::path::PathBuf::from(
        String::from_utf8(resolved.stdout)
            .map_err(|e| e.to_string())?
            .trim(),
    );
    let job = unsafe {
        let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if handle.is_null() {
            return Err(std::io::Error::last_os_error().to_string());
        }
        let job = Job(handle);
        let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
        limits.BasicLimitInformation.LimitFlags =
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK;
        if SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            &limits as *const _ as *const _,
            std::mem::size_of_val(&limits) as u32,
        ) == 0
        {
            return Err(std::io::Error::last_os_error().to_string());
        }
        Arc::new(job)
    };
    // Publish before creating a child; exit can cancel an incomplete startup.
    {
        let mut owner = JOB.lock().map_err(|e| e.to_string())?;
        if EXITING.load(Ordering::Acquire) {
            return Err("Operator exiting".into());
        }
        *owner = Some(job.clone());
    }
    let mut child = Command::new(executable)
        .arg("desktop")
        .args(["--instance", &instance()])
        .args(
            launch_option("--presentation")
                .map(|profile| ["--presentation".into(), profile])
                .into_iter()
                .flatten(),
        )
        .creation_flags(0x08000000) // CREATE_NO_WINDOW; this is an ordinary Medium companion.
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;
    // The child waits for our anonymous handshake before starting its agent
    // endpoint/provider. Job assignment therefore precedes all control.
    if unsafe { AssignProcessToJobObject(job.0, child.as_raw_handle() as HANDLE) } == 0 {
        let error = std::io::Error::last_os_error().to_string();
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }
    if EXITING.load(Ordering::Acquire) {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Operator exiting".into());
    }
    if let Some(stderr) = child.stderr.take() {
        crate::diagnostics::drain(stderr);
    }
    let input = child.stdin.take().ok_or("Resident input missing")?;
    let output = child.stdout.take().ok_or("Resident output missing")?;
    let (send, replies) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut reader = BufReader::new(output);
        loop {
            let value = read_reply(&mut reader);
            let terminal = value.is_err();
            if send.send(value).is_err() || terminal {
                break;
            }
        }
    });
    let mut runtime = Runtime {
        child,
        input,
        replies,
        _job: job,
    };
    let hello = runtime.call(&json!({"method":"hello", "processId":std::process::id()}))?;
    if EXITING.load(Ordering::Acquire) {
        return Err("Operator exiting".into());
    }
    STOP_PROCESS.store(runtime.child.id(), Ordering::Release);
    STOP_WINDOW.store(
        hello["stopWindow"].as_i64().unwrap_or(0) as isize,
        Ordering::Release,
    );
    *RUNTIME.lock().map_err(|e| e.to_string())? = Some(runtime);
    let args: Vec<_> = std::env::args().collect();
    if args.iter().any(|arg| arg == "--settings" || arg == "--gui")
        || (hello["presentation"]["profile"] == "personal"
            && !args.iter().any(|arg| arg == "--background"))
    {
        let ui = app.clone();
        let _ = app.run_on_main_thread(move || {
            let _ = crate::show_settings(&ui, None);
        });
    }
    Ok(())
}

pub fn command(command: Value) -> Result<Value, String> {
    if command["method"] == "stop" {
        return stop();
    }
    if command["operatorEpoch"]
        .as_u64()
        .is_some_and(|value| value != epoch())
    {
        return Err("Operator work cancelled by Stop".into());
    }
    // Reject overload instead of growing a queue behind a slow companion.
    let _permit = COMMAND_GATE
        .try_lock()
        .map_err(|_| "Resident is busy; try again")?;
    let app = APP.get().ok_or("Operator unavailable")?;
    if command["method"] == "permission.uac"
        || (command["method"] == "permission" && command["permission"] == "lockedUse")
    {
        let mut setup = UAC_SETUP.lock().map_err(|e| e.to_string())?;
        if setup.is_some() {
            return Err("Protected helper setup is already running".into());
        }
        {
            let mut owner = RUNTIME.lock().map_err(|e| e.to_string())?;
            let runtime = owner.as_mut().ok_or("Resident unavailable")?;
            let reply = runtime.call(&json!({"method":"prepare_update"}))?;
            if reply["ok"] != true {
                return Err("Stop access and finish approval before protected helper setup".into());
            }
            owner.take();
        }
        let mut launch = Command::new(bundled_runtime(app)?);
        launch
            .arg(if command["method"] == "permission.uac" {
                "uac-setup"
            } else {
                "unlock-desktop-setup"
            })
            .creation_flags(0x08000000);
        if command["remove"] == true {
            launch.arg("--remove");
        }
        match launch.spawn() {
            Ok(child) => {
                *setup = Some(child);
                *UAC_SETUP_ERROR.lock().map_err(|e| e.to_string())? = None;
            }
            Err(error) => {
                spawn_runtime(app)?;
                return Err(error.to_string());
            }
        }
        return Ok(json!({"ok":true}));
    }
    {
        let mut setup = UAC_SETUP.lock().map_err(|e| e.to_string())?;
        if let Some(child) = setup.as_mut() {
            if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
                setup.take();
                if !status.success() {
                    *UAC_SETUP_ERROR.lock().map_err(|e| e.to_string())? = Some(
                        "Protected helper setup was cancelled or failed. No access was enabled."
                            .into(),
                    );
                }
                spawn_runtime(app)?;
            } else {
                return Ok(json!({"ok":true,"setupPending":true}));
            }
        }
    }
    if command["method"] == "startup" {
        match command["enabled"].as_bool() {
            Some(true) => app.autolaunch().enable(),
            Some(false) => app.autolaunch().disable(),
            None => return Err("Choose a startup preference".into()),
        }
        .map_err(|e| e.to_string())?;
        return Ok(json!({"ok":true}));
    }
    let mut owner = RUNTIME.lock().map_err(|e| e.to_string())?;
    let runtime = owner.as_mut().ok_or("Resident unavailable")?;
    let mut reply = match runtime.call(&command) {
        Ok(value) => value,
        Err(error) => {
            crate::diagnostics::record("companion.protocol_error");
            // A broken private transport is terminal, never resynchronize or
            // replay mutating requests. Drop the complete owned process job.
            STOP_WINDOW.store(0, Ordering::Release);
            owner.take();
            return Err(error);
        }
    };
    if reply["ok"] != true {
        return Err(reply["error"]
            .as_str()
            .unwrap_or("Native operation failed")
            .into());
    }
    if command["method"] == "state" {
        reply["state"]["uac"]["setupError"] =
            json!(UAC_SETUP_ERROR.lock().map_err(|e| e.to_string())?.clone());
        reply["state"]["sourceRevision"] = json!(env!("MC_SOURCE_REVISION"));
        reply["state"]["version"] = json!(app.package_info().version.to_string());
        reply["state"]["startOnLogin"] =
            json!(app.autolaunch().is_enabled().map_err(|e| e.to_string())?);
    }
    Ok(reply)
}

pub fn shutdown() {
    EXITING.store(true, Ordering::Release);
    EPOCH.fetch_add(1, Ordering::AcqRel);
    STOP_WINDOW.store(0, Ordering::Release);
    // Exit hooks run on Tauri's event thread. Kill the owned job without
    // acquiring the IPC owner or waiting for any companion/provider reply.
    if let Ok(mut job) = JOB.lock() {
        if let Some(job) = job.take() {
            unsafe {
                TerminateJobObject(job.0, 0);
            }
        }
    }
}

static COMMAND_GATE: Mutex<()> = Mutex::new(());

fn read_reply(reader: &mut impl BufRead) -> Result<Value, String> {
    let mut bytes = Vec::new();
    reader
        .take(1024 * 1024 + 1)
        .read_until(b'\n', &mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > 1024 * 1024 || bytes.last() != Some(&b'\n') {
        return Err("Resident reply missing, truncated or too large".into());
    }
    serde_json::from_slice(&bytes).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reply_framing_is_bounded_and_terminal_on_corruption() {
        assert!(read_reply(&mut &b"{\"ok\":true}\n"[..]).is_ok());
        for frame in [&b"{}"[..], &b"invalid\n"[..], &b""[..]] {
            assert!(read_reply(&mut &frame[..]).is_err());
        }
        let frame = vec![b'x'; 2 * 1024 * 1024];
        let mut remaining = &frame[..];
        assert!(read_reply(&mut remaining).is_err());
        assert!(remaining.len() >= 1024 * 1024 - 1);
    }

    #[test]
    fn blocked_companion_write_has_a_deadline_and_owned_cleanup() {
        let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        assert!(!handle.is_null());
        let job = Arc::new(Job(handle));
        let mut child = Command::new("powershell.exe")
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Start-Sleep -Seconds 30",
            ])
            .creation_flags(0x08000000)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        assert_ne!(
            unsafe { AssignProcessToJobObject(job.0, child.as_raw_handle() as HANDLE) },
            0
        );
        let input = child.stdin.take().unwrap();
        let (_keep_reply_open, replies) = mpsc::sync_channel(1);
        let mut runtime = Runtime {
            child,
            input,
            replies,
            _job: job,
        };
        let started = std::time::Instant::now();
        assert!(runtime.call(&json!({"payload":"x".repeat(65000)})).is_err());
        assert!(started.elapsed() < Duration::from_secs(9));
        // The caller treats every protocol failure as terminal and drops the
        // owner. Keep the kernel process handle to independently prove exit.
        let process = unsafe {
            windows_sys::Win32::System::Threading::OpenProcess(
                windows_sys::Win32::System::Threading::PROCESS_SYNCHRONIZE,
                0,
                runtime.child.id(),
            )
        };
        assert!(!process.is_null());
        drop(runtime);
        assert_eq!(
            unsafe { windows_sys::Win32::System::Threading::WaitForSingleObject(process, 1000) },
            0
        );
        unsafe {
            CloseHandle(process);
        }
        // Stop posts directly even while the IPC owner is held.
        let _owner = RUNTIME.lock().unwrap();
        let stopped = std::time::Instant::now();
        let _ = stop();
        assert!(stopped.elapsed() < Duration::from_millis(250));
    }
}
