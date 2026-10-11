//! Bound native operator work waiting for the serial coordinator.
use std::sync::atomic::{AtomicUsize, Ordering};

static OUTSTANDING: AtomicUsize = AtomicUsize::new(0);
const LIMIT: usize = 32;

pub struct Permit;
impl Permit {
    pub fn acquire() -> Result<Self, String> {
        OUTSTANDING
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |count| {
                (count < LIMIT).then_some(count + 1)
            })
            .map(|_| Self)
            .map_err(|_| "Native operator queue is busy".into())
    }
}
impl Drop for Permit {
    fn drop(&mut self) {
        OUTSTANDING.fetch_sub(1, Ordering::AcqRel);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounds_pending_work_and_returns_capacity() {
        let permits: Vec<_> = (0..LIMIT).map(|_| Permit::acquire().unwrap()).collect();
        assert!(Permit::acquire().is_err());
        drop(permits);
        assert!(Permit::acquire().is_ok());
    }
}
