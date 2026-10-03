#[cfg(target_os = "macos")]
use tauri::Manager;

pub fn valid_launch_args(args: &[String]) -> bool {
    #[cfg(target_os = "windows")]
    if args == ["--gui"] {
        return true;
    }
    if args == ["--background"] {
        return true;
    }
    args.is_empty() || args.first().is_some_and(|v| v == "serve") && args.len() == 2
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
        .args(env.args_os.iter().skip(1))
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
