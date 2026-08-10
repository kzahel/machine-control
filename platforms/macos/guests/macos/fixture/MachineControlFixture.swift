import AppKit
import Foundation

final class InteractionSurface: NSView {
    var observe: ((String, NSEvent) -> Void)?
    private var tracking: NSTrackingArea?

    override var acceptsFirstResponder: Bool { true }
    override var intrinsicContentSize: NSSize { NSSize(width: 360, height: 120) }

    override func updateTrackingAreas() {
        if let tracking { removeTrackingArea(tracking) }
        let area = NSTrackingArea(
            rect: bounds,
            options: [.activeInKeyWindow, .inVisibleRect, .mouseMoved,
                      .mouseEnteredAndExited],
            owner: self,
            userInfo: nil
        )
        addTrackingArea(area)
        tracking = area
        super.updateTrackingAreas()
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.systemIndigo.withAlphaComponent(0.16).setFill()
        bounds.fill()
        NSColor.systemIndigo.setStroke()
        let border = NSBezierPath(roundedRect: bounds.insetBy(dx: 1, dy: 1),
                                  xRadius: 8, yRadius: 8)
        border.lineWidth = 2
        border.stroke()
        let message = "Resident visual fallback surface"
        let attributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 15, weight: .medium),
            .foregroundColor: NSColor.labelColor,
        ]
        let size = message.size(withAttributes: attributes)
        message.draw(at: NSPoint(x: (bounds.width - size.width) / 2,
                                 y: (bounds.height - size.height) / 2),
                     withAttributes: attributes)
    }

    override func mouseMoved(with event: NSEvent) { observe?("move", event) }
    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        observe?("down", event)
    }
    override func mouseDragged(with event: NSEvent) { observe?("drag", event) }
    override func mouseUp(with event: NSEvent) { observe?("up", event) }
    override func scrollWheel(with event: NSEvent) { observe?("scroll", event) }
}

final class FixtureController: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    private var count = 0
    private var enabled = false
    private var text = ""
    private var keyEventCount = 0
    private var lastKey = ""
    private var mouseMoveCount = 0
    private var mouseDownCount = 0
    private var mouseDragCount = 0
    private var mouseUpCount = 0
    private var scrollEventCount = 0
    private var scrollDeltaX = 0.0
    private var scrollDeltaY = 0.0
    private var lastPointerEvent = ""
    private var keyMonitor: Any?
    private var stateTimer: Timer?
    private let countLabel = NSTextField(labelWithString: "Count: 0")
    private let enabledLabel = NSTextField(labelWithString: "Enabled: false")
    private let textLabel = NSTextField(labelWithString: "Text: ")
    private let checkbox = NSButton(checkboxWithTitle: "Enabled", target: nil,
                                    action: nil)
    private let textField = NSTextField(string: "")
    private let interactionSurface = InteractionSurface()
    private weak var fixtureWindow: NSWindow?

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

        interactionSurface.setAccessibilityIdentifier("fixture.visual-surface")
        interactionSurface.setAccessibilityLabel("Visual fallback surface")
        interactionSurface.setAccessibilityRole(.group)
        interactionSurface.observe = { [weak self] kind, event in
            self?.observePointer(kind, event: event)
        }
        interactionSurface.widthAnchor.constraint(equalToConstant: 360).isActive = true
        interactionSurface.heightAnchor.constraint(equalToConstant: 120).isActive = true

        let stack = NSStackView(views: [
            countLabel, increment, checkbox, enabledLabel,
            textField, textLabel, interactionSurface, reset,
        ])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.edgeInsets = NSEdgeInsets(top: 24, left: 24, bottom: 24, right: 24)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 420, height: 520),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false
        )
        window.title = "Machine Control Fixture"
        window.setAccessibilityIdentifier("fixture.window")
        window.contentView = stack
        window.acceptsMouseMovedEvents = true
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(textField)
        NSApp.activate(ignoringOtherApps: true)
        fixtureWindow = window
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

    private func observePointer(_ kind: String, event: NSEvent) {
        switch kind {
        case "move": mouseMoveCount += 1
        case "down": mouseDownCount += 1
        case "drag": mouseDragCount += 1
        case "up": mouseUpCount += 1
        case "scroll":
            scrollEventCount += 1
            scrollDeltaX += event.scrollingDeltaX
            scrollDeltaY += event.scrollingDeltaY
        default: break
        }
        lastPointerEvent = kind
        persist()
    }

    private func surfaceBounds() -> [String: Double] {
        guard let window = fixtureWindow, let screen = window.screen else { return [:] }
        let inWindow = interactionSurface.convert(interactionSurface.bounds, to: nil)
        let inScreen = window.convertToScreen(inWindow)
        return [
            "x": Double(inScreen.minX),
            "y": Double(screen.frame.maxY - inScreen.maxY),
            "width": Double(inScreen.width),
            "height": Double(inScreen.height),
        ]
    }

    private func persist() {
        let object: [String: Any] = [
            "schema": "machine-control-macos-fixture/v0",
            "count": count,
            "enabled": enabled,
            "text": text,
            "keyEventCount": keyEventCount,
            "lastKey": lastKey,
            "mouseMoveCount": mouseMoveCount,
            "mouseDownCount": mouseDownCount,
            "mouseDragCount": mouseDragCount,
            "mouseUpCount": mouseUpCount,
            "scrollEventCount": scrollEventCount,
            "scrollDeltaX": scrollDeltaX,
            "scrollDeltaY": scrollDeltaY,
            "lastPointerEvent": lastPointerEvent,
            "surfaceBounds": surfaceBounds(),
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
