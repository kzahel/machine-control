#[cfg(target_os = "macos")]
mod macos;

pub fn run() -> i32 {
    #[cfg(target_os = "macos")]
    return macos::run();
    #[cfg(not(target_os = "macos"))]
    {
        eprintln!("mc-sudo: native authentication is currently available on macOS only");
        1
    }
}

pub fn askpass() -> i32 {
    #[cfg(target_os = "macos")]
    return macos::askpass();
    #[cfg(not(target_os = "macos"))]
    1
}
