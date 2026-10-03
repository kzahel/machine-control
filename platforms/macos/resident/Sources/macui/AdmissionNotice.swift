import AppKit

private final class AdmissionPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

/// Resource-level presentation. Actions use the operator's in-process surface,
/// never an agent JSON endpoint. Ordering front never activates the application.
final class AdmissionNotice: NSObject {
    private weak var server: ResidentServer?
    private var panel: NSPanel?
    private let heading = NSTextField(labelWithString:"Computer control is about to start")
    private let detail = NSTextField(wrappingLabelWithString:"")
    private let countdown = NSTextField(labelWithString:"")
    private var intentID: String?
    init(server: ResidentServer) { self.server = server }
    func update() {
        guard let server, server.approvalDesktopUnlocked(), !server.lockedUse.isCovered,
              let requests = server.broker.admission.status["requests"] as? [[String:Any]],
              let request = requests.first(where:{ $0["state"] as? String == "announcing" }),
              let id = request["intentId"] as? String else { dismiss(); return }
        intentID = id
        if panel == nil { makePanel() }
        let seconds = max(0, Int(ceil(request["noticeRemainingSeconds"] as? Double ?? 0)))
        let maximum = Int(request["maximumDurationSeconds"] as? Double ?? 0)
        detail.stringValue = "\(server.callerSummary(for:id))\n\(server.callerAssurance(for:id))\n\(request["reason"] as? String ?? "")"
        countdown.stringValue = "Starts in \(seconds)s · Maximum control time \(maximum)s"
        if let panel, !panel.isVisible { panel.orderFrontRegardless() }
    }
    private func makePanel() {
        let panel = AdmissionPanel(contentRect:NSRect(x:0,y:0,width:430,height:235),
            styleMask:[.titled, .nonactivatingPanel], backing:.buffered, defer:false)
        panel.title = "Machine Control"; panel.level = .floating
        panel.isReleasedWhenClosed = false; panel.becomesKeyOnlyIfNeeded = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        heading.font = .boldSystemFont(ofSize:15)
        detail.font = .systemFont(ofSize:12); detail.maximumNumberOfLines = 4
        countdown.font = .monospacedDigitSystemFont(ofSize:12, weight:.medium)
        let buttons = NSStackView(); buttons.orientation = .horizontal; buttons.spacing = 8
        for (title, selector) in [("Start now", #selector(startNow)), ("Wait 1 min", #selector(deferMinute)), ("Pause until Resume", #selector(pause))] {
            let button = NSButton(title:title, target:self, action:selector); button.bezelStyle = .rounded
            buttons.addArrangedSubview(button)
        }
        [heading, detail, countdown, buttons].forEach { stack.addArrangedSubview($0) }
        guard let content = panel.contentView else { return }
        stack.translatesAutoresizingMaskIntoConstraints = false; content.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo:content.leadingAnchor, constant:16),
            stack.trailingAnchor.constraint(equalTo:content.trailingAnchor, constant:-16),
            stack.topAnchor.constraint(equalTo:content.topAnchor, constant:16),
            stack.bottomAnchor.constraint(lessThanOrEqualTo:content.bottomAnchor, constant:-16)])
        if let frame = NSScreen.main?.visibleFrame { panel.setFrameOrigin(NSPoint(x:frame.maxX - 446, y:frame.maxY - 265)) }
        self.panel = panel
    }
    @objc private func startNow() {
        guard let server, let intentID else { return }
        do { try server.startNow(intentID) } catch { server.broker.journal?.diagnostic("admission.notice", code:"notice_changed") }
        update()
    }
    @objc private func deferMinute() {
        do { try server?.broker.pause(reason:"operator_deferral", seconds:60) }
        catch { server?.broker.journal?.diagnostic("admission.notice", code:"pause_storage_unavailable") }
        update()
    }
    @objc private func pause() {
        do { try server?.broker.pause() }
        catch { server?.broker.journal?.diagnostic("admission.notice", code:"pause_storage_unavailable") }
        update()
    }
    private func dismiss() { panel?.orderOut(nil); intentID = nil }
    deinit { panel?.orderOut(nil) }
}
