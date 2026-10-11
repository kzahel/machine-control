import AppKit
import ApplicationServices
import Carbon
import Darwin
import Foundation

private var desktopRuntime: ResidentRuntime?
private var desktopMenuTracking = false
private var desktopHotKey: EventHotKeyRef?

private func stopDesktopAccess() { desktopRuntime?.stopAccess() }

private func bridgeJSON(_ value: [String: Any]) -> UnsafeMutablePointer<CChar>? {
    guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
          let text = String(data: data, encoding: .utf8) else { return nil }
    return strdup(text)
}

@_cdecl("mc_desktop_mode")
public func mcDesktopMode(_ input: UnsafePointer<CChar>) -> Int32 {
    guard let args = try? JSONSerialization.jsonObject(with: Data(String(cString: input).utf8)) as? [String] else { return 0 }
    do {
        if args == ["locked-use-guardian"] { try runLockedUseGuardian() }
        if args == ["screen-capture-preflight"] { print(CGPreflightScreenCaptureAccess()); return 1 }
        if let origin = args.first, origin.hasPrefix("chrome-extension://") { runBrowserHost(origin: origin) }
        if args.first == "channel", args.count == 2 { try runAdmissionProxy(socketPath:args[1]); return 1 }
        if args.first == "delegated-channel", args.count == 2 { try runAdmissionProxy(socketPath:args[1], trustedDesktop:true); return 1 }
        if args.first == "request", (2...3).contains(args.count) {
            let data = args.count >= 3 ? Data(args[2].utf8) : FileHandle.standardInput.readDataToEndOfFile()
            try runResidentClient(socketPath: args[1], requestData: data)
            return 1
        }
        if args.first == "credential", args.count == 3 {
            try runCredentialClient(socketPath: args[1], leaseID: args[2]); return 1
        }
    } catch { FileHandle.standardError.write(Data("\(error)\n".utf8)); return -1 }
    return 0
}

@_cdecl("mc_desktop_start")
public func mcDesktopStart(_ path: UnsafePointer<CChar>) -> UnsafeMutablePointer<CChar>? {
    precondition(Thread.isMainThread)
    do {
        let socketPath = String(cString: path).isEmpty ? defaultResidentSocket : String(cString: path)
        let runtime = try ResidentRuntime(socketPath:socketPath)
        let server = runtime.server
        let pid = getpid()
        let identifiers = Set([Bundle.main.bundleIdentifier, "Machine Control", "macui"].compactMap { $0?.lowercased() })
        server.guardRequest = { [weak server] request in
            let own = OwnInterface(processID: pid, identifiers: identifiers,
                windowFrames: ownWindowFrames(pid, excluding:server?.lockedUse.coveredWindowIDs ?? []), hasKeyWindow: NSApp.keyWindow != nil,
                menuOpen: desktopMenuTracking, pointer: CGEvent(source: nil)?.location)
            let reference = (request["reference"] as? String).flatMap { server?.referencedProcess($0) }
            return selfTargetRefusal(request, own: own, referencedProcess: reference)
        }
        try runtime.start()
        desktopRuntime = runtime
        runtime.stopShortcutAvailable = { desktopHotKey != nil }
        // AppKit's standard application-menu termination can finish before the
        // Tauri exit-request callback. End protected control in the native
        // lifecycle notification as well, before the process disappears.
        NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification,
            object:nil, queue:.main) { [weak server] _ in
                server?.revoke(reason:"operator_quit")
            }
        NotificationCenter.default.addObserver(forName: NSMenu.didBeginTrackingNotification, object: nil, queue: .main) { _ in desktopMenuTracking = true }
        NotificationCenter.default.addObserver(forName: NSMenu.didEndTrackingNotification, object: nil, queue: .main) { _ in desktopMenuTracking = false }
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            stopDesktopAccess()
            return noErr
        }, 1, &spec, nil, nil)
        RegisterEventHotKey(UInt32(kVK_ANSI_Period), UInt32(controlKey | optionKey | cmdKey),
            EventHotKeyID(signature: OSType(0x4D43_5354), id: 1), GetApplicationEventTarget(), 0, &desktopHotKey)
        return bridgeJSON(["ok": true])
    } catch { return bridgeJSON(["ok": false, "error": String(describing: error)]) }
}

@_cdecl("mc_desktop_command")
public func mcDesktopCommand(_ input: UnsafePointer<CChar>) -> UnsafeMutablePointer<CChar>? {
    precondition(Thread.isMainThread)
    guard let runtime = desktopRuntime else { return bridgeJSON(["ok":false, "error":"Resident is unavailable"]) }
    guard let command = try? JSONSerialization.jsonObject(with:Data(String(cString:input).utf8)) as? [String:Any] else {
        return bridgeJSON(["ok":false, "error":"Invalid operator command"])
    }
    return bridgeJSON(runtime.operatorCommand(command))
}
