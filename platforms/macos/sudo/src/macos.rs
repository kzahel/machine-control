use serde::{Deserialize, Serialize};
use std::os::unix::net::{UnixListener, UnixStream};
use std::{
    env,
    ffi::{CStr, CString},
    fs,
    io::{Read, Write},
    os::{fd::AsRawFd, unix::process::ExitStatusExt},
    path::{Path, PathBuf},
    process::{Child, Command, ExitStatus},
    sync::atomic::{AtomicI32, Ordering},
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

const SOCKET_ENV: &str = "MC_SUDO_SOCKET";
const MAX_CONTEXT: usize = 65536;
static INTERRUPTED: AtomicI32 = AtomicI32::new(0);

extern "C" fn interrupted(signal: i32) {
    INTERRUPTED.store(signal, Ordering::Relaxed);
}

struct OwnedSudo(Child);
impl Drop for OwnedSudo {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn wait_for_sudo(child: &mut Child, helper: &Process, deadline: u64) -> Result<i32, String> {
    let mut prompting = true;
    loop {
        if let Some(status) = child.try_wait().map_err(|_| "could not observe sudo")? {
            return Ok(exit_code(status));
        }
        let signal = INTERRUPTED.swap(0, Ordering::Relaxed);
        prompting = prompting
            && matches!(process(helper.pid), Ok(ref current)
            if current.started == helper.started && current.parent == helper.parent);
        if prompting && (signal != 0 || now() >= deadline) {
            // sudo can defer termination while blocked on its askpass pipe.
            // Close the verified helper first; its EOF makes sudo refuse.
            unsafe { libc::kill(helper.pid, libc::SIGTERM) };
        }
        if signal != 0 {
            // sudo relays ordinary termination signals to its running command.
            unsafe { libc::kill(child.id() as i32, signal) };
        }
        thread::sleep(Duration::from_millis(25));
    }
}

extern "C" {
    fn mc_sudo_process(pid: i32) -> *mut libc::c_char;
    fn mc_sudo_peer(fd: i32) -> i32;
    fn mc_sudo_same_code(pid: i32, path: *const libc::c_char) -> i32;
    fn mc_sudo_prompt(context: *const libc::c_char, sudo_pid: i32, seconds: i32) -> i32;
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Process {
    pid: i32,
    parent: i32,
    uid: u32,
    started: String,
    path: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct Context {
    schema: u32,
    command: Vec<String>,
    cwd: String,
    sudo: Process,
    requester: Vec<Process>,
    deadline: u64,
}

fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

fn process(pid: i32) -> Result<Process, String> {
    let pointer = unsafe { mc_sudo_process(pid) };
    if pointer.is_null() {
        return Err("process identity is unavailable".into());
    }
    let result = unsafe { serde_json::from_slice(CStr::from_ptr(pointer).to_bytes()) };
    unsafe { libc::free(pointer.cast()) };
    result.map_err(|_| "invalid native process identity".into())
}

fn same_code(pid: i32, path: &Path) -> bool {
    let Ok(path) = CString::new(path.as_os_str().as_encoded_bytes()) else {
        return false;
    };
    unsafe { mc_sudo_same_code(pid, path.as_ptr()) == 1 }
}

fn ancestry(mut pid: i32) -> Vec<Process> {
    let mut result = Vec::new();
    for _ in 0..8 {
        let Ok(info) = process(pid) else { break };
        pid = info.parent;
        result.push(info);
        if pid <= 1 {
            break;
        }
    }
    result
}

fn resolve(command: &str, path: &str) -> Result<PathBuf, String> {
    let candidates: Vec<PathBuf> = if command.contains('/') {
        vec![PathBuf::from(command)]
    } else {
        env::split_paths(path)
            .map(|dir| dir.join(command))
            .collect()
    };
    for candidate in candidates {
        let Ok(path) = fs::canonicalize(candidate) else {
            continue;
        };
        let Ok(cpath) = CString::new(path.as_os_str().as_encoded_bytes()) else {
            continue;
        };
        if path.is_file() && unsafe { libc::access(cpath.as_ptr(), libc::X_OK) } == 0 {
            return Ok(path);
        }
    }
    Err("command is not an executable on PATH".into())
}

fn arguments(mut args: Vec<String>) -> Result<(u64, Vec<String>), String> {
    let mut seconds = 120;
    if args.first().map(String::as_str) == Some("--timeout") {
        if args.len() < 3 {
            return Err("--timeout requires seconds and a command".into());
        }
        seconds = args[1]
            .parse()
            .map_err(|_| "invalid authentication timeout")?;
        args.drain(..2);
        if !(1..=300).contains(&seconds) {
            return Err("authentication timeout must be 1–300 seconds".into());
        }
    }
    if args.first().map(String::as_str) == Some("--") {
        args.remove(0);
    }
    if args.is_empty() || args[0].starts_with('-') {
        return Err("usage: mc-sudo [--timeout SECONDS] -- COMMAND [ARGUMENTS...]".into());
    }
    if args.iter().map(String::len).sum::<usize>() > 24000 {
        return Err("command is too large to present for authentication".into());
    }
    Ok((seconds, args))
}

struct Endpoint(PathBuf);
impl Endpoint {
    fn new() -> Result<Self, String> {
        // A short path avoids Darwin's 104-byte Unix socket path limit.
        let mut name = b"/tmp/mc-sudo.XXXXXXXX\0".to_vec();
        let pointer = unsafe { libc::mkdtemp(name.as_mut_ptr().cast()) };
        if pointer.is_null() {
            return Err("could not create private authentication endpoint".into());
        }
        Ok(Self(PathBuf::from(
            unsafe { CStr::from_ptr(pointer) }
                .to_string_lossy()
                .as_ref(),
        )))
    }
    fn socket(&self) -> PathBuf {
        self.0.join("request.sock")
    }
}
impl Drop for Endpoint {
    fn drop(&mut self) {
        let _ = fs::remove_file(self.socket());
        let _ = fs::remove_dir(&self.0);
    }
}

fn exit_code(status: ExitStatus) -> i32 {
    status
        .code()
        .unwrap_or_else(|| 128 + status.signal().unwrap_or(1))
}

pub fn run() -> i32 {
    match run_inner() {
        Ok(code) => code,
        Err(error) => {
            eprintln!("mc-sudo: {error}");
            1
        }
    }
}

fn run_inner() -> Result<i32, String> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args == ["--help"] || args == ["-h"] {
        println!("Usage: mc-sudo [--timeout SECONDS] -- COMMAND [ARGUMENTS...]\nAuthenticate one command in a native Mac dialog; no new sudo cache is created.");
        return Ok(0);
    }
    let (seconds, mut command) = arguments(args)?;
    command[0] = resolve(&command[0], &env::var("PATH").unwrap_or_default())?
        .to_str()
        .ok_or("command path must be UTF-8")?
        .into();
    let wrapper = fs::canonicalize(env::current_exe().map_err(|_| "helper path is unavailable")?)
        .map_err(|_| "helper path is unavailable")?;
    let helper = wrapper.with_file_name("mc-sudo-askpass");
    if !helper.is_file() {
        return Err("bundled native password helper is missing".into());
    }
    let endpoint = Endpoint::new()?;
    let listener =
        UnixListener::bind(endpoint.socket()).map_err(|_| "could not bind private endpoint")?;
    listener
        .set_nonblocking(true)
        .map_err(|_| "could not configure private endpoint")?;
    for signal in [libc::SIGINT, libc::SIGTERM, libc::SIGHUP] {
        unsafe { libc::signal(signal, interrupted as libc::sighandler_t) };
    }
    let mut child = OwnedSudo(
        Command::new("/usr/bin/sudo")
            .args(["-A", "-k", "--"])
            .args(&command)
            .env("SUDO_ASKPASS", &helper)
            .env(SOCKET_ENV, endpoint.socket())
            .spawn()
            .map_err(|_| "could not launch system sudo")?,
    );
    let sudo_pid = child.0.id() as i32;
    let deadline = now() + seconds;
    let requester = ancestry(std::process::id() as i32);
    eprintln!("mc-sudo: waiting for native authentication (up to {seconds}s)");
    let dispatched = (|| -> Result<Process, String> {
        loop {
            if INTERRUPTED.load(Ordering::Relaxed) != 0 {
                return Err("authentication cancelled by signal".into());
            }
            if let Some(status) = child.0.try_wait().map_err(|_| "could not observe sudo")? {
                // sudoers may already permit a password-free command. Preserve
                // the existing OS policy rather than creating an artificial grant.
                return Err(format!("exit:{}", exit_code(status)));
            }
            if now() >= deadline {
                return Err("authentication timed out".into());
            }
            match listener.accept() {
                Ok((mut stream, _)) => {
                    let peer = unsafe { mc_sudo_peer(stream.as_raw_fd()) };
                    let sudo = process(sudo_pid)?;
                    let Ok(caller) = process(peer) else { continue };
                    if sudo.path != "/usr/bin/sudo"
                        || sudo.uid != 0
                        || sudo.parent != std::process::id() as i32
                        || !same_code(sudo_pid, Path::new("/usr/bin/sudo"))
                        || caller.parent != sudo_pid
                        || !same_code(peer, &helper)
                    {
                        continue;
                    }
                    stream
                        .set_write_timeout(Some(Duration::from_secs(2)))
                        .map_err(|_| "endpoint timeout failed")?;
                    let context = Context {
                        schema: 1,
                        command: command.clone(),
                        cwd: env::current_dir()
                            .map_err(|_| "working directory is unavailable")?
                            .to_string_lossy()
                            .into(),
                        sudo,
                        requester: requester.clone(),
                        deadline,
                    };
                    let data =
                        serde_json::to_vec(&context).map_err(|_| "context encoding failed")?;
                    if data.len() > MAX_CONTEXT {
                        return Err("authentication context is too large".into());
                    }
                    stream
                        .write_all(&data)
                        .map_err(|_| "password helper disconnected")?;
                    return Ok(caller);
                }
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(25));
                }
                Err(_) => return Err("authentication endpoint failed".into()),
            }
        }
    })();
    drop(listener);
    drop(endpoint);
    match dispatched {
        Ok(helper) => wait_for_sudo(&mut child.0, &helper, deadline),
        Err(error) => {
            let _ = child.0.kill();
            let _ = child.0.wait();
            if let Some(code) = error
                .strip_prefix("exit:")
                .and_then(|code| code.parse().ok())
            {
                Ok(code)
            } else {
                Err(error)
            }
        }
    }
}

pub fn askpass() -> i32 {
    match askpass_inner() {
        Ok(code) => code,
        Err(error) => {
            // Never print supplied prompt/context strings or secret bytes.
            eprintln!("mc-sudo: password helper refused invocation ({error})");
            1
        }
    }
}

fn askpass_inner() -> Result<i32, String> {
    let parent = process(unsafe { libc::getppid() })?;
    if parent.path != "/usr/bin/sudo" {
        return Err("system sudo parent path required".into());
    }
    if parent.uid != 0 {
        return Err("privileged system sudo parent required".into());
    }
    if !same_code(parent.pid, Path::new("/usr/bin/sudo")) {
        let path = CString::new("/usr/bin/sudo").unwrap();
        let status = unsafe { mc_sudo_same_code(parent.pid, path.as_ptr()) };
        return Err(format!("system sudo code verification failed: {status}"));
    }
    let helper = fs::canonicalize(env::current_exe().map_err(|_| "helper path unavailable")?)
        .map_err(|_| "helper path unavailable")?;
    let wrapper = helper.with_file_name("mc-sudo");
    let socket = env::var(SOCKET_ENV).map_err(|_| "endpoint missing")?;
    let mut stream = UnixStream::connect(socket).map_err(|_| "endpoint unavailable")?;
    let peer = unsafe { mc_sudo_peer(stream.as_raw_fd()) };
    if peer != parent.parent || !same_code(peer, &wrapper) {
        return Err("original wrapper required".into());
    }
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .map_err(|_| "endpoint timeout failed")?;
    let mut data = Vec::new();
    (&mut stream)
        .take((MAX_CONTEXT + 1) as u64)
        .read_to_end(&mut data)
        .map_err(|_| "endpoint read failed")?;
    if data.len() > MAX_CONTEXT {
        return Err("context too large".into());
    }
    let context: Context = serde_json::from_slice(&data).map_err(|_| "context invalid")?;
    let current = process(parent.pid)?;
    let remaining = context.deadline.saturating_sub(now());
    if context.schema != 1
        || context.sudo.pid != parent.pid
        || context.sudo.started != current.started
        || !(1..=300).contains(&remaining)
        || context.command.is_empty()
    {
        return Err("stale context".into());
    }
    let native = CString::new(data).map_err(|_| "context invalid")?;
    Ok(unsafe { mc_sudo_prompt(native.as_ptr(), parent.pid, remaining as i32) })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arguments_are_not_shell_text() {
        let (_, args) = arguments(vec![
            "--".into(),
            "/bin/echo".into(),
            "$(touch /tmp/no)".into(),
            "a b".into(),
        ])
        .unwrap();
        assert_eq!(args, ["/bin/echo", "$(touch /tmp/no)", "a b"]);
        assert!(arguments(vec![]).is_err());
        assert!(arguments(vec!["-s".into()]).is_err());
    }

    #[test]
    fn timeout_is_bounded() {
        for input in ["0", "301", "-1", "bad"] {
            assert!(arguments(vec!["--timeout".into(), input.into(), "/bin/true".into()]).is_err());
        }
        assert_eq!(
            arguments(vec![
                "--timeout".into(),
                "3".into(),
                "--".into(),
                "/bin/true".into()
            ])
            .unwrap()
            .0,
            3
        );
    }

    #[test]
    fn endpoint_is_private_and_removed() {
        use std::os::unix::fs::PermissionsExt;
        let endpoint = Endpoint::new().unwrap();
        let path = endpoint.0.clone();
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o700
        );
        drop(endpoint);
        assert!(!path.exists());
    }

    #[test]
    fn observes_kernel_parent_and_signed_self() {
        let pid = std::process::id() as i32;
        assert_eq!(process(pid).unwrap().parent, unsafe { libc::getppid() });
        assert!(same_code(pid, &env::current_exe().unwrap()));
        assert!(!same_code(pid, Path::new("/usr/bin/sudo")));
    }

    #[test]
    fn direct_askpass_refuses_without_stdout() {
        assert!(askpass_inner().is_err());
    }
}
