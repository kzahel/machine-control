#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::{json, Value};
#[cfg(target_os = "macos")]
use std::ffi::{CStr, CString};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager,
};
use tauri_plugin_updater::UpdaterExt;
mod diagnostics;
#[cfg(target_os = "linux")]
mod linux;
mod restart;
mod updates;
#[cfg(target_os = "windows")]
mod windows;
#[cfg(target_os = "windows")]
mod windows_cli;

#[cfg(target_os = "macos")]
extern "C" {
    fn mc_desktop_mode(input: *const libc::c_char) -> i32;
    fn mc_desktop_start(path: *const libc::c_char) -> *mut libc::c_char;
    fn mc_desktop_command(input: *const libc::c_char) -> *mut libc::c_char;
}

#[cfg(target_os = "macos")]
fn decode(pointer: *mut libc::c_char) -> Result<Value, String> {
    if pointer.is_null() {
        return Err("Native resident returned no result".into());
    }
    // The bridge returns a strdup-owned JSON string; consume it exactly once.
    let parsed = unsafe {
        let text = CStr::from_ptr(pointer).to_string_lossy().into_owned();
        libc::free(pointer.cast());
        serde_json::from_str::<Value>(&text).map_err(|e| e.to_string())
    }?;
    if parsed["ok"] != true {
        return Err(parsed["error"]
            .as_str()
            .unwrap_or("Native operation failed")
            .into());
    }
    Ok(parsed)
}

#[cfg(target_os = "macos")]
fn platform_command(command: Value) -> Result<Value, String> {
    let input = CString::new(command.to_string()).map_err(|e| e.to_string())?;
    decode(unsafe { mc_desktop_command(input.as_ptr()) })
}
#[cfg(target_os = "windows")]
fn platform_command(command: Value) -> Result<Value, String> {
    windows::command(command)
}
#[cfg(target_os = "linux")]
fn platform_command(command: Value) -> Result<Value, String> {
    linux::command(command)
}
#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
fn platform_command(_: Value) -> Result<Value, String> {
    Err("Desktop workstation control is currently available on macOS; this platform adapter is not installed".into())
}

fn native_command(command: Value) -> Result<Value, String> {
    if command["method"] == "logs.open" {
        let reply = platform_command(json!({"method":"logs.location"}))?;
        let path = reply["path"].as_str().ok_or("Log folder unavailable")?;
        #[cfg(target_os = "macos")]
        let status = std::process::Command::new("/usr/bin/open")
            .arg(path)
            .status();
        #[cfg(target_os = "windows")]
        let status = std::process::Command::new("explorer.exe")
            .arg(path)
            .status();
        #[cfg(target_os = "linux")]
        let status = std::process::Command::new("xdg-open").arg(path).status();
        status.map_err(|_| "Could not open log folder")?;
        return Ok(json!({"ok":true}));
    }
    let state_request = command["method"] == "state";
    let mut reply = platform_command(command)?;
    if state_request {
        reply["state"]["updates"] = updates::status();
    }
    Ok(reply)
}

#[tauri::command]
fn check_update(app: tauri::AppHandle, window: tauri::WebviewWindow) -> Result<Value, String> {
    if window.label() != "main" {
        return Err("Operator window required".into());
    }
    updates::check(&app, "manual")
}

// AT-SPI can call back into this GTK application while the resident handles
// another application. Never wait for Linux IPC on GTK's event thread.
fn schedule_native(
    app: &tauri::AppHandle,
    task: impl FnOnce() + Send + 'static,
) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        let _ = app;
        tauri::async_runtime::spawn_blocking(task);
        Ok(())
    }
    #[cfg(not(target_os = "linux"))]
    app.run_on_main_thread(task).map_err(|e| e.to_string())
}

#[tauri::command]
async fn operator_command(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
    command: Value,
) -> Result<Value, String> {
    if window.label() != "main" {
        let method = command["method"].as_str().unwrap_or("");
        if window.label() != "control-notice"
            || ![
                "state",
                "start_control",
                "defer_control",
                "pause",
                "cancel_control",
            ]
            .contains(&method)
        {
            return Err("Operator window required".into());
        }
    }
    let (send, receive) = std::sync::mpsc::channel();
    schedule_native(&app, move || {
        let _ = send.send(native_command(command));
    })
    .map_err(|e| e.to_string())?;
    receive
        .recv_timeout(std::time::Duration::from_secs(10))
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn restart_application(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Operator window required".into());
    }
    let (send, receive) = std::sync::mpsc::channel();
    let handle = app.clone();
    schedule_native(&app, move || {
        #[cfg(target_os = "windows")]
        let result = {
            let _ = native_command(json!({"method":"prepare_exit"}));
            restart::request(&handle)
        };
        #[cfg(target_os = "linux")]
        let result =
            native_command(json!({"method":"stop"})).and_then(|_| restart::request(&handle));
        #[cfg(target_os = "macos")]
        let result = native_command(json!({"method":"prepare_exit"}))
            .and_then(|_| restart::request(&handle));
        let _ = send.send(result);
    })
    .map_err(|e| e.to_string())?;
    receive
        .recv_timeout(std::time::Duration::from_secs(10))
        .map_err(|e| e.to_string())?
}

/// Keep the lifecycle gate in native code, outside the web presentation.
#[tauri::command]
async fn install_update(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
    version: String,
) -> Result<(), String> {
    if window.label() != "main" {
        return Err("Operator window required".into());
    }
    #[cfg(target_os = "linux")]
    if std::env::var_os("APPIMAGE").is_none() {
        return Err("Install Debian updates with the package manager".into());
    }
    updates::begin_install(&version)?;
    let result = perform_install(app, version).await;
    updates::finish_install(&result);
    result
}

async fn perform_install(app: tauri::AppHandle, version: String) -> Result<(), String> {
    let updater = app
        .updater_builder()
        .header("X-Check-Reason", "manual")
        .map_err(|e| e.to_string())?
        .timeout(std::time::Duration::from_secs(20));
    #[cfg(target_os = "windows")]
    let updater = {
        let exit = app.clone();
        updater.on_before_exit(move || {
            windows::shutdown();
            exit.cleanup_before_exit();
        })
    };
    let mut update = updater
        .build()
        .map_err(|e| e.to_string())?
        .check()
        .await
        .map_err(|e| e.to_string())?
        .ok_or("No update is available")?;
    if update.version != version {
        return Err("Update changed; check again before installing".into());
    }
    update.timeout = Some(std::time::Duration::from_secs(120));
    let bytes = update
        .download(|_, _| {}, || {})
        .await
        .map_err(|e| e.to_string())?;
    updates::installing();
    let (send, receive) = std::sync::mpsc::channel();
    let restart = app.clone();
    schedule_native(&app, move || {
        // Check immediately before replacement on the resident's serial
        // main thread. No grant or approval can race bundle replacement.
        let result = native_command(json!({"method":"prepare_update"}))
            .and_then(|_| update.install(bytes).map_err(|e| e.to_string()))
            .and_then(|_| restart::request(&restart));
        if result.is_err() {
            let _ = native_command(json!({"method":"cancel_update"}));
        }
        let _ = send.send(result);
    })
    .map_err(|e| e.to_string())?;
    // Once replacement is dispatched, retain update exclusion until it finishes.
    // Timing out the waiter would allow a second install to race that work.
    tauri::async_runtime::spawn_blocking(move || receive.recv().map_err(|e| e.to_string()))
        .await
        .map_err(|e| e.to_string())??
}

fn main() {
    #[cfg(target_os = "windows")]
    if let Some(code) = windows_cli::dispatch(&std::env::args_os().skip(1).collect::<Vec<_>>()) {
        std::process::exit(code);
    }
    let args: Vec<String> = std::env::args().skip(1).collect();
    #[cfg(target_os = "linux")]
    if args == ["--identity"] {
        println!(
            "{}",
            json!({"schema":"machine-control-desktop-identity/v0",
            "version":env!("CARGO_PKG_VERSION"), "sourceRevision":env!("MC_SOURCE_REVISION"),
            "platform":"linux", "arch":std::env::consts::ARCH, "purpose":env!("MC_DESKTOP_PURPOSE")})
        );
        return;
    }
    #[cfg(target_os = "linux")]
    if args == ["--stop"] {
        match linux::stop_from_shortcut() {
            Ok(()) => std::process::exit(0),
            Err(error) => {
                eprintln!("{error}");
                std::process::exit(1);
            }
        }
    }
    #[cfg(target_os = "macos")]
    {
        let input = CString::new(serde_json::to_string(&args).unwrap()).unwrap();
        let mode = unsafe { mc_desktop_mode(input.as_ptr()) };
        if mode != 0 {
            std::process::exit(if mode > 0 { 0 } else { 1 });
        }
    }
    if !restart::valid_launch_args(&args) {
        eprintln!("Usage: macui [serve SOCKET | request SOCKET [JSON] | credential SOCKET LEASE | screen-capture-preflight]");
        std::process::exit(2);
    }
    #[cfg(target_os = "macos")]
    let socket = if args.first().is_some_and(|v| v == "serve") {
        args.get(1).cloned().unwrap_or_default()
    } else {
        String::new()
    };
    let builder = tauri::Builder::default();
    #[cfg(target_os = "windows")]
    let builder = builder.plugin(tauri_plugin_autostart::init(
        tauri_plugin_autostart::MacosLauncher::LaunchAgent,
        Some(vec!["--background"]),
    ));
    builder
        .plugin(tauri_plugin_single_instance::init(|app, args, _| {
            if args.iter().any(|arg| arg == "--background") {
                return;
            }
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            operator_command,
            check_update,
            install_update,
            restart_application
        ])
        .setup(move |app| {
            diagnostics::start();
            #[cfg(target_os = "linux")]
            {
                linux::start(app.handle()).map_err(std::io::Error::other)?;
                if args == ["--background"] {
                    if let Some(window) = app.get_webview_window("main") {
                        window.hide()?;
                    }
                }
            }
            #[cfg(target_os = "windows")]
            {
                windows::start(app.handle()).map_err(std::io::Error::other)?;
                if args == ["--background"] {
                    if let Some(window) = app.get_webview_window("main") {
                        window.hide()?;
                    }
                }
            }
            #[cfg(target_os = "macos")]
            {
                let path = CString::new(socket.clone())?;
                decode(unsafe { mc_desktop_start(path.as_ptr()) })
                    .map_err(std::io::Error::other)?;
                if args == ["--background"] {
                    if let Some(window) = app.get_webview_window("main") {
                        window.hide()?;
                    }
                }
            }
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut previous_pending = String::new();
                loop {
                    std::thread::sleep(std::time::Duration::from_secs(1));
                    let (send, receive) = std::sync::mpsc::channel();
                    if schedule_native(&handle, move || {
                        let _ = send.send(native_command(json!({"method":"state"})));
                    })
                    .is_err()
                    {
                        break;
                    }
                    let Ok(Ok(value)) = receive.recv_timeout(std::time::Duration::from_secs(5))
                    else {
                        continue;
                    };
                    let pending = value["state"]["pending"]["id"]
                        .as_str()
                        .unwrap_or("")
                        .to_owned();
                    let active = !value["state"]["deployment"]["grant"].is_null()
                        || value["state"]["desktopCallerTrust"]["enabled"] == true;
                    let standing =
                        value["state"]["deployment"]["policy"]["grantMode"] == "standing";
                    let show = !pending.is_empty() && pending != previous_pending;
                    previous_pending = pending;
                    #[cfg(target_os = "windows")]
                    let announcing = value["state"]["admission"]["requests"]
                        .as_array()
                        .is_some_and(|requests| {
                            requests
                                .iter()
                                .any(|request| request["state"] == "announcing")
                        });
                    let ui = handle.clone();
                    let _ = handle.run_on_main_thread(move || {
                        if let Some(tray) = ui.tray_by_id("control") {
                            let _ = tray.set_tooltip(Some(if active {
                                "Machine Control — access allowed"
                            } else if standing {
                                "Machine Control — standing access"
                            } else {
                                "Machine Control — access off"
                            }));
                            #[cfg(target_os = "macos")]
                            {
                                let _ = tray.set_title(Some(if active || standing {
                                    "ON"
                                } else {
                                    ""
                                }));
                            }
                        }
                        #[cfg(target_os = "windows")]
                        {
                            if announcing {
                                if let Some(window) = ui.get_webview_window("control-notice") {
                                    let _ = window.show();
                                } else {
                                    let _ = tauri::WebviewWindowBuilder::new(
                                        &ui,
                                        "control-notice",
                                        tauri::WebviewUrl::App("index.html?control-notice".into()),
                                    )
                                    .title("Machine Control")
                                    .inner_size(470.0, 270.0)
                                    .resizable(false)
                                    .focused(false)
                                    .skip_taskbar(true)
                                    .always_on_top(true)
                                    .build();
                                }
                            } else if let Some(window) = ui.get_webview_window("control-notice") {
                                let _ = window.hide();
                            }
                        }
                        if show {
                            if let Some(window) = ui.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    });
                }
            });
            let open = MenuItem::with_id(app, "open", "Open Machine Control", true, None::<&str>)?;
            let settings = MenuItem::with_id(app, "settings", "Settings…", true, None::<&str>)?;
            let updates =
                MenuItem::with_id(app, "updates", "Check for Updates…", true, None::<&str>)?;
            let stop = MenuItem::with_id(app, "stop", "Stop access", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Machine Control", true, None::<&str>)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let menu =
                Menu::with_items(app, &[&open, &settings, &updates, &separator, &stop, &quit])?;
            TrayIconBuilder::with_id("control")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Machine Control")
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" | "settings" | "updates" => {
                        if event.id.as_ref() == "updates" {
                            let _ = updates::check(app, "manual");
                        }
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.emit("tray-command", event.id.as_ref());
                        }
                    }
                    "stop" => {
                        #[cfg(target_os = "linux")]
                        tauri::async_runtime::spawn_blocking(|| {
                            let _ = native_command(json!({"method":"stop"}));
                        });
                        #[cfg(not(target_os = "linux"))]
                        let _ = native_command(json!({"method":"stop"}));
                    }
                    "quit" => {
                        #[cfg(target_os = "linux")]
                        {
                            let handle = app.clone();
                            tauri::async_runtime::spawn_blocking(move || {
                                let _ = native_command(json!({"method":"stop"}));
                                linux::shutdown();
                                handle.exit(0);
                            });
                        }
                        #[cfg(not(target_os = "linux"))]
                        {
                            let _ = native_command(json!({"method":"prepare_exit"}));
                            #[cfg(target_os = "windows")]
                            windows::shutdown();
                            app.exit(0);
                        }
                    }
                    _ => {}
                })
                .build(app)?;
            updates::start(app.handle(), updates);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
                if window.label() == "control-notice" {
                    let app = window.app_handle().clone();
                    let _ = schedule_native(&app, || {
                        let _ = native_command(json!({"method":"defer_control"}));
                    });
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Machine Control could not start")
        .run(|_, event| {
            // The native application menu and Cmd-Q bypass the tray handler.
            // Finish volatile control while the event loop and native broker
            // still exist, preserving only the operator's durable choices.
            #[cfg(any(target_os = "macos", target_os = "windows"))]
            if matches!(event, tauri::RunEvent::ExitRequested { .. }) {
                let _ = native_command(json!({"method":"prepare_exit"}));
            }
            if matches!(event, tauri::RunEvent::Exit) {
                diagnostics::record("supervisor.stop");
            }
            #[cfg(target_os = "windows")]
            if matches!(event, tauri::RunEvent::Exit) {
                windows::shutdown();
            }
            #[cfg(target_os = "linux")]
            if matches!(event, tauri::RunEvent::Exit) {
                linux::shutdown();
            }
            #[cfg(not(any(target_os = "windows", target_os = "linux")))]
            let _ = event;
        });
}
