import AppKit
import Foundation

final class AdminAuthorizationFixture: NSObject, NSApplicationDelegate {
    private let requestID = UUID().uuidString.lowercased()

    private var stateURL: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(
                "machine-control-admin-fixture/state.json")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        persist(status: "requested", authorized: false,
                commandCompleted: false, errorCode: nil)

        let source = "do shell script \"/usr/bin/id -u\" " +
            "with administrator privileges"
        var details: NSDictionary?
        let result = NSAppleScript(source: source)?
            .executeAndReturnError(&details)
        let errorCode = details?[NSAppleScript.errorNumber] as? Int
        let authorized = errorCode == nil
        let completed = authorized && result?.stringValue == "0"
        let status: String
        if completed {
            status = "completed"
        } else if errorCode == -128 {
            status = "cancelled"
        } else {
            status = "failed"
        }
        persist(status: status, authorized: authorized,
                commandCompleted: completed, errorCode: errorCode)
        NSApplication.shared.terminate(nil)
    }

    private func persist(status: String, authorized: Bool,
                         commandCompleted: Bool, errorCode: Int?) {
        var object: [String: Any] = [
            "schema": "machine-control-admin-fixture/v0",
            "requestId": requestID,
            "status": status,
            "authorized": authorized,
            "commandCompleted": commandCompleted,
            "pid": ProcessInfo.processInfo.processIdentifier,
        ]
        if let errorCode { object["errorCode"] = errorCode }
        guard let data = try? JSONSerialization.data(
            withJSONObject: object, options: [.sortedKeys]) else { return }
        let directory = stateURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700])
        try? data.write(to: stateURL, options: .atomic)
    }
}

let application = NSApplication.shared
let fixture = AdminAuthorizationFixture()
application.delegate = fixture
application.setActivationPolicy(.accessory)
application.run()
