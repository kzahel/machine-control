import Foundation

/// Main-queue projection of one blocking dependency. A timeout expires the
/// projection, not the worker slot: a stuck OS call cannot create more workers.
/// Values are observations only; dispatch must independently check authority.
final class BackgroundObservation<Value> {
    private let queue: DispatchQueue
    private let read: () -> Value
    private let unknown: () -> Value
    private let interval: TimeInterval
    private let timeout: TimeInterval
    private let lifetime: TimeInterval
    private var generation = UUID()
    private var inFlight = false
    private var stopped = false
    private var nextRead: TimeInterval = 0
    private var observedAt: TimeInterval?
    private var stored: Value?
    private var deadline: DispatchWorkItem?
    var changed: (() -> Void)?
    var now: () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }

    init(label: String, interval: TimeInterval = 1, timeout: TimeInterval = 2,
         lifetime: TimeInterval = 3, unknown: @escaping () -> Value,
         read: @escaping () -> Value) {
        queue = DispatchQueue(label:label, qos:.utility)
        self.interval = interval; self.timeout = timeout; self.lifetime = lifetime
        self.unknown = unknown; self.read = read
    }

    var value: Value {
        guard let observedAt, now() - observedAt <= lifetime, let stored else { return unknown() }
        return stored
    }
    var metadata: [String:Any] {
        ["refreshing":inFlight, "available":observedAt.map { now() - $0 <= lifetime } ?? false,
         "ageMs":observedAt.map { max(0, Int((now() - $0) * 1000)) as Any } ?? NSNull()]
    }
    func refresh() {
        guard !stopped, !inFlight, now() >= nextRead else { return }
        inFlight = true
        let token = generation
        let expiry = DispatchWorkItem { [weak self] in
            guard let self, self.generation == token else { return }
            self.generation = UUID(); self.stored = nil; self.observedAt = nil
            self.changed?()
        }
        deadline = expiry
        DispatchQueue.main.asyncAfter(deadline:.now() + timeout, execute:expiry)
        queue.async { [weak self, read] in
            let result = autoreleasepool { read() }
            DispatchQueue.main.async {
                guard let self else { return }
                self.deadline?.cancel(); self.deadline = nil
                self.inFlight = false; self.nextRead = self.now() + self.interval
                guard !self.stopped, self.generation == token else { return }
                self.stored = result; self.observedAt = self.now(); self.changed?()
            }
        }
    }
    func invalidate() {
        generation = UUID(); stored = nil; observedAt = nil; nextRead = 0
        deadline?.cancel(); deadline = nil
    }
    /// A newer direct observation supersedes both cached data and reads that
    /// started before it. Retain the occupied worker slot until that read exits.
    func replace(with value: Value) {
        guard !stopped else { return }
        generation = UUID(); stored = value; observedAt = now(); nextRead = now() + interval
        deadline?.cancel(); deadline = nil
        changed?()
    }
    func stop() { stopped = true; invalidate() }
    deinit { deadline?.cancel() }
}
