use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Write},
    os::windows::{io::AsRawHandle, process::CommandExt},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{mpsc, Mutex, OnceLock},
    time::Duration,
};
use tauri::Manager;
use tauri_plugin_autostart::ManagerExt;
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_BREAKAWAY_OK, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    },
};

static RUNTIME: Mutex<Option<Runtime>> = Mutex::new(None);
static APP: OnceLock<tauri::AppHandle> = OnceLock::new();
static UAC_SETUP: Mutex<Option<Child>> = Mutex::new(None);
static UAC_SETUP_ERROR: Mutex<Option<String>> = Mutex::new(None);
struct Job(HANDLE);
// Kernel job handles have no thread affinity; access is owned by RUNTIME.
unsafe impl Send for Job {}
impl Drop for Job {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.0) };
    }
}
struct Runtime {
    child: Child,
    input: ChildStdin,
    replies: mpsc::Receiver<Result<Value, String>>,
    _job: Job,
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
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn start(app: &tauri::AppHandle) -> Result<(), String> {
    APP.set(app.clone())
        .map_err(|_| "Operator already initialized")?;
    spawn_runtime(app)
}

fn bundled_runtime(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    Ok(app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("runtime/machine-control-windows.exe"))
}

fn spawn_runtime(app: &tauri::AppHandle) -> Result<(), String> {
    let bundled = bundled_runtime(app)?;
    let resolved = Command::new(&bundled)
        .arg("uac-resolve")
        .creation_flags(0x08000000)
        .output()
        .map_err(|e| e.to_string())?;
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
        job
    };
    let mut child = Command::new(executable)
        .arg("desktop")
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
    if let Some(stderr) = child.stderr.take() {
        crate::diagnostics::drain(stderr);
    }
    let input = child.stdin.take().ok_or("Resident input missing")?;
    let output = child.stdout.take().ok_or("Resident output missing")?;
    let (send, replies) = mpsc::channel();
    std::thread::spawn(move || {
        for line in BufReader::new(output).lines() {
            let value = line.map_err(|e| e.to_string()).and_then(|text| {
                if text.len() > 1024 * 1024 {
                    return Err("Resident reply too large".into());
                }
                serde_json::from_str(&text).map_err(|e| e.to_string())
            });
            if send.send(value).is_err() {
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
    runtime.call(&json!({"method":"hello", "processId":std::process::id()}))?;
    *RUNTIME.lock().map_err(|e| e.to_string())? = Some(runtime);
    Ok(())
}

pub fn command(command: Value) -> Result<Value, String> {
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
    if let Ok(mut owner) = RUNTIME.lock() {
        if let Some(mut runtime) = owner.take() {
            let _ = runtime.call(&json!({"method":"quit"}));
        }
    }
}
