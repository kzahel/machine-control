#[cfg(any(target_os = "macos", target_os = "linux"))]
use tauri::Manager;

/// Presentation overrides apply to one launch; restart uses the saved choice.
#[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
pub(crate) fn restart_launch_args(args: &[std::ffi::OsString]) -> Vec<std::ffi::OsString> {
    let mut result = Vec::new();
    let mut input = args.iter();
    while let Some(arg) = input.next() {
        if arg == "--presentation" {
            input.next();
        } else {
            result.push(arg.clone());
        }
    }
    result
}

pub fn valid_launch_args(args: &[String]) -> bool {
    #[cfg(target_os = "windows")]
    if args == ["--gui"] {
        return true;
    }
    #[cfg(any(target_os = "macos", target_os = "windows", target_os = "linux"))]
    {
        let mut positional = Vec::new();
        let mut index = 0;
        let mut presentation = false;
        let mut settings = false;
        let mut background = false;
        while index < args.len() {
            match args[index].as_str() {
                "--settings" if !settings => settings = true,
                #[cfg(target_os = "windows")]
                "--gui" if !settings => settings = true,
                #[cfg(any(target_os = "windows", target_os = "linux"))]
                "--instance" if !positional.contains(&"--instance") => {
                    index += 1;
                    let Some(instance) = args.get(index) else {
                        return false;
                    };
                    if instance.is_empty()
                        || instance.len() > 48
                        || !instance
                            .bytes()
                            .all(|ch| ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == b'-')
                        || instance.starts_with('-')
                    {
                        return false;
                    }
                    positional.push("--instance");
                }
                "--background" if !background => background = true,
                "--presentation" if !presentation => {
                    index += 1;
                    if !args.get(index).is_some_and(|name| {
                        ["personal", "minimal", "appliance"].contains(&name.as_str())
                    }) {
                        return false;
                    }
                    presentation = true;
                }
                value if !value.starts_with('-') => positional.push(value),
                _ => return false,
            }
            index += 1;
        }
        #[cfg(any(target_os = "windows", target_os = "linux"))]
        positional.retain(|value| *value != "--instance");
        positional.is_empty() || positional.len() == 2 && positional[0] == "serve"
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    if args == ["--background"] {
        return true;
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        args.is_empty() || args.first().is_some_and(|v| v == "serve") && args.len() == 2
    }
}

/// A replacement must outlive the launchd job and wait until its predecessor's
/// IPC and single-instance endpoints have actually closed.
#[cfg(target_os = "macos")]
pub fn request(app: &tauri::AppHandle) -> Result<(), String> {
    use std::os::unix::process::CommandExt;
    let env = app.env();
    let binary = tauri::process::current_binary(&env).map_err(|e| e.to_string())?;
    // Use an OS helper: the replacement bundle may predate our private code.
    // Arguments stay positional; no app path or launch argument becomes shell
    // source. Only the verified bundle and its original launch args are used.
    const HANDOFF: &str = r#"
echo "Restart: helper started" >&2
predecessor=$1
shift
attempt=0
while kill -0 "$predecessor" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 400 ]; then
        echo 'Previous application did not exit' >&2
        exit 1
    fi
    /bin/sleep 0.025
done
echo "Restart: launching" >&2
exec "$@"
"#;
    eprintln!("Restart: starting helper");
    std::process::Command::new("/bin/sh")
        .args(["-c", HANDOFF, "mc-restart"])
        .arg(std::process::id().to_string())
        .arg(binary)
        .args(restart_launch_args(&env.args_os[1..]))
        .process_group(0)
        .spawn()
        .map_err(|e| e.to_string())?;
    app.exit(0);
    Ok(())
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn request(app: &tauri::AppHandle) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    crate::windows::shutdown();
    #[cfg(target_os = "linux")]
    crate::linux::shutdown();
    app.request_restart();
    Ok(())
}

#[cfg(all(
    test,
    any(target_os = "macos", target_os = "windows", target_os = "linux")
))]
mod tests {
    use super::{restart_launch_args, valid_launch_args};
    fn valid(args: &[&str]) -> bool {
        valid_launch_args(&args.iter().map(|arg| (*arg).to_owned()).collect::<Vec<_>>())
    }
    #[test]
    fn settings_and_temporary_modes_are_valid_launch_arguments() {
        assert!(valid(&["--settings"]));
        for profile in ["personal", "minimal", "appliance"] {
            assert!(valid(&[
                "serve",
                "/tmp/example.sock",
                "--presentation",
                profile,
                "--settings"
            ]));
            assert!(valid(&["--background", "--presentation", profile]));
        }
        assert!(!valid(&["--presentation"]));
        assert!(!valid(&["--presentation", "unknown"]));
        assert!(!valid(&["--settings", "--settings"]));
        assert!(!valid(&["serve", "/tmp/example.sock", "extra"]));
    }

    #[test]
    fn restart_expires_override_and_preserves_endpoint_and_recovery() {
        for profile in ["personal", "minimal", "appliance"] {
            let args: Vec<std::ffi::OsString> = [
                "serve",
                "/private/tmp/example with spaces.sock",
                "--presentation",
                profile,
                "--settings",
                "--background",
            ]
            .iter()
            .map(std::ffi::OsString::from)
            .collect();
            let expected: Vec<std::ffi::OsString> = [
                "serve",
                "/private/tmp/example with spaces.sock",
                "--settings",
                "--background",
            ]
            .iter()
            .map(std::ffi::OsString::from)
            .collect();
            assert_eq!(restart_launch_args(&args), expected);
            assert_eq!(restart_launch_args(&expected), expected);
        }
    }
}

#[cfg(target_os = "linux")]
fn linux_handoff(
    fd: i32,
    binary: &std::path::Path,
    args: &[std::ffi::OsString],
) -> std::process::Command {
    use std::os::unix::process::CommandExt;
    // A pidfd observes kernel exit even while the predecessor is an unreaped
    // zombie. The inherited descriptor also prevents PID reuse from retargeting.
    const WAIT: &str = "import os,select,sys; fd=int(sys.argv[1]); p=select.poll(); p.register(fd,select.POLLIN); ready=p.poll(10000); os.close(fd); ready or sys.exit('Previous application did not exit'); os.execv(sys.argv[2],sys.argv[2:])";
    let mut command = std::process::Command::new("/usr/bin/python3");
    command
        .args(["-I", "-B", "-c", WAIT])
        .arg(fd.to_string())
        .arg(binary)
        .args(args)
        .process_group(0);
    unsafe {
        command.pre_exec(move || {
            if libc::fcntl(fd, libc::F_SETFD, 0) < 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    command
}

#[cfg(target_os = "linux")]
pub fn request(app: &tauri::AppHandle) -> Result<(), String> {
    use std::os::fd::{AsRawFd, FromRawFd};
    let fd = unsafe { libc::syscall(libc::SYS_pidfd_open, std::process::id(), 0) as i32 };
    if fd < 0 {
        return Err("Kernel restart handle unavailable".into());
    }
    let handle = unsafe { std::fs::File::from_raw_fd(fd) };
    let env = app.env();
    let binary = tauri::process::current_binary(&env).map_err(|e| e.to_string())?;
    let mut command = linux_handoff(
        handle.as_raw_fd(),
        &binary,
        &restart_launch_args(&env.args_os[1..]),
    );
    crate::linux::sanitize_system_command(&mut command)?;
    command.spawn().map_err(|e| e.to_string())?;
    crate::linux::shutdown();
    app.exit(0);
    Ok(())
}

#[cfg(all(test, target_os = "linux"))]
mod linux_restart_tests {
    #[test]
    fn kernel_handoff_observes_exit_without_parent_reaping() {
        use std::os::fd::{AsRawFd, FromRawFd};
        let mut predecessor = std::process::Command::new("/bin/sleep")
            .arg("0.1")
            .spawn()
            .unwrap();
        let fd = unsafe { libc::syscall(libc::SYS_pidfd_open, predecessor.id(), 0) as i32 };
        assert!(fd >= 0);
        let handle = unsafe { std::fs::File::from_raw_fd(fd) };
        let mut helper =
            super::linux_handoff(handle.as_raw_fd(), std::path::Path::new("/bin/true"), &[])
                .spawn()
                .unwrap();
        let end = std::time::Instant::now() + std::time::Duration::from_secs(2);
        loop {
            if let Some(status) = helper.try_wait().unwrap() {
                assert!(status.success());
                break;
            }
            if std::time::Instant::now() >= end {
                let _ = helper.kill();
                panic!("Zombie predecessor blocked restart");
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        predecessor.wait().unwrap();
    }
}

#[cfg(target_os = "windows")]
pub fn request(app: &tauri::AppHandle) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    let binary = std::env::current_exe().map_err(|e| e.to_string())?;
    std::process::Command::new(binary)
        .args(["--restart-wait", &std::process::id().to_string()])
        .args(restart_launch_args(
            &std::env::args_os().skip(1).collect::<Vec<_>>(),
        ))
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .creation_flags(0x08000000)
        .spawn()
        .map_err(|e| e.to_string())?;
    crate::windows::shutdown();
    app.exit(0);
    Ok(())
}
