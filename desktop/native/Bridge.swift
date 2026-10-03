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

private func stopDesktopAccess() {
    if let pending = desktopApprover.request {
        try? desktopApprover.decide(id: pending.id, scopes: [], duration: 0, allow: false)
    }
    desktopServer?.revoke(reason: "stopped_by_person")
}

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
        let existing = try residentSocket()
        defer { Darwin.close(existing) }
        var (address, length) = try unixAddress(socketPath)
        if withSockAddr(&address, length: length, { Darwin.connect(existing, $0, $1) }) == 0 {
            throw MacUIError.action("Another Machine Control resident is already running")
        }
        try FileManager.default.createDirectory(atPath: (socketPath as NSString).deletingLastPathComponent,
            withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let broker = GrantBroker(policy: DeploymentPolicy.load())
        broker.journal = DesktopJournal()
        attachOperatorConsent(broker, socketPath:socketPath)
        let server = ResidentServer(socketPath: socketPath, service: ResidentService(), broker: broker)
        if broker.policy.grantMode == .approval { server.approver = desktopApprover }
        let pid = getpid()
        let identifiers = Set([Bundle.main.bundleIdentifier, "Machine Control", "macui"].compactMap { $0?.lowercased() })
        server.guardRequest = { [weak server] request in
            let own = OwnInterface(processID: pid, identifiers: identifiers,
                windowFrames: ownWindowFrames(pid, excluding:server?.lockedUse.coveredWindowIDs ?? []), hasKeyWindow: NSApp.keyWindow != nil,
                menuOpen: desktopMenuTracking, pointer: CGEvent(source: nil)?.location)
            let reference = (request["reference"] as? String).flatMap { server?.service.referencedProcess($0) }
            return selfTargetRefusal(request, own: own, referencedProcess: reference)
        }
        server.activity.respectRecentActivity = UserDefaults.standard.string(forKey:"machineControl.admissionPolicy") != "announce"
        let notice = UserDefaults.standard.integer(forKey:"machineControl.admissionNoticeSeconds")
        server.noticeSeconds = (5...60).contains(notice) ? Double(notice) : 10
        server.notice = AdmissionNotice(server:server)
        server.activity.enable()
        try server.start()
        server.devtools.start()
        desktopServer = server
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
    return autoreleasepool {
        do {
            guard let command = try JSONSerialization.jsonObject(with: Data(String(cString: input).utf8)) as? [String: Any],
                  let method = command["method"] as? String, let server = desktopServer else {
                throw MacUIError.action("Resident is unavailable")
            }
            switch method {
            case "update_sync":
                guard let state = command["state"] as? [String: Any] else {
                    throw MacUIError.usage("Update state required")
                }
                return bridgeJSON(["ok": true, "checkRequested": server.updates.sync(state)])
            case "state":
                let setup = currentSetupState(browserConnected: server.browser.connected, probeScreen: false)
                var state: [String: Any] = ["deployment": server.broker.statusJSON,
                    "permissions": ["accessibility": setup.accessibility, "screenRecording": setup.screen == .allowed],
                    "browser": server.browser.statusJSON, "activity": server.broker.audit.reversed().prefix(30).map(\.json),
                    "logging": server.broker.journal?.health ?? [:],
                    "stopShortcutAvailable": desktopHotKey != nil,
                    "manualUntilStoppedSupported": true,
                    "pauseSupported": true,
                    "admission": server.broker.admission.status,
                    "controlPolicy": ["supported":true, "mode":server.activity.respectRecentActivity ? "when_idle" : "announce", "noticeSeconds":server.noticeSeconds],
                    "physicalActivity": server.activity.status,
                    "lockedUse": server.lockedUse.status,
                    "socket": server.socketPath, "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "development"]
                if let pending = desktopApprover.request {
                    state["pending"] = ["id": pending.id, "reason": pending.reason, "caller": pending.caller.summary,
                        "scopes": pending.scopes.sorted().map(\.rawValue), "duration": pending.durationSeconds]
                }
                return bridgeJSON(["ok": true, "state": state])
            case "logs.query":
                return bridgeJSON(["ok": true, "history": server.broker.journal?.query(offset: command["offset"] as? Int ?? 0, operation: command["operation"] as? String ?? "", outcome: command["outcome"] as? String ?? "", stream: command["stream"] as? String ?? "audit") ?? [:]])
            case "logs.debug": server.broker.journal?.debug(command["enabled"] as? Bool == true)
            case "logs.preview": return bridgeJSON(["ok": true, "preview": server.broker.journal?.preview() ?? [:]])
            case "logs.export": return bridgeJSON(["ok": true, "path": try server.broker.journal?.export() ?? ""])
            case "logs.location": return bridgeJSON(["ok": true, "path": server.broker.journal?.root.path ?? ""])
            case "logs.diagnostic":
                server.broker.journal?.diagnostic("desktop.supervisor", code: command["code"] as? String ?? "unknown")
            case "stop":
                stopDesktopAccess()
            case "prepare_exit":
                server.revoke(reason:"operator_quit")
            case "pause":
                try server.broker.pause(seconds: command["duration"] as? Int)
            case "resume":
                try server.service.resumeCoveredAvailability()
                try server.broker.resume()
            case "control_policy":
                guard let mode = command["mode"] as? String, ["when_idle", "announce"].contains(mode),
                      let notice = command["noticeSeconds"] as? Int, (5...60).contains(notice),
                      (server.broker.admission.status["active"] as? Int ?? 0) == 0 else { throw MacUIError.usage("Choose a supported control policy while no agent is active") }
                UserDefaults.standard.set(mode, forKey:"machineControl.admissionPolicy")
                UserDefaults.standard.set(notice, forKey:"machineControl.admissionNoticeSeconds")
                server.activity.respectRecentActivity = mode == "when_idle"; server.noticeSeconds = Double(notice)
            case "start_control":
                try server.startNow(command["intentId"] as? String ?? "")
            case "defer_control":
                try server.broker.pause(reason:"operator_deferral", seconds:60)
            case "cancel_control":
                try server.cancelFromOperator(command["intentId"] as? String ?? "")
            case "locked_use":
                guard !desktopUpdating, let enabled = command["enabled"] as? Bool else {
                    throw MacUIError.usage("Choose whether locked use is enabled")
                }
                try server.lockedUse.configure(enabled:enabled)
            case "decision":
                if command["allow"] as? Bool == true, server.broker.journal?.event("access.approve.intent") == false { throw MacUIError.action("Audit storage unavailable") }
                try desktopApprover.decide(id: command["id"] as? String ?? "", scopes: command["scopes"] as? [String] ?? [],
                    duration: command["duration"] as? Int ?? 0, allow: command["allow"] as? Bool == true)
            case "arm":
                guard server.broker.journal?.event("access.arm.intent") != false else { throw MacUIError.action("Audit storage unavailable") }
                guard !desktopUpdating, server.broker.policy.grantMode == .approval, server.broker.pending == nil,
                      let names = command["scopes"] as? [String], !names.isEmpty,
                      names.allSatisfy({ GrantScope(rawValue: $0) != nil }) else {
                    throw MacUIError.usage("Choose access and duration while no approval is pending")
                }
                let scopes = Set(names.compactMap(GrantScope.init(rawValue:)))
                let lifetime = command["lifetime"] as? String ?? "timed"
                if lifetime == "until_stopped" {
                    server.broker.issueUntilStopped(scopes: scopes,
                        reason: "Manually enabled by the person", requester: "local operator", approver: "local_tauri")
                } else {
                    guard lifetime == "timed", let duration = command["duration"] as? Int,
                          GrantRequest.durationRange.contains(duration) else {
                        throw MacUIError.usage("Choose a supported access duration")
                    }
                    server.broker.issue(scopes: scopes, durationSeconds: duration,
                        reason: "Manually enabled by the person", requester: "local operator", approver: "local_tauri")
                }
                guard server.broker.journal?.errorCode == nil else { throw MacUIError.action("Audit storage unavailable") }
                do {
                    guard server.broker.consentStorageError == nil else { throw MacUIError.action("consent_storage_unavailable") }
                    try server.broker.consentStore?.enable(scopes:scopes,
                        duration:lifetime == "until_stopped" ? nil : command["duration"] as? Int,
                        console:server.service.observedConsoleSession)
                } catch { server.revoke(reason:"consent_storage_unavailable"); throw error }
            case "prepare_update":
                guard !desktopUpdating, server.broker.policy.grantMode == .approval,
                      server.broker.grant == nil, server.broker.pending == nil,
                      server.lockedUse.setupState == "idle", !server.lockedUse.isCovered,
                      server.lockedUse.lease == nil else {
                    throw MacUIError.action("Stop access and finish any approval before installing an update")
                }
                desktopUpdating = true
            case "cancel_update": desktopUpdating = false
            case "permission":
                if command["permission"] as? String == "lockedUse" {
                    guard !desktopUpdating else { throw MacUIError.action("Finish updating before changing permissions") }
                    try server.lockedUse.preparePermission()
                    break
                }
                guard ["screenRecording", "accessibility"].contains(command["permission"] as? String ?? "") else {
                    throw MacUIError.usage("Choose a supported permission")
                }
                let screen = command["permission"] as? String == "screenRecording"
                if screen { _ = CGRequestScreenCaptureAccess() }
                else { _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary) }
                let pane = screen ? "Privacy_ScreenCapture" : "Privacy_Accessibility"
                NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?\(pane)")!)
            case "permission.remove":
                guard !desktopUpdating, command["permission"] as? String == "lockedUse" else {
                    throw MacUIError.usage("Choose a supported helper permission")
                }
                try server.lockedUse.removePermission()
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
