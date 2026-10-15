import AppKit
import Foundation

// The only identity oracle is the incarnation owned by each actual NSButton.
// AXIdentifier names a logical slot, deliberately reused on replacement. The
// incarnation is exposed only in the independent file oracle. No native
// equality candidate uses identifiers, labels, sizes or tree offsets as keys.
final class IdentityButton: NSButton {
    let incarnation = "identity-control-" + UUID().uuidString.lowercased()
    let logical: String
    var onDeinit: ((String) -> Void)?
    init(logical: String, target: AnyObject, action: Selector) {
        self.logical = logical
        super.init(frame: .zero)
        title = "Identical control"
        self.target = target
        self.action = action
        bezelStyle = .rounded
        setAccessibilityIdentifier("identity-slot-" + logical)
        translatesAutoresizingMaskIntoConstraints = false
        widthAnchor.constraint(equalToConstant: 220).isActive = true
        heightAnchor.constraint(equalToConstant: 32).isActive = true
    }
    required init?(coder: NSCoder) { fatalError("not a storyboard fixture") }
    deinit { onDeinit?(incarnation) }
}

final class IdentityFixture: NSObject, NSApplicationDelegate {
    let root: URL
    let nonce: String
    let processIncarnation = UUID().uuidString.lowercased()
    var windowIncarnation = ""
    var window: NSWindow?
    var stack: NSStackView?
    var controls: [IdentityButton] = []
    var effects: [String: Int] = [:]
    var events: [[String: Any]] = []
    var lastCommand = ""
    var commandError: String?
    var revision = 0
    var timer: Timer?

    init(root: URL, nonce: String) { self.root = root; self.nonce = nonce }

    func event(_ kind: String, incarnation: String = "") {
        events.append(["sequence": events.count + 1, "kind": kind,
                       "incarnation": incarnation, "uptime": ProcessInfo.processInfo.systemUptime])
    }

    func makeControl(_ logical: String) -> IdentityButton {
        let button = IdentityButton(logical: logical, target: self, action: #selector(press(_:)))
        button.onDeinit = { [weak self] id in self?.event("deallocated", incarnation: id) }
        event("created", incarnation: button.incarnation)
        return button
    }

    func createWindow() {
        windowIncarnation = UUID().uuidString.lowercased()
        let next = NSWindow(contentRect: NSRect(x: 80, y: 100, width: 360, height: 360),
                            styleMask: [.titled, .closable], backing: .buffered, defer: false)
        next.isReleasedWhenClosed = false
        next.title = "Native Identity Fixture"
        next.setAccessibilityIdentifier("identity-window")
        let content = NSStackView()
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 8
        content.edgeInsets = NSEdgeInsets(top: 20, left: 20, bottom: 20, right: 20)
        controls = ["a", "b", "c"].map(makeControl)
        for button in controls { content.addArrangedSubview(button) }
        next.contentView = content
        stack = content
        window = next
        next.makeKeyAndOrderFront(nil)
        event("windowCreated", incarnation: windowIncarnation)
        layout()
    }

    func layout() {
        window?.contentView?.layoutSubtreeIfNeeded()
        window?.displayIfNeeded()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        createWindow()
        timer = Timer.scheduledTimer(withTimeInterval: 0.01, repeats: true) { [weak self] _ in self?.tick() }
        publish()
    }

    @objc func press(_ sender: IdentityButton) {
        effects[sender.incarnation, default: 0] += 1
        event("press", incarnation: sender.incarnation)
        publish()
    }

    func execute(_ command: [String: Any]) {
        commandError = nil
        switch command["operation"] as? String {
        case "barrier": break
        case "insert":
            let button = makeControl("inserted")
            controls.insert(button, at: 1)
            stack?.insertArrangedSubview(button, at: 1)
        case "reorder":
            controls.reverse()
            // removeArrangedSubview leaves each view in its superview. The
            // controls themselves survive; only layout/hierarchy order moves.
            for button in controls { stack?.removeArrangedSubview(button) }
            for (index, button) in controls.enumerated() { stack?.insertArrangedSubview(button, at: index) }
        case "replace", "remove":
            guard let logical = command["logical"] as? String,
                  let index = controls.firstIndex(where: { $0.logical == logical }) else {
                commandError = "logical_control_missing"; break
            }
            let old = controls.remove(at: index)
            stack?.removeArrangedSubview(old)
            old.removeFromSuperview()
            event("removed", incarnation: old.incarnation)
            if command["operation"] as? String == "replace" {
                let new = makeControl(logical)
                controls.insert(new, at: index)
                stack?.insertArrangedSubview(new, at: index)
            }
            // No manually posted AX destruction notification: measure what
            // AppKit actually emits after its NSButton is released.
        case "recreateWindow":
            event("windowClosed", incarnation: windowIncarnation)
            window?.close()
            window = nil; stack = nil; controls = []
            createWindow()
        case "quit":
            event("quit")
            publish()
            NSApp.terminate(nil)
        default: commandError = "unknown_operation"
        }
        revision += 1
        layout()
    }

    func tick() {
        if let bytes = try? Data(contentsOf: root.appendingPathComponent("command.json")),
           let command = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
           command["runNonce"] as? String == nonce,
           let id = command["id"] as? String, id != lastCommand {
            lastCommand = id
            execute(command)
        }
        publish()
    }

    func publish() {
        layout()
        let items: [[String: Any]] = controls.map { button in
            let local = button.convert(button.bounds, to: nil)
            let screen = window?.convertToScreen(local) ?? .zero
            return ["incarnation": button.incarnation, "logical": button.logical,
                    "identifier": "identity-slot-" + button.logical,
                    "label": button.title,
                    "frame": ["x": screen.origin.x, "y": screen.origin.y,
                              "width": screen.width, "height": screen.height]]
        }
        var state: [String: Any] = [
            "schema": "machine-control/native-identity-oracle/v1", "runNonce": nonce,
            "pid": ProcessInfo.processInfo.processIdentifier, "processIncarnation": processIncarnation,
            "windowIncarnation": windowIncarnation, "windowNumber": window?.windowNumber ?? -1,
            "items": items, "effects": effects, "events": events, "lastCommand": lastCommand,
            "revision": revision, "uptime": ProcessInfo.processInfo.systemUptime,
        ]
        if let commandError { state["commandError"] = commandError }
        do {
            let bytes = try JSONSerialization.data(withJSONObject: state, options: [.sortedKeys])
            try bytes.write(to: root.appendingPathComponent("state.json"), options: .atomic)
        } catch {
            fputs("fixture receipt write failed\n", stderr)
            NSApp.terminate(nil)
        }
    }
}

// Check before initializing NSApplication or creating any UI. The flag is an
// explicit operator assertion, not automatic proof that this OS is a guest.
let args = CommandLine.arguments
guard args.count == 6, args[1] == "--disposable-guest", args[2] == "--root",
      args[3].hasPrefix("/"), args[4] == "--run-nonce", UUID(uuidString: args[5]) != nil else {
    fputs("Requires --disposable-guest --root ABSOLUTE_DIR --run-nonce UUID; guest only\n", stderr)
    exit(64)
}
let fixture = IdentityFixture(root: URL(fileURLWithPath: args[3], isDirectory: true), nonce: args[5])
NSApplication.shared.delegate = fixture
NSApplication.shared.run()
