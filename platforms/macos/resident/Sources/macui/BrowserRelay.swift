import Darwin
import Foundation
import Security
import CryptoKit

/// Whether a socket peer is signed with this resident's own designated
/// requirement. With ad-hoc development signing that requirement is only an
/// identifier; release builds bind it to the publisher.
func peerHasOwnCodeIdentity(_ descriptor: Int32) -> Bool {
    var token = audit_token_t()
    var length = socklen_t(MemoryLayout<audit_token_t>.size)
    guard getsockopt(descriptor, SOL_LOCAL, LOCAL_PEERTOKEN, &token, &length) == 0 else {
        return false
    }
    let tokenData = withUnsafeBytes(of: &token) { Data($0) }
    var guest: SecCode?
    guard SecCodeCopyGuestWithAttributes(nil, [kSecGuestAttributeAudit: tokenData] as CFDictionary,
                                         [], &guest) == errSecSuccess, let guest,
          let requirement = ownDesignatedRequirement() else { return false }
    return SecCodeCheckValidity(guest, [], requirement) == errSecSuccess
}

private func ownDesignatedRequirement() -> SecRequirement? {
    var own: SecCode?
    var ownStatic: SecStaticCode?
    var requirement: SecRequirement?
    guard SecCodeCopySelf([], &own) == errSecSuccess, let own,
          SecCodeCopyStaticCode(own, [], &ownStatic) == errSecSuccess, let ownStatic,
          SecCodeCopyDesignatedRequirement(ownStatic, [], &requirement) == errSecSuccess else {
        return nil
    }
    return requirement
}

/// Checks files an agent asks to upload. Uploading sends a local file to a
/// website, so only named, readable regular files outside hidden directories
/// and the user's Library qualify; symbolic links are resolved first.
func validatedUploadFiles(_ value: Any?, home: String = NSHomeDirectory())
    -> Result<[String], GrantRefusal> {
    guard let names = value as? [String], (1...20).contains(names.count) else {
        return .failure(GrantRefusal("invalid_request", "files must list 1 to 20 absolute paths"))
    }
    let library = ((home as NSString).appendingPathComponent("Library") as NSString)
        .resolvingSymlinksInPath
    var resolved: [String] = []
    for name in names {
        guard name.hasPrefix("/") else {
            return .failure(GrantRefusal("invalid_request", "Upload paths must be absolute: \(name)"))
        }
        let path = (name as NSString).resolvingSymlinksInPath
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory),
              !isDirectory.boolValue, FileManager.default.isReadableFile(atPath: path) else {
            return .failure(GrantRefusal("upload_file_unavailable", "Not a readable file: \(name)"))
        }
        if path.split(separator: "/").contains(where: { $0.hasPrefix(".") }) ||
            path == library || path.hasPrefix(library + "/") {
            return .failure(GrantRefusal("upload_path_not_permitted",
                "Files in hidden folders or ~/Library are not uploaded: \(name)"))
        }
        resolved.append(path)
    }
    return .success(resolved)
}

/// Native identity/transport/effect adapter. The owned TypeScript child is the
/// only profile registry, browser coordinator and CDP endpoint authority.
final class BrowserRelay {
    static let route = "chrome.extension/cdp"
    struct Authority {
        let ownerSession: String
        let profileIDs: [String]
        let validate: () -> String?
    }
    private final class Peer {
        let descriptor: Int32, extensionID: String
        let tag = UUID().uuidString
        var source: DispatchSourceRead?
        var writer: DispatchSourceTimer?
        var writeDeadline: DispatchWorkItem?
        var input = Data(), output = Data()
        var outputOffset = 0
        var connectionID: String?, profileID: String?, problem: String?
        var attaching = false, closed = false
        var waiting: [[String: Any]] = []
        init(_ descriptor: Int32, extensionID: String) {
            self.descriptor = descriptor; self.extensionID = extensionID
        }
    }
    private struct Authorized {
        let owner: Authority
        let caller: CallerIdentity
        let generation: String
    }
    let service: ResidentService
    let broker: GrantBroker
    var identityCheck: (Int32) -> Bool = peerHasOwnCodeIdentity
    var respond: ((Int32, [String: Any], [String: Any], CallerIdentity, String?) -> Void)?
    private var host: SharedResidentHost?
    private var peers: [String: Peer] = [:]
    private var authorities: [String: Authorized] = [:]
    private var audits: [String: Authorized] = [:]
    private var stopped = true
    private var generation = UUID().uuidString
    private var nativeState: String?
    private var problem: String?
    private var queuedBytes = 0

    init(service: ResidentService, broker: GrantBroker, policyDirectory: URL? = nil,
         policyExecutable: URL? = nil) {
        self.service = service; self.broker = broker
        do {
            let receive: (SharedResidentHost.Frame) -> Void = { [weak self] in self?.receive($0) }
            let check: (SharedResidentHost.Frame) -> Bool = { [weak self] in self?.check($0) ?? false }
            let failed: (String) -> Void = { [weak self] in self?.failed($0) }
            if let policyDirectory, let policyExecutable {
                host = try SharedResidentHost(executable: policyExecutable,
                    arguments: [policyDirectory.appendingPathComponent("policy/node/main.ts").path],
                    directory: policyDirectory, receive: receive, native: check, failed: failed)
            } else {
                host = try SharedResidentHost.packaged(receive: receive, native: check, failed: failed)
            }
            try broker.admission.bind { [weak self] in
                guard let host = self?.host else { throw SharedPolicyError(code: "control_policy_unavailable") }
                return try host.call($0)
            }
            broker.admission.bindBackground { [weak self] frame, done in
                guard let host = self?.host else {
                    DispatchQueue.main.async { done(.failure(SharedPolicyError(code: "control_policy_unavailable"))) }
                    return
                }
                host.request(frame) { result in DispatchQueue.main.async { done(result) } }
            }
        } catch { problem = (error as? SharedPolicyError)?.code ?? "policy_startup_failed"; host?.stop() }
    }
    var available: Bool { host?.alive == true }
    var profiles: [[String: Any]] { host?.state["profiles"] as? [[String: Any]] ?? [] }
    var connected: Bool { profiles.contains { $0["connected"] as? Bool == true } }
    var statusJSON: [String: Any] {
        ["connected": connected, "available": available, "route": Self.route,
         "profileSelectionSupported": true, "profiles": profiles,
         "approvedProfiles": host?.state["selectedProfiles"] ?? [],
         "sharedRuntime": "typescript_node", "runtimeProblem": problem as Any? ?? NSNull(),
         "problems": peers.values.compactMap { peer -> [String: Any]? in
             peer.problem.map { ["reason": $0] }
         },
         "streamingCdp": ["available": available, "browserLevel": true,
            "binding": "live_browser_surface_owner", "transport": "target_loopback_websocket"],
         "knownOmissions": ["incognito tabs", "browser chrome UI", "OS file dialogs"]]
    }
    func configure(profiles: [String], seconds: Int?, enabled: Bool) throws {
        guard let host else { throw SharedPolicyError(code: "control_policy_unavailable") }
        synchronizeSafety()
        _ = try host.call(["method": "operator.configure", "scopes": enabled ? ["browser", "devtools"] : [],
            "profileIds": profiles, "durationMs": seconds.map { $0 * 1000 } as Any? ?? NSNull()])
        generation = UUID().uuidString; nativeState = nil; stopped = false
        endAudits(); authorities.removeAll()
    }
    func stopAccess() {
        stopped = true; generation = UUID().uuidString; nativeState = nil
        if let host, host.alive { _ = try? host.call(["method": "operator.stop"]) }
        endAudits(); authorities.removeAll()
    }
    func stop() {
        stopAccess()
        for peer in Array(peers.values) { disconnect(peer) }
        host?.stop()
    }
    func synchronizeSafety() {
        guard let host, host.alive else { return }
        let allowed = !stopped && broker.browserAllowed
        let state = generation + (allowed ? ":ready" : ":unavailable")
        guard state != nativeState else { return }
        if (try? host.call(["method": "native.state", "generation": generation,
                           "readable": allowed, "writable": allowed])) != nil { nativeState = state }
    }

    func register(_ descriptor: Int32, _ request: [String: Any]) -> [String: Any]? {
        guard identityCheck(descriptor), let origin = request["origin"] as? String,
              let url = URL(string: origin), url.scheme == "chrome-extension",
              let extensionID = url.host,
              ["ncbfifkjllmnkkjmomjohinigfgdocjc", "epejchbeajneooefnklikkfhbaeadkpc"].contains(extensionID) else {
            return service.refusal(request, code: "browser_provider_untrusted",
                message: "The browser provider must have this application's code identity and an allowed extension origin")
        }
        guard available, peers.count < 16 else {
            return service.refusal(request, code: available ? "browser_provider_capacity" : "control_policy_unavailable",
                message: "The shared browser runtime is unavailable")
        }
        let flags = fcntl(descriptor, F_GETFL)
        guard flags >= 0, fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == 0 else {
            return service.refusal(request, code: "browser_transport_unavailable", message: "Provider transport unavailable")
        }
        let peer = Peer(descriptor, extensionID: extensionID); peers[peer.tag] = peer
        let source = DispatchSource.makeReadSource(fileDescriptor: descriptor, queue: .main)
        source.setEventHandler { [weak self, weak peer] in if let peer { self?.read(peer) } }
        source.setCancelHandler { Darwin.close(descriptor) }
        peer.source = source; source.resume()
        enqueue(["type": "registered", "protocolVersion": 1], peer)
        return nil
    }
    private func read(_ peer: Peer) {
        var bytes = [UInt8](repeating: 0, count: 65536)
        while !peer.closed {
            let count = Darwin.read(peer.descriptor, &bytes, bytes.count)
            if count < 0 && errno == EINTR { continue }
            if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) { return }
            guard count > 0 else { disconnect(peer); return }
            peer.input.append(bytes, count: count)
            guard peer.input.count <= 32 * 1_048_576 else { disconnect(peer); return }
            while let newline = peer.input.firstIndex(of: 10) {
                let line = peer.input.prefix(upTo: newline); peer.input.removeSubrange(...newline)
                guard line.count <= 16 * 1_048_576,
                      let frame = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] else {
                    disconnect(peer); return
                }
                if peer.problem != nil { continue } // Hold incompatible copies unarmed; no reconnect fight.
                if peer.connectionID == nil {
                    if peer.attaching {
                        guard peer.waiting.count < 8, line.count <= 262144 else { disconnect(peer); return }
                        peer.waiting.append(frame); continue
                    }
                    guard frame["type"] as? String == "hello" else { disconnect(peer); return }
                    peer.attaching = true
                    host?.request(["method": "browser.attach", "extensionId": peer.extensionID,
                        "hello": frame, "transportTag": peer.tag], timeout: 10) { [weak self, weak peer] result in
                        DispatchQueue.main.async {
                            guard let self, let peer, !peer.closed else { return }
                            peer.attaching = false
                            switch result {
                            case let .success(value):
                                peer.connectionID = value["connectionId"] as? String
                                peer.profileID = value["profileId"] as? String
                                guard peer.connectionID != nil else { self.disconnect(peer); return }
                                let queued = peer.waiting; peer.waiting.removeAll()
                                for item in queued { self.providerFrame(item, peer) }
                            case let .failure(error):
                                let code = (error as? SharedPolicyError)?.code ?? "browser_profile_protocol_required"
                                peer.problem = code
                                self.enqueue(["type": "profile.refused", "protocolVersion": 1, "reason": code], peer)
                            }
                        }
                    }
                } else { providerFrame(frame, peer) }
            }
        }
    }
    private func providerFrame(_ frame: [String: Any], _ peer: Peer) {
        guard let id = peer.connectionID else { return }
        host?.request(["method": "provider.frame", "connectionId": id, "frame": frame]) { [weak self, weak peer] result in
            if case .failure = result {
                DispatchQueue.main.async { if let peer { self?.disconnect(peer) } }
            }
        }
    }
    private func disconnect(_ peer: Peer) {
        guard !peer.closed else { return }; peer.closed = true
        queuedBytes -= peer.output.count - peer.outputOffset
        peer.output.removeAll(); peer.writer?.cancel(); peer.writeDeadline?.cancel()
        peer.source?.cancel(); peer.source = nil; peers.removeValue(forKey: peer.tag)
        if let id = peer.connectionID, let host, host.alive {
            host.request(["method": "provider.disconnect", "connectionId": id]) { [weak host] _ in
                host?.request(["method": "provider.retire", "connectionId": id]) { _ in }
            }
        }
    }
    private func enqueue(_ frame: [String: Any], _ peer: Peer) {
        guard !peer.closed, let bytes = try? encodeJSONLine(frame),
              queuedBytes + bytes.count <= 32 * 1_048_576 else { disconnect(peer); return }
        if peer.outputOffset > 0 { peer.output.removeFirst(peer.outputOffset); peer.outputOffset = 0 }
        peer.output.append(bytes); queuedBytes += bytes.count
        if peer.writeDeadline == nil {
            let deadline = DispatchWorkItem { [weak self, weak peer] in if let peer { self?.disconnect(peer) } }
            peer.writeDeadline = deadline; DispatchQueue.main.asyncAfter(deadline: .now() + 3, execute: deadline)
        }
        flush(peer)
    }
    private func flush(_ peer: Peer) {
        guard available, !peer.closed else { disconnect(peer); return }
        while peer.outputOffset < peer.output.count {
            let count = peer.output.withUnsafeBytes { bytes in
                Darwin.write(peer.descriptor, bytes.baseAddress!.advanced(by: peer.outputOffset),
                    peer.output.count - peer.outputOffset)
            }
            if count > 0 { peer.outputOffset += count; queuedBytes -= count; continue }
            if count < 0 && errno == EINTR { continue }
            if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) {
                if peer.writer == nil {
                    let timer = DispatchSource.makeTimerSource(queue: .main)
                    timer.schedule(deadline: .now() + 0.01, repeating: .milliseconds(10))
                    timer.setEventHandler { [weak self, weak peer] in if let peer { self?.flush(peer) } }
                    peer.writer = timer; timer.resume()
                }
                return
            }
            disconnect(peer); return
        }
        peer.output.removeAll(keepingCapacity: true); peer.outputOffset = 0
        peer.writer?.cancel(); peer.writer = nil
        peer.writeDeadline?.cancel(); peer.writeDeadline = nil
    }
    private func receive(_ message: [String: Any]) {
        if message["type"] as? String == "access.event" {
            if broker.journal?.admission(message) == false { failed("audit_storage_unavailable"); return }
            broker.admission.receive(message)
            if ["yielded", "ended"].contains(message["event"] as? String ?? ""),
               let session = message["sessionId"] as? String {
                authorities = authorities.filter { !$0.value.owner.ownerSession.hasSuffix(":" + session) }
            }
            return
        }
        guard let peer = peers.values.first(where: {
            $0.tag == message["transportTag"] as? String ||
                ($0.connectionID != nil && $0.connectionID == message["connectionId"] as? String)
        }) else { return }
        if message["type"] as? String == "provider.close" { disconnect(peer); return }
        guard let frame = message["frame"] as? [String: Any] else { disconnect(peer); return }
        if ["request", "session.open", "session.command"].contains(frame["type"] as? String ?? "") {
            guard let id = message["authorityId"] as? String, let authority = authorities[id],
                  authority.generation == generation, authority.owner.validate() == nil else {
                disconnect(peer); return
            }
        }
        if frame["type"] as? String == "grant",
           frame["browser"] as? Bool == true || frame["devtools"] as? Bool == true {
            let current = (host?.state["authorizationGeneration"] as? NSNumber)?.stringValue ??
                (host?.state["authorizationGeneration"] as? String ?? "")
            guard !stopped, (frame["grantGeneration"] as? String)?.hasPrefix("shared:" + current + ":") == true else { return }
        }
        enqueue(frame, peer)
    }

    func forward(_ client: Int32, _ original: [String: Any], caller: CallerIdentity,
                 claimID: String?, authority: Authority? = nil,
                 completion: (([String: Any]) -> Void)? = nil) -> [String: Any]? {
        let operation = original["operation"] as? String ?? ""
        guard let host, host.alive else { return service.refusal(original,
            code: "control_policy_unavailable", message: "Shared browser runtime unavailable") }
        if operation != "browser.profiles" {
            guard let authority else { return service.refusal(original, code: "control_session_required",
                message: "Use one live Browser control session") }
            if let code = authority.validate() { return service.refusal(original, code: code, message: "Browser authority ended") }
        }
        synchronizeSafety()
        var request = original
        if operation == "browser.upload" {
            switch validatedUploadFiles(original["files"]) {
            case let .failure(error): return service.refusal(original, code: error.code, message: error.message)
            case let .success(files): request["files"] = files
            }
        }
        let retained = operation == "browser.endpoint"
        let id = UUID().uuidString
        let authorityID: String
        if retained, let authority, let existing = authorities.first(where: {
            $0.value.owner.ownerSession == authority.ownerSession && $0.value.generation == generation
        }) { authorityID = existing.key }
        else if let authority {
            guard authorities.count < 128 else { return service.refusal(original,
                code: "browser_stream_capacity", message: "Browser owner capacity reached") }
            authorityID = UUID().uuidString
            authorities[authorityID] = Authorized(owner: authority, caller: caller, generation: generation)
        } else { authorityID = "metadata" }
        host.request(["method": "browser.call", "requestId": id, "authorityId": authorityID,
            "ownerSession": authority?.ownerSession as Any? ?? NSNull(),
            "ownerProfileIds": authority?.profileIDs ?? [], "request": request], timeout: 50) { [weak self] result in
            DispatchQueue.main.async {
                guard let self else { return }
                var response: [String: Any]
                switch result {
                case let .success(reply):
                    response = self.service.acceptance(original, data: reply["data"] as? [String: Any] ?? [:])
                    for key in ["accepted", "errorCode", "message", "delivery", "effect", "uncertainty", "retrySafety"] {
                        if let value = reply[key] { response[key] = value }
                    }
                    var data = response["data"] as? [String: Any] ?? [:]
                    if let profile = reply["profileId"] { data["browserProfileId"] = profile }
                    if let provider = reply["providerGeneration"] { data["providerGeneration"] = provider }
                    if operation == "browser.capture", response["accepted"] as? Bool == true,
                       let encoded = data.removeValue(forKey: "png") as? String {
                        do {
                            guard let bytes = Data(base64Encoded: encoded),
                                  bytes.starts(with: [137, 80, 78, 71, 13, 10, 26, 10]) else {
                                throw SharedPolicyError(code: "invalid_browser_capture")
                            }
                            let url = try self.service.artifactURL()
                            try bytes.write(to: url, options: .atomic)
                            data["artifactPath"] = url.path; data["targetLocalPath"] = url.path
                            data["bytes"] = bytes.count
                            data["sha256"] = SHA256.hash(data:bytes).map { String(format:"%02x", $0) }.joined()
                        } catch {
                            response = self.service.refusal(original, code: "artifact_failed", message: "Browser capture storage failed")
                        }
                    }
                    response["data"] = data
                case let .failure(error):
                    if let code = (error as? SharedPolicyError)?.code,
                       !code.hasPrefix("ipc_"), !["resident_stopping", "control_policy_unavailable"].contains(code),
                       code.range(of:"^[a-z][a-z0-9_]{0,95}$",options:.regularExpression) != nil {
                        response = self.service.refusal(original, code:code, message:"Browser request refused before dispatch")
                        response["retrySafety"] = "safe_not_dispatched"
                    } else {
                        response = self.service.refusal(original, code: "browser_completion_unavailable", message: "Browser completion unobserved")
                        response["delivery"] = "unknown"; response["effect"] = "unknown"
                        response["uncertainty"] = "browser_completion_not_observed"; response["retrySafety"] = "unsafe_delivery_unknown"
                    }
                }
                response["actualRoute"] = Self.route; response["generation"] = self.generation
                if let authority, authority.validate() != nil {
                    response["accepted"] = false; response["errorCode"] = "stale_control_session"
                    response["uncertainty"] = "interrupted_after_possible_dispatch"; response["retrySafety"] = "unsafe"
                }
                if !retained { self.authorities.removeValue(forKey: authorityID) }
                if let completion { completion(response) }
                else { self.respond?(client, original, response, caller, claimID); Darwin.close(client) }
            }
        }
        return nil
    }

    private func check(_ frame: [String: Any]) -> Bool {
        guard let id = frame["authorityId"] as? String, let authority = authorities[id] else { return false }
        let allowed = !stopped && authority.generation == generation && authority.owner.validate() == nil
        let phase = frame["phase"] as? String, auditID = frame["auditId"] as? String ?? ""
        if phase == "check" { return allowed }
        if phase == "begin" {
            guard allowed, audits.count < 256, audits[auditID] == nil,
                  broker.journal?.begin(["operation": "browser.cdp", "requestId": auditID], caller: authority.caller) != false else { return false }
            audits[auditID] = authority; return true
        }
        guard phase == "result", audits.removeValue(forKey: auditID) != nil else { return false }
        let confirmed = allowed && frame["delivery"] as? String == "confirmed"
        return broker.journal?.record(cdpResult(auditID, generation: authority.generation, confirmed: confirmed)) != false && allowed
    }
    private func cdpResult(_ id: String, generation: String, confirmed: Bool) -> [String: Any] {
        ["operation": "browser.cdp", "requestId": id, "generation": generation,
         "actualRoute": Self.route, "accepted": confirmed, "delivery": confirmed ? "confirmed" : "unknown",
         "effect": "unverifiable", "uncertainty": confirmed ? "application_effect_not_independently_observed" : "browser_completion_not_observed",
         "retrySafety": confirmed ? "unsafe_to_replay" : "unsafe_delivery_unknown"]
    }
    private func endAudits() {
        for (id, authority) in audits { _ = broker.journal?.record(cdpResult(id, generation: authority.generation, confirmed: false)) }
        audits.removeAll()
    }
    private func failed(_ code: String) {
        problem = code; stopped = true; generation = UUID().uuidString
        for peer in Array(peers.values) { disconnect(peer) }
        host?.stop()
        endAudits(); authorities.removeAll(); broker.admission.invalidate()
        broker.journal?.diagnostic("resident.policy", code: code)
    }
}
