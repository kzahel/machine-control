import AppKit
import Foundation

final class FixtureController: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    private var count = 0
    private var enabled = false
    private var text = ""
    private var keyEventCount = 0
    private var lastKey = ""
    private var keyMonitor: Any?
    private var stateTimer: Timer?
    private let countLabel = NSTextField(labelWithString: "Count: 0")
    private let enabledLabel = NSTextField(labelWithString: "Enabled: false")
    private let textLabel = NSTextField(labelWithString: "Text: ")
    private let checkbox = NSButton(checkboxWithTitle: "Enabled", target: nil,
                                    action: nil)
    private let textField = NSTextField(string: "")

    private var stateURL: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("machine-control-fixture/state.json")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        countLabel.setAccessibilityIdentifier("fixture.count")
        enabledLabel.setAccessibilityIdentifier("fixture.enabled-state")
        textLabel.setAccessibilityIdentifier("fixture.text-state")

        let increment = NSButton(title: "Increment", target: self,
                                 action: #selector(increment(_:)))
        increment.setAccessibilityIdentifier("fixture.increment")
        checkbox.target = self
        checkbox.action = #selector(toggle(_:))
        checkbox.setAccessibilityIdentifier("fixture.enabled")
        textField.placeholderString = "Fixture text"
        textField.delegate = self
        textField.target = self
        textField.action = #selector(textChanged(_:))
        textField.setAccessibilityIdentifier("fixture.text")
        let reset = NSButton(title: "Reset", target: self,
                             action: #selector(reset(_:)))
        reset.setAccessibilityIdentifier("fixture.reset")

        let stack = NSStackView(views: [
            countLabel, increment, checkbox, enabledLabel,
            textField, textLabel, reset,
        ])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.edgeInsets = NSEdgeInsets(top: 24, left: 24, bottom: 24, right: 24)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 420, height: 360),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false
        )
        window.title = "Machine Control Fixture"
        window.setAccessibilityIdentifier("fixture.window")
        window.contentView = stack
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(textField)
        NSApp.activate(ignoringOtherApps: true)
        keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) {
            [weak self] event in
            self?.keyEventCount += 1
            self?.lastKey = event.charactersIgnoringModifiers ?? ""
            self?.persist()
            return event
        }
        stateTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) {
            [weak self] _ in
            guard let self, self.text != self.textField.stringValue else { return }
            self.text = self.textField.stringValue
            self.textLabel.stringValue = "Text: \(self.text)"
            self.persist()
        }
        persist()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    @objc private func increment(_ sender: Any?) {
        count += 1
        countLabel.stringValue = "Count: \(count)"
        persist()
    }

    @objc private func toggle(_ sender: NSButton) {
        enabled = sender.state == .on
        enabledLabel.stringValue = "Enabled: \(enabled)"
        persist()
    }

    @objc private func textChanged(_ sender: NSTextField) {
        text = sender.stringValue
        textLabel.stringValue = "Text: \(text)"
        persist()
    }

    func controlTextDidChange(_ notification: Notification) {
        guard let field = notification.object as? NSTextField else { return }
        textChanged(field)
    }

    @objc private func reset(_ sender: Any?) {
        count = 0
        enabled = false
        text = ""
        checkbox.state = .off
        textField.stringValue = ""
        countLabel.stringValue = "Count: 0"
        enabledLabel.stringValue = "Enabled: false"
        textLabel.stringValue = "Text: "
        persist()
    }

    private func persist() {
        let object: [String: Any] = [
            "schema": "machine-control-macos-fixture/v0",
            "count": count,
            "enabled": enabled,
            "text": text,
            "keyEventCount": keyEventCount,
            "lastKey": lastKey,
            "pid": ProcessInfo.processInfo.processIdentifier,
        ]
        guard let data = try? JSONSerialization.data(
            withJSONObject: object, options: [.sortedKeys]) else { return }
        let directory = stateURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700])
        try? data.write(to: stateURL, options: .atomic)
    }
}

let application = NSApplication.shared
let controller = FixtureController()
application.delegate = controller
application.setActivationPolicy(.regular)
application.run()
