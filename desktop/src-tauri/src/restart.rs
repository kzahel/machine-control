#[cfg(target_os = "macos")]
use tauri::Manager;

/// Presentation overrides apply to one launch; restart uses the saved choice.
#[cfg(target_os = "macos")]
fn restart_launch_args(args: &[std::ffi::OsString]) -> Vec<std::ffi::OsString> {
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
    #[cfg(target_os = "macos")]
    {
        let mut positional = Vec::new();
        let mut index = 0;
        let mut presentation = false;
        let mut settings = false;
        let mut background = false;
        while index < args.len() {
            match args[index].as_str() {
                "--settings" if !settings => settings = true,
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
        positional.is_empty() || positional.len() == 2 && positional[0] == "serve"
    }
    #[cfg(not(target_os = "macos"))]
    if args == ["--background"] {
        return true;
    }
    #[cfg(not(target_os = "macos"))]
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

#[cfg(not(target_os = "macos"))]
pub fn request(app: &tauri::AppHandle) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    crate::windows::shutdown();
    #[cfg(target_os = "linux")]
    crate::linux::shutdown();
    app.request_restart();
    Ok(())
}

#[cfg(all(test, target_os = "macos"))]
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
