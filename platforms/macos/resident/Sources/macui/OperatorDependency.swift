import Foundation

/// One operator dependency slot. Deadlines finish the caller, not the worker;
/// a stuck native call cannot grow a queue or commit after Stop/timeout.
final class OperatorDependency {
    private let queue = DispatchQueue(label:"machine-control.operator-dependency", qos:.userInitiated)
    private let epoch = ProviderEpoch()
    private var pending: (([String:Any]) -> Void)?
    private var deadline: DispatchWorkItem?
    private(set) var busy = false

    func cancel(_ reason: String = "operator_cancelled") {
        precondition(Thread.isMainThread)
        epoch.invalidate()
        finish(["ok":false, "error":reason])
    }
    private func finish(_ result: [String:Any]) {
        deadline?.cancel(); deadline = nil
        let completion = pending; pending = nil; completion?(result)
    }
    func perform(timeout: TimeInterval = 3,
                 work: @escaping (@escaping () -> String?) throws -> Void,
                 commit: @escaping () throws -> Void,
                 completion: @escaping ([String:Any]) -> Void) {
        precondition(Thread.isMainThread)
        guard !busy else { completion(["ok":false, "error":"operator_dependency_busy"]); return }
        busy = true; pending = completion
        let token = epoch.current
        let deadline = DispatchWorkItem { [weak self] in self?.cancel("operator_dependency_timeout") }
        self.deadline = deadline
        DispatchQueue.main.asyncAfter(deadline:.now() + timeout, execute:deadline)
        queue.async { [self] in
            let issue: String?
            do {
                if let reason = epoch.refusal(token) { throw MacUIError.action(reason) }
                try work { [epoch] in epoch.refusal(token) }
                issue = nil
            } catch { issue = String(describing:error) }
            DispatchQueue.main.async { [self] in
                busy = false
                guard pending != nil, epoch.refusal(token) == nil else { return }
                if let issue { finish(["ok":false, "error":issue]); return }
                do { try commit(); finish(["ok":true]) }
                catch { finish(["ok":false, "error":String(describing:error)]) }
            }
        }
    }
}
