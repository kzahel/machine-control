//! Bounded verification of an owned companion before the resident handshake.
use std::{
    process::Child,
    time::{Duration, Instant},
};

pub const TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Debug, PartialEq)]
pub enum Failure {
    Timeout,
    Cancelled,
    Wait,
}
#[cfg(target_os = "windows")]
impl Failure {
    pub fn code(&self) -> &'static str {
        match self {
            Self::Timeout => "companion.resolve_timeout",
            Self::Cancelled => "companion.resolve_cancelled",
            Self::Wait => "companion.resolve_failed",
        }
    }
}

pub fn wait(
    child: &mut Child,
    timeout: Duration,
    cancelled: impl Fn() -> bool,
) -> Result<(), Failure> {
    let deadline = Instant::now() + timeout;
    loop {
        let failure = match child.try_wait() {
            Ok(Some(_)) => return Ok(()),
            Ok(None) if cancelled() => Some(Failure::Cancelled),
            Ok(None) if Instant::now() >= deadline => Some(Failure::Timeout),
            Ok(None) => None,
            Err(_) => Some(Failure::Wait),
        };
        if let Some(failure) = failure {
            // Kill and reap this exact owned process; a timed-out verification
            // must never select a path or survive a cancelled operator startup.
            let _ = child.kill();
            let _ = child.wait();
            return Err(failure);
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::{Command, Stdio};

    #[test]
    fn owned_child_fixture() {
        if let Ok(delay) = std::env::var("MC_RESOLUTION_FIXTURE_MS") {
            std::thread::sleep(Duration::from_millis(delay.parse().unwrap()));
            println!("RESOLVED");
        }
    }
    fn child(milliseconds: u64) -> Child {
        Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                &format!(
                    "{}::owned_child_fixture",
                    module_path!().split_once("::").unwrap().1
                ),
                "--nocapture",
            ])
            .env("MC_RESOLUTION_FIXTURE_MS", milliseconds.to_string())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .unwrap()
    }
    #[test]
    fn verification_can_outlast_three_seconds_without_starting_authority() {
        let mut child = child(4000);
        wait(&mut child, TIMEOUT, || false).unwrap();
        let output = child.wait_with_output().unwrap();
        assert!(output.status.success());
        assert!(String::from_utf8(output.stdout)
            .unwrap()
            .contains("RESOLVED"));
    }
    #[test]
    fn timeout_and_cancellation_reap_the_owned_process() {
        for cancelled in [false, true] {
            let mut child = child(10_000);
            let start = Instant::now();
            assert_eq!(
                wait(&mut child, Duration::from_millis(50), || cancelled),
                Err(if cancelled {
                    Failure::Cancelled
                } else {
                    Failure::Timeout
                })
            );
            assert!(start.elapsed() < Duration::from_secs(2));
            assert!(child.try_wait().unwrap().is_some());
        }
    }
}
