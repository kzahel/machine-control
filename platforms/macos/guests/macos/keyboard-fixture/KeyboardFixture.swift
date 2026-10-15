import AppKit
import WebKit
// Keyboard fixture: logs what each AppKit and web layer receives for
// synthesized keys, so layout and modifier behavior can be compared against
// the resident. Usage: KeyboardFixture [--web] [--log PATH]
let arguments = CommandLine.arguments
let logPath = arguments.firstIndex(of: "--log").map { arguments[$0 + 1] } ?? "/tmp/keyboard-fixture.jsonl"
let logURL = URL(fileURLWithPath: logPath)
func log(_ d: [String: Any]) {
    var d = d; d["t"] = Date().timeIntervalSince1970
    let line = (try! JSONSerialization.data(withJSONObject: d)) + Data("\n".utf8)
    if let h = try? FileHandle(forWritingTo: logURL) { h.seekToEndOfFile(); h.write(line); h.closeFile() } else { try? line.write(to: logURL) }
}
func describe(_ e: NSEvent) -> [String: Any] {
    ["keyCode": e.keyCode, "chars": e.characters ?? "", "ignoring": e.charactersIgnoringModifiers ?? "",
     "cmd": e.modifierFlags.contains(.command), "shift": e.modifierFlags.contains(.shift),
     "ctrl": e.modifierFlags.contains(.control), "opt": e.modifierFlags.contains(.option)]
}
final class Probe: NSTextView {
    override func performKeyEquivalent(with e: NSEvent) -> Bool { var d = describe(e); d["layer"] = "performKeyEquivalent"; log(d); return super.performKeyEquivalent(with: e) }
    override func keyDown(with e: NSEvent) { var d = describe(e); d["layer"] = "keyDown"; log(d); super.keyDown(with: e) }
}
final class Target: NSObject { @objc func fire(_ s: NSMenuItem) { log(["layer": "menu", "item": s.title]) } }
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let target = Target()
let main = NSMenu(); let appItem = NSMenuItem(); main.addItem(appItem)
let appMenu = NSMenu(); appMenu.addItem(withTitle: "Quit Keyboard Fixture", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); appItem.submenu = appMenu
let probeItem = NSMenuItem(); main.addItem(probeItem)
let probe = NSMenu(title: "Probe")
for k in ["l","n","w",",","t","y","g","i","b","e","."] {
    for shift in [false, true] {
        let item = NSMenuItem(title: "cmd\(shift ? "+shift" : "")+\(k)", action: #selector(Target.fire(_:)), keyEquivalent: k)
        item.keyEquivalentModifierMask = shift ? [.command, .shift] : [.command]; item.target = target; probe.addItem(item)
    }
}
probeItem.submenu = probe; app.mainMenu = main
let window = NSWindow(contentRect: NSRect(x: 200, y: 200, width: 520, height: 300), styleMask: [.titled, .closable], backing: .buffered, defer: false)
window.title = "Keyboard Fixture"
let scroll = NSScrollView(frame: window.contentView!.bounds); scroll.autoresizingMask = [.width, .height]
let view = Probe(frame: scroll.bounds); scroll.documentView = view; window.contentView = scroll
window.makeKeyAndOrderFront(nil); window.makeFirstResponder(view)
final class Bridge: NSObject, WKScriptMessageHandler {
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if var d = m.body as? [String: Any] { d["layer"] = "web"; log(d) }
    }
}
let bridge = Bridge()
let config = WKWebViewConfiguration()
config.userContentController.add(bridge, name: "probe")
let web = WKWebView(frame: NSRect(x: 0, y: 0, width: 520, height: 300), configuration: config)
web.loadHTMLString("<input id=f autofocus style='width:90%'><script>for (const t of ['keydown']) addEventListener(t, e => webkit.messageHandlers.probe.postMessage({type:t, key:e.key, code:e.code, meta:e.metaKey, shift:e.shiftKey}), true); document.getElementById('f').focus()</script>", baseURL: nil)
let webWindow = NSWindow(contentRect: NSRect(x: 760, y: 200, width: 520, height: 300), styleMask: [.titled, .closable], backing: .buffered, defer: false)
webWindow.title = "Keyboard Fixture Web"; webWindow.contentView = web
if CommandLine.arguments.contains("--web") { webWindow.makeKeyAndOrderFront(nil); webWindow.makeFirstResponder(web) }
app.activate(ignoringOtherApps: true)
log(["layer": "ready", "pid": ProcessInfo.processInfo.processIdentifier])
app.run()
