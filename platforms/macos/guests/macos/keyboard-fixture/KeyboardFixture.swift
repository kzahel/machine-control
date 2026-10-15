import AppKit
import WebKit

// Independent AppKit/WebKit oracle. A scratch command file controls only this
// fixture. Secure-field observations retain a match boolean, never its value.
let arguments = CommandLine.arguments
func argument(_ name: String, _ fallback: String) -> String { arguments.firstIndex(of:name).map { arguments[$0+1] } ?? fallback }
let logURL = URL(fileURLWithPath: argument("--log", "/tmp/keyboard-fixture.jsonl"))
let commandURL = URL(fileURLWithPath: argument("--commands", "/tmp/keyboard-fixture-command.json"))
let stateURL = URL(fileURLWithPath: argument("--state", "/tmp/keyboard-fixture-state.json"))
let dummy = "Fake2Pass!@#[]{}+-_=;:'\",.<>/?\\|`~"
var mode = "text", revision = 0, state: [String:Any] = [:]
func log(_ data: [String:Any]) {
    var data = data; data["t"] = Date().timeIntervalSince1970
    let line = (try! JSONSerialization.data(withJSONObject:data)) + Data("\n".utf8)
    if let h = try? FileHandle(forWritingTo:logURL) { h.seekToEndOfFile(); h.write(line); h.closeFile() }
    else { try? line.write(to:logURL) }
}
func writeState() {
    state["pid"] = getpid(); state["mode"] = mode; state["revision"] = revision
    try? JSONSerialization.data(withJSONObject:state).write(to:stateURL,options:.atomic)
}
func describe(_ e: NSEvent) -> [String:Any] {
    ["keyCode":e.keyCode,"chars":e.characters ?? "","ignoring":e.charactersIgnoringModifiers ?? "",
     "cmd":e.modifierFlags.contains(.command),"shift":e.modifierFlags.contains(.shift),
     "ctrl":e.modifierFlags.contains(.control),"opt":e.modifierFlags.contains(.option)]
}
final class Probe: NSTextView {
    override func performKeyEquivalent(with e: NSEvent) -> Bool { var d=describe(e); d["layer"]="performKeyEquivalent"; log(d); return super.performKeyEquivalent(with:e) }
    override func keyDown(with e: NSEvent) { var d=describe(e); d["layer"]="keyDown"; log(d); super.keyDown(with:e) }
    override func didChangeText() { super.didChangeText(); state["text"]=string; writeState() }
    override func mouseDown(with e: NSEvent) { log(["layer":"pointer","flags":e.modifierFlags.rawValue]); super.mouseDown(with:e) }
    override func scrollWheel(with e: NSEvent) { log(["layer":"scroll","flags":e.modifierFlags.rawValue]); super.scrollWheel(with:e) }
}
final class Target: NSObject, NSTextFieldDelegate {
    @objc func fire(_ sender: NSMenuItem) { log(["layer":"menu","item":sender.title]); state["menu"]=sender.title; writeState() }
    func controlTextDidChange(_ notification: Notification) { state["secureMatches"] = secure.stringValue == dummy; writeState() }
}
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let target = Target()
let main = NSMenu(), appItem = NSMenuItem(); main.addItem(appItem)
let appMenu = NSMenu(); appMenu.addItem(withTitle:"Quit Keyboard Fixture",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q"); appItem.submenu=appMenu
let probeItem = NSMenuItem(); main.addItem(probeItem)
let probe = NSMenu(title:"Probe")
for key in ["l","n","w",",","t","y","g","i","b","e",".","]","?","+"] {
    for shifted in [false,true] {
        let item=NSMenuItem(title:"cmd\(shifted ? "+shift" : "")+\(key)",action:#selector(Target.fire(_:)),keyEquivalent:key)
        item.keyEquivalentModifierMask=shifted ? [.command,.shift] : [.command]; item.target=target; probe.addItem(item)
    }
}
for (name,flags) in [("option",NSEvent.ModifierFlags.option),("ctrl",.control)] {
    let item=NSMenuItem(title:"cmd+\(name)+l",action:#selector(Target.fire(_:)),keyEquivalent:"l")
    item.keyEquivalentModifierMask=[.command,flags]; item.target=target; probe.addItem(item)
}
probeItem.submenu=probe
let editItem=NSMenuItem(); main.addItem(editItem)
let edit=NSMenu(title:"Edit")
for (title,action,key) in [("Select All","selectAll:","a"),("Copy","copy:","c"),("Paste","paste:","v"),("Cut","cut:","x"),("Undo","undo:","z")] {
    edit.addItem(withTitle:title,action:Selector(action),keyEquivalent:key)
}
editItem.submenu=edit; app.mainMenu=main
let window=NSWindow(contentRect:NSRect(x:100,y:150,width:600,height:320),styleMask:[.titled,.closable],backing:.buffered,defer:false)
window.title="Keyboard Fixture"
let container=NSView(frame:window.contentView!.bounds); window.contentView=container
let scroll=NSScrollView(frame:container.bounds); scroll.autoresizingMask=[.width,.height]
let view=Probe(frame:scroll.bounds); view.isRichText=false; view.isAutomaticQuoteSubstitutionEnabled=false; view.isAutomaticDashSubstitutionEnabled=false; view.allowsUndo=true
scroll.documentView=view; container.addSubview(scroll)
let secure=NSSecureTextField(frame:NSRect(x:30,y:220,width:500,height:30)); secure.delegate=target; secure.isHidden=true; container.addSubview(secure)
final class Bridge: NSObject, WKScriptMessageHandler {
    func userContentController(_ controller:WKUserContentController,didReceive message:WKScriptMessage) {
        if var data=message.body as? [String:Any] { data["layer"]="web"; log(data); if let text=data["text"] { state["webText"]=text; writeState() } }
    }
}
let bridge=Bridge(), config=WKWebViewConfiguration(); config.userContentController.add(bridge,name:"probe")
let web=WKWebView(frame:container.bounds,configuration:config); web.autoresizingMask=[.width,.height]; web.isHidden=true; container.addSubview(web)
web.loadHTMLString("<input id=f autofocus style='width:90%'><script>for(const t of ['keydown','keyup'])addEventListener(t,e=>webkit.messageHandlers.probe.postMessage({type:t,key:e.key,code:e.code,meta:e.metaKey,shift:e.shiftKey,ctrl:e.ctrlKey,opt:e.altKey}),true);f.oninput=()=>webkit.messageHandlers.probe.postMessage({text:f.value});</script>",baseURL:nil)
window.makeKeyAndOrderFront(nil); window.makeFirstResponder(view); app.activate(ignoringOtherApps:true)
var lastCommand=Data()
let timer=Timer.scheduledTimer(withTimeInterval:0.05,repeats:true) { _ in
    guard let data=try? Data(contentsOf:commandURL),data != lastCommand,
          let command=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else { return }
    lastCommand=data; revision=command["revision"] as? Int ?? revision+1
    mode=command["mode"] as? String ?? "text"
    state=["pid":getpid(),"text":"","secureMatches":false]
    scroll.isHidden=mode != "text"; secure.isHidden=mode != "secure"; web.isHidden=mode != "web"
    view.string=""; secure.stringValue=""
    window.makeKeyAndOrderFront(nil); app.activate(ignoringOtherApps:true)
    if mode == "web" { window.makeFirstResponder(web); web.evaluateJavaScript("f.value='';f.focus()") }
    else { window.makeFirstResponder(mode == "secure" ? secure : view) }
    if let text=command["text"] as? String,mode == "text" { view.string=text; view.setSelectedRange(NSRange(location:text.utf16.count,length:0)); state["text"]=text }
    log(["layer":"configured","revision":revision,"mode":mode]); writeState()
}
log(["layer":"ready","pid":getpid()]); writeState(); app.run()
