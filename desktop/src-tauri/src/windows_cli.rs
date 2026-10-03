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
    if args == ["--background"] || args == ["--gui"] {
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
        println!("\nWindows desktop: bare command or --start starts the app and prints guidance.\nUse --gui to open the operator window. agent identity --paths shows this installation.");
    }
    Ok(status.code().unwrap_or(1))
}
