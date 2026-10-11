import Foundation

/// Cancellation generations contain no grant or bearer authority.
final class ProviderEpoch {
    private let lock = NSLock()
    private var generation = UUID()
    var current: UUID { lock.lock(); defer { lock.unlock() }; return generation }
    func invalidate() { lock.lock(); generation = UUID(); lock.unlock() }
    func refusal(_ token: UUID) -> String? { current == token ? nil : "control_generation_changed" }
}

/// One bounded provider slot. AX references and credential leases belong only
/// to this serial worker; the coordinator receives immutable projections.
final class NativeProviderExecutor {
    private final class PendingReply {
        var deadline: DispatchWorkItem?
        private var callback: (([String:Any]) -> Void)?
        init(_ callback: @escaping ([String:Any]) -> Void) { self.callback = callback }
        var pending: Bool { callback != nil }
        func finish(_ result: [String:Any]) {
            deadline?.cancel(); deadline = nil
            let completion = callback; callback = nil; completion?(result)
        }
    }
    private let queue = DispatchQueue(label:"machine-control.native-provider", qos:.userInitiated)
    private let provider: ResidentService
    init(runtimeGeneration: String = UUID().uuidString.lowercased()) {
        provider = ResidentService(generation:runtimeGeneration)
    }
    private let epoch = ProviderEpoch()
    private var providerGeneration: UUID?
    private(set) var busy = false
    private var stopped = false
    private(set) var referenceOwners: [String:pid_t] = [:]
    var readSession: () -> [String:Any] = { nativeSessionObservation() }
    var preflightTimeout: TimeInterval = 5

    func invalidate() { epoch.invalidate(); referenceOwners.removeAll() }
    func stop() { stopped = true; invalidate() }

    func execute(_ request: [String:Any], coveredWindows: Set<Int>,
                 cancellation: @escaping () -> String?,
                 observed: @escaping ([String:Any]) -> Void,
                 authorize: @escaping () -> GrantRefusal?,
                 custom: (([String:Any]) -> [String:Any])? = nil,
                 credentialSocket: Int32? = nil,
                 completion: @escaping ([String:Any]) -> Void) {
        guard !busy, !stopped else {
            completion(provider.refusal(request, code:"native_provider_busy", message:"Native provider is busy or stopping")); return
        }
        busy = true
        let reply = PendingReply(completion)
        let expiry = DispatchWorkItem { [self, reply] in
            guard reply.pending else { return }
            epoch.invalidate()
            reply.finish(provider.refusal(request, code:"native_preflight_timeout",
                message:"Native preflight exceeded its deadline"))
        }
        reply.deadline = expiry
        DispatchQueue.main.asyncAfter(deadline:.now() + preflightTimeout, execute:expiry)
        let read = readSession
        let preflightToken = epoch.current
        queue.async { [self] in
            let current = preflightToken
            if providerGeneration != current { provider.invalidateReferences(); providerGeneration = current }
            let session = autoreleasepool { read() }
            provider.applySessionObservation(session)
            let owners = provider.referenceOwnerProjection()
            DispatchQueue.main.async { [self] in
                // A deadline completes the caller while retaining the occupied
                // worker slot. Its eventual read cannot schedule an effect.
                guard reply.pending else { busy = false; return }
                reply.deadline?.cancel(); reply.deadline = nil
                // A Stop/new grant while preflight was blocked must not let
                // this old request adopt the replacement authority.
                if stopped || epoch.refusal(preflightToken) != nil {
                    busy = false
                    reply.finish(provider.refusal(request, code:"control_generation_changed",
                        message:"Control changed while native preflight was pending")); return
                }
                observed(session)
                if epoch.refusal(preflightToken) == nil { referenceOwners = owners }
                let refusal = authorize()
                if stopped || refusal != nil {
                    busy = false
                    let refusal = refusal ?? GrantRefusal("resident_stopping", "Resident is stopping")
                    reply.finish(provider.refusal(request, code:refusal.code, message:refusal.message)); return
                }
                let token = epoch.current
                queue.async { [self] in
                    guard epoch.refusal(token) == nil else {
                        let result = provider.refusal(request, code:"control_generation_changed",
                            message:"Control changed before native dispatch")
                        DispatchQueue.main.async { [self] in busy = false; reply.finish(result) }
                        return
                    }
                    if providerGeneration != token { provider.invalidateReferences(); providerGeneration = token }
                    provider.coveredWindowIDs = { coveredWindows }
                    provider.inputCancellation = { [epoch] in epoch.refusal(token) ?? cancellation() }
                    var response: [String:Any]
                    if let credentialSocket {
                        // Discover the exact provider/field before requesting secret bytes.
                        if let refusal = provider.credentialPreflight(request) { response = refusal }
                        else if let reason = provider.inputCancellation() {
                            response = provider.refusal(request, code:reason, message:"Credential operation cancelled")
                        } else {
                            do {
                                try writeSocket(credentialSocket, data:Data([0x06]))
                                var credential = try readSocket(credentialSocket, limit:257)
                                defer { credential.resetBytes(in:0..<credential.count); credential.removeAll(keepingCapacity:false) }
                                response = provider.handleCredential(request, credential:credential)
                            } catch { response = provider.refusal(request, code:"credential_transport_failed", message:"Credential transport failed") }
                        }
                    } else {
                        response = autoreleasepool { custom?(request) ?? provider.handle(request) }
                    }
                    if ["input.key", "input.text"].contains(request["operation"] as? String ?? ""), response["accepted"] as? Bool == true {
                        var data = response["data"] as? [String:Any] ?? [:]
                        data["keyboardReceiver"] = keyboardReceiver(); response["data"] = data
                    }
                    let owners = provider.referenceOwnerProjection()
                    let result = response
                    DispatchQueue.main.async { [self] in
                        var response = result
                        busy = false
                        if epoch.refusal(token) != nil {
                            response["accepted"] = false; response["errorCode"] = "control_generation_changed"
                            if response["delivery"] as? String == "confirmed" {
                                response["uncertainty"] = "interrupted_after_possible_dispatch"; response["retrySafety"] = "unsafe"
                            }
                        } else { referenceOwners = owners }
                        reply.finish(response)
                    }
                }
            }
        }
    }
}
