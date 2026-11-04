import AppKit

private final class AdmissionPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
private final class AdmissionAction: NSObject {
    let id: String
    let run: (String) -> Void
    init(_ id: String, _ run: @escaping (String) -> Void) { self.id = id; self.run = run }
    @objc func invoke(_ sender: Any?) { run(id) }
}

/// One nonactivating task notice. Buttons retain their displayed intent, so a
/// late click cannot approve a different task after the presentation changes.
final class AdmissionNotice: NSObject {
    private weak var server: ResidentServer?
    private var panel: NSPanel?
    private let heading = NSTextField(labelWithString: "")
    private let detail = NSTextField(wrappingLabelWithString: "")
    private let countdown = NSTextField(labelWithString: "")
    private var displayed: String?
    private var actions: [AdmissionAction] = []
    init(server: ResidentServer) { self.server = server }
    func update() {
        guard let server, server.approvalDesktopUnlocked(), !server.lockedUse.isCovered,
              let requests = server.broker.admission.status["requests"] as? [[String: Any]],
              let request = requests.first(where: { ["announcing", "waiting_for_approval"].contains($0["state"] as? String ?? "") }),
              let id = request["intentId"] as? String else { dismiss(); return }
        let ask = request["state"] as? String == "waiting_for_approval"
        let identity = id + (ask ? ":ask" : ":notice")
        if displayed != identity { dismiss(); displayed = identity; makePanel(id: id, ask: ask) }
        let surfaces = request["surfaces"] as? [String] ?? []
        let names = (request["profileIds"] as? [String] ?? []).map { id in
            server.browser.profiles.first(where: { $0["profileId"] as? String == id })?["name"] as? String ?? String(id.prefix(12))
        }
        let scope = surfaces.map { $0 == "desktop" ? "Desktop" : "Browser" }.joined(separator: " and ")
        heading.stringValue = ask ? "Allow \(scope) control for this task?" : "\(scope) control is about to start"
        let profiles = names.isEmpty ? "" : "\nProfiles: " + names.prefix(3).joined(separator: ", ") +
            (names.count > 3 ? " and \(names.count - 3) more" : "")
        detail.stringValue = "\(server.callerSummary(for:id))\n\(server.callerAssurance(for:id))\n\(request["reason"] as? String ?? "")\(profiles)"
        detail.toolTip = names.joined(separator: "\n")
        let seconds = Int(ceil((request["noticeRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0))
        countdown.stringValue = ask ? "Approval is limited to this task and the current access lifetime." :
            "Starts in \(max(0, seconds)) seconds unless paused."
        if let panel, !panel.isVisible { panel.orderFrontRegardless() }
    }
    private func makePanel(id: String, ask: Bool) {
        let panel = AdmissionPanel(contentRect: NSRect(x:0, y:0, width:560, height:330),
            styleMask:[.titled, .nonactivatingPanel], backing:.buffered, defer:false)
        panel.title = "Machine Control"; panel.level = .floating
        panel.isReleasedWhenClosed = false; panel.becomesKeyOnlyIfNeeded = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        heading.font = .boldSystemFont(ofSize:15)
        detail.font = .systemFont(ofSize:12); detail.maximumNumberOfLines = 8
        countdown.font = .monospacedDigitSystemFont(ofSize:12, weight:.medium)
        func button(_ title: String, _ work: @escaping (ResidentServer, String) throws -> Void) -> NSButton {
            let action = AdmissionAction(id) { [weak self] id in
                guard let self, let server = self.server else { return }
                do { try work(server, id) }
                catch { server.broker.journal?.diagnostic("admission.notice", code:"notice_changed") }
                self.update()
            }
            actions.append(action)
            let value = NSButton(title:title, target:action, action:#selector(AdmissionAction.invoke(_:)))
            value.bezelStyle = .rounded; return value
        }
        let first = NSStackView(); first.orientation = .horizontal; first.spacing = 8
        first.addArrangedSubview(button(ask ? "Allow this task" : "Start now") { server, id in
            if ask { try server.broker.admission.approve(id) } else { try server.startNow(id) }
        })
        first.addArrangedSubview(button("Pause 30 seconds") { try $0.broker.admission.deferRequest($1, seconds:30) })
        first.addArrangedSubview(button("Pause 1 minute") { try $0.broker.admission.deferRequest($1, seconds:60) })
        let second = NSStackView(); second.orientation = .horizontal; second.spacing = 8
        second.addArrangedSubview(button("Pause until Resume") { try $0.broker.admission.deferRequest($1, seconds:nil) })
        second.addArrangedSubview(button("Deny task") { try $0.broker.admission.deny($1) })
        second.addArrangedSubview(button("Stop access") { server, _ in server.revoke(reason:"stopped_by_person") })
        [heading, detail, countdown, first, second].forEach { stack.addArrangedSubview($0) }
        guard let content = panel.contentView else { return }
        stack.translatesAutoresizingMaskIntoConstraints = false; content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo:content.leadingAnchor, constant:16),
            stack.trailingAnchor.constraint(equalTo:content.trailingAnchor, constant:-16),
            stack.topAnchor.constraint(equalTo:content.topAnchor, constant:16),
            stack.bottomAnchor.constraint(lessThanOrEqualTo:content.bottomAnchor, constant:-16)])
        if let frame = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x:frame.maxX - 576, y:frame.maxY - 350))
        }
        self.panel = panel
    }
    private func dismiss() { panel?.orderOut(nil); panel = nil; actions.removeAll(); displayed = nil }
    deinit { panel?.orderOut(nil) }
}
