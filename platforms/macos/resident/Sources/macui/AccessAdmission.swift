import Foundation

/// Native facts and authenticated owner handles over the shared v2 policy.
/// This adapter contains no grant, queue, countdown, cooldown or expiry engine.
final class AccessAdmission {
    static let schema = "machine-control-admission/v2"
    // Used only for native helper ceilings, never as the shared policy clock.
    var now: () -> Double = { ProcessInfo.processInfo.systemUptime }
    var sessionEnded: ((String, String, String) -> Void)?
    var changed: (() -> Void)?
    private var invoke: (([String: Any]) throws -> [String: Any])?
    private var owners = Set<String>()
    private struct Requirement {
        let owner: String
        let surfaces: [String]
        let check: () -> String?
    }
    private var requirements: [String: Requirement] = [:]
    private var sessions: [String: String] = [:]
    private var readiness: [String: (Bool, Bool)] = [:]
    private var pauses: [String: [String: Double?]] = [:]
    private var inputReady = false
    private var refreshing = false
    private var desktopFingerprint: Data?
    private(set) var revision = 0
    private(set) var availabilityRevision = 0
    // Operator status presentation reads the last full projection and never
    // waits for the policy process. The pipe is FIFO, so a background status
    // reply is stale only if a full projection requested later replaced the
    // cache first; `fullReplies` counts those synchronous replacements.
    private var request: (([String: Any], @escaping (Result<[String: Any], Error>) -> Void) -> Void)?
    private(set) var cachedStatus: [String: Any]?
    private var fullReplies = 0
    private var binding = 0
    private(set) var polling = false
    private var presenting = 0

    func bind(_ call: @escaping ([String: Any]) throws -> [String: Any]) throws {
        guard invoke == nil else { throw SharedPolicyError(code: "control_policy_already_bound") }
        invoke = call
        _ = try send("input-ready", ["ready": inputReady])
        for (surface, value) in readiness {
            _ = try send("ready", ["surface": surface, "ready": value.0, "noticeVisible": value.1])
        }
        for (surface, reasons) in pauses {
            for (reason, seconds) in reasons {
                _ = try send("pause", ["surface": surface, "reason": reason,
                    "milliseconds": seconds.map { Int($0 * 1000) } as Any? ?? NSNull()])
            }
        }
    }
    /// Asynchronous route for background refreshes; completions run on main.
    func bindBackground(_ request: @escaping ([String: Any], @escaping (Result<[String: Any], Error>) -> Void) -> Void) {
        self.request = request; binding += 1
    }
    func invalidate() {
        invoke = nil; request = nil; cachedStatus = nil; polling = false; binding += 1
        let ended = sessions; sessions.removeAll()
        for (id, session) in ended {
            if let requirement = requirements[id], requirement.surfaces.contains("desktop") {
                sessionEnded?(requirement.owner, session, "control_policy_unavailable")
            }
        }
        owners.removeAll(); requirements.removeAll()
        revision += 1; availabilityRevision += 1; desktopFingerprint = nil
        changed?()
    }
    private func send(_ method: String, _ fields: [String: Any] = [:]) throws -> [String: Any] {
        if presenting > 0, invoke != nil, method == "query" || method == "state", var cached = cachedStatus {
            if method == "query" {
                // Status omits query's activeDesktop; derive it from requests.
                cached["activeDesktop"] = (cached["requests"] as? [[String: Any]] ?? []).contains {
                    $0["sessionId"] is String && ($0["surfaces"] as? [String] ?? []).contains("desktop")
                }
            }
            return cached
        }
        guard let invoke else { throw SharedPolicyError(code: "control_policy_unavailable") }
        var frame = fields; frame["method"] = "access." + method
        let result: [String: Any]
        do { result = try invoke(frame) }
        catch {
            if let error = error as? SharedPolicyError,
               error.code.hasPrefix("ipc_") || ["control_policy_unavailable", "resident_stopping"].contains(error.code) {
                invalidate()
            }
            throw error
        }
        observe(result)
        return result
    }
    private func endNative(_ id: String, reason: String) {
        guard let session = sessions.removeValue(forKey: id), let requirement = requirements[id],
              requirement.surfaces.contains("desktop") else { return }
        availabilityRevision += 1
        sessionEnded?(requirement.owner, session, reason)
        changed?()
    }
    private func observe(_ result: [String: Any]) {
        if let value = result["revision"] as? Int { revision = value }
        if result["experienceVersion"] != nil { cachedStatus = result; fullReplies += 1 }
        func request(_ value: [String: Any]) {
            guard let id = value["intentId"] as? String else { return }
            let session = value["sessionId"] as? String
            if let old = sessions[id], old != session {
                endNative(id, reason: value["terminalReason"] as? String ?? "control_generation_changed")
            }
            if let session, sessions[id] == nil {
                sessions[id] = session
                if requirements[id]?.surfaces.contains("desktop") == true {
                    availabilityRevision += 1; changed?()
                }
            }
        }
        if let requests = result["requests"] as? [[String: Any]] {
            let live = Set(requests.compactMap { $0["intentId"] as? String })
            for id in Array(sessions.keys) where !live.contains(id) {
                // Status omits terminal intents. Its synchronous reply can
                // overtake the main-queue ending event; retain the actual
                // shared reason before releasing the native protected owner.
                var reason = "control_policy_unavailable"
                if let requirement = requirements[id], let invoke,
                   let ended = try? invoke(["method":"access.inspect", "owner":requirement.owner,
                                            "intentId":id, "heartbeat":false]),
                   let terminal = ended["terminalReason"] as? String {
                    reason = terminal
                }
                endNative(id, reason:reason)
            }
            for item in requests { request(item) }
        } else { request(result) }
        if let surfaces = result["surfaces"] as? [String: [String: Any]],
           let desktop = surfaces["desktop"] {
            // Browser choices/availability and renewal time must not fence
            // unrelated native Desktop references or a protected Desktop task.
            let facts: [String: Any] = [
                "mode": desktop["mode"] ?? "off", "expired": desktop["expired"] ?? false,
                "ready": desktop["ready"] ?? false,
                "pauses": (desktop["pauses"] as? [[String: Any]] ?? []).map {
                    ["reason": $0["reason"] ?? "", "scope": $0["scope"] ?? ""]
                }
            ]
            if let bytes = try? JSONSerialization.data(withJSONObject: facts, options: .sortedKeys),
               bytes != desktopFingerprint {
                desktopFingerprint = bytes; availabilityRevision += 1; changed?()
            }
        }
    }
    func receive(_ event: [String: Any]) {
        guard event["type"] as? String == "access.event",
              let id = event["intentId"] as? String else { changed?(); return }
        if ["yielded", "ended"].contains(event["event"] as? String ?? "") {
            if let session = event["sessionId"] as? String, sessions[id] != session { return }
            endNative(id, reason: event["reason"] as? String ?? "access_ended")
        }
        changed?()
    }
    func register(_ name: String, ready: Bool = true) { setReady(name, ready) }
    func setReady(_ surface: String, _ ready: Bool, noticeVisible: Bool? = nil) {
        let value = (ready, noticeVisible ?? ready)
        if let old = readiness[surface], old == value { return }
        readiness[surface] = value
        if invoke != nil { _ = try? send("ready", ["surface": surface, "ready": ready, "noticeVisible": value.1]) }
    }
    func setInputReady(_ ready: Bool) {
        guard ready != inputReady else { return }; inputReady = ready
        if invoke != nil { _ = try? send("input-ready", ["ready": ready]) }
    }
    func input(_ surface: String, kind: String) { _ = try? send("input", ["surface": surface, "kind": kind]) }
    func configure(_ surface: String, mode: String, seconds: Int?, profiles: [String] = []) throws {
        _ = try send("configure", ["surface": surface, "configuration": [
            "mode": mode, "durationMs": seconds.map { Int($0 * 1000) } as Any? ?? NSNull(), "profileIds": profiles]])
        if surface == "desktop" { availabilityRevision += 1 }
        changed?()
    }
    func pause(_ surface: String, reason: String, seconds: Double? = nil) throws {
        guard seconds == nil || (seconds!.isFinite && seconds! > 0 && seconds! <= 28800) else {
            throw MacUIError.usage("invalid_pause")
        }
        // Optional dictionary values need updateValue to retain manual pauses.
        pauses[surface, default: [:]].updateValue(seconds, forKey: reason)
        if invoke != nil {
            _ = try send("pause", ["surface": surface, "reason": reason,
                "milliseconds": seconds.map { Int($0 * 1000) } as Any? ?? NSNull()])
        }
        changed?()
    }
    func resume(_ surface: String, reason: String) {
        pauses[surface]?.removeValue(forKey: reason)
        _ = try? send("resume", ["surface": surface, "reason": reason]); changed?()
    }
    func blocks(_ surface: String) -> [String] {
        refresh()
        guard let value = (try? send("query"))?["surfaces"] as? [String: [String: Any]],
              let state = value[surface] else { return ["control_policy_unavailable"] }
        return ((state["pauses"] as? [[String: Any]] ?? []).compactMap { $0["reason"] as? String } +
            (state["ready"] as? Bool == true ? [] : ["resource_unavailable"])).sorted()
    }
    func surface(_ surface: String) -> [String: Any] {
        ((try? send("query"))?["surfaces"] as? [String: [String: Any]])?[surface] ?? ["mode": "off", "expired": true]
    }
    func enabled(_ surface: String) -> Bool {
        let value = self.surface(surface)
        return value["mode"] as? String != "off" && value["expired"] as? Bool != true
    }
    func submit(owner: String, requestID: String, resources surfaces: [String],
                wait: Double, duration: Double, reason: String,
                authority: @escaping () -> String?, notice: Double = 0,
                profileIDs: [String] = [], operations: [String]? = nil) throws -> [String: Any] {
        guard wait.isFinite, duration.isFinite, (1...14400).contains(wait),
              (1...900).contains(duration), !reason.isEmpty, reason.count <= 240 else {
            throw MacUIError.usage("invalid_admission_request")
        }
        refresh()
        if !owners.contains(owner) { _ = try send("open", ["owner": owner]); owners.insert(owner) }
        var request: [String: Any] = ["requestId": requestID, "surfaces": surfaces, "profileIds": profileIDs,
            "waitMs": Int(wait * 1000), "durationMs": Int(duration * 1000), "reason": reason]
        if let operations { request["operations"] = operations }
        let value = try send("submit", ["owner": owner, "request": request])
        guard let id = value["intentId"] as? String else { throw SharedPolicyError(code: "ipc_invalid_projection") }
        requirements[id] = Requirement(owner: owner, surfaces: surfaces, check: authority)
        return value
    }
    func inspect(owner: String, id: String, heartbeat: Bool = false) throws -> [String: Any] {
        refresh(); return try send("inspect", ["owner": owner, "intentId": id, "heartbeat": heartbeat])
    }
    func accept(owner: String, id: String, generation: Int) throws -> [String: Any] {
        refresh(); return try send("accept", ["owner": owner, "intentId": id, "offerGeneration": generation])
    }
    func authorize(owner: String, id: String, session: String, generations: [String: Int],
                   operation: String? = nil) -> String? {
        refresh()
        guard owners.contains(owner) else { return "stale_control_session" }
        var frame: [String: Any] = ["owner": owner, "fence": [
            "intentId": id, "sessionId": session, "resourceGenerations": generations]]
        if let operation { frame["operation"] = operation }
        do { return try send("authorize", frame)["refusal"] as? String }
        catch { return (error as? SharedPolicyError)?.code ?? "control_policy_unavailable" }
    }
    func renew(owner: String, id: String, session: String, generations: [String: Int],
               seconds: Double, prepare: (Double) throws -> Void = { _ in }) throws -> [String: Any] {
        guard seconds.isFinite, seconds > 0, seconds <= 900 else {
            throw MacUIError.usage("invalid_renewal_duration")
        }
        if let refusal = authorize(owner: owner, id: id, session: session, generations: generations) {
            throw MacUIError.action(refusal)
        }
        let before = try inspect(owner: owner, id: id)
        let surfaces = requirements[id]?.surfaces ?? []
        let ceilings = surfaces.compactMap { (surface($0)["consentRemainingSeconds"] as? NSNumber)?.doubleValue }
        let seconds = min(seconds, ceilings.min() ?? seconds)
        guard seconds > 0 else { throw MacUIError.action("access_ended") }
        let active = (before["activeRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0
        do {
            if seconds > active { try prepare(now() + seconds) }
            if let refusal = authorize(owner: owner, id: id, session: session, generations: generations) {
                throw MacUIError.action(refusal)
            }
            return try send("renew", ["owner": owner, "durationMs": Int(seconds * 1000),
                "fence": ["intentId": id, "sessionId": session, "resourceGenerations": generations]])
        } catch { try? cancel(owner: owner, id: id); throw error }
    }
    func cancel(owner: String, id: String) throws {
        _ = try send("cancel", ["owner": owner, "intentId": id]); changed?()
    }
    func disconnect(_ owner: String) {
        _ = try? send("close", ["owner": owner])
        for (id, requirement) in requirements where requirement.owner == owner {
            endNative(id, reason: "owner_disconnected"); requirements.removeValue(forKey: id)
        }
        owners.remove(owner); changed?()
    }
    func stop(_ reason: String) { _ = try? send("stop"); changed?() }
    func reconfigureNotice(_ seconds: Double) {
        guard seconds.isFinite, (0...60).contains(seconds) else { return }
        _ = try? send("notice", ["milliseconds": Int(seconds * 1000)]); changed?()
    }
    func startNow(_ id: String) throws { _ = try send("start", ["intentId": id]); changed?() }
    func approve(_ id: String, seconds: Int = 0) throws { _ = try send("approve", ["intentId": id, "milliseconds": seconds * 1000]); changed?() }
    @discardableResult func preferences(_ value: [String: Any]) throws -> [String: Any] {
        let result = try send("preferences", ["preferences": value]); changed?()
        guard let normalized = result["preferences"] as? [String: Any] else { throw MacUIError.action("invalid_access_preferences_reply") }
        return normalized
    }
    func hold(_ id: String) throws { _ = try send("hold", ["intentId": id]); changed?() }
    func postpone(_ id: String, seconds: Int) throws { _ = try send("postpone", ["intentId": id, "milliseconds": seconds * 1000]); changed?() }
    func deny(_ id: String) throws { _ = try send("deny", ["intentId": id]); changed?() }
    func deferRequest(_ id: String, seconds: Int?) throws {
        _ = try send("defer", ["intentId": id, "milliseconds": seconds.map { Int($0 * 1000) } as Any? ?? NSNull()]); changed?()
    }
    /// Run operator status presentation over the cached projection, then
    /// refresh it in the background. The first call populates it directly.
    func presentation<T>(_ body: () throws -> T) rethrows -> T {
        presenting += 1
        defer { presenting -= 1; poll() }
        return try body()
    }
    /// Refresh the presentation cache in the background. Owner-ended
    /// cancellation stays with refresh(), which the resident tick runs.
    func poll() {
        guard !polling, invoke != nil, let request else { return }
        polling = true
        let issued = fullReplies, bound = binding
        // Only the presentation cache changes here. Synchronous replies keep
        // owning session tracking and change notification.
        request(["method": "access.state"]) { [weak self] result in
            // A reply from before invalidation or rebinding is never cached.
            guard let self, self.binding == bound else { return }
            self.polling = false
            if case .success(let value) = result, self.fullReplies == issued, self.invoke != nil,
               value["experienceVersion"] != nil {
                self.cachedStatus = value
            }
        }
    }
    func refresh() {
        guard !refreshing, presenting == 0, invoke != nil else { return }
        refreshing = true; defer { refreshing = false }
        for (id, requirement) in Array(requirements) {
            if requirement.check() != nil { _ = try? send("cancel", ["owner": requirement.owner, "intentId": id]) }
        }
        _ = try? send("query")
    }
    var reserved: Bool {
        ((try? send("query"))?["requests"] as? [[String: Any]] ?? []).contains {
            ["active", "offered", "announcing"].contains($0["state"] as? String ?? "")
        }
    }
    var activeDesktop: Bool { (try? send("query"))?["activeDesktop"] as? Bool == true }
    var status: [String: Any] {
        refresh()
        return (try? send("state")) ?? ["schema": Self.schema, "available": false,
            "errorCode": "control_policy_unavailable", "revision": revision, "requests": [[String: Any]](),
            "surfaces": ["desktop": ["mode": "off", "ready": false], "browser": ["mode": "off", "ready": false]]]
    }
}
