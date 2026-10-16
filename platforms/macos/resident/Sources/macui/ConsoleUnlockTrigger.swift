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
    private func passwordPanelIssue() -> String? {
        let app = AXUIElementCreateApplication(identity.pid)
        AXUIElementSetMessagingTimeout(app, 0.3)
        return Self.passwordPanelIssue(app:app) { element, name in
            var value: CFTypeRef?
            let result = AXUIElementCopyAttributeValue(element, name as CFString, &value)
            switch result {
            case .success: return value
            case .noValue, .attributeUnsupported: return nil
            default: throw MacUIError.action("ax_read_failed")
            }
        }
    }

    /// The injectable reader admits only the metadata used by the production
    /// discovery path. Diagnostics are fixed codes, with no UI text or values.
    static func passwordPanelIssue<Element>(app: Element,
        read: (Element, String) throws -> Any?) -> String? {
        var readFailed = false
        func value(_ element: Element, _ name: String) -> Any? {
            do { return try read(element, name) }
            catch { readFailed = true; return nil }
        }
        guard let allWindows = value(app, kAXWindowsAttribute) as? [Element] else {
            return readFailed ? "ax_read_failed" : "windows_unavailable"
        }
        let windows = allWindows.filter { value($0, kAXIdentifierAttribute) as? String == "login" }
        if readFailed { return "ax_read_failed" }
        guard !windows.isEmpty else { return "login_window_absent" }
        guard windows.count == 1 else { return "login_window_ambiguous" }
        var fields = 0, ready = 0, disabled = false, unfocused = false, depthLimited = false
        var remaining = 64
        func visit(_ element: Element, depth:Int) {
            guard remaining > 0 else { return }
            guard depth <= 6 else { depthLimited = true; return }
            remaining -= 1
            if value(element, kAXRoleAttribute) as? String == "AXTextField",
               value(element, kAXSubroleAttribute) as? String == "AXSecureTextField",
               value(element, kAXIdentifierAttribute) as? String == "UserPasswordTextField" {
                fields += 1
                let enabled = value(element, kAXEnabledAttribute) as? Bool == true
                let focused = value(element, kAXFocusedAttribute) as? Bool == true
                disabled = disabled || !enabled; unfocused = unfocused || !focused
                if enabled && focused { ready += 1 }
            }
            for child in (value(element, kAXChildrenAttribute) as? [Element] ?? []) {
                visit(child, depth:depth + 1)
            }
        }
        visit(windows[0], depth:0)
        if readFailed { return "ax_read_failed" }
        guard remaining > 0 else { return "node_limit" }
        if ready == 1 { return nil }
        if ready > 1 { return "password_field_ambiguous" }
        if fields == 0 { return depthLimited ? "depth_limit" : "password_field_absent" }
        if disabled { return "password_field_disabled" }
        if unfocused { return "password_field_unfocused" }
        return "password_field_unavailable"
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
        if passwordPanelIssue() != nil {
            try enter() // Reveal the password panel on Touch ID lock screens.
            let deadline = ProcessInfo.processInfo.systemUptime + 2
            while passwordPanelIssue() != nil, ProcessInfo.processInfo.systemUptime < deadline {
                guard try stillLocked() else { return }
                Thread.sleep(forTimeInterval:0.05)
            }
        }
        guard try stillLocked() else { return }
        if let issue = passwordPanelIssue() {
            throw MacUIError.action("unlock_password_panel_unavailable_\(issue)")
        }
        try enter()
    }
}
