import AppKit
import ApplicationServices
import Carbon
import Darwin
import Foundation

private var desktopServer: ResidentServer?
private let desktopApprover = DesktopApprover()
private var desktopMenuTracking = false
private var desktopHotKey: EventHotKeyRef?
private var desktopUpdating = false

private func bridgeJSON(_ value: [String: Any]) -> UnsafeMutablePointer<CChar>? {
    guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
          let text = String(data: data, encoding: .utf8) else { return nil }
    return strdup(text)
}

@_cdecl("mc_desktop_mode")
public func mcDesktopMode(_ input: UnsafePointer<CChar>) -> Int32 {
    guard let args = try? JSONSerialization.jsonObject(with: Data(String(cString: input).utf8)) as? [String] else { return 0 }
    do {
        if args == ["screen-capture-preflight"] { print(CGPreflightScreenCaptureAccess()); return 1 }
        if let origin = args.first, origin.hasPrefix("chrome-extension://") { runBrowserHost(origin: origin) }
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
        // Never unlink another resident's live endpoint.
        let existing = socket(AF_UNIX, SOCK_STREAM, 0)
        defer { Darwin.close(existing) }
        var (address, length) = try unixAddress(socketPath)
        if withSockAddr(&address, length: length, { Darwin.connect(existing, $0, $1) }) == 0 {
            throw MacUIError.action("Another Machine Control resident is already running")
        }
        try FileManager.default.createDirectory(atPath: (socketPath as NSString).deletingLastPathComponent,
            withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let broker = GrantBroker(policy: DeploymentPolicy.load())
        let server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker)
        if broker.policy.grantMode == .approval { server.approver = desktopApprover }
        let pid = getpid()
        let identifiers = Set([Bundle.main.bundleIdentifier, "Machine Control", "macui"].compactMap { $0?.lowercased() })
        server.guardRequest = { [weak server] request in
            let own = OwnInterface(processID: pid, identifiers: identifiers,
                windowFrames: ownWindowFrames(pid), hasKeyWindow: NSApp.keyWindow != nil,
                menuOpen: desktopMenuTracking, pointer: CGEvent(source: nil)?.location)
            let reference = (request["reference"] as? String).flatMap { server?.service.referencedProcess($0) }
            return selfTargetRefusal(request, own: own, referencedProcess: reference)
        }
        try server.start()
        server.devtools.start()
        desktopServer = server
        NotificationCenter.default.addObserver(forName: NSMenu.didBeginTrackingNotification, object: nil, queue: .main) { _ in desktopMenuTracking = true }
        NotificationCenter.default.addObserver(forName: NSMenu.didEndTrackingNotification, object: nil, queue: .main) { _ in desktopMenuTracking = false }
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            desktopServer?.revoke(reason: "stopped_by_hotkey")
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
    return autoreleasepool {
        do {
            guard let command = try JSONSerialization.jsonObject(with: Data(String(cString: input).utf8)) as? [String: Any],
                  let method = command["method"] as? String, let server = desktopServer else {
                throw MacUIError.action("Resident is unavailable")
            }
            switch method {
            case "state":
                let setup = currentSetupState(browserConnected: server.browser.connected, probeScreen: false)
                var state: [String: Any] = ["deployment": server.broker.statusJSON,
                    "permissions": ["accessibility": setup.accessibility, "screenRecording": setup.screen == .allowed],
                    "browser": server.browser.statusJSON, "activity": server.broker.audit.reversed().prefix(30).map(\.json),
                    "socket": server.socketPath, "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "development"]
                if let pending = desktopApprover.request {
                    state["pending"] = ["id": pending.id, "reason": pending.reason, "caller": pending.caller.summary,
                        "scopes": pending.scopes.sorted().map(\.rawValue), "duration": pending.durationSeconds]
                }
                return bridgeJSON(["ok": true, "state": state])
            case "stop":
                if let pending = desktopApprover.request {
                    try desktopApprover.decide(id: pending.id, scopes: [], duration: 0, allow: false)
                }
                server.revoke(reason: "stopped_by_person")
            case "decision":
                try desktopApprover.decide(id: command["id"] as? String ?? "", scopes: command["scopes"] as? [String] ?? [],
                    duration: command["duration"] as? Int ?? 0, allow: command["allow"] as? Bool == true)
            case "arm":
                guard !desktopUpdating, server.broker.policy.grantMode == .approval, server.broker.pending == nil,
                      let names = command["scopes"] as? [String], !names.isEmpty,
                      names.allSatisfy({ GrantScope(rawValue: $0) != nil }),
                      let duration = command["duration"] as? Int, GrantRequest.durationRange.contains(duration) else {
                    throw MacUIError.usage("Choose access and duration while no approval is pending")
                }
                server.broker.issue(scopes: Set(names.compactMap(GrantScope.init(rawValue:))), durationSeconds: duration,
                    reason: "Manually enabled by the person", requester: "local operator", approver: "local_tauri")
            case "prepare_update":
                guard !desktopUpdating, server.broker.policy.grantMode == .approval,
                      server.broker.grant == nil, server.broker.pending == nil else {
                    throw MacUIError.action("Stop access and finish any approval before installing an update")
                }
                desktopUpdating = true
            case "cancel_update": desktopUpdating = false
            case "permission":
                let screen = command["permission"] as? String == "screenRecording"
                if screen { _ = CGRequestScreenCaptureAccess() }
                else { _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary) }
                let pane = screen ? "Privacy_ScreenCapture" : "Privacy_Accessibility"
                NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?\(pane)")!)
            case "browser.setup":
                let origin = "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/"
                let directory = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Google/Chrome/NativeMessagingHosts")
                try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                let host: [String: Any] = ["name": "org.machine_control.browser", "description": "Machine Control browser provider",
                    "path": Bundle.main.executableURL!.path, "type": "stdio", "allowed_origins": [origin]]
                try JSONSerialization.data(withJSONObject: host, options: [.prettyPrinted, .sortedKeys])
                    .write(to: directory.appendingPathComponent("org.machine_control.browser.json"), options: .atomic)
                let extensionURL = Bundle.main.resourceURL!.appendingPathComponent("chrome-extension")
                NSPasteboard.general.clearContents(); NSPasteboard.general.setString(extensionURL.path, forType: .string)
                NSWorkspace.shared.activateFileViewerSelecting([extensionURL])
                return bridgeJSON(["ok": true, "extensionPath": extensionURL.path])
            default: throw MacUIError.usage("Unknown operator command")
            }
            return bridgeJSON(["ok": true])
        } catch { return bridgeJSON(["ok": false, "error": String(describing: error)]) }
    }
}
