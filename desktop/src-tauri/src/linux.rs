use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Read, Write},
    os::unix::{net::UnixStream, process::CommandExt},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{mpsc, Mutex, OnceLock},
    time::Duration,
};
use tauri::Manager;
use tauri_plugin_autostart::ManagerExt;

static RUNTIME: Mutex<Option<Runtime>> = Mutex::new(None);
static APP: OnceLock<tauri::AppHandle> = OnceLock::new();

struct Runtime {
    child: Child,
    input: ChildStdin,
    replies: mpsc::Receiver<Result<Value, String>>,
}

impl Runtime {
    fn call(&mut self, command: &Value) -> Result<Value, String> {
        if self.child.try_wait().map_err(|e| e.to_string())?.is_some() {
            return Err("Resident stopped; restart Machine Control".into());
        }
        let bytes = serde_json::to_vec(command).map_err(|e| e.to_string())?;
        if bytes.len() > 65536 {
            return Err("Operator command is too large".into());
        }
        self.input.write_all(&bytes).map_err(|e| e.to_string())?;
        self.input.write_all(b"\n").map_err(|e| e.to_string())?;
        self.input.flush().map_err(|e| e.to_string())?;
        self.replies
            .recv_timeout(Duration::from_secs(5))
            .map_err(|_| "Resident did not respond; restart Machine Control".to_owned())?
    }
}

impl Drop for Runtime {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn start(app: &tauri::AppHandle) -> Result<(), String> {
    APP.set(app.clone())
        .map_err(|_| "Operator already initialized")?;
    let directory = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("linux-runtime");
    let parent = std::process::id();
    let mut command = Command::new("/usr/bin/python3");
    command
        .arg(directory.join("desktop.py"))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    // The kernel ends this exact child if its operator dies. Pipe EOF also
    // closes the portal and revokes access; no PID file grants kill authority.
    unsafe {
        command.pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            if libc::getppid() as u32 != parent {
                return Err(std::io::Error::other("Operator exited during spawn"));
            }
            Ok(())
        });
    }
    let mut child = command.spawn().map_err(|e| e.to_string())?;
    let input = child.stdin.take().ok_or("Resident input missing")?;
    let output = child.stdout.take().ok_or("Resident output missing")?;
    let (send, replies) = mpsc::channel();
    std::thread::spawn(move || {
        let mut reader = BufReader::new(output);
        loop {
            let mut frame = Vec::new();
            let mut bounded = reader.by_ref().take(1024 * 1024 + 1);
            let result = bounded.read_until(b'\n', &mut frame);
            if matches!(result, Ok(0)) {
                break;
            }
            let value = result.map_err(|e| e.to_string()).and_then(|_| {
                if frame.len() > 1024 * 1024 || frame.last() != Some(&b'\n') {
                    return Err("Resident reply too large".into());
                }
                serde_json::from_slice(&frame).map_err(|e| e.to_string())
            });
            let failed = value.is_err();
            if send.send(value).is_err() || failed {
                break;
            }
        }
    });
    let mut runtime = Runtime {
        child,
        input,
        replies,
    };
    let executable = std::env::var_os("APPIMAGE")
        .map(std::path::PathBuf::from)
        .unwrap_or(std::env::current_exe().map_err(|e| e.to_string())?);
    let reply =
        runtime.call(&json!({"method":"hello", "processId":parent, "executable":executable}))?;
    if reply["ok"] != true {
        return Err("Resident handshake failed".into());
    }
    *RUNTIME.lock().map_err(|e| e.to_string())? = Some(runtime);
    Ok(())
}

pub fn command(command: Value) -> Result<Value, String> {
    let app = APP.get().ok_or("Operator unavailable")?;
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
        reply["state"]["version"] = json!(app.package_info().version.to_string());
        reply["state"]["sourceRevision"] = json!(env!("MC_SOURCE_REVISION"));
        reply["state"]["startOnLogin"] =
            json!(app.autolaunch().is_enabled().map_err(|e| e.to_string())?);
    }
    Ok(reply)
}

pub fn shutdown() {
    if let Ok(mut owner) = RUNTIME.lock() {
        if let Some(mut runtime) = owner.take() {
            let _ = runtime.call(&json!({"method":"quit"}));
            // The socket/portal close before a replacement is launched.
            for _ in 0..100 {
                if runtime.child.try_wait().ok().flatten().is_some() {
                    break;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
        }
    }
}

pub fn stop_from_shortcut() -> Result<(), String> {
    let directory = std::env::var("XDG_RUNTIME_DIR").map_err(|e| e.to_string())?;
    let mut socket =
        UnixStream::connect(format!("{directory}/machine-control-desktop/desktop.sock"))
            .map_err(|e| e.to_string())?;
    socket
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|e| e.to_string())?;
    socket
        .write_all(b"{\"operation\":\"grant.revoke\"}\n")
        .map_err(|e| e.to_string())?;
    Ok(())
}
