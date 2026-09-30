import AppKit
import ApplicationServices

/// What the person still has to do so Machine Control can work, as one
/// live checklist. None of these steps gives an agent access; they only let
/// macOS and Chrome carry out requests the person later approves.
struct SetupState: Equatable {
    enum Screen: Equatable {
        case allowed
        /// Allowed in System Settings, but this process only sees it after
        /// a restart.
        case allowedNeedsRestart
        case notAllowed
    }

    var accessibility: Bool
    var screen: Screen
    var browserConnected: Bool

    /// The two macOS permissions are required; the browser is optional.
    var requiredDone: Int { (accessibility ? 1 : 0) + (screen == .allowed ? 1 : 0) }
    static let requiredCount = 2
    var complete: Bool { requiredDone == SetupState.requiredCount }
}

/// macOS applies a new Screen Recording grant only to processes started after
/// it. A short-lived child of this application inherits its identity, so it
/// reports the current setting even while this process cannot see it yet.
func screenRecordingAllowedInFreshProcess() -> Bool {
    let probe = Process()
    probe.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
    probe.arguments = ["screen-capture-preflight"]
    let output = Pipe()
    probe.standardOutput = output
    probe.standardError = FileHandle.nullDevice
    do { try probe.run() } catch { return false }
    probe.waitUntilExit()
    let text = String(decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
    return probe.terminationStatus == 0 && text.trimmingCharacters(in: .whitespacesAndNewlines) == "true"
}

func currentSetupState(browserConnected: Bool, probeScreen: Bool) -> SetupState {
    let screen: SetupState.Screen
    if CGPreflightScreenCaptureAccess() {
        screen = .allowed
    } else if probeScreen && screenRecordingAllowedInFreshProcess() {
        screen = .allowedNeedsRestart
    } else {
        screen = .notAllowed
    }
    return SetupState(accessibility: AXIsProcessTrusted(), screen: screen,
                      browserConnected: browserConnected)
}

final class SetupWindowController: NSObject, NSWindowDelegate {
    static let reopenKey = "reopenSetupAfterRestart"
    static let extensionDirectory = "providers/chrome-extension"

    var browserConnected: () -> Bool = { false }
    var onChange: ((SetupState) -> Void)?

    private var window: NSWindow?
    private var timer: Timer?
    private var rows: [String: (status: NSTextField, button: NSButton)] = [:]
    private var summary: NSTextField?
    private var restartNote: NSTextField?
    private(set) var state = SetupState(accessibility: false, screen: .notAllowed, browserConnected: false)
    private var restarting = false

    var isVisible: Bool { window?.isVisible == true }

    func refresh(probeScreen: Bool = false) {
        let next = currentSetupState(browserConnected: browserConnected(), probeScreen: probeScreen)
        let changed = next != state
        state = next
        render()
        if changed { onChange?(state) }
        if state.screen == .allowedNeedsRestart && !restarting {
            restarting = true
            // Give the person a moment to see why the app is restarting.
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { relaunchResident(reopenSetup: true) }
        }
    }

    func show(activate: Bool = true, restarted: Bool = false) {
        if window == nil { build() }
        restartNote?.isHidden = !restarted
        refresh(probeScreen: true)
        window?.center()
        if activate {
            NSApp.activate(ignoringOtherApps: true)
            window?.makeKeyAndOrderFront(nil)
        } else {
            window?.orderFrontRegardless()
        }
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            // Probe with a fresh process only while waiting for that grant.
            self?.refresh(probeScreen: self?.state.screen == .notAllowed)
        }
    }

    func windowWillClose(_ notification: Notification) {
        timer?.invalidate()
        timer = nil
    }

    private func build() {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 10),
                              styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "Set Up Machine Control"
        window.isReleasedWhenClosed = false
        window.delegate = self

        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.edgeInsets = NSEdgeInsets(top: 20, left: 24, bottom: 20, right: 24)

        let intro = label("macOS asks for two separate permissions before any app can see or "
            + "operate the screen. Turning them on does not give agents access: each agent "
            + "still has to ask, and you approve or deny every request.", size: 13)
        stack.addArrangedSubview(intro)
        let summary = label("", size: 13, bold: true)
        stack.addArrangedSubview(summary)
        self.summary = summary
        let note = label("Machine Control restarted so the new permission takes effect. If "
            + "System Settings still offers to quit and reopen it, choose Later.", size: 12)
        note.textColor = .systemBlue
        note.isHidden = true
        stack.addArrangedSubview(note)
        restartNote = note

        stack.addArrangedSubview(row(
            id: "accessibility", title: "1. Accessibility",
            detail: "Lets Machine Control read buttons and text on screen and send clicks "
                + "and keystrokes. In the list, switch on Machine Control.",
            button: "Open Accessibility Settings", action: #selector(openAccessibility)))
        stack.addArrangedSubview(row(
            id: "screen", title: "2. Screen & System Audio Recording",
            detail: "Lets Machine Control see what is on screen. Switch on Machine Control; "
                + "it restarts itself automatically so the change takes effect.",
            button: "Open Screen Recording Settings", action: #selector(openScreenRecording)))
        stack.addArrangedSubview(row(
            id: "browser", title: "Optional: Chrome extension",
            detail: "Lets agents operate Chrome tabs when you allow browser access. In "
                + "chrome://extensions, turn on Developer mode, choose Load unpacked, and "
                + "select the extension folder.",
            button: "Copy Extension Folder Path", action: #selector(copyExtensionPath)))

        let done = NSButton(title: "Done", target: self, action: #selector(close))
        done.bezelStyle = .rounded
        done.keyEquivalent = "\r"
        stack.addArrangedSubview(done)

        window.contentView = stack
        window.setContentSize(stack.fittingSize)
        self.window = window
    }

    private func row(id: String, title: String, detail: String, button: String,
                     action: Selector) -> NSView {
        let heading = NSStackView()
        heading.orientation = .horizontal
        heading.spacing = 10
        heading.addArrangedSubview(label(title, size: 13, bold: true, width: nil))
        let status = label("", size: 13, width: nil)
        heading.addArrangedSubview(status)
        let control = NSButton(title: button, target: self, action: action)
        control.bezelStyle = .rounded
        let column = NSStackView()
        column.orientation = .vertical
        column.alignment = .leading
        column.spacing = 6
        column.addArrangedSubview(heading)
        column.addArrangedSubview(label(detail, size: 12, secondary: true))
        column.addArrangedSubview(control)
        rows[id] = (status, control)
        return column
    }

    private func render() {
        func mark(_ id: String, _ text: String, _ color: NSColor, buttonVisible: Bool) {
            rows[id]?.status.stringValue = text
            rows[id]?.status.textColor = color
            rows[id]?.button.isHidden = !buttonVisible
        }
        mark("accessibility", state.accessibility ? "✓ Allowed" : "Not allowed yet",
             state.accessibility ? .systemGreen : .systemOrange,
             buttonVisible: !state.accessibility)
        switch state.screen {
        case .allowed:
            mark("screen", "✓ Allowed", .systemGreen, buttonVisible: false)
        case .allowedNeedsRestart:
            mark("screen", "✓ Allowed — restarting to apply…", .systemGreen, buttonVisible: false)
        case .notAllowed:
            mark("screen", "Not allowed yet", .systemOrange, buttonVisible: true)
        }
        mark("browser", state.browserConnected ? "✓ Connected" : "Not connected",
             state.browserConnected ? .systemGreen : .secondaryLabelColor,
             buttonVisible: !state.browserConnected)
        summary?.stringValue = state.complete ?
            "Setup is complete. Machine Control is off until you approve a request." :
            "\(state.requiredDone) of \(SetupState.requiredCount) required permissions allowed."
        if let window, let content = window.contentView {
            window.setContentSize(content.fittingSize)
        }
    }

    @objc private func openAccessibility() {
        // Asking once makes macOS add Machine Control to the list.
        let promptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        _ = AXIsProcessTrustedWithOptions([promptKey: true] as CFDictionary)
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    }

    @objc private func openScreenRecording() {
        // The first request adds Machine Control to the list.
        _ = CGRequestScreenCaptureAccess()
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")
    }

    @objc private func copyExtensionPath() {
        let path = extensionPath()
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(path, forType: .string)
        rows["browser"]?.button.title = "Copied — paste it in Chrome's Load unpacked dialog"
    }

    @objc private func close() {
        window?.close()
    }

    private func extensionPath() -> String {
        // Development installs record the checkout they were built from.
        if let checkout = Bundle.main.object(forInfoDictionaryKey: "MCSourceCheckout") as? String,
           !checkout.isEmpty {
            return (checkout as NSString).appendingPathComponent(SetupWindowController.extensionDirectory)
        }
        return SetupWindowController.extensionDirectory
    }

    private func open(_ address: String) {
        if let url = URL(string: address) { NSWorkspace.shared.open(url) }
    }

    private func label(_ text: String, size: CGFloat, bold: Bool = false,
                       secondary: Bool = false, width: CGFloat? = 512) -> NSTextField {
        let field = width == nil ? NSTextField(labelWithString: text) :
            NSTextField(wrappingLabelWithString: text)
        field.font = bold ? .boldSystemFont(ofSize: size) : .systemFont(ofSize: size)
        if secondary { field.textColor = .secondaryLabelColor }
        if let width {
            field.preferredMaxLayoutWidth = width
            field.widthAnchor.constraint(equalToConstant: width).isActive = true
        }
        return field
    }
}

/// Restarts the resident so it sees new macOS permissions. Under its
/// LaunchAgent an unsuccessful exit makes launchd start it again.
func relaunchResident(reopenSetup: Bool) {
    UserDefaults.standard.set(reopenSetup, forKey: SetupWindowController.reopenKey)
    UserDefaults.standard.synchronize()
    if ProcessInfo.processInfo.environment["XPC_SERVICE_NAME"] == residentLabel {
        exit(75)
    }
    let relaunch = Process()
    relaunch.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    relaunch.arguments = ["-n", Bundle.main.bundlePath, "--args"] + Array(CommandLine.arguments.dropFirst())
    try? relaunch.run()
    exit(0)
}
