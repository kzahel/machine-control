import AppKit

/// A floating, non-activating prompt that turns a grant request into a
/// person's decision. It has no default button, so a stray Return cannot
/// approve it.
final class ApprovalPanelController: NSObject, GrantApprover {
    let kind = "local_click"
    var onChange: (() -> Void)?

    private var panel: NSPanel?
    private var requestID: String?
    private var completion: ((GrantDecision) -> Void)?
    private var request: GrantRequest?
    private var deadline = Date()
    private var countdown: Timer?
    private var countdownLabel: NSTextField?
    private var durationPopup: NSPopUpButton?
    private var durationChoices: [Int] = []

    var isVisible: Bool { panel?.isVisible == true }

    func present(_ request: GrantRequest, completion: @escaping (GrantDecision) -> Void) {
        dismiss(requestID: requestID ?? "")
        self.request = request
        self.requestID = request.id
        self.completion = completion
        deadline = Date().addingTimeInterval(TimeInterval(request.timeoutSeconds))

        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 460, height: 10),
                            styleMask: [.titled, .nonactivatingPanel],
                            backing: .buffered, defer: false)
        panel.title = "Machine Control"
        panel.level = .modalPanel
        panel.isFloatingPanel = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isReleasedWhenClosed = false

        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 20, bottom: 16, right: 20)

        let title = NSTextField(labelWithString: "An agent is asking to use this Mac")
        title.font = .boldSystemFont(ofSize: 14)
        stack.addArrangedSubview(title)
        stack.addArrangedSubview(wrapping("“\(request.reason)”", size: 13))
        stack.addArrangedSubview(wrapping("Access: " + describe(request.scopes), size: 12))

        let durationRow = NSStackView()
        durationRow.orientation = .horizontal
        durationRow.addArrangedSubview(NSTextField(labelWithString: "For:"))
        let popup = NSPopUpButton(frame: .zero, pullsDown: false)
        durationChoices = Array(Set([300, 900, 3600, request.durationSeconds]
            .filter { $0 <= request.durationSeconds })).sorted()
        for seconds in durationChoices { popup.addItem(withTitle: format(seconds)) }
        popup.selectItem(at: durationChoices.count - 1)
        durationRow.addArrangedSubview(popup)
        durationPopup = popup
        stack.addArrangedSubview(durationRow)

        let caller = wrapping("Requested by \(request.caller.summary) (pid \(request.caller.pid)). "
            + "This is what macOS reports about the connecting process; it is not verified.",
            size: 11)
        caller.textColor = .secondaryLabelColor
        stack.addArrangedSubview(caller)
        if let claim = request.claimID {
            let claimLabel = wrapping("Claim: \(claim)", size: 11)
            claimLabel.textColor = .secondaryLabelColor
            stack.addArrangedSubview(claimLabel)
        }
        let countdown = NSTextField(labelWithString: "")
        countdown.font = .systemFont(ofSize: 11)
        countdown.textColor = .secondaryLabelColor
        stack.addArrangedSubview(countdown)
        countdownLabel = countdown

        let buttons = NSStackView()
        buttons.orientation = .horizontal
        buttons.addArrangedSubview(button("Deny", #selector(deny)))
        if request.scopes.contains(.observe) && request.scopes.count > 1 {
            buttons.addArrangedSubview(button("Allow View Only", #selector(allowObserve)))
        }
        buttons.addArrangedSubview(button("Allow", #selector(allow)))
        stack.addArrangedSubview(buttons)

        panel.contentView = stack
        panel.setContentSize(stack.fittingSize)
        if let screen = NSScreen.main {
            let frame = screen.visibleFrame
            panel.setFrameTopLeftPoint(NSPoint(x: frame.midX - panel.frame.width / 2,
                                               y: frame.maxY - 40))
        }
        panel.orderFrontRegardless()
        self.panel = panel
        updateCountdown()
        self.countdown = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.updateCountdown()
        }
        onChange?()
    }

    func dismiss(requestID: String) {
        guard self.requestID == requestID || requestID.isEmpty else { return }
        countdown?.invalidate()
        countdown = nil
        panel?.orderOut(nil)
        panel = nil
        self.requestID = nil
        completion = nil
        request = nil
        onChange?()
    }

    private func finish(_ decision: GrantDecision) {
        let completion = self.completion
        self.completion = nil
        completion?(decision)
    }

    @objc private func deny() { finish(.denied) }

    @objc private func allow() {
        guard let request else { return }
        finish(.approved(scopes: request.scopes, durationSeconds: selectedDuration()))
    }

    @objc private func allowObserve() {
        finish(.approved(scopes: [.observe], durationSeconds: selectedDuration()))
    }

    private func selectedDuration() -> Int {
        let index = durationPopup?.indexOfSelectedItem ?? -1
        return durationChoices.indices.contains(index) ? durationChoices[index] :
            (request?.durationSeconds ?? GrantRequest.defaultDuration)
    }

    private func updateCountdown() {
        let remaining = max(0, Int(deadline.timeIntervalSinceNow))
        countdownLabel?.stringValue = String(format: "Denies automatically in %d:%02d",
                                             remaining / 60, remaining % 60)
    }

    private func describe(_ scopes: Set<GrantScope>) -> String {
        scopes.sorted().map { scope -> String in
            switch scope {
            case .observe: return "see the screen and windows"
            case .control: return "use the keyboard, mouse, and apps"
            case .browser: return "control Chrome tabs and upload files to web pages"
            case .devtools: return "full Chrome DevTools access, including running scripts and "
                + "reading data on any site you are signed into"
            }
        }.joined(separator: "; ")
    }

    private func format(_ seconds: Int) -> String {
        seconds % 3600 == 0 ? "\(seconds / 3600) hour\(seconds == 3600 ? "" : "s")" :
            "\(max(1, seconds / 60)) minutes"
    }

    private func wrapping(_ text: String, size: CGFloat) -> NSTextField {
        let label = NSTextField(wrappingLabelWithString: text)
        label.font = .systemFont(ofSize: size)
        label.preferredMaxLayoutWidth = 420
        label.widthAnchor.constraint(equalToConstant: 420).isActive = true
        return label
    }

    private func button(_ title: String, _ action: Selector) -> NSButton {
        let button = NSButton(title: title, target: self, action: action)
        button.bezelStyle = .rounded
        button.keyEquivalent = ""
        return button
    }
}
