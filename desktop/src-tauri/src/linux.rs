use serde_json::{json, Value};
use std::{
    ffi::OsString,
    io::{BufRead, BufReader, Read, Write},
    os::fd::AsRawFd,
    os::unix::{net::UnixStream, process::CommandExt},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicU64, Ordering},
        mpsc, Mutex, OnceLock,
    },
    time::Duration,
};
use tauri::Manager;

static EPOCH: AtomicU64 = AtomicU64::new(0);
static GENERATION: Mutex<Option<String>> = Mutex::new(None);

pub fn epoch() -> u64 {
    EPOCH.load(Ordering::Acquire)
}

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
            crate::diagnostics::record("companion.exited");
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
            .map_err(|_| {
                crate::diagnostics::record("companion.timeout");
                "Resident did not respond; restart Machine Control".to_owned()
            })?
    }
}

impl Drop for Runtime {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn instance() -> String {
    let args: Vec<String> = std::env::args().collect();
    args.iter()
        .position(|arg| arg == "--instance")
        .and_then(|index| args.get(index + 1))
        .cloned()
        .unwrap_or_else(|| "desktop".into())
}

pub fn cli(args: &[OsString]) -> Option<i32> {
    if args.first().is_none_or(|arg| arg != "presentation") {
        return None;
    }
    let context: tauri::Context<tauri::Wry> = tauri::generate_context!();
    let result =
        tauri::utils::platform::resource_dir(context.package_info(), &tauri::Env::default())
            .map_err(|error| error.to_string())
            .and_then(|directory| {
                Command::new("/usr/bin/python3")
                    .args(["-I", "-B"])
                    .arg(directory.join("linux-runtime/presentation.py"))
                    .args(&args[1..])
                    .status()
                    .map_err(|error| error.to_string())
            });
    Some(match result {
        Ok(status) => status.code().unwrap_or(1),
        Err(error) => {
            eprintln!("{error}");
            1
        }
    })
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
        .stderr(Stdio::piped());
    // AppImage libraries belong to the Tauri process. The system Python/GI
    // companion uses the installed desktop libraries and typelibs instead.
    for name in [
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "GI_TYPELIB_PATH",
        "GST_PLUGIN_PATH",
        "GST_PLUGIN_SYSTEM_PATH",
        "GST_PLUGIN_SYSTEM_PATH_1_0",
        "GST_PLUGIN_PATH_1_0",
        "GST_PLUGIN_SCANNER",
        "GST_REGISTRY",
        "GSTREAMER_PREFIX",
        "GTK_PATH",
        "GTK_MODULES",
        "GTK_DATA_PREFIX",
        "GTK_EXE_PREFIX",
        "GSETTINGS_SCHEMA_DIR",
        "GDK_BACKEND",
        "GTK_IM_MODULE_FILE",
        "GIO_MODULE_DIR",
        "GIO_EXTRA_MODULES",
        "GDK_PIXBUF_MODULE_FILE",
        "GDK_PIXBUF_MODULEDIR",
        "APPDIR",
        "PYTHONHOME",
        "PYTHONPATH",
    ] {
        command.env_remove(name);
    }
    if let Some(appdir) = std::env::var_os("APPDIR") {
        // Keep the user's ordinary data search paths, excluding this mounted
        // bundle's GTK/GIO data. The companion uses the system desktop stack.
        if let Some(paths) = std::env::var_os("XDG_DATA_DIRS") {
            let kept: Vec<_> = std::env::split_paths(&paths)
                .filter(|path| !path.starts_with(&appdir))
                .collect();
            command.env(
                "XDG_DATA_DIRS",
                std::env::join_paths(kept).map_err(|e| e.to_string())?,
            );
        }
    }
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
    if let Some(stderr) = child.stderr.take() {
        crate::diagnostics::drain(stderr);
    }
    let input = child.stdin.take().ok_or("Resident input missing")?;
    // Fail and reap on a full companion pipe; never block a worker indefinitely.
    unsafe {
        let flags = libc::fcntl(input.as_raw_fd(), libc::F_GETFL);
        if flags < 0 || libc::fcntl(input.as_raw_fd(), libc::F_SETFL, flags | libc::O_NONBLOCK) < 0
        {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Companion pipe setup failed".into());
        }
    }
    let output = child.stdout.take().ok_or("Resident output missing")?;
    let (send, replies) = mpsc::sync_channel(1);
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
    let args: Vec<String> = std::env::args().collect();
    let presentation = args
        .iter()
        .position(|arg| arg == "--presentation")
        .and_then(|index| args.get(index + 1));
    let reply = runtime.call(&json!({"method":"hello", "processId":parent,
        "executable":executable, "instance":instance(), "presentation":presentation}))?;
    if let Some(generation) = reply["coordinatorGeneration"].as_str() {
        let mut previous = GENERATION.lock().map_err(|e| e.to_string())?;
        if previous.as_deref() != Some(generation) {
            *previous = Some(generation.to_owned());
            EPOCH.fetch_add(1, Ordering::AcqRel);
        }
    }
    if reply["ok"] != true {
        return Err("Resident handshake failed".into());
    }
    *RUNTIME.lock().map_err(|e| e.to_string())? = Some(runtime);
    Ok(())
}

pub fn command(command: Value) -> Result<Value, String> {
    let app = APP.get().ok_or("Operator unavailable")?;
    let mut owner = RUNTIME.lock().map_err(|e| e.to_string())?;
    let runtime = owner.as_mut().ok_or("Resident unavailable")?;
    if command.get("operatorEpoch").is_some() && command["operatorEpoch"].as_u64() != Some(epoch())
    {
        return Err("Operator authority changed before dispatch".into());
    }
    let mut command = command;
    if ["arm", "resume", "pause", "permission", "prepare_update"]
        .contains(&command["method"].as_str().unwrap_or(""))
    {
        command["expectedGeneration"] =
            json!(GENERATION.lock().map_err(|e| e.to_string())?.clone());
    }
    let mut reply = match runtime.call(&command) {
        Ok(value) => value,
        Err(error) => {
            crate::diagnostics::record("companion.protocol_error");
            owner.take();
            return Err(error);
        }
    };
    if let Some(generation) = reply["coordinatorGeneration"].as_str() {
        let mut previous = GENERATION.lock().map_err(|e| e.to_string())?;
        if previous.as_deref() != Some(generation) {
            *previous = Some(generation.to_owned());
            EPOCH.fetch_add(1, Ordering::AcqRel);
        }
    }
    if reply["ok"] != true {
        return Err(reply["error"]
            .as_str()
            .unwrap_or("Native operation failed")
            .into());
    }
    if command["method"] == "state" {
        reply["state"]["version"] = json!(app.package_info().version.to_string());
        reply["state"]["sourceRevision"] = json!(env!("MC_SOURCE_REVISION"));
        reply["state"]["updateInstallSupported"] = json!(std::env::var_os("APPIMAGE").is_some());
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
    EPOCH.fetch_add(1, Ordering::AcqRel);
    let directory = std::env::var("XDG_RUNTIME_DIR").map_err(|e| e.to_string())?;
    let mut socket = UnixStream::connect(format!(
        "{directory}/machine-control-{}/operator.sock",
        instance()
    ))
    .map_err(|e| e.to_string())?;
    socket
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|e| e.to_string())?;
    socket
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|e| e.to_string())?;
    socket
        .write_all(b"{\"method\":\"stop\"}\n")
        .map_err(|e| e.to_string())?;
    let mut frame = Vec::new();
    BufReader::new(socket)
        .take(4097)
        .read_until(b'\n', &mut frame)
        .map_err(|e| e.to_string())?;
    let reply: Value = serde_json::from_slice(&frame).map_err(|e| e.to_string())?;
    if reply["ok"] != true {
        return Err("Stop refused".into());
    }
    Ok(())
}
