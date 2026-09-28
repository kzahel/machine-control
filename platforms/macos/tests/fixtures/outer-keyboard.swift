import AppKit
import Foundation

// Disposable guest-only oracle. No input injection or Accessibility permission.
final class KeyboardOracle: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    let field = NSTextField(string: "")
    let secureField = NSSecureTextField(string: "")
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 600, height: 160),
                          styleMask: [.titled, .closable], backing: .buffered,
                          defer: false)
    let root = URL(fileURLWithPath: CommandLine.arguments[1])
    var commands = 0
    var shiftedCommands = 0
    var timer: Timer?
    var lastState: Data?

    func persist() {
        let data = try! JSONSerialization.data(withJSONObject: [
            "text": field.stringValue,
            "active": NSApp.isActive && window.isKeyWindow,
            "focusedField": field.currentEditor() != nil ? "text" :
                (secureField.currentEditor() != nil ? "secure" : "none"),
            "commands": commands,
            "shiftedCommands": shiftedCommands,
            "secureMatches": secureField.stringValue == "AbC!@Z",
        ], options: [.sortedKeys])
        if data != lastState {
            try! data.write(to: root.appendingPathComponent("state.json"), options: .atomic)
            lastState = data
        }
    }

    @objc func command(_ sender: Any?) { commands += 1; persist() }
    @objc func shiftedCommand(_ sender: Any?) { shiftedCommands += 1; persist() }
    @objc func focusSecure(_ sender: Any?) {
        window.makeFirstResponder(secureField)
        persist()
    }
    func controlTextDidChange(_ notification: Notification) { persist() }

    func applicationDidFinishLaunching(_ notification: Notification) {
        try! String(ProcessInfo.processInfo.processIdentifier).write(
            to: root.appendingPathComponent("pid"), atomically: true, encoding: .utf8)
        let menu = NSMenu()
        let top = NSMenuItem()
        let actions = NSMenu()
        for (title, selector, modifiers) in [
            ("Command effect", #selector(command(_:)), NSEvent.ModifierFlags.command),
            ("Shift Command effect", #selector(shiftedCommand(_:)), [.command, .shift]),
        ] {
            let item = NSMenuItem(title: title, action: selector, keyEquivalent: "k")
            item.keyEquivalentModifierMask = modifiers
            item.target = self
            actions.addItem(item)
        }
        let secure = NSMenuItem(title: "Focus dummy secure field",
                                action: #selector(focusSecure(_:)), keyEquivalent: "j")
        secure.keyEquivalentModifierMask = .command
        secure.target = self
        actions.addItem(secure)
        top.submenu = actions
        menu.addItem(top)
        NSApp.mainMenu = menu
        field.frame = NSRect(x: 20, y: 60, width: 560, height: 30)
        field.delegate = self
        secureField.frame = NSRect(x: 20, y: 20, width: 560, height: 30)
        secureField.delegate = self
        window.contentView!.addSubview(secureField)
        window.contentView!.addSubview(field)
        window.title = "Outer Keyboard Oracle — non-secret test text"
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(field)
        NSApp.activate(ignoringOtherApps: true)
        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [self] _ in
            let reset = root.appendingPathComponent("reset")
            if FileManager.default.fileExists(atPath: reset.path) {
                try! FileManager.default.removeItem(at: reset)
                field.stringValue = ""
                secureField.stringValue = ""
                commands = 0
                shiftedCommands = 0
                window.makeFirstResponder(field)
                persist()
            }
            persist()
        }
        persist()
    }
}
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let oracle = KeyboardOracle()
app.delegate = oracle
app.run()
