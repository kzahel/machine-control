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
    private let queue = DispatchQueue(label:"machine-control.native-provider", qos:.userInitiated)
    private let provider = ResidentService()
    private let epoch = ProviderEpoch()
    private var providerGeneration: UUID?
    private(set) var busy = false
    private var stopped = false
    private(set) var referenceOwners: [String:pid_t] = [:]
    var readSession: () -> [String:Any] = { nativeSessionObservation() }

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
        let read = readSession
        queue.async { [self] in
            let current = epoch.current
            if providerGeneration != current { provider.invalidateReferences(); providerGeneration = current }
            let session = autoreleasepool { read() }
            provider.applySessionObservation(session)
            let owners = provider.referenceOwnerProjection()
            DispatchQueue.main.async { [self] in
                observed(session)
                referenceOwners = owners
                let refusal = authorize()
                if stopped || refusal != nil {
                    busy = false
                    let refusal = refusal ?? GrantRefusal("resident_stopping", "Resident is stopping")
                    completion(provider.refusal(request, code:refusal.code, message:refusal.message)); return
                }
                let token = epoch.current
                queue.async { [self] in
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
                        completion(response)
                    }
                }
            }
        }
    }
}
