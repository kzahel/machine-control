//! Early Windows CLI dispatch. No Tauri initialization or single-instance focus.
use std::{ffi::OsString, io, os::windows::process::CommandExt, process::Command};
use windows_sys::Win32::{
    Foundation::{GetLastError, HANDLE, INVALID_HANDLE_VALUE},
    Storage::FileSystem::GetFileType,
    System::Console::{
        AttachConsole, GetConsoleCP, GetStdHandle, SetStdHandle, ATTACH_PARENT_PROCESS,
        STD_ERROR_HANDLE, STD_INPUT_HANDLE, STD_OUTPUT_HANDLE,
    },
};

fn valid(handle: HANDLE) -> bool {
    !handle.is_null() && handle != INVALID_HANDLE_VALUE && unsafe { GetFileType(handle) } != 0
}

fn console() -> bool {
    // Attaching can replace redirected standard handles. Save and restore each
    // valid inherited handle, including pipes, files and explicitly supplied NUL.
    let ids = [STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE];
    let inherited = ids.map(|id| unsafe { GetStdHandle(id) });
    let attached = unsafe { AttachConsole(ATTACH_PARENT_PROCESS) } != 0;
    let already_attached = !attached && unsafe { GetLastError() } == 5;
    for (id, handle) in ids.into_iter().zip(inherited) {
        if valid(handle) {
            unsafe { SetStdHandle(id, handle) };
        }
    }
    attached || already_attached || inherited[1..].iter().any(|handle| valid(*handle))
}

pub fn dispatch(args: &[OsString]) -> Option<i32> {
    if args.first().is_some_and(|arg| arg == "--restart-wait") {
        return Some(restart_wait(args).unwrap_or(1));
    }
    if !args.is_empty()
        && crate::restart::valid_launch_args(
            &args
                .iter()
                .map(|arg| arg.to_string_lossy().into_owned())
                .collect::<Vec<_>>(),
        )
    {
        return None;
    }
    let terminal = console();
    if args.is_empty() && !terminal {
        return None;
    }
    Some(match run(args) {
        Ok(code) => code,
        Err(error) => {
            eprintln!("Machine Control CLI unavailable: {error}");
            1
        }
    })
}

fn run(args: &[OsString]) -> io::Result<i32> {
    let executable = std::env::current_exe()?;
    let root = executable
        .parent()
        .ok_or_else(|| io::Error::other("Installation directory missing"))?;
    if args.first().is_some_and(|arg| arg == "presentation") {
        let status = Command::new(root.join("runtime/machine-control-windows.exe"))
            .args(args)
            .creation_flags(0x08000000)
            .status()?;
        return Ok(status.code().unwrap_or(1));
    }
    let cli = root.join("mc-cli");
    let script = if args.is_empty() || args == ["--start"] {
        "windows-launch.py"
    } else {
        "launch.py"
    };
    let mut command = Command::new(cli.join("python/python.exe"));
    command.args(["-I", "-B"]).arg(cli.join(script));
    if script == "launch.py" {
        command.args(args);
    }
    let status = command
        .env("MACHINE_CONTROL_CLI_LAUNCHER", &executable)
        .env("MACHINE_CONTROL_DESKTOP_INSTALL_DIR", root)
        // Keep a real calling console when attached. Without one, suppress a
        // Python console window while preserving the caller's redirected pipes.
        .creation_flags(if unsafe { GetConsoleCP() } == 0 {
            0x08000000 // CREATE_NO_WINDOW
        } else {
            0
        })
        .status()?;
    if status.success() && (args == ["--help"] || args == ["-h"]) {
        println!("\nWindows desktop: bare command or --start starts the app and prints guidance.\nUse --settings to recover Settings in the existing runtime; --gui remains supported.\nUse presentation status|set personal|minimal|appliance|reset for local configuration.\nagent identity --paths shows this installation.");
    }
    Ok(status.code().unwrap_or(1))
}

fn restart_wait(args: &[OsString]) -> Result<i32, String> {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE},
    };
    let pid: u32 = args
        .get(1)
        .and_then(|arg| arg.to_str())
        .and_then(|text| text.parse().ok())
        .ok_or("Restart predecessor missing")?;
    let launch: Vec<_> = args
        .iter()
        .skip(2)
        .map(|arg| arg.to_string_lossy().into_owned())
        .collect();
    if !crate::restart::valid_launch_args(&launch) {
        return Err("Invalid restart arguments".into());
    }
    let process = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, pid) };
    if !process.is_null() {
        let result = unsafe { WaitForSingleObject(process, 10000) };
        unsafe {
            CloseHandle(process);
        }
        if result != 0 {
            return Err("Previous application did not exit".into());
        }
    }
    Command::new(std::env::current_exe().map_err(|e| e.to_string())?)
        .args(launch)
        .creation_flags(0x08000000)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(0)
}
