import AppKit
import Foundation

// Independent foreground and keyboard oracle. Run only in a dedicated VM.
final class Sentinel: NSObject, NSApplicationDelegate {
    let root = URL(fileURLWithPath: CommandLine.arguments[1])
    let field = NSTextField(string: "")
    var window: NSWindow!
    var timer: Timer?
    var changes = 0
    var previous: pid_t = 0
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        window = NSWindow(contentRect: NSRect(x: 40, y: 40, width: 350, height: 130),
                          styleMask: [.titled], backing: .buffered, defer: false)
        window.title = "Browser focus sentinel"
        field.frame = NSRect(x: 20, y: 45, width: 300, height: 30)
        window.contentView!.addSubview(field)
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(field)
        NSApp.activate(ignoringOtherApps: true)
        timer = Timer.scheduledTimer(withTimeInterval: 0.02, repeats: true) { [self] _ in
            let front = NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0
            if front != previous { changes += 1; previous = front }
            let point = NSEvent.mouseLocation
            let state: [String: Any] = ["pid": ProcessInfo.processInfo.processIdentifier,
                "frontPid": front, "keyWindow": window.isKeyWindow, "text": field.stringValue,
                "foregroundChanges": changes, "cursor": [point.x, point.y]]
            try! JSONSerialization.data(withJSONObject: state).write(to: root, options: .atomic)
        }
    }
}
let app = NSApplication.shared
let delegate = Sentinel()
app.delegate = delegate
app.run()
