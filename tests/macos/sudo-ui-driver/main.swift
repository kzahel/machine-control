// Dedicated-appliance fixture only. Build with Native.swift and give this
// transient app native Accessibility consent; never deploy on a workstation.
// The password is read only after exact helper/code/field discovery succeeds.
import AppKit
import ApplicationServices
import Darwin
import Foundation

func stop(_ reason: String) -> Never {
    FileHandle.standardError.write(Data("sudo fixture: \(reason)\n".utf8))
    exit(1)
}

func value(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var result: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &result) == .success else { return nil }
    return result
}

func descendants(_ root: AXUIElement, depth: Int = 0) -> [AXUIElement] {
    guard depth < 12 else { return [] }
    return [root] + ((value(root, kAXChildrenAttribute) as? [AXUIElement]) ?? [])
        .flatMap { descendants($0, depth: depth + 1) }
}

let args = Array(CommandLine.arguments.dropFirst())
if args == ["permission"] {
    let prompt = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
    print(AXIsProcessTrustedWithOptions([prompt: true] as CFDictionary) ? "trusted" : "untrusted")
    exit(0)
}
guard args.count == 3, ["inspect", "cancel", "authenticate", "interrupt"].contains(args[0]),
      let pid = Int32(args[1]), AXIsProcessTrusted() else { stop("trusted driver and exact helper PID required") }
let helper = URL(fileURLWithPath: args[2]).resolvingSymlinksInPath()
guard helper.lastPathComponent == "mc-sudo-askpass",
      helper.path.withCString({ sameCode(pid, $0) }) == 1,
      let pointer = processJSON(pid) else { stop("helper identity mismatch") }
let process = try JSONSerialization.jsonObject(with: Data(String(cString: pointer).utf8)) as! [String: Any]
free(pointer)
guard let sudoPID = process["parent"] as? Int32,
      "/usr/bin/sudo".withCString({ sameCode(sudoPID, $0) }) == 1,
      let sudoPointer = processJSON(sudoPID) else { stop("system sudo parent missing") }
let sudoProcess = try JSONSerialization.jsonObject(with: Data(String(cString: sudoPointer).utf8)) as! [String: Any]
free(sudoPointer)
let wrapper = helper.deletingLastPathComponent().appendingPathComponent("mc-sudo")
guard let wrapperPID = sudoProcess["parent"] as? Int32,
      wrapper.path.withCString({ sameCode(wrapperPID, $0) }) == 1 else { stop("original wrapper missing") }
let app = NSRunningApplication(processIdentifier: pid)
let elements = descendants(AXUIElementCreateApplication(pid))
let labels = elements.flatMap { element in
    [kAXTitleAttribute, kAXValueAttribute, kAXDescriptionAttribute]
        .compactMap { value(element, $0) as? String }
}
guard labels.contains("Run this command as administrator?") else { stop("authentication prompt fingerprint missing") }
let fields = elements.filter {
    value($0, kAXRoleAttribute) as? String == kAXTextFieldRole &&
    value($0, kAXSubroleAttribute) as? String == kAXSecureTextFieldSubrole &&
    value($0, kAXIdentifierAttribute) as? String == "mc-sudo-password"
}
let buttons = elements.filter { value($0, kAXRoleAttribute) as? String == kAXButtonRole }
guard fields.count == 1,
      let confirm = buttons.first(where: { value($0, kAXTitleAttribute) as? String == "Authenticate" }),
      let cancel = buttons.first(where: { value($0, kAXTitleAttribute) as? String == "Cancel" }) else { stop("unique secure field and buttons required") }
if args[0] == "inspect" { print("verified native sudo dialog"); exit(0) }
if args[0] == "interrupt" {
    guard kill(wrapperPID, SIGTERM) == 0 else { stop("wrapper signal failed") }
    print("wrapper termination delivered"); exit(0)
}
if args[0] == "cancel" {
    guard AXUIElementPerformAction(cancel, kAXPressAction as CFString) == .success else { stop("cancel delivery failed") }
    print("cancel delivered"); exit(0)
}
guard app?.activate(options: [.activateIgnoringOtherApps]) == true,
      AXUIElementSetAttributeValue(fields[0], kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success else { stop("secure field focus failed") }
// Dedicated non-echoing stdin secret transport. No secret enters arguments,
// JSON, environment, temporary files, screenshots, or result values.
var secret = FileHandle.standardInput.readDataToEndOfFile()
defer { secret.resetBytes(in: 0..<secret.count) }
if secret.last == 10 { secret.removeLast() }
if secret.last == 13 { secret.removeLast() }
guard !secret.isEmpty, secret.count <= 256, let text = String(data: secret, encoding: .utf8) else { stop("credential encoding rejected") }
var units = Array(text.utf16)
defer { _ = units.withUnsafeMutableBytes { memset_s($0.baseAddress, $0.count, 0, $0.count) } }
for var unit in units {
    for down in [true, false] {
        guard let event = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: down) else { stop("keyboard event unavailable") }
        event.keyboardSetUnicodeString(stringLength: 1, unicodeString: &unit)
        event.postToPid(pid)
    }
}
usleep(100_000)
guard AXUIElementPerformAction(confirm, kAXPressAction as CFString) == .success else { stop("authentication delivery failed") }
print("credential delivered through native secure field")
