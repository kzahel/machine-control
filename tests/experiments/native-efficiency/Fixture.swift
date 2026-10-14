import AppKit
import Foundation

// Independent event oracle for an owned disposable test application.
final class ObservedButton: NSButton {
    var record: ((String) -> Void)?
    override func accessibilityPerformPress() -> Bool {
        record?("accessibilityPress")
        return super.accessibilityPerformPress()
    }
    override func mouseDown(with event: NSEvent) {
        record?("buttonMouseDown")
        super.mouseDown(with: event)
    }
}
final class PointerSurface: NSView {
    var record: ((String) -> Void)?
    override func draw(_ rect: NSRect) {
        NSColor.systemBlue.setFill(); bounds.fill()
        ("Pointer only" as NSString).draw(at: NSPoint(x: 10, y: 20),
            withAttributes: [.foregroundColor: NSColor.white])
    }
    override func mouseDown(with event: NSEvent) { record?("pointerDown") }
    override func mouseUp(with event: NSEvent) { record?("pointerUp") }
}
final class Fixture: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    let root: URL
    let sentinel: Bool
    var window: NSWindow!
    let field = NSTextField(string: "")
    let status = NSTextField(labelWithString: "Revision 0")
    let rows = NSStackView()
    var counters: [String: Int] = [:]
    var revision = 0
    var events: [[String: Any]] = []
    var lastCommand = ""
    var timer: Timer?
    var updates: Timer?
    var monitor: Any?
    var generation = 0
    var previousPoint = NSEvent.mouseLocation
    var previousFront: pid_t = 0
    var sheet: NSWindow?
    init(root: URL, sentinel: Bool) { self.root = root; self.sentinel = sentinel }
    func record(_ name: String) {
        counters[name, default: 0] += 1
        events.append(["kind": name, "uptime": ProcessInfo.processInfo.systemUptime,
                       "revision": revision])
        if events.count > 2000 { events.removeFirst(events.count - 2000) }
    }
    func button(_ name: String, _ action: Selector) -> NSButton {
        let b = ObservedButton(title: name, target: self, action: action)
        b.record = { [weak self] in self?.record($0) }
        return b
    }
    func applicationDidFinishLaunching(_ note: Notification) {
        try! FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        NSApp.setActivationPolicy(.regular)
        let main = NSMenu()
        let entry = NSMenuItem(title: "Fixture", action: nil, keyEquivalent: "")
        main.addItem(entry)
        let menu = NSMenu(title: "Fixture")
        menu.addItem(withTitle: "Increment from menu", action: #selector(increment), keyEquivalent: "i").target = self
        menu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        entry.submenu = menu; NSApp.mainMenu = main
        field.placeholderString = "Probe text"; field.delegate = self
        field.setAccessibilityLabel("Probe text")
        let pointer = PointerSurface(frame: NSRect(x: 0, y: 0, width: 200, height: 65))
        pointer.setAccessibilityElement(true); pointer.setAccessibilityRole(.group)
        pointer.setAccessibilityLabel("Pointer only")
        pointer.record = { [weak self] in self?.record($0) }
        pointer.heightAnchor.constraint(equalToConstant: 65).isActive = true
        pointer.widthAnchor.constraint(equalToConstant: 200).isActive = true
        let top = NSStackView(views: [status, field, button("Increment", #selector(increment)),
            button("Show sheet", #selector(showSheet)),
            button("Delayed update", #selector(delayed)), button("Burst updates", #selector(burst)),
            button("Continuous updates", #selector(continuous)), pointer])
        top.orientation = .vertical; top.spacing = 8; top.alignment = .leading
        rows.orientation = .vertical; rows.alignment = .leading
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 400, height: 280))
        scroll.hasVerticalScroller = true; scroll.documentView = rows
        scroll.heightAnchor.constraint(equalToConstant: 280).isActive = true
        top.addArrangedSubview(scroll)
        top.edgeInsets = NSEdgeInsets(top: 15, left: 15, bottom: 15, right: 15)
        window = NSWindow(contentRect: NSRect(x: sentinel ? 620 : 30, y: 100, width: 470, height: 600),
            styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        window.title = sentinel ? "Efficiency Sentinel" : "Efficiency Target"
        window.contentView = top
        rebuild(20)
        window.makeKeyAndOrderFront(nil); window.makeFirstResponder(field)
        NSApp.activate(ignoringOtherApps: true)
        monitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp, .leftMouseDown, .leftMouseUp]) {
            [weak self] event in
            self?.record("event-\(event.type.rawValue)")
            return event
        }
        timer = Timer.scheduledTimer(withTimeInterval: 0.02, repeats: true) { [weak self] _ in self?.tick() }
        record("launched"); tick()
    }
    func rebuild(_ count: Int) {
        for v in rows.arrangedSubviews { rows.removeArrangedSubview(v); v.removeFromSuperview() }
        for i in 0..<count {
            let label = NSTextField(labelWithString: "Row \(i) value \(i * 7)")
            rows.addArrangedSubview(label)
        }
        rows.frame = NSRect(x: 0, y: 0, width: 390, height: max(280, count * 22))
        record("rebuild")
    }
    @objc func increment() {
        revision += 1; status.stringValue = "Revision \(revision)"
        NSAccessibility.post(element: status, notification: .valueChanged)
        record("increment")
    }
    @objc func showSheet() {
        guard sheet == nil else { return }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 260, height: 100),
                         styleMask: [.titled], backing: .buffered, defer: false)
        w.contentView = button("Close probe sheet", #selector(closeSheet))
        sheet = w; window.beginSheet(w); record("sheetOpened")
    }
    @objc func closeSheet() {
        if let w = sheet { window.endSheet(w); w.orderOut(nil); sheet = nil; record("sheetClosed") }
    }
    @objc func delayed() { scheduleUpdates(delay: 0.35, interval: 0.05, count: 1) }
    @objc func burst() { scheduleUpdates(delay: 0.02, interval: 0.05, count: 8) }
    @objc func continuous() { scheduleUpdates(delay: 0.02, interval: 0.03, count: 100) }
    func scheduleUpdates(delay: Double, interval: Double, count: Int) {
        generation += 1; updates?.invalidate()
        let token = generation
        var remaining = count
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, token == self.generation else { return }
            self.increment(); remaining -= 1
            if remaining > 0 {
                self.updates = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] t in
                    guard let self, token == self.generation else { t.invalidate(); return }
                    self.increment(); remaining -= 1
                    if remaining <= 0 { t.invalidate() }
                }
            }
        }
    }
    func controlTextDidChange(_ note: Notification) { record("textChanged") }
    func tick() {
        let commandURL = root.appendingPathComponent("command.json")
        if let data = try? Data(contentsOf: commandURL),
           let cmd = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let id = cmd["id"] as? String, id != lastCommand {
            lastCommand = id
            switch cmd["operation"] as? String {
            case "foreground":
                window.makeKeyAndOrderFront(nil); window.makeFirstResponder(field)
                NSApp.activate(ignoringOtherApps: true)
            case "reset":
                generation += 1; updates?.invalidate(); updates = nil
                counters = [:]; events = []; field.stringValue = ""; revision = 0
                status.stringValue = "Revision 0"; closeSheet()
            case "rows": rebuild(cmd["count"] as? Int ?? 20)
            case "updates":
                scheduleUpdates(delay: cmd["delay"] as? Double ?? 0.2,
                                interval: cmd["interval"] as? Double ?? 0.05,
                                count: cmd["count"] as? Int ?? 1)
            default: break
            }
            record("command")
        }
        let point = NSEvent.mouseLocation
        let front = NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0
        if point != previousPoint { record("cursorMoved"); previousPoint = point }
        if front != previousFront { record("foregroundChanged"); previousFront = front }
        let state: [String: Any] = ["uptime": ProcessInfo.processInfo.systemUptime,
            "pid": ProcessInfo.processInfo.processIdentifier, "frontPid": front,
            "keyWindow": window.isKeyWindow, "revision": revision, "text": field.stringValue,
            "cursor": [point.x, point.y], "counters": counters, "events": events,
            "lastCommand": lastCommand, "sheetVisible": sheet != nil,
            "clipboardChangeCount": NSPasteboard.general.changeCount]
        if let data = try? JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]) {
            try? data.write(to: root.appendingPathComponent("state.json"), options: .atomic)
        }
    }
}
let args = CommandLine.arguments
let root = URL(fileURLWithPath: args[1], isDirectory: true)
let delegate = Fixture(root: root, sentinel: args.contains("--sentinel"))
NSApplication.shared.delegate = delegate
NSApplication.shared.run()
