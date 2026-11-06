import AppKit
import ApplicationServices
import Foundation
import CoreFoundation

/// Missing means now; malformed delayed approval must never become immediate.
func accessDelaySeconds(_ supplied: Any?) throws -> Int {
    guard let supplied else { return 0 }
    guard let number = supplied as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
          number.doubleValue.isFinite, number.doubleValue.rounded(.towardZero) == number.doubleValue,
          (0...28800).contains(number.doubleValue) else { throw MacUIError.usage("Choose an integer delay") }
    return number.intValue
}

/// Operator-only browser registration and explicitly selected installation path.
func setupBrowserExtension(bundled: Bool = false, bundledExtension: URL? = nil) throws -> String {
    // Unpacked development copy and Chrome Web Store release.
    let origins = ["chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/",
                   "chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/"]
    let directory = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Google/Chrome/NativeMessagingHosts")
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let host: [String: Any] = ["name": "org.machine_control.browser", "description": "Machine Control browser provider",
        "path": Bundle.main.executableURL!.path, "type": "stdio", "allowed_origins": origins]
    try JSONSerialization.data(withJSONObject: host, options: [.prettyPrinted, .sortedKeys])
        .write(to: directory.appendingPathComponent("org.machine_control.browser.json"), options: .atomic)
    let extensionURL = bundledExtension ?? Bundle.main.resourceURL!.appendingPathComponent("chrome-extension")
    if bundled {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(extensionURL.path, forType: .string)
    } else {
        guard NSWorkspace.shared.open(URL(string: "https://chromewebstore.google.com/detail/machine-control/epejchbeajneooefnklikkfhbaeadkpc")!) else {
            throw MacUIError.action("Browser registered; could not open the Chrome Web Store")
        }
    }
    return extensionURL.path
}

extension ResidentRuntime {
    /// Resume's helper wait is asynchronous; its local authority transition
    /// returns to the coordinator only while the initiating intent is live.
    func operatorCommand(_ command: [String:Any], completion: @escaping ([String:Any]) -> Void) {
        precondition(Thread.isMainThread)
        if let method = command["method"] as? String, ["logs.preview", "logs.export", "logs.crashes.preview", "logs.crashes.export"].contains(method) {
            final class Reply { var value: [String:Any] = [:] }
            let reply = Reply()
            guard let journal = server.broker.journal else { completion(["ok":false, "error":"Logging unavailable"]); return }
            operatorDependency.perform(timeout:5, work:{ _ in
                switch method {
                case "logs.preview": reply.value = ["preview":journal.preview()]
                case "logs.export": reply.value = ["path":try journal.export()]
                case "logs.crashes.preview": reply.value = journal.previewWithCrashReports()
                default: reply.value = ["path":try journal.exportCrashPreview(id:command["previewId"] as? String ?? "")]
                }
            }, commit:{}, completion:{ result in
                guard result["ok"] as? Bool == true else { completion(result); return }
                completion(reply.value.merging(["ok":true]) { _, new in new })
            })
            return
        }
        let method = command["method"] as? String
        let resumeDesktop = ["surface.resume", "resume_surface"].contains(method ?? "") && command["surface"] as? String == "desktop"
        guard method == "resume" || resumeDesktop else {
            completion(operatorCommand(command)); return
        }
        guard !updating else { completion(["ok":false, "error":"Finish updating before resuming"]); return }
        let observation = server.service.observedConsoleSession
        let revision = server.broker.admission.availabilityRevision
        let grant = server.broker.grant?.id
        let read = resumeHelper
        operatorDependency.perform(work:{ cancelled in try read(observation, cancelled) },
            commit:{ [weak self] in
                guard let self, self.running else { throw MacUIError.action("resident_stopping") }
                guard self.server.broker.admission.availabilityRevision == revision,
                      self.server.broker.grant?.id == grant else {
                    throw MacUIError.action("control_generation_changed")
                }
                try self.server.broker.resume(surface:resumeDesktop ? "desktop" : "all")
            }, completion:completion)
    }
    /// Status poll projection; admission reads come from the cached view.
    private func operatorState(_ server: ResidentServer) -> [String: Any] {
        let setup = currentSetupState(browserConnected: server.browser.connected, probeScreen: false)
        var state: [String: Any] = ["deployment": server.broker.statusJSON,
            "accessChoices":NSNull(),
            "permissions": ["accessibility": setup.accessibility, "screenRecording": setup.screen == .allowed],
            "browser": server.browser.statusJSON, "activity": server.broker.audit.reversed().prefix(30).map(\.json),
            "logging": server.broker.journal?.health ?? [:],
            "stopShortcutAvailable": stopShortcutAvailable(),
            "manualUntilStoppedSupported": true,
            "pauseSupported": true,
            "admission": server.admissionPresentation,
            "accessPolicy":server.admissionPresentation,
            "controlPolicy": ["supported":true, "mode":"announce", "noticeSeconds":server.noticeSeconds],
            "physicalActivity": server.activity.status,
            "observations": ["session":server.service.sessionObservation.metadata,
                             "helper":server.service.helperObservation.metadata],
            "desktopCallerTrust": server.callerTrust.status,
            "lockedUse": server.lockedUse.status,
            "browserWhileLocked": server.browserWhileLockedStatus,
            "presentation":presentationJSON, "nativeApproval":true,
            "socket": server.socketPath, "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "development"]
        if let pending = approver.request {
            state["pending"] = ["id": pending.id, "reason": pending.reason, "caller": pending.caller.summary,
                "scopes": pending.scopes.sorted().map(\.rawValue), "duration": pending.durationSeconds]
        }
        return ["ok": true, "state": state]
    }

    /// In-process operator authority; never registered on the agent socket.
    func operatorCommand(_ command: [String:Any]) -> [String:Any] {
        precondition(Thread.isMainThread)
        return autoreleasepool {
            do {
                guard let method = command["method"] as? String else {
                    throw MacUIError.action("Resident is unavailable")
                }
                let server = self.server
                switch method {
                case "update_sync":
                    guard let state = command["state"] as? [String: Any] else {
                        throw MacUIError.usage("Update state required")
                    }
                    return ["ok": true, "checkRequested": server.updates.sync(state)]
                case "state":
                    if command["fresh"] as? Bool == true { return operatorState(server) }
                    return server.broker.admission.presentation { operatorState(server) }
                case "presentation":
                    guard let name = command["profile"] as? String, let profile = PresentationProfile(rawValue:name) else {
                        throw MacUIError.usage("Choose personal, minimal or appliance presentation")
                    }
                    try configurePresentation(profile)
                case "logs.query":
                    return ["ok": true, "history": server.broker.journal?.query(offset: command["offset"] as? Int ?? 0, operation: command["operation"] as? String ?? "", outcome: command["outcome"] as? String ?? "", stream: command["stream"] as? String ?? "audit") ?? [:]]
                case "logs.debug": server.broker.journal?.debug(command["enabled"] as? Bool == true)
                case "logs.crashes.cancel": server.broker.journal?.cancelCrashPreview()
                case "logs.preview": return ["ok": true, "preview": server.broker.journal?.preview() ?? [:]]
                case "logs.export": return ["ok": true, "path": try server.broker.journal?.export() ?? ""]
                case "logs.location": return ["ok": true, "path": server.broker.journal?.root.path ?? ""]
                case "logs.open":
                    guard let root = server.broker.journal?.root,
                          NSWorkspace.shared.open(root) else {
                        throw MacUIError.action("Log folder unavailable")
                    }
                case "logs.diagnostic":
                    server.broker.journal?.diagnostic("desktop.supervisor", code: command["code"] as? String ?? "unknown")
                case "stop":
                    stopAccess()
                case "desktop_caller_trust":
                    server.service.refreshSession()
                    guard server.broker.policy.grantMode == .approval,
                          server.service.observedDesktopState == "unlocked",
                          (server.service.observedConsoleSession["uid"] as? NSNumber)?.uint32Value == getuid(),
                          let enabled = command["enabled"] as? Bool else {
                        throw MacUIError.permission("desktop_trust_operator_unavailable")
                    }
                    if enabled {
                        guard (server.broker.admission.status["active"] as? Int ?? 0) == 0,
                              let names = command["scopes"] as? [String], !names.isEmpty,
                              names.allSatisfy({ GrantScope(rawValue:$0) != nil }) else {
                            throw MacUIError.usage("Choose trusted scopes while no agent is active")
                        }
                        try server.callerTrust.enroll(VerifiedDesktopIntegration.yepAnywhere(), scopes:Set(names.compactMap(GrantScope.init(rawValue:))))
                    } else { server.callerTrust.remove() }
                    server.broker.refreshAvailability()
                    server.service.invalidateReferences()
                case "finish_exit": server.broker.journal?.finishRuntime()
                case "prepare_exit":
                    operatorDependency.cancel("operator_quit")
                    server.revoke(reason:"operator_quit")
                case "pause":
                    operatorDependency.cancel("operator_paused")
                    try server.broker.pause(seconds: command["duration"] as? Int)
                case "resume":
                    throw MacUIError.action("Resume requires asynchronous operator dispatch")
                case "control_policy", "control_notice":
                    guard let notice = command["noticeSeconds"] as? Int, (0...60).contains(notice) else {
                        throw MacUIError.usage("Choose a warning from 0 to 60 seconds")
                    }
                    UserDefaults.standard.set(notice, forKey:"machineControl.admissionNoticeSeconds")
                    server.noticeSeconds = Double(notice)
                case "start_control":
                    try server.startNow(command["intentId"] as? String ?? "")
                case "defer_control", "pause_request":
                    try server.broker.admission.deferRequest(command["intentId"] as? String ?? "",
                        seconds:command["duration"] as? Int)
                case "cancel_control":
                    try server.broker.admission.deny(command["intentId"] as? String ?? "")
                case "locked_use":
                    guard !updating, let enabled = command["enabled"] as? Bool else {
                        throw MacUIError.usage("Choose whether locked use is enabled")
                    }
                    try server.lockedUse.configure(enabled:enabled)
                case "browser_while_locked":
                    guard !updating, let enabled = command["enabled"] as? Bool else {
                        throw MacUIError.usage("Choose whether approved browser access continues while locked")
                    }
                    try server.configureBrowserWhileLocked(enabled:enabled)
                case "surface.configure":
                    guard !updating, let surface = command["surface"] as? String,
                          let mode = command["mode"] as? String,
                          let lifetime = command["lifetime"] as? String,
                          ["timed", "until_stopped"].contains(lifetime) else {
                        throw MacUIError.usage("Choose a surface, mode and lifetime")
                    }
                    let seconds = lifetime == "until_stopped" ? nil : command["duration"] as? Int
                    if lifetime == "timed" && seconds == nil { throw MacUIError.usage("Choose an access duration") }
                    try server.configureSurface(surface, mode:mode, seconds:seconds,
                        profiles:command["browserProfileIds"] as? [String] ?? [])
                case "surface.pause", "pause_surface":
                    guard let surface = command["surface"] as? String, ["desktop", "browser"].contains(surface) else {
                        throw MacUIError.usage("Choose a surface")
                    }
                    try server.broker.pause(seconds:command["duration"] as? Int, surface:surface)
                case "surface.resume", "resume_surface":
                    guard let surface = command["surface"] as? String, ["desktop", "browser"].contains(surface) else {
                        throw MacUIError.usage("Choose a surface")
                    }
                    try server.broker.resume(surface:surface)
                case "access_preferences":
                    guard let value = command["preferences"] as? [String: Any] else { throw MacUIError.usage("Choose access preferences") }
                    try server.configureAccessPreferences(value)
                case "hold_control":
                    try server.broker.admission.hold(command["intentId"] as? String ?? "")
                case "postpone_control":
                    let seconds = try accessDelaySeconds(command["duration"])
                    guard seconds > 0 else { throw MacUIError.usage("Choose a positive delay") }
                    try server.broker.admission.postpone(command["intentId"] as? String ?? "", seconds: seconds)
                case "approve_control", "continue_control":
                    try server.approveTask(command["intentId"] as? String ?? "", seconds: try accessDelaySeconds(command["duration"]))
                case "deny_control":
                    try server.broker.admission.deny(command["intentId"] as? String ?? "")
                case "decision", "arm":
                    throw MacUIError.action("legacy_grant_request_unsupported")
                case "prepare_update":
                    guard !updating, server.broker.policy.grantMode == .approval,
                          !server.broker.admission.enabled("desktop"), !server.broker.admission.enabled("browser"),
                          server.lockedUse.setupState == "idle", !server.lockedUse.isCovered,
                          server.lockedUse.lease == nil, !operatorDependency.busy else {
                        throw MacUIError.action("Stop access and finish any approval before installing an update")
                    }
                    updating = true
                case "cancel_update": updating = false
                case "permission":
                    if command["permission"] as? String == "lockedUse" {
                        guard !updating else { throw MacUIError.action("Finish updating before changing permissions") }
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
                    guard !updating, command["permission"] as? String == "lockedUse" else {
                        throw MacUIError.usage("Choose a supported helper permission")
                    }
                    try server.lockedUse.removePermission()
                case "browser.setup":
                    return ["ok": true, "extensionPath": try setupBrowserExtension(bundled: command["bundled"] as? Bool == true)]
                default: throw MacUIError.usage("Unknown operator command")
                }
                return ["ok": true]
            } catch { return ["ok": false, "error": String(describing: error)] }
        }
    }
}
