import AppKit
import ApplicationServices
import CoreGraphics
import Darwin
import Foundation

/// Loginwindow is not necessarily an NSWorkspace running application on a
/// physical Mac. Resolve its window owner, then verify kernel path, UID, and
/// process birth time. Never activate an ordinary application or post globally.
struct ConsoleUnlockTrigger {
    struct Identity: Equatable {
        let pid: pid_t
        let startedSeconds: Int
        let startedMicroseconds: Int
    }
    private static let executable = "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow"
    let identity: Identity

    static func kernelIdentity(_ pid: pid_t) -> Identity? {
        guard pid > 1 else { return nil }
        var info = kinfo_proc()
        var size = MemoryLayout<kinfo_proc>.stride
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
        guard sysctl(&mib, 4, &info, &size, nil, 0) == 0,
              size == MemoryLayout<kinfo_proc>.stride,
              info.kp_eproc.e_ucred.cr_uid == getuid() else { return nil }
        var buffer = [UInt8](repeating:0, count:4 * Int(MAXPATHLEN))
        guard mcProcPIDPath(pid, &buffer, UInt32(buffer.count)) > 0,
              String(decoding:buffer.prefix { $0 != 0 }, as:UTF8.self) == executable else { return nil }
        return Identity(pid:pid, startedSeconds:Int(info.kp_proc.p_starttime.tv_sec),
                        startedMicroseconds:Int(info.kp_proc.p_starttime.tv_usec))
    }

    static func resolve() throws -> ConsoleUnlockTrigger {
        let windows = CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String:Any]] ?? []
        let owners = Set(windows.compactMap { ($0[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value })
        let candidates = owners.compactMap(kernelIdentity)
        guard candidates.count == 1 else { throw MacUIError.action("loginwindow_identity_unavailable") }
        return ConsoleUnlockTrigger(identity:candidates[0])
    }

    /// Reads role/identity/focus metadata only, never the secure field's value.
    private func passwordField() -> AXUIElement? {
        let app = AXUIElementCreateApplication(identity.pid)
        AXUIElementSetMessagingTimeout(app, 0.3)
        let windows = (attribute(app, kAXWindowsAttribute as CFString) as? [AXUIElement] ?? [])
            .filter { stringAttribute($0, kAXIdentifierAttribute as CFString) == "login" }
        guard windows.count == 1 else { return nil }
        var fields: [AXUIElement] = []
        var remaining = 64
        func visit(_ element: AXUIElement, depth:Int) {
            guard remaining > 0, depth <= 6 else { return }; remaining -= 1
            if stringAttribute(element, kAXRoleAttribute as CFString) == "AXTextField",
               stringAttribute(element, kAXSubroleAttribute as CFString) == "AXSecureTextField",
               stringAttribute(element, kAXIdentifierAttribute as CFString) == "UserPasswordTextField",
               boolAttribute(element, kAXEnabledAttribute as CFString) == true,
               boolAttribute(element, kAXFocusedAttribute as CFString) == true { fields.append(element) }
            for child in (attribute(element, kAXChildrenAttribute as CFString) as? [AXUIElement] ?? []) {
                visit(child, depth:depth + 1)
            }
        }
        visit(windows[0], depth:0)
        return remaining > 0 && fields.count == 1 ? fields[0] : nil
    }

    /// The caller must already own covers, hardware cancellation, and the
    /// authenticated broker's short-lived grant. Events only address loginwindow.
    func submit(initial:[String:Any], cancelled:() -> String?) throws {
        func stillLocked() throws -> Bool {
            if let reason = cancelled() { throw MacUIError.action(reason) }
            let current = nativeSessionObservation()
            guard sameConsoleSession(initial, current), Self.kernelIdentity(identity.pid) == identity else {
                throw MacUIError.action("unlock_session_changed")
            }
            if current["desktopState"] as? String == "unlocked" { return false }
            guard current["desktopState"] as? String == "locked" else { throw MacUIError.action("unlock_session_unavailable") }
            return true
        }
        func enter() throws {
            guard try stillLocked() else { return }
            let source = CGEventSource(stateID:.privateState)
            guard let down = CGEvent(keyboardEventSource:source, virtualKey:36, keyDown:true),
                  let up = CGEvent(keyboardEventSource:source, virtualKey:36, keyDown:false) else {
                throw MacUIError.action("unlock_event_unavailable")
            }
            down.flags = []; up.flags = []
            down.postToPid(identity.pid)
            Thread.sleep(forTimeInterval:0.05)
            up.postToPid(identity.pid)
        }
        guard try stillLocked() else { return }
        if passwordField() == nil {
            try enter() // Reveal the password panel on Touch ID lock screens.
            let deadline = ProcessInfo.processInfo.systemUptime + 2
            while passwordField() == nil, ProcessInfo.processInfo.systemUptime < deadline {
                guard try stillLocked() else { return }
                Thread.sleep(forTimeInterval:0.05)
            }
        }
        guard try stillLocked() else { return }
        guard passwordField() != nil else { throw MacUIError.action("unlock_password_panel_unavailable") }
        try enter()
    }
}
