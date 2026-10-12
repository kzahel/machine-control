//! Bound native operator work waiting for the serial coordinator.
use std::sync::atomic::{AtomicUsize, Ordering};

static OUTSTANDING: AtomicUsize = AtomicUsize::new(0);
const LIMIT: usize = 32;

pub struct Permit;
impl Permit {
    pub fn acquire() -> Result<Self, String> {
        let mut count = OUTSTANDING.load(Ordering::Acquire);
        loop {
            if count >= LIMIT {
                return Err("Native operator queue is busy".into());
            }
            match OUTSTANDING.compare_exchange_weak(
                count,
                count + 1,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_) => return Ok(Self),
                Err(current) => count = current,
            }
        }
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

        // Hold every successful permit until all concurrent callers finish.
        let barrier = std::sync::Barrier::new(LIMIT * 2);
        let permits = std::thread::scope(|scope| {
            let workers: Vec<_> = (0..LIMIT * 2)
                .map(|_| {
                    let barrier = &barrier;
                    scope.spawn(move || {
                        barrier.wait();
                        Permit::acquire()
                    })
                })
                .collect();
            workers
                .into_iter()
                .filter_map(|worker| worker.join().unwrap().ok())
                .collect::<Vec<_>>()
        });
        assert_eq!(permits.len(), LIMIT);
        assert!(Permit::acquire().is_err());
        drop(permits);
        assert_eq!(OUTSTANDING.load(Ordering::Acquire), 0);
    }
}
