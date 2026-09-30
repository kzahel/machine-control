#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::{json, Value};
use std::ffi::{CStr, CString};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager,
};
use tauri_plugin_updater::UpdaterExt;

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
fn native_command(command: Value) -> Result<Value, String> {
    let input = CString::new(command.to_string()).map_err(|e| e.to_string())?;
    decode(unsafe { mc_desktop_command(input.as_ptr()) })
}
#[cfg(not(target_os = "macos"))]
fn native_command(_: Value) -> Result<Value, String> {
    Err("Desktop workstation control is currently available on macOS; this platform adapter is not installed".into())
}

#[tauri::command]
async fn operator_command(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
    command: Value,
) -> Result<Value, String> {
    if window.label() != "main" {
        return Err("Operator window required".into());
    }
    let (send, receive) = std::sync::mpsc::channel();
    app.run_on_main_thread(move || {
        let _ = send.send(native_command(command));
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
    let update = app
        .updater()
        .map_err(|e| e.to_string())?
        .check()
        .await
        .map_err(|e| e.to_string())?
        .ok_or("No update is available")?;
    if update.version != version {
        return Err("Update changed; check again before installing".into());
    }
    let bytes = update
        .download(|_, _| {}, || {})
        .await
        .map_err(|e| e.to_string())?;
    let (send, receive) = std::sync::mpsc::channel();
    let restart = app.clone();
    app.run_on_main_thread(move || {
        // Check immediately before replacement on the resident's serial
        // main thread. No grant or approval can race bundle replacement.
        let result = native_command(json!({"method":"prepare_update"}))
            .and_then(|_| update.install(bytes).map_err(|e| e.to_string()));
        if result.is_ok() {
            restart.restart();
        } else {
            let _ = native_command(json!({"method":"cancel_update"}));
            let _ = send.send(result.map(|_| ()));
        }
    })
    .map_err(|e| e.to_string())?;
    receive
        .recv_timeout(std::time::Duration::from_secs(60))
        .map_err(|e| e.to_string())?
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    #[cfg(target_os = "macos")]
    {
        let input = CString::new(serde_json::to_string(&args).unwrap()).unwrap();
        let mode = unsafe { mc_desktop_mode(input.as_ptr()) };
        if mode != 0 {
            std::process::exit(if mode > 0 { 0 } else { 1 });
        }
    }
    if !(args.is_empty() || args.first().is_some_and(|v| v == "serve") && args.len() == 2) {
        eprintln!("Usage: macui [serve SOCKET | request SOCKET [JSON] | credential SOCKET LEASE | screen-capture-preflight]");
        std::process::exit(2);
    }
    let socket = if args.first().is_some_and(|v| v == "serve") {
        args.get(1).cloned().unwrap_or_default()
    } else {
        String::new()
    };
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![operator_command, install_update])
        .setup(move |app| {
            #[cfg(target_os = "macos")]
            {
                let path = CString::new(socket.clone())?;
                decode(unsafe { mc_desktop_start(path.as_ptr()) })
                    .map_err(std::io::Error::other)?;
            }
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut previous_pending = String::new();
                loop {
                    std::thread::sleep(std::time::Duration::from_secs(1));
                    let (send, receive) = std::sync::mpsc::channel();
                    if handle
                        .run_on_main_thread(move || {
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
                    let active = !value["state"]["deployment"]["grant"].is_null();
                    let standing =
                        value["state"]["deployment"]["policy"]["grantMode"] == "standing";
                    let show = !pending.is_empty() && pending != previous_pending;
                    previous_pending = pending;
                    let ui = handle.clone();
                    let _ = handle.run_on_main_thread(move || {
                        if let Some(tray) = ui.tray_by_id("control") {
                            let _ = tray.set_tooltip(Some(if active {
                                "Machine Control — access active"
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
            let stop = MenuItem::with_id(app, "stop", "Stop access", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Machine Control", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &stop, &quit])?;
            TrayIconBuilder::with_id("control")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Machine Control")
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "stop" => {
                        let _ = native_command(json!({"method":"stop"}));
                    }
                    "quit" => {
                        let _ = native_command(json!({"method":"stop"}));
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("Machine Control could not start");
}
