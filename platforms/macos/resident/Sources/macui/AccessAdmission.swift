import Foundation

/// Main-thread arbiter with the common admission v1 projection. Resource and
/// owner identities are supplied by the resident, never by request labels.
final class AccessAdmission {
    static let schema = "machine-control-admission/v1"
    var now: () -> Double = { ProcessInfo.processInfo.systemUptime }
    var sessionEnded: ((String, String, String) -> Void)?
    var changed: (() -> Void)?
    var queueLeaseSeconds = 60.0
    var offerSeconds = 15.0
    var activeHeartbeatSeconds = 5.0
    private var resources: [String: Resource] = [:]
    private var intents: [Intent] = []
    private var events: [[String: Any]] = []
    private(set) var revision = 0
    private var refreshing = false

    private final class Resource {
        var ready: Bool
        var generation = 0
        var holder: String?
        // Dictionary cannot retain nil values; infinity means until resumed.
        var pauses: [String: Double] = [:]
        init(ready: Bool) { self.ready = ready }
    }
    private final class Intent {
        let id = UUID().uuidString.lowercased()
        let owner, requestID, reason: String
        let resources: [String]
        let duration, waitSeconds, deadline, requestedNotice: Double
        let authority: () -> String?
        var heartbeat, notice: Double
        var noticeDeadline = 0.0, offerDeadline = 0.0, activeDeadline = 0.0
        var state = "waiting_for_resource"
        var terminal, session, authorizationBlock: String?
        var offerGeneration = 0
        var generations: [String: Int] = [:]
        init(owner: String, requestID: String, resources: [String], wait: Double,
             duration: Double, reason: String, authority: @escaping () -> String?,
             notice: Double, now: Double, lease: Double) {
            self.owner = owner; self.requestID = requestID; self.resources = resources
            self.waitSeconds = wait; self.duration = duration; self.reason = reason
            self.authority = authority; self.notice = notice; self.requestedNotice = notice
            deadline = now + wait; heartbeat = now + lease
        }
    }

    func register(_ name: String, ready: Bool = true) {
        precondition(!name.isEmpty && name.count <= 128)
        if resources[name] != nil { return }
        precondition(resources.count < 64)
        resources[name] = Resource(ready: ready)
    }
    func setReady(_ name: String, _ ready: Bool) {
        guard let resource = resources[name], resource.ready != ready else { return }
        resource.ready = ready; change("resource.readiness"); refresh()
    }
    func pause(_ name: String, reason: String, seconds: Double? = nil) throws {
        guard let resource = resources[name], !reason.isEmpty, reason.count <= 80,
              seconds == nil || (seconds!.isFinite && (0 < seconds! && seconds! <= 28800)) else {
            throw MacUIError.usage("invalid_pause")
        }
        resource.pauses[reason] = seconds.map { now() + $0 } ?? .infinity
        change("resource.paused"); refresh(); changed?()
    }
    func resume(_ name: String, reason: String) {
        if resources[name]?.pauses.removeValue(forKey: reason) != nil { change("resource.resumed") }
        refresh(); changed?()
    }
    func blocks(_ name: String) -> [String] {
        refresh()
        return resources[name].map(resourceBlocks) ?? ["resource_unavailable"]
    }

    func submit(owner: String, requestID: String, resources names: [String],
                wait: Double, duration: Double, reason: String,
                authority: @escaping () -> String?, notice: Double = 0) throws -> [String: Any] {
        refresh()
        guard !owner.isEmpty, !requestID.isEmpty, requestID.count <= 80,
              (1...8).contains(names.count), Set(names).count == names.count,
              names.allSatisfy({ resources[$0] != nil }), wait.isFinite, (1...14400).contains(wait),
              duration.isFinite, (1...900).contains(duration), notice.isFinite, (0...60).contains(notice),
              !reason.isEmpty, reason.count <= 240 else { throw MacUIError.usage("invalid_admission_request") }
        let normalized = names.sorted()
        if let existing = intents.first(where: { $0.owner == owner && $0.requestID == requestID }) {
            guard existing.resources == normalized, existing.duration == duration,
                  existing.waitSeconds == wait, existing.reason == reason, existing.requestedNotice == notice else {
                throw MacUIError.usage("admission_idempotency_conflict")
            }
            return view(existing)
        }
        guard intents.filter({ $0.terminal == nil && $0.owner == owner }).count < 4,
              intents.filter({ $0.terminal == nil }).count < 256 else { throw MacUIError.action("admission_queue_full") }
        let intent = Intent(owner: owner, requestID: requestID, resources: normalized, wait: wait,
            duration: duration, reason: reason, authority: authority, notice: notice, now: now(), lease: queueLeaseSeconds)
        intents.append(intent); change("intent.submitted", intent); refresh(); changed?()
        return view(intent)
    }
    func inspect(owner: String, id: String, heartbeat: Bool = false) throws -> [String: Any] {
        refresh()
        let intent = try owned(owner, id)
        if heartbeat, intent.terminal == nil { intent.heartbeat = now() + (intent.session == nil ? queueLeaseSeconds : activeHeartbeatSeconds) }
        return view(intent)
    }
    func accept(owner: String, id: String, generation: Int) throws -> [String: Any] {
        refresh()
        let intent = try owned(owner, id)
        guard intent.terminal == nil, intent.state == "offered", intent.offerGeneration == generation else {
            throw MacUIError.action("stale_activation_offer")
        }
        guard intent.resources.allSatisfy({ resourceBlocks(resources[$0]!).isEmpty && resources[$0]!.holder == nil }) else {
            throw MacUIError.action("admission_changed")
        }
        intent.session = UUID().uuidString.lowercased(); intent.state = "active"
        intent.activeDeadline = now() + intent.duration; intent.heartbeat = now() + activeHeartbeatSeconds
        intent.generations.removeAll()
        for name in intent.resources {
            let resource = resources[name]!
            resource.holder = intent.id; resource.generation += 1; intent.generations[name] = resource.generation
        }
        change("session.activated", intent); changed?()
        return view(intent)
    }
    func authorize(owner: String, id: String, session: String, generations: [String: Int]) -> String? {
        refresh()
        guard let intent = intents.first(where: { $0.id == id && $0.owner == owner }),
              intent.terminal == nil, intent.session == session, intent.state == "active" else { return "stale_control_session" }
        return generations == intent.generations ? nil : "stale_generation"
    }
    func cancel(owner: String, id: String) throws {
        refresh(); let intent = try owned(owner, id)
        if intent.terminal == nil { finish(intent, "cancelled") }
        refresh(); changed?()
    }
    func disconnect(_ owner: String) {
        for intent in intents.filter({ $0.owner == owner && $0.terminal == nil }) { finish(intent, "owner_disconnected") }
        refresh(); changed?()
    }
    func stop(_ reason: String) {
        for intent in intents.filter({ $0.terminal == nil }) { finish(intent, reason) }
        changed?()
    }
    func reconfigureNotice(_ seconds: Double) {
        precondition(seconds.isFinite && (0...60).contains(seconds))
        for intent in intents where intent.terminal == nil && intent.session == nil {
            intent.notice = seconds; intent.state = "waiting_for_resource"; intent.offerGeneration = 0
            change("intent.notice_changed", intent)
        }
        refresh(); changed?()
    }

    /// Operator-only. Activity and faults still block admission.
    func startNow(_ id: String) throws {
        refresh()
        guard let intent = intents.first(where: { $0.id == id && $0.terminal == nil && $0.session == nil }) else {
            throw MacUIError.action("stale_activation_notice")
        }
        intent.notice = 0; intent.state = "waiting_for_resource"; refresh(); changed?()
    }

    func refresh() {
        guard !refreshing else { return }
        refreshing = true; defer { refreshing = false }
        let time = now()
        for resource in resources.values {
            for reason in resource.pauses.keys.filter({ time >= resource.pauses[$0]! }) {
                resource.pauses.removeValue(forKey: reason); change("resource.pause_expired")
            }
        }
        for intent in intents.filter({ $0.terminal == nil }) {
            let denied = intent.authority(); intent.authorizationBlock = denied
            if intent.terminal != nil { continue }
            if let denied, denied != "approval_required" || intent.session != nil { finish(intent, denied); continue }
            if time >= intent.heartbeat {
                finish(intent, intent.session == nil ? "queue_lease_expired" : "owner_disconnected"); continue
            }
            if intent.session != nil {
                if time >= intent.activeDeadline { finish(intent, "duration_expired"); continue }
                if intent.resources.contains(where: { !resourceBlocks(resources[$0]!).isEmpty }) {
                    release(intent, "paused"); intent.state = "paused"; intent.heartbeat = time + queueLeaseSeconds
                    intents.removeAll { $0 === intent }; intents.append(intent)
                }
            } else if time >= intent.deadline { finish(intent, "wait_deadline_exceeded") }
            else if intent.state == "offered", time >= intent.offerDeadline { finish(intent, "activation_offer_expired") }
        }
        var reserved = Set(resources.filter({ $0.value.holder != nil }).map(\.key))
        for intent in intents.filter({ $0.terminal == nil && $0.session == nil }) {
            if intent.authorizationBlock != nil {
                if intent.state != "waiting_for_approval" {
                    intent.state = "waiting_for_approval"; intent.offerGeneration = 0; change("intent.waiting", intent)
                }
                continue
            }
            let blocks = intent.resources.flatMap { resourceBlocks(resources[$0]!) }
            if !blocks.isEmpty || intent.resources.contains(where: reserved.contains) {
                let state = blocks.isEmpty ? "waiting_for_resource" : "paused"
                if intent.state != state { intent.state = state; intent.offerGeneration = 0; change("intent.waiting", intent) }
                continue
            }
            reserved.formUnion(intent.resources)
            if !["announcing", "offered"].contains(intent.state) {
                intent.noticeDeadline = time + intent.notice
                intent.state = intent.notice > 0 ? "announcing" : "offered"
                intent.offerDeadline = time + offerSeconds
                intent.offerGeneration = change("intent.eligible", intent)
            }
            if intent.state == "announcing", time >= intent.noticeDeadline {
                intent.state = "offered"; intent.offerDeadline = time + offerSeconds
                intent.offerGeneration = change("intent.offered", intent)
            }
        }
        let terminal = intents.filter { $0.terminal != nil }
        for old in terminal.prefix(max(0, terminal.count - 256)) { intents.removeAll { $0 === old } }
    }
    var reserved: Bool {
        refresh()
        return intents.contains { $0.terminal == nil && ["active", "offered", "announcing"].contains($0.state) }
    }

    var status: [String: Any] {
        refresh()
        return ["schema": Self.schema, "revision": revision, "ownerBinding": "admitted_channel",
            "resources": resources.keys.sorted().map { name -> [String: Any] in
                let resource = resources[name]!
                return ["resource": name, "generation": resource.generation,
                    "blockingReasons": resourceBlocks(resource), "held": resource.holder != nil]
            },
            "waiting": intents.filter { $0.terminal == nil && $0.session == nil }.count,
            "active": intents.filter { $0.session != nil }.count,
            "events": events, "requests": intents.filter { $0.terminal == nil }.map(view)]
    }
    private func owned(_ owner: String, _ id: String) throws -> Intent {
        guard let intent = intents.first(where: { $0.owner == owner && $0.id == id }) else {
            throw MacUIError.action("admission_owner_mismatch")
        }
        return intent
    }
    private func resourceBlocks(_ resource: Resource) -> [String] {
        (Array(resource.pauses.keys) + (resource.ready ? [] : ["resource_unavailable"])).sorted()
    }
    private func release(_ intent: Intent, _ reason: String) {
        guard let session = intent.session else { return }
        for name in intent.resources {
            let resource = resources[name]!
            if resource.holder == intent.id { resource.holder = nil; resource.generation += 1 }
        }
        intent.session = nil; intent.generations.removeAll(); intent.offerGeneration = 0
        change("session." + reason, intent); sessionEnded?(intent.owner, session, reason)
    }
    private func finish(_ intent: Intent, _ reason: String) {
        release(intent, reason); intent.terminal = reason; intent.state = "ended"; change("intent." + reason, intent)
    }
    @discardableResult private func change(_ kind: String, _ intent: Intent? = nil) -> Int {
        revision += 1; events.append(["revision": revision, "kind": kind, "intentId": intent?.id as Any? ?? NSNull()])
        if events.count > 128 { events.removeFirst(events.count - 128) }
        return revision
    }
    private func view(_ intent: Intent) -> [String: Any] {
        ["schema": Self.schema, "revision": revision, "intentId": intent.id, "state": intent.state,
            "terminalReason": intent.terminal as Any? ?? NSNull(), "offerGeneration": intent.offerGeneration,
            "sessionId": intent.session as Any? ?? NSNull(), "resourceGenerations": intent.generations,
            "blockingReasons": Set(intent.resources.flatMap { resourceBlocks(resources[$0]!) } +
                (intent.authorizationBlock.map { [$0] } ?? [])).sorted(),
            "waitRemainingSeconds": max(0, intent.deadline - now()), "leaseRemainingSeconds": max(0, intent.heartbeat - now()),
            "offerRemainingSeconds": intent.state == "offered" ? max(0, intent.offerDeadline - now()) as Any : NSNull(),
            "noticeRemainingSeconds": intent.state == "announcing" ? max(0, intent.noticeDeadline - now()) as Any : NSNull(),
            "activeRemainingSeconds": intent.session == nil ? NSNull() : max(0, intent.activeDeadline - now()) as Any,
            "reason": intent.reason, "maximumDurationSeconds": intent.duration]
    }
}
