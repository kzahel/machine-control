import Foundation

/// The WebView supplies presentation; this native in-process approver owns
/// the completion. No socket operation can submit an approval decision.
final class DesktopApprover: GrantApprover {
    let kind = "local_tauri"
    var request: GrantRequest?
    private var completion: ((GrantDecision) -> Void)?
    func present(_ request: GrantRequest, completion: @escaping (GrantDecision) -> Void) {
        self.request = request
        self.completion = completion
    }
    func dismiss(requestID: String) {
        guard request?.id == requestID else { return }
        request = nil
        completion = nil
    }
    func decide(id: String, scopes: [String], duration: Int, allow: Bool) throws {
        guard let pending = request, pending.id == id, let completion else {
            throw MacUIError.action("The approval request is no longer current")
        }
        let selected = Set(scopes.compactMap(GrantScope.init(rawValue:)))
        guard !allow || (scopes.allSatisfy({ GrantScope(rawValue: $0) != nil }) &&
                        !selected.isEmpty && selected.isSubset(of: pending.scopes) &&
                        duration >= 60 && duration <= pending.durationSeconds) else {
            throw MacUIError.usage("Approval may only narrow the requested access and duration")
        }
        completion(allow ? .approved(scopes: selected, durationSeconds: duration) : .denied)
    }
}
