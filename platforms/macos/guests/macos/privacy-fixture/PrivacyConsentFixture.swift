import AppKit
import ApplicationServices
import AVFoundation
import Foundation
import Network
import ScreenCaptureKit
import UserNotifications

final class PrivacyFixtureController: NSObject, NSApplicationDelegate {
    private var services: [String: [String: Any]] = [:]
    private var lastService = "none"
    private var localBrowser: NWBrowser?
    private let statusLabel = NSTextField(labelWithString: "Ready")

    private var stateURL: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("machine-control-privacy-fixture/state.json")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let definitions: [(String, String, Selector)] = [
            ("Accessibility", "accessibility", #selector(requestAccessibility)),
            ("Screen Recording", "screen-recording", #selector(requestScreenRecording)),
            ("Input Monitoring", "input-monitoring", #selector(requestInputMonitoring)),
            ("Automation (System Events)", "automation", #selector(requestAutomation)),
            ("Notifications", "notifications", #selector(requestNotifications)),
            ("Camera", "camera", #selector(requestCamera)),
            ("Microphone", "microphone", #selector(requestMicrophone)),
            ("Documents Folder", "documents-folder", #selector(requestDocuments)),
            ("Downloads Folder", "downloads-folder", #selector(requestDownloads)),
            ("Full Disk Access probe", "full-disk-access", #selector(probeFullDiskAccess)),
            ("Local Network", "local-network", #selector(requestLocalNetwork)),
            ("Refresh states", "refresh", #selector(refreshStates)),
        ]
        let buttons = definitions.map { title, identifier, action -> NSView in
            let button = NSButton(title: title, target: self, action: action)
            button.setAccessibilityIdentifier("privacy.\(identifier)")
            button.widthAnchor.constraint(equalToConstant: 260).isActive = true
            return button
        }
        statusLabel.setAccessibilityIdentifier("privacy.status")
        statusLabel.maximumNumberOfLines = 3
        let stack = NSStackView(views: buttons + [statusLabel])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 24, left: 24, bottom: 24, right: 24)
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 440, height: 600),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.title = "Machine Control Privacy Fixture"
        window.setAccessibilityIdentifier("privacy.window")
        window.contentView = stack
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        refreshCurrentStates()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func authorizationName(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: return "not_determined"
        case .restricted: return "restricted"
        case .denied: return "denied"
        case .authorized: return "authorized"
        @unknown default: return "unknown"
        }
    }

    private func notificationName(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: return "not_determined"
        case .denied: return "denied"
        case .authorized: return "authorized"
        case .provisional: return "provisional"
        case .ephemeral: return "ephemeral"
        @unknown default: return "unknown"
        }
    }

    private func update(_ service: String, _ fields: [String: Any]) {
        DispatchQueue.main.async {
            var state = self.services[service] ?? [:]
            let attempts = state["attempts"] as? Int ?? 0
            for (key, value) in fields { state[key] = value }
            if fields["event"] as? String == "requested" {
                state["attempts"] = attempts + 1
            }
            state["updatedAt"] = ISO8601DateFormatter().string(from: Date())
            self.services[service] = state
            self.lastService = service
            self.statusLabel.stringValue =
                "\(service): \(fields["authorization"] ?? fields["event"] ?? "updated")"
            self.persist()
        }
    }

    private func refreshCurrentStates() {
        update("accessibility", ["event": "observed",
            "authorization": AXIsProcessTrusted() ? "authorized" : "not_authorized"])
        update("screen-recording", ["event": "observed",
            "authorization": CGPreflightScreenCaptureAccess() ?
                "authorized" : "not_authorized"])
        update("input-monitoring", ["event": "observed",
            "authorization": CGPreflightListenEventAccess() ?
                "authorized" : "not_authorized"])
        update("camera", ["event": "observed",
            "authorization": authorizationName(AVCaptureDevice.authorizationStatus(for: .video)),
            "hardwareAvailable": AVCaptureDevice.default(for: .video) != nil])
        update("microphone", ["event": "observed",
            "authorization": authorizationName(AVCaptureDevice.authorizationStatus(for: .audio)),
            "hardwareAvailable": AVCaptureDevice.default(for: .audio) != nil])
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            self.update("notifications", ["event": "observed",
                "authorization": self.notificationName(settings.authorizationStatus)])
        }
    }

    @objc private func refreshStates(_ sender: Any?) { refreshCurrentStates() }

    @objc private func requestAccessibility(_ sender: Any?) {
        update("accessibility", ["event": "requested"])
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
            as CFDictionary
        let granted = AXIsProcessTrustedWithOptions(options)
        update("accessibility", ["event": "request_returned",
            "authorization": granted ? "authorized" : "not_authorized"])
    }

    @objc private func requestScreenRecording(_ sender: Any?) {
        update("screen-recording", ["event": "requested"])
        let granted = CGRequestScreenCaptureAccess()
        update("screen-recording", ["event": "request_returned",
            "authorization": granted ? "authorized" : "not_authorized"])
        Task {
            do {
                let content = try await SCShareableContent.excludingDesktopWindows(
                    false, onScreenWindowsOnly: true)
                self.update("screen-recording", ["event": "capture_probe_completed",
                    "captureAvailable": !content.displays.isEmpty])
            } catch {
                self.update("screen-recording", ["event": "capture_probe_completed",
                    "captureAvailable": false, "errorCode": (error as NSError).code])
            }
        }
    }

    @objc private func requestInputMonitoring(_ sender: Any?) {
        update("input-monitoring", ["event": "requested"])
        let granted = CGRequestListenEventAccess()
        update("input-monitoring", ["event": "request_returned",
            "authorization": granted ? "authorized" : "not_authorized"])
    }

    @objc private func requestAutomation(_ sender: Any?) {
        update("automation", ["event": "requested"])
        DispatchQueue.global(qos: .userInitiated).async {
            var error: NSDictionary?
            let value = NSAppleScript(source:
                "tell application \"System Events\" to get name of first process")?
                .executeAndReturnError(&error)
            let code = (error?[NSAppleScript.errorNumber] as? NSNumber)?.intValue
            self.update("automation", ["event": "request_returned",
                "effect": value?.stringValue?.isEmpty == false ?
                    "system_events_replied" : "no_reply",
                "errorCode": code.map { $0 as Any } ?? NSNull()])
        }
    }

    @objc private func requestNotifications(_ sender: Any?) {
        update("notifications", ["event": "requested"])
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .badge, .sound]) { granted, error in
            self.update("notifications", ["event": "request_completed",
                "authorization": granted ? "authorized" : "denied",
                "error": error.map { $0.localizedDescription as Any } ?? NSNull()])
        }
    }

    @objc private func requestCamera(_ sender: Any?) {
        update("camera", ["event": "requested"])
        AVCaptureDevice.requestAccess(for: .video) { granted in
            self.update("camera", ["event": "request_completed",
                "authorization": granted ? "authorized" : "denied",
                "hardwareAvailable": AVCaptureDevice.default(for: .video) != nil])
        }
    }

    @objc private func requestMicrophone(_ sender: Any?) {
        update("microphone", ["event": "requested"])
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            self.update("microphone", ["event": "request_completed",
                "authorization": granted ? "authorized" : "denied",
                "hardwareAvailable": AVCaptureDevice.default(for: .audio) != nil])
        }
    }

    private func probeFolder(_ service: String, component: String) {
        update(service, ["event": "requested"])
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(component, isDirectory: true)
        do {
            let entries = try FileManager.default.contentsOfDirectory(atPath: url.path)
            update(service, ["event": "request_returned", "effect": "read_succeeded",
                "entryCount": entries.count])
        } catch {
            update(service, ["event": "request_returned", "effect": "read_refused",
                "errorCode": (error as NSError).code])
        }
    }

    @objc private func requestDocuments(_ sender: Any?) {
        probeFolder("documents-folder", component: "Documents")
    }
    @objc private func requestDownloads(_ sender: Any?) {
        probeFolder("downloads-folder", component: "Downloads")
    }

    @objc private func probeFullDiskAccess(_ sender: Any?) {
        update("full-disk-access", ["event": "requested"])
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Safari/History.db")
        do {
            let data = try Data(contentsOf: url, options: .mappedIfSafe)
            update("full-disk-access", ["event": "request_returned",
                "effect": "protected_read_succeeded", "byteCount": data.count,
                "management": "system_settings"])
        } catch {
            update("full-disk-access", ["event": "request_returned",
                "effect": "protected_read_refused", "errorCode": (error as NSError).code,
                "management": "system_settings"])
        }
    }

    @objc private func requestLocalNetwork(_ sender: Any?) {
        update("local-network", ["event": "requested"])
        localBrowser?.cancel()
        let browser = NWBrowser(for: .bonjour(
            type: "_machine-control._tcp", domain: nil), using: .tcp)
        browser.stateUpdateHandler = { state in
            self.update("local-network", ["event": "browser_state",
                "effect": String(describing: state)])
        }
        localBrowser = browser
        browser.start(queue: DispatchQueue(label: "org.machine-control.privacy.local"))
    }

    private func persist() {
        let object: [String: Any] = ["schema": "machine-control-macos-privacy-fixture/v0",
            "lastService": lastService, "services": services,
            "pid": ProcessInfo.processInfo.processIdentifier]
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(
                withJSONObject: object, options: [.sortedKeys]) else { return }
        let directory = stateURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: directory,
            withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? data.write(to: stateURL, options: .atomic)
    }
}

let application = NSApplication.shared
let controller = PrivacyFixtureController()
application.delegate = controller
application.setActivationPolicy(.regular)
application.run()
