import AppKit

private final class CallerPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

private final class CallerChoice: NSObject {
    let allow: Bool
    let run: (Bool) -> Void
    init(_ allow: Bool, _ run: @escaping (Bool) -> Void) { self.allow = allow; self.run = run }
    @objc func invoke(_ sender: Any?) { run(allow) }
}

/// First-use "Allow callers from APP?" prompt. It is owned by the resident
/// process, so the resident's self-target guard refuses agent input aimed at
/// it. Each panel is bound to the one host it names; a late click cannot
/// approve a different app.
final class CallerApprovalPanels {
    private var panels: [String:(panel: NSPanel, choices: [CallerChoice], finish: (Bool) -> Void)] = [:]

    func present(_ host: CallerHost, completion: @escaping (Bool) -> Void) -> Bool {
        guard let key = host.key, panels[key] == nil else { return false }
        let panel = CallerPanel(contentRect:NSRect(x:0, y:0, width:520, height:220),
            styleMask:[.titled, .nonactivatingPanel], backing:.buffered, defer:false)
        panel.title = "Machine Control"; panel.level = .floating
        panel.isReleasedWhenClosed = false; panel.becomesKeyOnlyIfNeeded = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        let heading = NSTextField(labelWithString:"Allow callers from \(host.name)?")
        heading.font = .boldSystemFont(ofSize:15)
        let publisher = NSTextField(labelWithString:"Publisher: \(host.publisher)" +
            (host.teamID.map { " (\($0))" } ?? ""))
        publisher.font = .systemFont(ofSize:12)
        let detail = NSTextField(wrappingLabelWithString:
            "A program started from \(host.name) asked to use Machine Control while Only verified callers is on. " +
            "Allowing lets anything \(host.name) runs, including agents, shells and scripts, use Machine Control. " +
            "Desktop and Browser access settings still apply. This is not a sandbox. You can remove the app in Settings.")
        detail.font = .systemFont(ofSize:12); detail.maximumNumberOfLines = 6
        var choices: [CallerChoice] = []
        let finish: (Bool) -> Void = { [weak self] allow in
            guard let self, let entry = self.panels.removeValue(forKey:key) else { return }
            entry.panel.orderOut(nil)
            completion(allow)
        }
        func button(_ title: String, allow: Bool) -> NSButton {
            let choice = CallerChoice(allow, finish); choices.append(choice)
            let value = NSButton(title:title, target:choice, action:#selector(CallerChoice.invoke(_:)))
            value.bezelStyle = .rounded; return value
        }
        let row = NSStackView(); row.orientation = .horizontal; row.spacing = 8
        let deny = button("Don’t Allow", allow:false)
        deny.keyEquivalent = "\u{1b}"
        row.addArrangedSubview(deny)
        row.addArrangedSubview(button("Allow", allow:true))
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 10
        [heading, publisher, detail, row].forEach { stack.addArrangedSubview($0) }
        guard let content = panel.contentView else { return false }
        stack.translatesAutoresizingMaskIntoConstraints = false; content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo:content.leadingAnchor, constant:16),
            stack.trailingAnchor.constraint(equalTo:content.trailingAnchor, constant:-16),
            stack.topAnchor.constraint(equalTo:content.topAnchor, constant:16),
            stack.bottomAnchor.constraint(lessThanOrEqualTo:content.bottomAnchor, constant:-16)])
        if let frame = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x:frame.maxX - 536, y:frame.maxY - 260 - CGFloat(panels.count) * 24))
        }
        panels[key] = (panel, choices, finish)
        panel.orderFrontRegardless()
        return true
    }
    /// Stop or resident shutdown dismisses prompts without approving.
    func dismissAll() {
        for entry in Array(panels.values) { entry.finish(false) }
    }
}
