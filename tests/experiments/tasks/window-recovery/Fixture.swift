import AppKit
import Foundation

final class Fixture: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    let root = URL(fileURLWithPath: CommandLine.arguments[1])
    var target: NSWindow!
    var guardWindow: NSWindow!
    var targetField: NSTextField!
    let guardField = NSTextField(string: "DO NOT EDIT")
    var replacements = 0
    var focusChanges = 0
    var cursorChanges = 0
    var previousKey = ""
    var previousCursor = NSEvent.mouseLocation
    var timer: Timer?
    func makeWindow(_ title: String, _ x: CGFloat) -> NSWindow {
        let w = NSWindow(contentRect: NSRect(x:x,y:180,width:430,height:210),
                         styleMask:[.titled,.closable], backing:.buffered,defer:false)
        w.title = title; w.isReleasedWhenClosed = false
        return w
    }
    func writeState() {
        let state: [String:Any] = ["target":targetField?.stringValue ?? "",
            "protected":guardField.stringValue,"replacements":replacements,
            "focusChanges":focusChanges,"cursorChanges":cursorChanges]
        if let data = try? JSONSerialization.data(withJSONObject:state,options:.sortedKeys) {
            try? data.write(to:root.appendingPathComponent("state.json"),options:.atomic)
        }
    }
    func createTarget() {
        target = makeWindow("Target document",30)
        targetField = NSTextField(string: "Draft")
        targetField.setAccessibilityLabel("Target content");targetField.delegate = self
        let button = NSButton(title:"Replace editor",target:self,action:#selector(replace))
        let stack = NSStackView(views:[NSTextField(labelWithString:"Target document"),targetField,button])
        stack.orientation = .vertical;stack.spacing = 15
        stack.edgeInsets = NSEdgeInsets(top:25,left:25,bottom:25,right:25)
        target.contentView = stack;target.makeKeyAndOrderFront(nil)
    }
    @objc func replace() {
        target.close(); replacements += 1;createTarget();writeState()
    }
    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.regular)
        try? FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        createTarget()
        guardWindow = makeWindow("Protected document",500)
        guardField.setAccessibilityLabel("Protected content");guardField.delegate = self
        let stack = NSStackView(views:[NSTextField(labelWithString:"Leave this document unchanged"),guardField])
        stack.orientation = .vertical;stack.spacing = 15
        stack.edgeInsets = NSEdgeInsets(top:25,left:25,bottom:25,right:25)
        guardWindow.contentView = stack;guardWindow.makeKeyAndOrderFront(nil)
        guardWindow.makeFirstResponder(guardField);NSApp.activate(ignoringOtherApps:true)
        previousKey = NSApp.keyWindow?.title ?? ""
        timer = Timer.scheduledTimer(withTimeInterval:0.02,repeats:true) { [weak self] _ in
            guard let self = self else { return }
            let key = NSApp.keyWindow?.title ?? ""
            let cursor = NSEvent.mouseLocation
            if key != self.previousKey { self.focusChanges += 1; self.previousKey = key }
            if cursor != self.previousCursor { self.cursorChanges += 1; self.previousCursor = cursor }
            self.writeState()
        }
        writeState()
    }
    func controlTextDidChange(_ note: Notification) { writeState() }
}
let delegate = Fixture()
NSApplication.shared.delegate = delegate
NSApplication.shared.run()
