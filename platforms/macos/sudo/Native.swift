import AppKit
import CoreGraphics
import Darwin
import Foundation
import Security

@_silgen_name("proc_pidpath")
private func processPath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer, _ size: UInt32) -> Int32

@_silgen_name("csops")
private func signingStatus(_ pid: Int32, _ operation: UInt32, _ buffer: UnsafeMutableRawPointer, _ size: Int) -> Int32

private func information(_ pid: pid_t) -> kinfo_proc? {
    var info = kinfo_proc()
    var size = MemoryLayout<kinfo_proc>.stride
    var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
    guard pid > 0, sysctl(&mib, 4, &info, &size, nil, 0) == 0, size > 0 else { return nil }
    return info
}

@_cdecl("mc_sudo_process")
public func processJSON(_ pid: Int32) -> UnsafeMutablePointer<CChar>? {
    guard let info = information(pid) else { return nil }
    var buffer = [UInt8](repeating: 0, count: 4 * Int(MAXPATHLEN))
    let count = processPath(pid, &buffer, UInt32(buffer.count))
    guard count > 0 else { return nil }
    let start = info.kp_proc.p_un.__p_starttime
    let value: [String: Any] = ["pid": Int(pid), "parent": Int(info.kp_eproc.e_ppid),
        "uid": Int(info.kp_eproc.e_ucred.cr_uid), "started": "\(start.tv_sec):\(start.tv_usec)",
        "path": String(decoding: buffer.prefix(Int(count)), as: UTF8.self)]
    guard let data = try? JSONSerialization.data(withJSONObject: value),
          let text = String(data: data, encoding: .utf8) else { return nil }
    return strdup(text)
}

@_cdecl("mc_sudo_peer")
public func peerPID(_ fd: Int32) -> Int32 {
    var pid: pid_t = 0
    var size = socklen_t(MemoryLayout<pid_t>.size)
    guard getsockopt(fd, SOL_LOCAL, LOCAL_PEERPID, &pid, &size) == 0 else { return 0 }
    return pid
}

@_cdecl("mc_sudo_same_code")
public func sameCode(_ pid: Int32, _ path: UnsafePointer<CChar>) -> Int32 {
    let url = URL(fileURLWithPath: String(cString: path))
    var buffer = [UInt8](repeating: 0, count: 4 * Int(MAXPATHLEN))
    let count = processPath(pid, &buffer, UInt32(buffer.count))
    guard count > 0,
          URL(fileURLWithPath: String(decoding: buffer.prefix(Int(count)), as: UTF8.self)).resolvingSymlinksInPath()
            == url.resolvingSymlinksInPath() else { return 0 }
    if url.path == "/usr/bin/sudo" {
        // System sudo is mode 4511: a normal user cannot read its signature
        // from disk. CS_OPS_STATUS obtains kernel signing state without reading
        // the executable. Constants come from Apple's XNU cs_blobs.h.
        let validPlatformSignature: UInt32 = 0x00000001 | 0x04000000 | 0x20000000
        var flags: UInt32 = 0
        var attributes = stat()
        guard signingStatus(pid, 0, &flags, MemoryLayout<UInt32>.size) == 0,
              flags & validPlatformSignature == validPlatformSignature,
              flags & 0x10000000 == 0, // CS_DEBUGGED is never acceptable.
              lstat("/usr/bin/sudo", &attributes) == 0,
              attributes.st_uid == 0, attributes.st_mode & 0o022 == 0,
              attributes.st_mode & 0o4000 != 0,
              information(pid)?.kp_eproc.e_ucred.cr_uid == 0 else { return 0 }
        return 1
    }
    var expected: SecStaticCode?
    var requirement: SecRequirement?
    var actual: SecCode?
    let created = SecStaticCodeCreateWithPath(url as CFURL, [], &expected)
    guard created == errSecSuccess, let expected else { return -1 }
    let staticStatus = SecStaticCodeCheckValidity(expected, SecCSFlags(rawValue: kSecCSStrictValidate), nil)
    guard staticStatus == errSecSuccess else { return -2 }
    let requirementStatus = SecCodeCopyDesignatedRequirement(expected, [], &requirement)
    guard requirementStatus == errSecSuccess, let requirement else { return -3 }
    let guestStatus = SecCodeCopyGuestWithAttributes(nil, [kSecGuestAttributePid: pid] as CFDictionary, [], &actual)
    guard guestStatus == errSecSuccess, let actual else { return -4 }
    let dynamicStatus = SecCodeCheckValidity(actual, SecCSFlags(rawValue: kSecCSStrictValidate), requirement)
    guard dynamicStatus == errSecSuccess else { return -5 }
    do {
        var own: SecCode?
        var ownStatic: SecStaticCode?
        var ownInfo: CFDictionary?
        var expectedInfo: CFDictionary?
        guard SecCodeCopySelf([], &own) == errSecSuccess, let own,
              SecCodeCopyStaticCode(own, [], &ownStatic) == errSecSuccess, let ownStatic,
              SecCodeCopySigningInformation(ownStatic, [], &ownInfo) == errSecSuccess,
              SecCodeCopySigningInformation(expected, [], &expectedInfo) == errSecSuccess else { return 0 }
        let ownTeam = (ownInfo as? [String: Any])?[kSecCodeInfoTeamIdentifier as String] as? String
        let expectedTeam = (expectedInfo as? [String: Any])?[kSecCodeInfoTeamIdentifier as String] as? String
        guard ownTeam == expectedTeam else { return 0 }
    }
    // A designated requirement alone can match several releases. The peer
    // must also execute the exact sibling path belonging to this installation.
    return 1
}

private func usableDesktop() -> Bool {
    guard let session = CGSessionCopyCurrentDictionary() as? [String: Any],
          session[kCGSessionOnConsoleKey as String] as? Bool == true,
          session[kCGSessionLoginDoneKey as String] as? Bool == true,
          (session[kCGSessionUserIDKey as String] as? NSNumber)?.uint32Value == getuid(),
          session["CGSSessionScreenIsLocked"] as? Bool != true else { return false }
    return true
}

@_cdecl("mc_sudo_prompt")
public func passwordPrompt(_ input: UnsafePointer<CChar>, _ sudoPID: Int32, _ seconds: Int32) -> Int32 {
    guard usableDesktop(), seconds > 0,
          let context = try? JSONSerialization.jsonObject(with: Data(String(cString: input).utf8)) as? [String: Any],
          let command = context["command"] as? [String], !command.isEmpty,
          let cwd = context["cwd"] as? String,
          let requester = context["requester"] as? [[String: Any]] else { return 1 }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    // This executable is entered through sudo rather than NSApplicationMain.
    // Finish AppKit launch before opening the modal window so its native
    // services, including Accessibility, are registered with WindowServer.
    app.finishLaunching()
    let alert = NSAlert()
    alert.messageText = "Run this command as administrator?"
    alert.informativeText = "Authenticate this invocation only. Its child processes can also run as administrator."
    alert.addButton(withTitle: "Authenticate")
    alert.addButton(withTitle: "Cancel")
    let content = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 230))
    let scroll = NSScrollView(frame: NSRect(x: 0, y: 65, width: 520, height: 165))
    scroll.hasVerticalScroller = true
    let details = NSTextView(frame: scroll.bounds)
    details.isEditable = false
    details.isRichText = false
    details.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
    let args = command.enumerated().map { index, value in "\(index == 0 ? "Executable" : "Argument \(index)"): \(String(reflecting: value))" }.joined(separator: "\n")
    let chain = requester.map { "\(($0["path"] as? String) ?? "unknown") [PID \($0["pid"] ?? "?")]" }.joined(separator: "\n← ")
    details.string = "\(args)\n\nDirectory: \(cwd)\n\nObserved processes (informative, same-user):\n\(chain)"
    details.setAccessibilityIdentifier("mc-sudo-details")
    scroll.documentView = details
    content.addSubview(scroll)
    let label = NSTextField(labelWithString: "Your macOS login password")
    label.frame = NSRect(x: 0, y: 39, width: 520, height: 20)
    content.addSubview(label)
    let password = NSSecureTextField(frame: NSRect(x: 0, y: 5, width: 520, height: 28))
    password.setAccessibilityIdentifier("mc-sudo-password")
    password.setAccessibilityLabel("Your macOS login password")
    content.addSubview(password)
    alert.accessoryView = content
    alert.window.title = "Machine Control — Administrator authentication"
    alert.window.initialFirstResponder = password
    app.activate(ignoringOtherApps: true)
    let deadline = Date().addingTimeInterval(TimeInterval(seconds))
    guard let sudoInfo = information(sudoPID) else { return 1 }
    let wrapperPID = sudoInfo.kp_eproc.e_ppid
    let sudoStart = sudoInfo.kp_proc.p_un.__p_starttime
    func sameInvocation() -> Bool {
        guard let current = information(sudoPID) else { return false }
        let start = current.kp_proc.p_un.__p_starttime
        return current.kp_eproc.e_ppid == wrapperPID && start.tv_sec == sudoStart.tv_sec
            && start.tv_usec == sudoStart.tv_usec
    }
    var interrupted = false
    let timer = Timer(timeInterval: 0.1, repeats: true) { _ in
        if Date() >= deadline || !usableDesktop() || !sameInvocation() {
            interrupted = true
            app.abortModal()
            alert.window.orderOut(nil)
        }
    }
    RunLoop.main.add(timer, forMode: .modalPanel)
    RunLoop.main.add(timer, forMode: .common)
    let response = alert.runModal()
    timer.invalidate()
    defer { password.stringValue = "" }
    guard !interrupted, response == .alertFirstButtonReturn,
          Date() < deadline, usableDesktop(), sameInvocation(),
          !password.stringValue.isEmpty else { return 1 }
    // Only sudo's private askpass pipe receives these bytes. No Rust, JSON,
    // logging, app WebView, clipboard, or credential cache handles the password.
    var bytes = Array(password.stringValue.utf8)
    bytes.append(10)
    defer { _ = bytes.withUnsafeMutableBytes { memset_s($0.baseAddress, $0.count, 0, $0.count) } }
    var offset = 0
    while offset < bytes.count {
        let written = bytes.withUnsafeBytes { raw in
            Darwin.write(STDOUT_FILENO, raw.baseAddress!.advanced(by: offset), bytes.count - offset)
        }
        if written < 0 { if errno == EINTR { continue }; return 1 }
        if written == 0 { return 1 }
        offset += written
    }
    return 0
}
