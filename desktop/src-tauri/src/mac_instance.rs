//! Same-user Settings forwarding, keyed by resident endpoint, not package ID.
//! No grant, policy, configuration or provider mutations exist on this socket.
use std::{
    fs,
    io::{Read, Write},
    os::unix::{
        fs::FileTypeExt,
        fs::MetadataExt,
        fs::PermissionsExt,
        net::{UnixListener, UnixStream},
    },
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread::JoinHandle,
    time::Duration,
};

fn endpoint_identity(endpoint: &str) -> PathBuf {
    let input = PathBuf::from(endpoint);
    let mut anchor = if input.is_absolute() {
        input
    } else {
        std::env::current_dir()
            .expect("Current directory unavailable")
            .join(input)
    };
    let mut missing = Vec::new();
    loop {
        if let Ok(mut resolved) = fs::canonicalize(&anchor) {
            for component in missing.into_iter().rev() {
                resolved.push(component);
            }
            return resolved;
        }
        let Some(name) = anchor.file_name().map(|name| name.to_owned()) else {
            return anchor;
        };
        missing.push(name);
        anchor.pop();
    }
}

fn path(endpoint: &str) -> PathBuf {
    // Stable namespace only; this hash is not bearer authority.
    let mut hash = 0xcbf29ce484222325u64;
    for byte in endpoint_identity(endpoint).to_string_lossy().bytes() {
        hash = (hash ^ u64::from(byte)).wrapping_mul(0x100000001b3);
    }
    PathBuf::from(format!("/tmp/mc-settings-{}-{hash:016x}.sock", unsafe {
        libc::getuid()
    }))
}
fn same_user(stream: &UnixStream) -> bool {
    use std::os::fd::AsRawFd;
    let mut uid = 0;
    let mut gid = 0;
    unsafe {
        libc::getpeereid(stream.as_raw_fd(), &mut uid, &mut gid) == 0
            && uid == libc::getuid()
            && uid != 0
    }
}
fn exchange(stream: &mut UnixStream, open: bool) -> Result<(), String> {
    if !same_user(stream) {
        return Err("Settings operator identity refused".into());
    }
    stream
        .set_read_timeout(Some(Duration::from_secs(4)))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|e| e.to_string())?;
    stream
        .write_all(if open { b"settings\n" } else { b"ping\n" })
        .map_err(|e| e.to_string())?;
    let mut reply = [0u8; 3];
    stream.read_exact(&mut reply).map_err(|e| e.to_string())?;
    if reply == *b"ok\n" {
        Ok(())
    } else {
        Err("Settings recovery refused".into())
    }
}

pub enum Acquisition {
    Primary(Instance),
    Forwarded,
}
pub struct Instance {
    path: PathBuf,
    listener: Option<UnixListener>,
    stopped: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}
impl Instance {
    pub fn acquire(endpoint: &str, open: bool) -> Result<Acquisition, String> {
        let path = path(endpoint);
        if let Ok(mut stream) = UnixStream::connect(&path) {
            exchange(&mut stream, open)?;
            return Ok(Acquisition::Forwarded);
        }
        if let Ok(info) = fs::symlink_metadata(&path) {
            if !info.file_type().is_socket() || info.uid() != unsafe { libc::getuid() } {
                return Err("Settings endpoint is unsafe".into());
            }
            fs::remove_file(&path).map_err(|e| e.to_string())?;
        }
        let listener = UnixListener::bind(&path).map_err(|e| e.to_string())?;
        if let Err(error) = fs::set_permissions(&path, fs::Permissions::from_mode(0o600)) {
            let _ = fs::remove_file(&path);
            return Err(error.to_string());
        }
        Ok(Acquisition::Primary(Self {
            path,
            listener: Some(listener),
            stopped: Arc::new(AtomicBool::new(false)),
            thread: None,
        }))
    }
    pub fn start(mut self, handler: impl Fn() -> bool + Send + 'static) -> Self {
        let listener = self
            .listener
            .take()
            .expect("Settings listener already started");
        let stopped = self.stopped.clone();
        self.thread = Some(std::thread::spawn(move || {
            // One bounded reader; missing or malicious peers cannot accumulate
            // native threads or hold the application's main event loop.
            for stream in listener.incoming() {
                if stopped.load(Ordering::Acquire) {
                    break;
                }
                let Ok(mut stream) = stream else {
                    break;
                };
                if !same_user(&stream) {
                    continue;
                }
                let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
                let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
                let mut bytes = Vec::new();
                let mut byte = [0u8; 1];
                while bytes.len() < 16 {
                    if stream.read_exact(&mut byte).is_err() {
                        break;
                    }
                    bytes.push(byte[0]);
                    if byte[0] == b'\n' {
                        break;
                    }
                }
                let accepted = bytes == b"ping\n" || bytes == b"settings\n" && handler();
                let _ = stream.write_all(if accepted { b"ok\n" } else { b"no\n" });
            }
        }));
        self
    }
}
impl Drop for Instance {
    fn drop(&mut self) {
        self.stopped.store(true, Ordering::Release);
        if self.thread.is_some() {
            let _ = UnixStream::connect(&self.path);
        }
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
        let _ = fs::remove_file(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;
    #[test]
    fn same_endpoint_forwards_but_distinct_runtimes_stay_independent() {
        let endpoint = format!("/tmp/mc-instance-{}-one.sock", std::process::id());
        let resolved = fs::canonicalize("/tmp")
            .unwrap()
            .join(format!("mc-instance-{}-one.sock", std::process::id()));
        assert_eq!(path(&endpoint), path(resolved.to_str().unwrap()));
        let calls = Arc::new(AtomicUsize::new(0));
        let Acquisition::Primary(primary) = Instance::acquire(&endpoint, false).unwrap() else {
            panic!("primary")
        };
        let count = calls.clone();
        let primary = primary.start(move || {
            count.fetch_add(1, Ordering::SeqCst);
            true
        });
        assert!(matches!(
            Instance::acquire(&endpoint, true).unwrap(),
            Acquisition::Forwarded
        ));
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        assert!(matches!(
            Instance::acquire(&endpoint, false).unwrap(),
            Acquisition::Forwarded
        ));
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        let Acquisition::Primary(other) =
            Instance::acquire(&(endpoint.clone() + "other"), false).unwrap()
        else {
            panic!("independent")
        };
        let mut peer = UnixStream::connect(path(&endpoint)).unwrap();
        peer.write_all(b"approve\n").unwrap();
        let mut reply = [0; 3];
        peer.read_exact(&mut reply).unwrap();
        assert_eq!(&reply, b"no\n");
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        drop(other);
        drop(primary);
        assert!(!path(&endpoint).exists());
    }
    #[test]
    fn unsafe_existing_path_is_never_removed() {
        let endpoint = format!("/tmp/mc-instance-{}-unsafe.sock", std::process::id());
        let filename = path(&endpoint);
        fs::write(&filename, b"unchanged").unwrap();
        assert!(Instance::acquire(&endpoint, true).is_err());
        assert_eq!(fs::read(&filename).unwrap(), b"unchanged");
        fs::remove_file(filename).unwrap();
    }
}
