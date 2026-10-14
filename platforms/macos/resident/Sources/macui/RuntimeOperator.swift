import AppKit
import ApplicationServices
import Foundation

extension ResidentRuntime {
    /// Resume's helper wait is asynchronous; its local authority transition
    /// returns to the coordinator only while the initiating intent is live.
    func operatorCommand(_ command: [String:Any], completion: @escaping ([String:Any]) -> Void) {
        precondition(Thread.isMainThread)
        guard command["method"] as? String == "resume" else {
            completion(operatorCommand(command)); return
        }
        guard !updating else { completion(["ok":false, "error":"Finish updating before resuming"]); return }
        let observation = server.service.observedConsoleSession
        let revision = server.broker.admission.revision
        let grant = server.broker.grant?.id
        let read = resumeHelper
        operatorDependency.perform(work:{ cancelled in try read(observation, cancelled) },
            commit:{ [weak self] in
                guard let self, self.running else { throw MacUIError.action("resident_stopping") }
                guard self.server.broker.admission.revision == revision,
                      self.server.broker.grant?.id == grant else {
                    throw MacUIError.action("control_generation_changed")
                }
                try self.server.broker.resume()
            }, completion:completion)
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
                    let setup = currentSetupState(browserConnected: server.browser.connected, probeScreen: false)
                    var state: [String: Any] = ["deployment": server.broker.statusJSON,
                        "permissions": ["accessibility": setup.accessibility, "screenRecording": setup.screen == .allowed],
                        "browser": server.browser.statusJSON, "activity": server.broker.audit.reversed().prefix(30).map(\.json),
                        "logging": server.broker.journal?.health ?? [:],
                        "stopShortcutAvailable": stopShortcutAvailable(),
                        "manualUntilStoppedSupported": true,
                        "pauseSupported": true,
                        "admission": server.admissionPresentation,
                        "controlPolicy": ["supported":true, "mode":server.activity.respectRecentActivity ? "when_idle" : "announce", "noticeSeconds":server.noticeSeconds],
                        "physicalActivity": server.activity.status,
                        "observations": ["session":server.service.sessionObservation.metadata,
                                         "helper":server.service.helperObservation.metadata],
                        "desktopCallerTrust": server.callerTrust.status,
                        "lockedUse": server.lockedUse.status,
                        "presentation":presentationJSON, "nativeApproval":true,
                        "socket": server.socketPath, "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "development"]
                    if let pending = approver.request {
                        state["pending"] = ["id": pending.id, "reason": pending.reason, "caller": pending.caller.summary,
                            "scopes": pending.scopes.sorted().map(\.rawValue), "duration": pending.durationSeconds]
                    }
                    return ["ok": true, "state": state]
                case "presentation":
                    guard let name = command["profile"] as? String, let profile = PresentationProfile(rawValue:name) else {
                        throw MacUIError.usage("Choose personal, minimal or appliance presentation")
                    }
                    try configurePresentation(profile)
                case "logs.query":
                    return ["ok": true, "history": server.broker.journal?.query(offset: command["offset"] as? Int ?? 0, operation: command["operation"] as? String ?? "", outcome: command["outcome"] as? String ?? "", stream: command["stream"] as? String ?? "audit") ?? [:]]
                case "logs.debug": server.broker.journal?.debug(command["enabled"] as? Bool == true)
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
                    server.browser.closeAllSessions(reason:"desktop_trust_changed")
                case "prepare_exit":
                    operatorDependency.cancel("operator_quit")
                    server.revoke(reason:"operator_quit")
                case "pause":
                    operatorDependency.cancel("operator_paused")
                    try server.broker.pause(seconds: command["duration"] as? Int)
                case "resume":
                    throw MacUIError.action("Resume requires asynchronous operator dispatch")
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
                    guard !updating, let enabled = command["enabled"] as? Bool else {
                        throw MacUIError.usage("Choose whether locked use is enabled")
                    }
                    try server.lockedUse.configure(enabled:enabled)
                case "decision":
                    if command["allow"] as? Bool == true, server.broker.journal?.event("access.approve.intent") == false { throw MacUIError.action("Audit storage unavailable") }
                    try approver.decide(id: command["id"] as? String ?? "", scopes: command["scopes"] as? [String] ?? [],
                        duration: command["duration"] as? Int ?? 0, allow: command["allow"] as? Bool == true)
                case "arm":
                    guard server.broker.journal?.event("access.arm.intent") != false else { throw MacUIError.action("Audit storage unavailable") }
                    guard !updating, server.broker.policy.grantMode == .approval, server.broker.pending == nil,
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
                            reason: "Manually enabled by the person", requester: "local operator", approver: "local_tauri",
                            origin: .person)
                    }
                    guard server.broker.journal?.errorCode == nil else { throw MacUIError.action("Audit storage unavailable") }
                    do {
                        guard server.broker.consentStorageError == nil else { throw MacUIError.action("consent_storage_unavailable") }
                        try server.broker.consentStore?.enable(scopes:scopes,
                            duration:lifetime == "until_stopped" ? nil : command["duration"] as? Int,
                            console:server.service.observedConsoleSession)
                    } catch { server.revoke(reason:"consent_storage_unavailable"); throw error }
                case "prepare_update":
                    guard !updating, server.broker.policy.grantMode == .approval,
                          server.broker.grant == nil, server.broker.pending == nil,
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
                    // Unpacked development copy and Chrome Web Store release.
                    let origins = ["chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/",
                                   "chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/"]
                    let directory = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Google/Chrome/NativeMessagingHosts")
                    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                    let host: [String: Any] = ["name": "org.machine_control.browser", "description": "Machine Control browser provider",
                        "path": Bundle.main.executableURL!.path, "type": "stdio", "allowed_origins": origins]
                    try JSONSerialization.data(withJSONObject: host, options: [.prettyPrinted, .sortedKeys])
                        .write(to: directory.appendingPathComponent("org.machine_control.browser.json"), options: .atomic)
                    let extensionURL = Bundle.main.resourceURL!.appendingPathComponent("chrome-extension")
                    NSPasteboard.general.clearContents(); NSPasteboard.general.setString(extensionURL.path, forType: .string)
                    NSWorkspace.shared.activateFileViewerSelecting([extensionURL])
                    return ["ok": true, "extensionPath": extensionURL.path]
                default: throw MacUIError.usage("Unknown operator command")
                }
                return ["ok": true]
            } catch { return ["ok": false, "error": String(describing: error)] }
        }
    }
}
