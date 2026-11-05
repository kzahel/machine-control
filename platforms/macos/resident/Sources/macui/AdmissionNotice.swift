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
    private var yieldShown = false
    private var yieldUntil = Date.distantPast
    init(server: ResidentServer) { self.server = server }
    func update() {
        guard let server, server.approvalDesktopUnlocked(), !server.lockedUse.isCovered else { dismiss(); return }
        let state = server.broker.admission.status
        let cooldown = (state["handoffCooldownRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0
        if cooldown <= 0 { yieldShown = false }
        let requests = state["requests"] as? [[String: Any]] ?? []
        guard let request = requests.first(where: { ["announcing", "waiting_for_approval"].contains($0["state"] as? String ?? "") }),
              let id = request["intentId"] as? String else {
            if cooldown > 0 && !yieldShown {
                dismiss(); yieldShown = true; yieldUntil = Date().addingTimeInterval(3)
                let toast = AdmissionPanel(contentRect: NSRect(x:0, y:0, width:380, height:75), styleMask:[.titled, .nonactivatingPanel], backing:.buffered, defer:false)
                toast.title = "Machine Control"; toast.level = .floating; toast.isReleasedWhenClosed = false
                let label = NSTextField(wrappingLabelWithString: "Desktop yielded. You have control.")
                label.frame = NSRect(x:16,y:16,width:348,height:40); toast.contentView?.addSubview(label)
                if let frame = NSScreen.main?.visibleFrame { toast.setFrameOrigin(NSPoint(x:frame.maxX-396,y:frame.maxY-110)) }
                panel = toast; toast.orderFrontRegardless()
            } else if Date() >= yieldUntil { dismiss() }
            return
        }
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
        detail.toolTip = detail.stringValue + "\n" + names.joined(separator: "\n")
        let seconds = Int(ceil((request["noticeRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0))
        countdown.stringValue = ask ? "Approval is limited to this task and the current access lifetime." :
            "Starts in \(max(0, seconds)) seconds unless paused."
        if let panel, !panel.isVisible { panel.orderFrontRegardless() }
    }
    private func makePanel(id: String, ask: Bool) {
        let panel = AdmissionPanel(contentRect: NSRect(x:0, y:0, width:560, height:260),
            styleMask:[.titled, .nonactivatingPanel], backing:.buffered, defer:false)
        panel.title = "Machine Control"; panel.level = .floating
        panel.isReleasedWhenClosed = false; panel.becomesKeyOnlyIfNeeded = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        heading.font = .boldSystemFont(ofSize:15)
        detail.font = .systemFont(ofSize:12); detail.maximumNumberOfLines = 4
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
        first.addArrangedSubview(button(ask ? "Allow now" : "Start now") { server, id in
            if ask { try server.approveTask(id) } else { try server.startNow(id) }
        })
        let delay = NSPopUpButton()
        delay.addItem(withTitle: ask ? "Allow in…" : "More time…")
        let row = (server?.broker.admission.status["requests"] as? [[String: Any]])?.first { $0["intentId"] as? String == id }
        let budget = (row?["taskRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0
        for (title, seconds) in [("30 seconds",30), ("1 minute",60), ("5 minutes",300)] {
            delay.addItem(withTitle:title); delay.lastItem?.representedObject = seconds
            delay.lastItem?.isEnabled = Double(seconds + 65) < budget
        }
        delay.menu?.autoenablesItems = false
        let delayed = AdmissionAction(id) { [weak self, weak delay] id in
            guard let self, let server = self.server, let seconds = delay?.selectedItem?.representedObject as? Int else { return }
            do {
                if ask { try server.approveTask(id, seconds:seconds) }
                else { try server.broker.admission.postpone(id, seconds:seconds) }
            } catch { server.broker.journal?.diagnostic("admission.notice", code:"notice_changed") }
            delay?.selectItem(at:0); self.update()
        }
        actions.append(delayed); delay.target = delayed; delay.action = #selector(AdmissionAction.invoke(_:))
        first.addArrangedSubview(delay)
        first.addArrangedSubview(button(ask ? "Decline" : "Cancel") { try $0.broker.admission.deny($1) })
        let second = NSStackView(); second.orientation = .horizontal; second.spacing = 8
        second.addArrangedSubview(button("Turn off access") { server, _ in server.revoke(reason:"stopped_by_person") })
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
