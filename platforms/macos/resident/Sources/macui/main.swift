import AppKit
import ApplicationServices
import Darwin
import Foundation

var arguments = Array(CommandLine.arguments.dropFirst())
if arguments.count >= 4, arguments[0] == "--output",
   arguments[2] == "--status" {
    let outputPath = arguments[1]
    macUIStatusPath = arguments[3]
    removeStaleCommandDirectories(currentOutputPath: outputPath)
    guard freopen(outputPath, "w", stdout) != nil,
          freopen(outputPath, "a", stderr) != nil else {
        fail(MacUIError.action("Unable to open MacVM UI command output"))
    }
    atexit(writeMacUIExitStatus)
    arguments.removeFirst(4)
}
guard let command = arguments.first else {
    fail(MacUIError.usage(usage()), status: 2)
}

if command == "serve" || command == "request" || command == "credential" {
    do {
        guard arguments.count >= 2 else {
            throw MacUIError.usage("Usage: macui \(command) SOCKET [JSON]")
        }
        let socketPath = arguments[1]
        if command == "serve" {
            try runResident(socketPath: socketPath)
        }
        if command == "credential" {
            guard arguments.count == 3 else {
                throw MacUIError.usage(
                    "Usage: macui credential SOCKET LEASE_ID")
            }
            try runCredentialClient(
                socketPath: socketPath, leaseID: arguments[2])
            exit(0)
        }
        let requestData: Data
        if arguments.count >= 3 {
            requestData = Data(arguments[2].utf8)
        } else {
            requestData = FileHandle.standardInput.readDataToEndOfFile()
        }
        try runResidentClient(socketPath: socketPath, requestData: requestData)
        exit(0)
    } catch {
        fail(error)
    }
}

do {
    let options = try parseOptions(Array(arguments.dropFirst()))
    switch command {
    case "help", "-h", "--help":
        print(usage())
    case "session-state":
        let state = nativeSessionObservation()
        print(String(decoding: try JSONSerialization.data(withJSONObject: [
            "desktopState": state["desktopState"] ?? "unknown",
            "observationSource": "iokit.console-session"
        ]), as: UTF8.self))
    case "health":
        let frontmost = NSWorkspace.shared.frontmostApplication
        let payload: [String: Any] = [
            "accessibilityTrusted": AXIsProcessTrusted(),
            "frontmostApplication": frontmost?.localizedName ?? NSNull(),
            "frontmostPID": frontmost?.processIdentifier ?? 0,
            "user": NSUserName(),
        ]
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    case "authorize":
        let promptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        let trusted = AXIsProcessTrustedWithOptions([promptKey: true] as CFDictionary)
        if trusted {
            print("Accessibility access is granted.")
        } else {
            throw MacUIError.permission(
                "Accessibility access is pending. Use the Tart screenshot/input path " +
                "to enable MacVM UI in System Settings, then retry."
            )
        }
    case "apps":
        for app in runningApplications() {
            let active = app.isActive ? " active" : ""
            let hidden = app.isHidden ? " hidden" : ""
            print("\(app.processIdentifier)\t\(app.localizedName ?? "?")\t" +
                  "\(app.bundleIdentifier ?? "-")\(active)\(hidden)")
        }
    case "windows":
        try requireAccessibility()
        let app = try resolveApplication(options.app)
        let root = AXUIElementCreateApplication(app.processIdentifier)
        let windows = (attribute(root, kAXWindowsAttribute as CFString) as? [AXUIElement]) ?? []
        for (index, window) in windows.enumerated() {
            print(formatted(record(window, reference: index, depth: 0)))
        }
    case "tree":
        for item in try records(for: options)
            where !options.interactiveOnly || isInteractive(item) {
            print(formatted(item))
        }
    case "find":
        guard options.positionals.count == 1 else {
            throw MacUIError.usage("Usage: macui find QUERY [OPTIONS]")
        }
        let found = try matchingRecords(for: options, query: options.positionals[0])
        for item in found { print(formatted(item)) }
        if found.isEmpty { throw MacUIError.element("No matching elements") }
    case "actions":
        guard options.positionals.count == 1 else {
            throw MacUIError.usage("Usage: macui actions QUERY [OPTIONS]")
        }
        let item = try selectedRecord(for: options, query: options.positionals[0])
        print(formatted(item))
        for action in item.actions { print(action) }
    case "press":
        guard options.positionals.count == 1 else {
            throw MacUIError.usage("Usage: macui press QUERY [OPTIONS]")
        }
        try perform(kAXPressAction as CFString,
                    on: selectedRecord(for: options, query: options.positionals[0]))
    case "focus":
        guard options.positionals.count == 1 else {
            throw MacUIError.usage("Usage: macui focus QUERY [OPTIONS]")
        }
        let item = try selectedRecord(for: options, query: options.positionals[0])
        let result = AXUIElementSetAttributeValue(
            item.element, kAXFocusedAttribute as CFString, kCFBooleanTrue
        )
        guard result == .success else {
            throw MacUIError.action("Focus failed with AX error \(result.rawValue)")
        }
    case "set-value":
        guard options.positionals.count == 2 else {
            throw MacUIError.usage("Usage: macui set-value QUERY VALUE [OPTIONS]")
        }
        let item = try selectedRecord(for: options, query: options.positionals[0])
        let result = AXUIElementSetAttributeValue(
            item.element, kAXValueAttribute as CFString,
            options.positionals[1] as CFString
        )
        guard result == .success else {
            throw MacUIError.action("Set-value failed with AX error \(result.rawValue)")
        }
    default:
        throw MacUIError.usage("Unknown command: \(command)\n\n\(usage())")
    }
} catch let error as MacUIError {
    let status: Int32
    if case .usage = error { status = 2 } else { status = 1 }
    fail(error, status: status)
} catch {
    fail(error)
}
