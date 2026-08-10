import AppKit
import ApplicationServices
import CoreGraphics
import Darwin
import Foundation
import SystemConfiguration

enum MacUIError: Error, CustomStringConvertible {
    case usage(String)
    case permission(String)
    case application(String)
    case element(String)
    case action(String)

    var description: String {
        switch self {
        case let .usage(message), let .permission(message),
             let .application(message), let .element(message),
             let .action(message):
            return message
        }
    }
}

struct Options {
    var app: String?
    var role: String?
    var depth = 8
    var limit = 500
    var nth = 1
    var interactiveOnly = false
    var exact = false
    var positionals: [String] = []
}

struct ElementRecord {
    let element: AXUIElement
    let reference: Int
    let depth: Int
    let role: String
    let subrole: String
    let title: String
    let description: String
    let value: String
    let identifier: String
    let enabled: Bool?
    let focused: Bool?
    let position: CGPoint?
    let size: CGSize?
    let actions: [String]
}

var macUIExitStatus: Int32 = 0
var macUIStatusPath: String?

func writeMacUIExitStatus() {
    guard let path = macUIStatusPath else { return }
    try? "\(macUIExitStatus)\n".write(
        toFile: path, atomically: true, encoding: .utf8
    )
}

func removeStaleCommandDirectories(currentOutputPath: String) {
    let fileManager = FileManager.default
    let currentDirectory = URL(fileURLWithPath: currentOutputPath)
        .deletingLastPathComponent().standardizedFileURL.path
    let temporaryDirectory = URL(fileURLWithPath: "/tmp", isDirectory: true)
    let staleBefore = Date().addingTimeInterval(-300)
    guard let entries = try? fileManager.contentsOfDirectory(
        at: temporaryDirectory,
        includingPropertiesForKeys: [.isDirectoryKey, .contentModificationDateKey],
        options: [.skipsHiddenFiles]
    ) else { return }
    for entry in entries where entry.lastPathComponent.hasPrefix("macvm-ui.") {
        guard entry.standardizedFileURL.path != currentDirectory,
              let values = try? entry.resourceValues(
                  forKeys: [.isDirectoryKey, .contentModificationDateKey]
              ),
              values.isDirectory == true,
              let modified = values.contentModificationDate,
              modified < staleBefore else { continue }
        try? fileManager.removeItem(at: entry)
    }
}

func fail(_ error: Error, status: Int32 = 1) -> Never {
    macUIExitStatus = status
    fputs("\(error)\n", stderr)
    exit(status)
}

func usage() -> String {
    """
    Usage: macui COMMAND [ARG...]

      health | authorize | apps
      windows [--app APP]
      tree [--app APP] [--depth N] [--limit N] [--interactive]
      find QUERY [--app APP] [--role ROLE] [--depth N] [--limit N]
      actions QUERY [--app APP] [--role ROLE] [--nth N]
      press QUERY [--app APP] [--role ROLE] [--nth N]
      focus QUERY [--app APP] [--role ROLE] [--nth N]
      set-value QUERY VALUE [--app APP] [--role ROLE] [--nth N]
    """
}

func parseOptions(_ arguments: [String]) throws -> Options {
    var options = Options()
    var index = 0
    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--app", "--role", "--depth", "--limit", "--nth":
            guard index + 1 < arguments.count else {
                throw MacUIError.usage("Missing value for \(argument)")
            }
            let value = arguments[index + 1]
            switch argument {
            case "--app": options.app = value
            case "--role": options.role = value
            case "--depth":
                guard let parsed = Int(value), parsed >= 0 else {
                    throw MacUIError.usage("--depth must be a non-negative integer")
                }
                options.depth = parsed
            case "--limit":
                guard let parsed = Int(value), parsed > 0 else {
                    throw MacUIError.usage("--limit must be a positive integer")
                }
                options.limit = parsed
            case "--nth":
                guard let parsed = Int(value), parsed > 0 else {
                    throw MacUIError.usage("--nth must be a positive integer")
                }
                options.nth = parsed
            default: break
            }
            index += 2
        case "--interactive":
            options.interactiveOnly = true
            index += 1
        case "--exact":
            options.exact = true
            index += 1
        default:
            if argument.hasPrefix("--") {
                throw MacUIError.usage("Unknown option: \(argument)")
            }
            options.positionals.append(argument)
            index += 1
        }
    }
    return options
}

func attribute(_ element: AXUIElement, _ name: CFString) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name, &value) == .success else {
        return nil
    }
    return value
}

func stringAttribute(_ element: AXUIElement, _ name: CFString) -> String {
    guard let value = attribute(element, name) else { return "" }
    if let string = value as? String { return string }
    if let number = value as? NSNumber { return number.stringValue }
    if let attributed = value as? NSAttributedString { return attributed.string }
    return ""
}

func boolAttribute(_ element: AXUIElement, _ name: CFString) -> Bool? {
    (attribute(element, name) as? NSNumber)?.boolValue
}

func pointAttribute(_ element: AXUIElement, _ name: CFString) -> CGPoint? {
    guard let raw = attribute(element, name),
          CFGetTypeID(raw) == AXValueGetTypeID() else { return nil }
    let value = unsafeBitCast(raw, to: AXValue.self)
    guard AXValueGetType(value) == .cgPoint else { return nil }
    var point = CGPoint.zero
    return AXValueGetValue(value, .cgPoint, &point) ? point : nil
}

func sizeAttribute(_ element: AXUIElement, _ name: CFString) -> CGSize? {
    guard let raw = attribute(element, name),
          CFGetTypeID(raw) == AXValueGetTypeID() else { return nil }
    let value = unsafeBitCast(raw, to: AXValue.self)
    guard AXValueGetType(value) == .cgSize else { return nil }
    var size = CGSize.zero
    return AXValueGetValue(value, .cgSize, &size) ? size : nil
}

func childElements(_ element: AXUIElement) -> [AXUIElement] {
    (attribute(element, kAXChildrenAttribute as CFString) as? [AXUIElement]) ?? []
}

func actionNames(_ element: AXUIElement) -> [String] {
    var names: CFArray?
    guard AXUIElementCopyActionNames(element, &names) == .success,
          let result = names as? [String] else { return [] }
    return result
}

func clean(_ value: String, limit: Int = 120) -> String {
    let collapsed = value
        .replacingOccurrences(of: "\n", with: " ")
        .replacingOccurrences(of: "\r", with: " ")
    if collapsed.count <= limit { return collapsed }
    return String(collapsed.prefix(limit - 1)) + "…"
}

func record(_ element: AXUIElement, reference: Int, depth: Int) -> ElementRecord {
    ElementRecord(
        element: element,
        reference: reference,
        depth: depth,
        role: stringAttribute(element, kAXRoleAttribute as CFString),
        subrole: stringAttribute(element, kAXSubroleAttribute as CFString),
        title: stringAttribute(element, kAXTitleAttribute as CFString),
        description: stringAttribute(element, kAXDescriptionAttribute as CFString),
        value: stringAttribute(element, kAXValueAttribute as CFString),
        identifier: stringAttribute(element, kAXIdentifierAttribute as CFString),
        enabled: boolAttribute(element, kAXEnabledAttribute as CFString),
        focused: boolAttribute(element, kAXFocusedAttribute as CFString),
        position: pointAttribute(element, kAXPositionAttribute as CFString),
        size: sizeAttribute(element, kAXSizeAttribute as CFString),
        actions: actionNames(element)
    )
}

func traverse(root: AXUIElement, maxDepth: Int, limit: Int) -> [ElementRecord] {
    var records: [ElementRecord] = []

    func visit(_ element: AXUIElement, depth: Int) {
        guard depth <= maxDepth, records.count < limit else { return }
        records.append(record(element, reference: records.count, depth: depth))
        guard depth < maxDepth else { return }
        for child in childElements(element) {
            visit(child, depth: depth + 1)
            if records.count >= limit { break }
        }
    }

    visit(root, depth: 0)
    return records
}

func normalizedRole(_ role: String) -> String {
    let lowered = role.lowercased()
    return lowered.hasPrefix("ax") ? String(lowered.dropFirst(2)) : lowered
}

func matches(_ record: ElementRecord, query: String,
             role: String?, exact: Bool) -> Bool {
    if let role, normalizedRole(record.role) != normalizedRole(role) {
        return false
    }
    let values = [record.title, record.description, record.value,
                  record.identifier, record.role, record.subrole]
        .filter { !$0.isEmpty }
    if query.isEmpty { return true }
    if exact {
        return values.contains { $0.caseInsensitiveCompare(query) == .orderedSame }
    }
    return values.contains {
        $0.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) != nil
    }
}

func isInteractive(_ record: ElementRecord) -> Bool {
    if !record.actions.isEmpty { return true }
    let role = normalizedRole(record.role)
    return ["button", "checkbox", "combobox", "link", "menuitem", "radiobutton",
            "slider", "textfield", "textarea", "switch", "tabgroup"]
        .contains(role)
}

func formatted(_ record: ElementRecord) -> String {
    var parts = ["@\(record.reference)", record.role.isEmpty ? "AXUnknown" : record.role]
    let label = [record.title, record.description, record.value]
        .first(where: { !$0.isEmpty }) ?? ""
    if !label.isEmpty { parts.append("\"\(clean(label))\"") }
    if !record.identifier.isEmpty { parts.append("id=\(clean(record.identifier, limit: 60))") }
    if let position = record.position, let size = record.size {
        parts.append("[\(Int(position.x)),\(Int(position.y)) " +
                     "\(Int(size.width))x\(Int(size.height))]")
    }
    if record.enabled == false { parts.append("disabled") }
    if record.focused == true { parts.append("focused") }
    if !record.actions.isEmpty {
        parts.append("actions=\(record.actions.map(normalizedRole).joined(separator: ","))")
    }
    return String(repeating: "  ", count: record.depth) + parts.joined(separator: " ")
}

func runningApplications() -> [NSRunningApplication] {
    NSWorkspace.shared.runningApplications
        .filter { !$0.isTerminated }
        .sorted {
            ($0.localizedName ?? $0.bundleIdentifier ?? "")
                .localizedCaseInsensitiveCompare(
                    $1.localizedName ?? $1.bundleIdentifier ?? ""
                ) == .orderedAscending
        }
}

func resolveApplication(_ query: String?) throws -> NSRunningApplication {
    if query == nil {
        guard let frontmost = NSWorkspace.shared.frontmostApplication else {
            throw MacUIError.application("No frontmost application")
        }
        return frontmost
    }

    let wanted = query!
    if let pid = Int32(wanted),
       let app = NSRunningApplication(processIdentifier: pid) {
        return app
    }

    let apps = runningApplications()
    if let exact = apps.first(where: {
        $0.localizedName?.caseInsensitiveCompare(wanted) == .orderedSame ||
        $0.bundleIdentifier?.caseInsensitiveCompare(wanted) == .orderedSame
    }) {
        return exact
    }

    let matches = apps.filter {
        ($0.localizedName?.localizedCaseInsensitiveContains(wanted) ?? false) ||
        ($0.bundleIdentifier?.localizedCaseInsensitiveContains(wanted) ?? false)
    }
    guard matches.count == 1, let match = matches.first else {
        let names = matches.prefix(10).map {
            "\($0.localizedName ?? "?") (\($0.bundleIdentifier ?? "no bundle id"), pid \($0.processIdentifier))"
        }
        if matches.isEmpty {
            throw MacUIError.application("No running application matches '\(wanted)'")
        }
        throw MacUIError.application(
            "Application query '\(wanted)' is ambiguous:\n" + names.joined(separator: "\n")
        )
    }
    return match
}

func requireAccessibility() throws {
    guard AXIsProcessTrusted() else {
        throw MacUIError.permission(
            "Accessibility access is not granted. Run: macvm authorize-ui"
        )
    }
}

func records(for options: Options) throws -> [ElementRecord] {
    try requireAccessibility()
    let app = try resolveApplication(options.app)
    let root = AXUIElementCreateApplication(app.processIdentifier)
    return traverse(root: root, maxDepth: options.depth, limit: options.limit)
}

func matchingRecords(for options: Options, query: String) throws -> [ElementRecord] {
    try records(for: options).filter {
        matches($0, query: query, role: options.role, exact: options.exact)
    }
}

func selectedRecord(for options: Options, query: String) throws -> ElementRecord {
    let found = try matchingRecords(for: options, query: query)
    guard options.nth <= found.count else {
        throw MacUIError.element(
            "Found \(found.count) matching element(s); --nth \(options.nth) is unavailable"
        )
    }
    return found[options.nth - 1]
}

func perform(_ action: CFString, on record: ElementRecord) throws {
    let result = AXUIElementPerformAction(record.element, action)
    guard result == .success else {
        throw MacUIError.action(
            "\(action) failed for @\(record.reference) with AX error \(result.rawValue)"
        )
    }
}

// MARK: - Persistent machine-control facade

struct CuaReference {
    let pid: Int
    let windowID: Int
    let snapshotID: String
    let token: String
}

struct AuthorizationSheet {
    let processID: pid_t
    let windowID: Int
    let requester: String
    let secureField: AXUIElement
    let cancelButton: AXUIElement
    let confirmButton: AXUIElement
}

struct AuthorizationLease {
    let id: String
    let contextID: String
    let requester: String
    let processID: pid_t
    let windowID: Int
    let createdAt: Date
    let expiresAt: Date
    var used: Bool
}

final class ResidentService {
    let generation = UUID().uuidString.lowercased()
    private var snapshotNumber = 0
    private var references: [String: AXUIElement] = [:]
    private var cuaReferences: [String: CuaReference] = [:]
    private var referenceOrder: [String] = []
    private var authorizationLeases: [String: AuthorizationLease] = [:]

    private func requestString(_ request: [String: Any], _ key: String) -> String? {
        guard let value = request[key] as? String, !value.isEmpty else { return nil }
        return value
    }

    private func requestInt(_ request: [String: Any], _ key: String,
                            default fallback: Int) -> Int {
        if let value = request[key] as? Int { return value }
        if let value = request[key] as? NSNumber { return value.intValue }
        return fallback
    }

    private var cuaExecutable: URL? {
        let homeCandidate = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/bin/cua-driver-local")
        if FileManager.default.isExecutableFile(atPath: homeCandidate.path) {
            return homeCandidate
        }
        let applicationCandidate = URL(fileURLWithPath:
            "/Applications/CuaDriverLocal.app/Contents/MacOS/cua-driver-local")
        return FileManager.default.isExecutableFile(atPath: applicationCandidate.path) ?
            applicationCandidate : nil
    }

    private func cuaCall(_ tool: String, _ arguments: [String: Any]) throws
        -> [String: Any] {
        guard let executable = cuaExecutable else {
            throw MacUIError.application("Cua Driver is not installed")
        }
        let argumentData = try JSONSerialization.data(
            withJSONObject: arguments, options: [.sortedKeys])
        let process = Process()
        let output = Pipe()
        let errors = Pipe()
        process.executableURL = executable
        process.arguments = ["call", tool, String(decoding: argumentData, as: UTF8.self)]
        process.standardOutput = output
        process.standardError = errors
        try process.run()
        let outputData = output.fileHandleForReading.readDataToEndOfFile()
        let errorData = errors.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            let message = String(decoding: errorData, as: UTF8.self)
            throw MacUIError.action("Cua \(tool) failed: \(clean(message))")
        }
        let object = try JSONSerialization.jsonObject(with: outputData)
        guard let result = object as? [String: Any] else {
            throw MacUIError.action("Cua \(tool) returned non-object JSON")
        }
        return result
    }

    private func cuaPermissions() -> [String: Any]? {
        guard let executable = cuaExecutable else { return nil }
        let process = Process()
        let output = Pipe()
        process.executableURL = executable
        process.arguments = ["permissions", "status", "--json"]
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            guard process.terminationStatus == 0,
                  let object = try JSONSerialization.jsonObject(with: data)
                    as? [String: Any], object["refusal"] == nil else { return nil }
            return object
        } catch { return nil }
    }

    private func useCua(_ request: [String: Any]) -> Bool {
        let requested = requestString(request, "provider")
        if requested == "macos-native" { return false }
        if requested == "cua" { return true }
        return !AXIsProcessTrusted() && cuaPermissions() != nil
    }

    private func cuaApplication(_ query: String) throws -> (Int, String) {
        let apps = try cuaCall("list_apps", [:])["apps"] as? [[String: Any]] ?? []
        let matching = apps.filter {
            (($0["name"] as? String)?.localizedCaseInsensitiveContains(query) ?? false) ||
            (($0["bundle_id"] as? String)?.localizedCaseInsensitiveContains(query) ?? false)
        }
        guard let app = matching.first(where: {
            ($0["name"] as? String)?.caseInsensitiveCompare(query) == .orderedSame ||
            ($0["bundle_id"] as? String)?.caseInsensitiveCompare(query) == .orderedSame
        }) ?? (matching.count == 1 ? matching[0] : nil),
              let pid = (app["pid"] as? NSNumber)?.intValue, pid > 0 else {
            throw MacUIError.application("No unique running Cua application matches '\(query)'")
        }
        return (pid, app["name"] as? String ?? query)
    }

    private func cuaWindow(pid: Int) throws -> [String: Any] {
        let windows = try cuaCall("list_windows", [:])["windows"]
            as? [[String: Any]] ?? []
        guard let window = windows.first(where: {
            ($0["pid"] as? NSNumber)?.intValue == pid &&
            ($0["layer"] as? NSNumber)?.intValue == 0 &&
            ($0["is_on_screen"] as? Bool) == true &&
            (($0["bounds"] as? [String: Any])?["width"] as? NSNumber)?.doubleValue ?? 0 > 1
        }) else {
            throw MacUIError.element("Cua found no on-screen window for pid \(pid)")
        }
        return window
    }

    private func projectCuaResult(_ request: [String: Any], providerOperation: String,
                                  providerResult: [String: Any],
                                  route: String) -> [String: Any] {
        if let refusal = providerResult["refusal"] as? [String: Any] {
            return refused(request,
                code: refusal["code"] as? String ?? "provider_refused",
                message: refusal["message"] as? String ?? "Cua refused the operation",
                route: route)
        }
        if let code = providerResult["error"] as? String {
            return refused(request, code: code.lowercased(),
                           message: "Cua \(providerOperation) reported \(code)",
                           route: route)
        }
        if providerResult["effect"] as? String == "refused" ||
                providerResult["code"] != nil {
            return refused(request,
                code: providerResult["code"] as? String ?? "provider_refused",
                message: providerResult["message"] as? String ??
                    "Cua \(providerOperation) refused the operation",
                route: route)
        }
        let delivery: String
        if let value = providerResult["delivery"] as? String {
            delivery = value
        } else if providerResult["delivery"] != nil {
            delivery = "confirmed"
        } else {
            delivery = "confirmed"
        }
        let effect = providerResult["effect"] as? String ?? "confirmed"
        var result = base(request, route: route)
        result["delivery"] = delivery
        result["effect"] = effect
        result["uncertainty"] = effect == "unverifiable" ?
            "provider_effect_unverifiable" : "none"
        result["providerAttempts"] = [[
            "provider": "cua", "operation": providerOperation,
            "outcome": "completed",
            "delivery": delivery,
            "effect": effect,
        ]]
        result["data"] = providerResult
        return result
    }

    private func base(_ request: [String: Any], accepted: Bool = true,
                      route: String = "guest.user/macos.resident") -> [String: Any] {
        [
            "schema": "machine-control/v0",
            "requestId": requestString(request, "requestId") ?? UUID().uuidString.lowercased(),
            "operation": requestString(request, "operation") ?? "unknown",
            "accepted": accepted,
            "actualRoute": route,
            "desktop": "Aqua",
            "generation": generation,
            "hostInterference": "none",
            "uncertainty": "none",
            "retrySafety": "not_applicable",
            "fallbackUsed": false,
            "agentRoundTrips": 1,
            "retryCount": 0,
            "staleReferenceEvents": 0,
        ]
    }

    private func refused(_ request: [String: Any], code: String,
                         message: String, route: String = "guest.user/macos.resident",
                         stale: Bool = false) -> [String: Any] {
        var result = base(request, accepted: false, route: route)
        result["delivery"] = "refused"
        result["effect"] = "refused"
        result["errorCode"] = code
        result["message"] = message
        result["staleReferenceEvents"] = stale ? 1 : 0
        return result
    }

    private func applicationJSON(_ app: NSRunningApplication) -> [String: Any] {
        [
            "processId": app.processIdentifier,
            "name": app.localizedName ?? NSNull(),
            "bundleId": app.bundleIdentifier ?? NSNull(),
            "running": !app.isTerminated,
            "active": app.isActive,
            "hidden": app.isHidden,
            "terminated": app.isTerminated,
        ]
    }

    private func cuaApplicationJSON(_ app: [String: Any]) -> [String: Any] {
        let running = app["running"] as? Bool ?? false
        return [
            "processId": app["pid"] ?? 0,
            "name": app["name"] ?? NSNull(),
            "bundleId": app["bundle_id"] ?? NSNull(),
            "running": running,
            "active": app["active"] ?? false,
            "hidden": app["hidden"] ?? false,
            "terminated": !running,
        ]
    }

    private func normalizedBounds(_ bounds: [String: Any]) -> [String: Any] {
        [
            "x": bounds["x"] ?? bounds["X"] ?? 0,
            "y": bounds["y"] ?? bounds["Y"] ?? 0,
            "width": bounds["width"] ?? bounds["Width"] ?? 0,
            "height": bounds["height"] ?? bounds["Height"] ?? 0,
        ]
    }

    private func cuaWindowJSON(_ window: [String: Any]) -> [String: Any] {
        [
            "windowId": window["window_id"] ?? 0,
            "processId": window["pid"] ?? 0,
            "owner": window["app_name"] ?? "",
            "title": window["title"] ?? "",
            "layer": window["layer"] ?? 0,
            "bounds": normalizedBounds(
                window["bounds"] as? [String: Any] ?? [:]),
            "onScreen": window["is_on_screen"] ?? false,
        ]
    }

    private func rectJSON(position: CGPoint?, size: CGSize?) -> [String: Any]? {
        guard let position, let size else { return nil }
        return [
            "x": Double(position.x), "y": Double(position.y),
            "width": Double(size.width), "height": Double(size.height),
        ]
    }

    private func elementJSON(_ item: ElementRecord, reference: String,
                             compact: Bool) -> [String: Any] {
        let label = item.title.isEmpty ? item.description : item.title
        if compact {
            var result: [String: Any] = [
                "reference": reference,
                "depth": item.depth,
                "role": item.role.isEmpty ? "AXUnknown" : item.role,
                "label": label,
                "identifier": item.identifier,
                "enabled": item.enabled ?? true,
                "actions": item.actions,
            ]
            if !item.value.isEmpty { result["value"] = item.value }
            if let rect = rectJSON(position: item.position, size: item.size) {
                result["bounds"] = rect
            }
            return result
        }
        var result: [String: Any] = [
            "reference": reference,
            "depth": item.depth,
            "role": item.role.isEmpty ? "AXUnknown" : item.role,
            "label": label,
            "subrole": item.subrole,
            "title": item.title,
            "description": item.description,
            "value": item.value,
            "identifier": item.identifier,
            "enabled": item.enabled ?? true,
            "focused": item.focused ?? false,
            "actions": item.actions,
        ]
        if let rect = rectJSON(position: item.position, size: item.size) {
            result["bounds"] = rect
        }
        return result
    }

    private func recordsMatchingQuery(_ records: [ElementRecord],
                                      query: String?) -> [ElementRecord] {
        guard let query, !query.isEmpty else { return records }
        return records.filter { item in
            [item.role, item.subrole, item.title, item.description,
             item.value, item.identifier].contains {
                $0.localizedCaseInsensitiveContains(query)
            }
        }
    }

    private func cuaElementJSON(_ element: [String: Any], reference: String,
                                compact: Bool) -> [String: Any] {
        var result: [String: Any] = [
            "reference": reference,
            "depth": element["depth"] ?? 0,
            "role": element["role"] ?? "AXUnknown",
            "label": element["label"] ?? element["name"] ?? "",
            "enabled": element["enabled"] ?? true,
        ]
        for key in ["value", "identifier", "bounds", "actions"] {
            if let value = element[key] { result[key] = value }
        }
        if !compact {
            for key in ["subrole", "title", "description", "focused"] {
                if let value = element[key] { result[key] = value }
            }
        }
        return result
    }

    private func remember(_ records: [ElementRecord]) -> (String, [[String: Any]], [[String: Any]]) {
        snapshotNumber += 1
        let snapshot = "s\(snapshotNumber)"
        var full: [[String: Any]] = []
        var compact: [[String: Any]] = []
        for item in records {
            let reference = "\(generation):\(snapshot):\(item.reference)"
            references[reference] = item.element
            referenceOrder.append(reference)
            full.append(elementJSON(item, reference: reference, compact: false))
            compact.append(elementJSON(item, reference: reference, compact: true))
        }
        while referenceOrder.count > 4_000 {
            references.removeValue(forKey: referenceOrder.removeFirst())
        }
        return (snapshot, full, compact)
    }

    private func applicationRecords(_ request: [String: Any]) throws
        -> (NSRunningApplication, [ElementRecord]) {
        try requireAccessibility()
        let app = try resolveApplication(requestString(request, "target"))
        let root = AXUIElementCreateApplication(app.processIdentifier)
        let depth = max(0, min(requestInt(request, "maxDepth", default: 8), 30))
        let limit = max(1, min(requestInt(request, "maxElements", default: 500), 2_000))
        return (app, traverse(root: root, maxDepth: depth, limit: limit))
    }

    private func observationFingerprint() -> String {
        var parts: [String] = []
        for app in runningApplications() {
            parts.append("a:\(app.processIdentifier):\(app.isActive):\(app.isHidden)")
            let root = AXUIElementCreateApplication(app.processIdentifier)
            let windows = (attribute(root, kAXWindowsAttribute as CFString)
                           as? [AXUIElement]) ?? []
            for window in windows.prefix(12) {
                parts.append("w:\(app.processIdentifier):" +
                    stringAttribute(window, kAXTitleAttribute as CFString) + ":" +
                    stringAttribute(window, kAXValueAttribute as CFString))
            }
        }
        return parts.joined(separator: "|")
    }

    private func activateTarget(_ query: String?) throws -> NSRunningApplication? {
        guard let query else { return nil }
        let app = try resolveApplication(query)
        _ = app.activate(options: [.activateIgnoringOtherApps])
        usleep(120_000)
        return app
    }

    private func keyCode(_ name: String) -> CGKeyCode? {
        let codes: [String: CGKeyCode] = [
            "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
            "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
            "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
            "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
            "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
            "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
            "enter": 36, "return": 36, "l": 37, "j": 38, "'": 39,
            "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45,
            "m": 46, ".": 47, "tab": 48, "space": 49, "delete": 51,
            "`": 50, "escape": 53, "esc": 53, "left": 123, "right": 124,
            "down": 125, "up": 126,
        ]
        return codes[name.lowercased()]
    }

    private func sendKey(_ chord: String) throws {
        let parts = chord.lowercased().split(separator: "-").map(String.init)
        guard let keyName = parts.last, let code = keyCode(keyName) else {
            throw MacUIError.usage("Unsupported key chord: \(chord)")
        }
        var flags: CGEventFlags = []
        for modifier in parts.dropLast() {
            switch modifier {
            case "cmd", "command": flags.insert(.maskCommand)
            case "shift": flags.insert(.maskShift)
            case "ctrl", "control": flags.insert(.maskControl)
            case "option", "alt": flags.insert(.maskAlternate)
            default: throw MacUIError.usage("Unsupported key modifier: \(modifier)")
            }
        }
        guard let down = CGEvent(keyboardEventSource: nil, virtualKey: code,
                                 keyDown: true),
              let up = CGEvent(keyboardEventSource: nil, virtualKey: code,
                               keyDown: false) else {
            throw MacUIError.action("Unable to create keyboard event")
        }
        down.flags = flags
        up.flags = flags
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
    }

    private func sendText(_ text: String) throws {
        for character in text {
            let units = Array(String(character).utf16)
            guard let down = CGEvent(keyboardEventSource: nil, virtualKey: 0,
                                     keyDown: true),
                  let up = CGEvent(keyboardEventSource: nil, virtualKey: 0,
                                   keyDown: false) else {
                throw MacUIError.action("Unable to create text event")
            }
            units.withUnsafeBufferPointer { buffer in
                down.keyboardSetUnicodeString(stringLength: units.count,
                                              unicodeString: buffer.baseAddress!)
                up.keyboardSetUnicodeString(stringLength: units.count,
                                            unicodeString: buffer.baseAddress!)
            }
            down.post(tap: .cghidEventTap)
            up.post(tap: .cghidEventTap)
        }
    }

    private func windowList(ownerPID: pid_t? = nil) -> [[String: Any]] {
        guard let raw = CGWindowListCopyWindowInfo(
            [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID
        ) as? [[String: Any]] else { return [] }
        return raw.filter { info in
            guard let ownerPID else { return true }
            return (info[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == ownerPID
        }.map { info in
            let bounds = info[kCGWindowBounds as String] as? [String: Any] ?? [:]
            return [
                "windowId": info[kCGWindowNumber as String] ?? 0,
                "processId": info[kCGWindowOwnerPID as String] ?? 0,
                "owner": info[kCGWindowOwnerName as String] ?? "",
                "title": info[kCGWindowName as String] ?? "",
                "layer": info[kCGWindowLayer as String] ?? 0,
                "bounds": normalizedBounds(bounds),
                "onScreen": true,
            ]
        }
    }

    private func launchApplication(_ query: String,
                                   argument: String? = nil) throws
        -> NSRunningApplication {
        let before = Set(runningApplications().map(\.processIdentifier))
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        if query.contains(".") && !query.contains("/") {
            process.arguments = ["-b", query]
        } else {
            process.arguments = ["-a", query]
        }
        if let argument, !argument.isEmpty { process.arguments?.append(argument) }
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw MacUIError.application("Application launch failed: \(query)")
        }
        for _ in 0..<30 {
            if let app = try? resolveApplication(query) {
                _ = app.activate(options: [.activateIgnoringOtherApps])
                return app
            }
            if let app = runningApplications().first(where: {
                !before.contains($0.processIdentifier) && $0.activationPolicy == .regular
            }) {
                return app
            }
            usleep(100_000)
        }
        throw MacUIError.application("Application did not become observable: \(query)")
    }

    private func artifactURL() throws -> URL {
        let root = FileManager.default.urls(for: .cachesDirectory,
                                             in: .userDomainMask)[0]
            .appendingPathComponent("machine-control/artifacts", isDirectory: true)
        try FileManager.default.createDirectory(at: root,
                                                withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        let existing = (try? FileManager.default.contentsOfDirectory(
            at: root, includingPropertiesForKeys: [.contentModificationDateKey]
        )) ?? []
        let ordered = existing.sorted {
            let left = (try? $0.resourceValues(forKeys: [.contentModificationDateKey])
                .contentModificationDate) ?? .distantPast
            let right = (try? $1.resourceValues(forKeys: [.contentModificationDateKey])
                .contentModificationDate) ?? .distantPast
            return left < right
        }
        for url in ordered.dropLast(15) { try? FileManager.default.removeItem(at: url) }
        return root.appendingPathComponent("capture-\(UUID().uuidString.lowercased()).png")
    }

    private func activeDisplayJSON() -> [[String: Any]] {
        var count: UInt32 = 0
        guard CGGetActiveDisplayList(0, nil, &count) == .success,
              count > 0 else { return [] }
        var identifiers = [CGDirectDisplayID](repeating: 0, count: Int(count))
        guard CGGetActiveDisplayList(count, &identifiers, &count) == .success else {
            return []
        }
        let main = CGMainDisplayID()
        return identifiers.prefix(Int(count)).map { identifier in
            let bounds = CGDisplayBounds(identifier)
            let mode = CGDisplayCopyDisplayMode(identifier)
            let pixelWidth = mode?.pixelWidth ?? CGDisplayPixelsWide(identifier)
            let pixelHeight = mode?.pixelHeight ?? CGDisplayPixelsHigh(identifier)
            return [
                "displayId": identifier,
                "main": identifier == main,
                "bounds": [
                    "x": Double(bounds.origin.x),
                    "y": Double(bounds.origin.y),
                    "width": Double(bounds.width),
                    "height": Double(bounds.height),
                ],
                "pixelWidth": pixelWidth,
                "pixelHeight": pixelHeight,
                "scaleX": bounds.width > 0 ?
                    Double(pixelWidth) / Double(bounds.width) : 1,
                "scaleY": bounds.height > 0 ?
                    Double(pixelHeight) / Double(bounds.height) : 1,
            ]
        }
    }

    private func pointIsOnActiveDisplay(_ point: CGPoint) -> Bool {
        activeDisplayJSON().contains { display in
            guard let bounds = display["bounds"] as? [String: Any],
                  let x = bounds["x"] as? Double,
                  let y = bounds["y"] as? Double,
                  let width = bounds["width"] as? Double,
                  let height = bounds["height"] as? Double else { return false }
            return point.x >= x && point.x < x + width &&
                point.y >= y && point.y < y + height
        }
    }

    private func pointerButton(_ name: String?)
        throws -> (CGMouseButton, CGEventType, CGEventType) {
        switch name?.lowercased() ?? "left" {
        case "left": return (.left, .leftMouseDown, .leftMouseUp)
        case "right": return (.right, .rightMouseDown, .rightMouseUp)
        case "middle", "center": return (.center, .otherMouseDown, .otherMouseUp)
        default: throw MacUIError.usage("button must be left, right, or middle")
        }
    }

    private func validateCoordinateSpace(_ request: [String: Any]) throws {
        guard let space = requestString(request, "coordinateSpace") else { return }
        guard space == "global_display_points" else {
            throw MacUIError.usage(
                "coordinateSpace must be global_display_points for target-local input")
        }
    }

    private func authorizationSheet(expectedRequester: String) throws
        -> AuthorizationSheet {
        try requireAccessibility()
        let matching = runningApplications().filter {
            $0.bundleIdentifier == "com.apple.SecurityAgent" && !$0.isTerminated
        }
        guard matching.count == 1, let app = matching.first, app.isActive else {
            throw MacUIError.element(
                "No unique active SecurityAgent authorization sheet is present")
        }
        let root = AXUIElementCreateApplication(app.processIdentifier)
        let records = traverse(root: root, maxDepth: 16, limit: 300)
        let text = records.flatMap { [$0.title, $0.description, $0.value] }
            .filter { !$0.isEmpty }
        guard text.contains(expectedRequester),
              text.contains("\(expectedRequester) wants to make changes."),
              text.contains("Enter your password to allow this.") else {
            throw MacUIError.element(
                "SecurityAgent sheet did not match the expected requester")
        }
        let secureFields = records.filter {
            $0.role == "AXTextField" && $0.subrole == "AXSecureTextField"
        }
        let cancelButtons = records.filter {
            $0.role == "AXButton" && $0.title == "Cancel" &&
                $0.actions.contains(kAXPressAction as String)
        }
        let confirmButtons = records.filter {
            $0.role == "AXButton" && $0.title == "OK" &&
                $0.actions.contains(kAXPressAction as String)
        }
        guard secureFields.count == 1, cancelButtons.count == 1,
              confirmButtons.count == 1 else {
            throw MacUIError.element(
                "SecurityAgent sheet controls did not match the strict fingerprint")
        }
        let windows = windowList(ownerPID: app.processIdentifier)
        guard windows.count == 1,
              let number = windows[0]["windowId"] as? NSNumber else {
            throw MacUIError.element(
                "SecurityAgent did not expose one exact on-screen window")
        }
        return AuthorizationSheet(
            processID: app.processIdentifier,
            windowID: number.intValue,
            requester: expectedRequester,
            secureField: secureFields[0].element,
            cancelButton: cancelButtons[0].element,
            confirmButton: confirmButtons[0].element)
    }

    private func authorizationLeaseForUse(_ request: [String: Any])
        -> (AuthorizationLease?, [String: Any]?) {
        guard let leaseID = requestString(request, "leaseId") else {
            return (nil, refused(request, code: "invalid_request",
                message: "leaseId is required",
                route: "guest.user/macos.authorization"))
        }
        guard leaseID.hasPrefix(generation + ":auth:") else {
            return (nil, refused(request, code: "stale_reference",
                message: "Authorization lease belongs to another resident generation",
                route: "guest.user/macos.authorization", stale: true))
        }
        guard var lease = authorizationLeases[leaseID] else {
            return (nil, refused(request, code: "authorization_lease_missing",
                message: "Authorization lease is not present",
                route: "guest.user/macos.authorization"))
        }
        if lease.used {
            return (nil, refused(request, code: "authorization_lease_used",
                message: "Authorization lease has already been consumed",
                route: "guest.user/macos.authorization"))
        }
        if Date() >= lease.expiresAt {
            lease.used = true
            authorizationLeases[leaseID] = lease
            return (nil, refused(request, code: "authorization_lease_expired",
                message: "Authorization lease expired",
                route: "guest.user/macos.authorization"))
        }
        guard let sheet = try? authorizationSheet(
                expectedRequester: lease.requester),
              sheet.processID == lease.processID,
              sheet.windowID == lease.windowID else {
            lease.used = true
            authorizationLeases[leaseID] = lease
            return (nil, refused(request, code: "authorization_sheet_changed",
                message: "Authorization sheet no longer matches the lease",
                route: "guest.user/macos.authorization"))
        }
        return (lease, nil)
    }

    private func consumeAuthorizationLease(_ lease: AuthorizationLease) {
        var consumed = lease
        consumed.used = true
        authorizationLeases[lease.id] = consumed
    }

    private func physicalKey(for byte: UInt8) -> (CGKeyCode, CGEventFlags)? {
        let character = Character(UnicodeScalar(byte))
        let string = String(character)
        if byte >= 97 && byte <= 122, let code = keyCode(string) {
            return (code, [])
        }
        if byte >= 65 && byte <= 90,
           let code = keyCode(string.lowercased()) {
            return (code, .maskShift)
        }
        if byte >= 48 && byte <= 57, let code = keyCode(string) {
            return (code, [])
        }
        let punctuation: [UInt8: (String, Bool)] = [
            32: ("space", false), 45: ("-", false), 95: ("-", true),
            61: ("=", false), 43: ("=", true), 91: ("[", false),
            123: ("[", true), 93: ("]", false), 125: ("]", true),
            59: (";", false), 58: (";", true),
            39: ("'", false), 34: ("'", true), 44: (",", false),
            60: (",", true), 46: (".", false), 62: (".", true),
            47: ("/", false), 63: ("/", true), 92: ("\\", false),
            124: ("\\", true), 96: ("`", false), 126: ("`", true),
            33: ("1", true), 64: ("2", true), 35: ("3", true),
            36: ("4", true), 37: ("5", true), 94: ("6", true),
            38: ("7", true), 42: ("8", true), 40: ("9", true),
            41: ("0", true),
        ]
        guard let entry = punctuation[byte], let code = keyCode(entry.0) else {
            return nil
        }
        return (code, entry.1 ? .maskShift : [])
    }

    private func sendCredential(_ credential: Data) throws {
        for byte in credential {
            guard let (code, flags) = physicalKey(for: byte),
                  let down = CGEvent(keyboardEventSource: nil,
                                     virtualKey: code, keyDown: true),
                  let up = CGEvent(keyboardEventSource: nil,
                                   virtualKey: code, keyDown: false) else {
                throw MacUIError.usage(
                    "Credential contains a character unavailable to the input route")
            }
            down.flags = flags
            up.flags = flags
            down.post(tap: .cghidEventTap)
            up.post(tap: .cghidEventTap)
            usleep(18_000)
        }
    }

    func handleCredential(_ request: [String: Any], credential: Data)
        -> [String: Any] {
        let started = DispatchTime.now().uptimeNanoseconds
        var result: [String: Any]
        let (candidate, refusal) = authorizationLeaseForUse(request)
        if let refusal {
            result = refusal
        } else if let lease = candidate {
            consumeAuthorizationLease(lease)
            if credential.isEmpty || credential.count > 256 {
                result = refused(request, code: "credential_size_invalid",
                    message: "Credential must contain 1 through 256 bytes",
                    route: "guest.user/macos.authorization")
            } else if let sheet = try? authorizationSheet(
                        expectedRequester: lease.requester),
                      sheet.processID == lease.processID,
                      sheet.windowID == lease.windowID {
                let focused = AXUIElementSetAttributeValue(
                    sheet.secureField, kAXFocusedAttribute as CFString,
                    kCFBooleanTrue)
                if focused != .success {
                    result = refused(request, code: "secure_field_unavailable",
                        message: "Secure credential field could not be focused",
                        route: "guest.user/macos.authorization")
                } else {
                    do {
                        try sendKey("cmd-a")
                        try sendKey("delete")
                        try sendCredential(credential)
                        usleep(120_000)
                        let pressed = AXUIElementPerformAction(
                            sheet.confirmButton, kAXPressAction as CFString)
                        guard pressed == .success else {
                            throw MacUIError.action(
                                "Authorization confirmation was not delivered")
                        }
                        var dismissed = false
                        for _ in 0..<30 {
                            usleep(100_000)
                            if (try? authorizationSheet(
                                    expectedRequester: lease.requester)) == nil {
                                dismissed = true
                                break
                            }
                        }
                        result = base(request,
                            route: "guest.user/macos.authorization")
                        result["delivery"] = "confirmed"
                        result["effect"] = dismissed ? "confirmed" : "no_effect"
                        result["uncertainty"] = dismissed ? "none" :
                            "authorization_not_observed"
                        result["retrySafety"] = "observe_before_retry"
                        result["data"] = [
                            "contextId": lease.contextID,
                            "sheetDismissed": dismissed,
                            "attemptConsumed": true,
                        ]
                    } catch {
                        result = refused(request,
                            code: "credential_delivery_failed",
                            message: String(describing: error),
                            route: "guest.user/macos.authorization")
                    }
                }
            } else {
                result = refused(request, code: "authorization_sheet_changed",
                    message: "Authorization sheet no longer matches the lease",
                    route: "guest.user/macos.authorization")
            }
        } else {
            result = refused(request, code: "authorization_lease_missing",
                message: "Authorization lease is not present",
                route: "guest.user/macos.authorization")
        }
        result["elapsedMs"] = Int(
            (DispatchTime.now().uptimeNanoseconds - started) / 1_000_000)
        return result
    }

    func handle(_ request: [String: Any]) -> [String: Any] {
        let started = DispatchTime.now().uptimeNanoseconds
        let operation = requestString(request, "operation") ?? ""
        var result = refused(request, code: "internal_error",
                             message: "Operation did not produce a result")
        do {
            switch operation {
            case "capabilities":
                let cua = cuaPermissions()
                let defaultSemanticProvider = AXIsProcessTrusted() ? "macos.ax" :
                    (cua == nil ? "unavailable" : "cua")
                let defaultVisualProvider = CGPreflightScreenCaptureAccess() ?
                    "macos.quartz" : (cua == nil ? "unavailable" : "cua")
                result = base(request)
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["data"] = [
                    "providers": [
                        ["id": "macos-native", "state": AXIsProcessTrusted() ? "ready" : "degraded",
                         "routeClass": "guest.user", "placement": "target_resident",
                         "operations": ["applications", "windows", "snapshot", "action",
                                        "application.launch", "application.activate",
                                        "application.terminate", "input.key",
                                        "input.text", "input.click", "input.move",
                                        "input.drag", "input.scroll", "window.close",
                                        "capture", "authorization.begin",
                                        "authorization.cancel"]],
                        ["id": "cua", "state": cua == nil ? "unavailable" : "ready",
                         "routeClass": "guest.user", "placement": "target_resident",
                         "operations": ["applications", "windows", "snapshot", "action",
                                        "application.launch", "application.activate",
                                        "application.terminate", "input.key",
                                        "input.text", "input.click", "window.close",
                                        "capture"]],
                    ],
                    "routing": [
                        ["operations": ["snapshot", "action"],
                         "provider": defaultSemanticProvider],
                        ["operations": ["input.key", "input.click", "input.move",
                                         "input.drag", "input.scroll"],
                         "provider": AXIsProcessTrusted() ? "macos.coregraphics" :
                            (cua == nil ? "unavailable" : "cua")],
                        ["operations": ["input.text"],
                         "provider": cua == nil ? "macos.coregraphics" : "cua"],
                        ["operations": ["windows", "capture"],
                         "provider": defaultVisualProvider],
                        ["operations": ["applications", "application.launch",
                                         "application.activate", "application.terminate"],
                         "provider": AXIsProcessTrusted() ? "macos.workspace" :
                            (cua == nil ? "unavailable" : "cua")],
                        ["operations": ["window.close"],
                         "provider": defaultSemanticProvider],
                        ["operations": ["authorization.begin", "authorization.cancel"],
                         "provider": AXIsProcessTrusted() ? "macos.authorization" :
                            "unavailable"],
                    ],
                    "screenCaptureAuthorized": CGPreflightScreenCaptureAccess(),
                    "accessibilityAuthorized": AXIsProcessTrusted(),
                    "displays": activeDisplayJSON(),
                    "cuaPermissions": cua.map { $0 as Any } ?? NSNull(),
                ]
            case "status":
                let cua = cuaPermissions()
                let cuaAccessibility = cua?["accessibility"] as? Bool == true
                let cuaCapture = cua?["screen_recording"] as? Bool == true
                result = base(request)
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["data"] = [
                    "processId": ProcessInfo.processInfo.processIdentifier,
                    "user": NSUserName(),
                    "consoleUser": (SCDynamicStoreCopyConsoleUser(nil, nil, nil)
                        as String?).map { $0 as Any } ?? NSNull(),
                    "desktopState": "unlocked",
                    "semanticState": AXIsProcessTrusted() || cuaAccessibility ?
                        "ready" : "unavailable",
                    "nativeSemanticState": AXIsProcessTrusted() ? "ready" : "unavailable",
                    "captureState": CGPreflightScreenCaptureAccess() || cuaCapture ?
                        "ready" : "unavailable",
                    "nativeCaptureState": CGPreflightScreenCaptureAccess() ?
                        "ready" : "unavailable",
                    "cuaState": cua == nil ? "unavailable" : "ready",
                ]
            case "authorization.begin":
                guard let requester = requestString(request, "expectedRequester"),
                      let contextID = requestString(request, "contextId") else {
                    result = refused(request, code: "invalid_request",
                        message: "expectedRequester and contextId are required",
                        route: "guest.user/macos.authorization")
                    break
                }
                guard let sheet = try? authorizationSheet(
                        expectedRequester: requester) else {
                    result = refused(request,
                        code: "authorization_sheet_unavailable",
                        message: "No exact matching authorization sheet is present",
                        route: "guest.user/macos.authorization")
                    break
                }
                let timeout = max(250, min(
                    requestInt(request, "timeoutMs", default: 30_000), 30_000))
                let leaseID = generation + ":auth:" +
                    UUID().uuidString.lowercased()
                let now = Date()
                authorizationLeases[leaseID] = AuthorizationLease(
                    id: leaseID, contextID: contextID, requester: requester,
                    processID: sheet.processID, windowID: sheet.windowID,
                    createdAt: now,
                    expiresAt: now.addingTimeInterval(Double(timeout) / 1_000),
                    used: false)
                if authorizationLeases.count > 64 {
                    let removable = authorizationLeases.values
                        .filter { $0.used || $0.expiresAt <= now }
                        .sorted { $0.createdAt < $1.createdAt }
                    for lease in removable.prefix(
                            authorizationLeases.count - 64) {
                        authorizationLeases.removeValue(forKey: lease.id)
                    }
                }
                result = base(request,
                    route: "guest.user/macos.authorization")
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["data"] = [
                    "leaseId": leaseID,
                    "contextId": contextID,
                    "requester": requester,
                    "processId": sheet.processID,
                    "windowId": sheet.windowID,
                    "secureInput": true,
                    "expiresInMs": timeout,
                ]
            case "authorization.cancel":
                let (candidate, refusal) = authorizationLeaseForUse(request)
                if let refusal {
                    result = refusal
                    break
                }
                guard let lease = candidate,
                      let sheet = try? authorizationSheet(
                        expectedRequester: lease.requester),
                      sheet.processID == lease.processID,
                      sheet.windowID == lease.windowID else {
                    result = refused(request,
                        code: "authorization_sheet_changed",
                        message: "Authorization sheet no longer matches the lease",
                        route: "guest.user/macos.authorization")
                    break
                }
                consumeAuthorizationLease(lease)
                let delivery = AXUIElementPerformAction(
                    sheet.cancelButton, kAXPressAction as CFString)
                var dismissed = false
                if delivery == .success {
                    for _ in 0..<20 {
                        usleep(100_000)
                        if (try? authorizationSheet(
                                expectedRequester: lease.requester)) == nil {
                            dismissed = true
                            break
                        }
                    }
                }
                result = base(request,
                    route: "guest.user/macos.authorization")
                result["delivery"] = delivery == .success ? "confirmed" : "unknown"
                result["effect"] = dismissed ? "confirmed" : "unverifiable"
                result["uncertainty"] = dismissed ? "none" :
                    "sheet_dismissal_not_observed"
                result["retrySafety"] = "observe_before_retry"
                result["data"] = [
                    "contextId": lease.contextID,
                    "sheetDismissed": dismissed,
                    "attemptConsumed": true,
                ]
            case "applications":
                if useCua(request) {
                    let output = try cuaCall("list_apps", [:])
                    let apps = output["apps"] as? [[String: Any]] ?? []
                    result = projectCuaResult(request, providerOperation: "list_apps",
                                              providerResult: [
                                                "applications": apps.map(cuaApplicationJSON)
                                              ],
                                              route: "guest.user/macos.cua")
                    result["delivery"] = "not_applicable"
                    result["effect"] = "not_applicable"
                    break
                }
                result = base(request, route: "guest.user/macos.workspace")
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["data"] = ["applications": runningApplications().map(applicationJSON)]
            case "windows":
                if useCua(request) {
                    var output = try cuaCall("list_windows", [:])
                    if let target = requestString(request, "target") {
                        let (pid, _) = try cuaApplication(target)
                        let windows = output["windows"] as? [[String: Any]] ?? []
                        output["windows"] = windows.filter {
                            ($0["pid"] as? NSNumber)?.intValue == pid
                        }
                    }
                    let windows = output["windows"] as? [[String: Any]] ?? []
                    result = projectCuaResult(request, providerOperation: "list_windows",
                                              providerResult: [
                                                "windows": windows.map(cuaWindowJSON)
                                              ],
                                              route: "guest.user/macos.cua")
                    result["delivery"] = "not_applicable"
                    result["effect"] = "not_applicable"
                    result["coordinateSpace"] = "global_display_points_top_left"
                    break
                }
                let app = try requestString(request, "target").map(resolveApplication)
                result = base(request, route: "guest.user/macos.quartz")
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["coordinateSpace"] = "global_display_points_top_left"
                result["data"] = ["windows": windowList(ownerPID: app?.processIdentifier)]
            case "snapshot":
                if useCua(request) {
                    guard let target = requestString(request, "target") else {
                        result = refused(request, code: "invalid_request",
                                         message: "target is required for Cua snapshot")
                        break
                    }
                    let (pid, name) = try cuaApplication(target)
                    let window = try cuaWindow(pid: pid)
                    guard let windowID = (window["window_id"] as? NSNumber)?.intValue else {
                        throw MacUIError.element("Cua window has no native identifier")
                    }
                    var arguments: [String: Any] = [
                        "pid": pid, "window_id": windowID, "include_screenshot": false,
                        "max_depth": max(1, min(requestInt(request, "maxDepth", default: 12), 25)),
                        "max_elements": max(1, min(requestInt(request, "maxElements", default: 500), 2_000)),
                    ]
                    if let query = requestString(request, "query") { arguments["query"] = query }
                    var output = try cuaCall("get_window_state", arguments)
                    let snapshotID = output["snapshot_id"] as? String ?? "unknown"
                    let compact = requestString(request, "projection") == "compact"
                    var projected: [[String: Any]] = []
                    for element in output["elements"] as? [[String: Any]] ?? [] {
                        guard let token = element["element_token"] as? String else { continue }
                        let reference = "\(generation):cua:\(pid):\(windowID):\(token)"
                        cuaReferences[reference] = CuaReference(
                            pid: pid, windowID: windowID,
                            snapshotID: snapshotID, token: token)
                        projected.append(cuaElementJSON(
                            element, reference: reference, compact: compact))
                    }
                    let running = try? resolveApplication(target)
                    output = [
                        "application": running.map(applicationJSON) ??
                            ["processId": pid, "name": name],
                        "window": cuaWindowJSON(window),
                        "snapshotId": snapshotID,
                        "projection": compact ? "compact" : "full",
                        "elements": projected,
                        "truncated": output["truncated"] ?? false,
                    ]
                    result = projectCuaResult(request,
                        providerOperation: "get_window_state", providerResult: output,
                        route: "guest.user/macos.cua")
                    result["delivery"] = "not_applicable"
                    result["effect"] = "not_applicable"
                    result["fidelity"] = "semantic_native"
                    result["coordinateSpace"] = "window_points_top_left"
                    break
                }
                let (app, allRecords) = try applicationRecords(request)
                let records = recordsMatchingQuery(
                    allRecords, query: requestString(request, "query"))
                let remembered = remember(records)
                let compact = requestString(request, "projection") == "compact"
                result = base(request, route: "guest.user/macos.ax")
                result["delivery"] = "not_applicable"
                result["effect"] = "not_applicable"
                result["fidelity"] = "semantic_native"
                result["coordinateSpace"] = "global_display_points_top_left"
                result["data"] = [
                    "application": applicationJSON(app),
                    "snapshotId": remembered.0,
                    "projection": compact ? "compact" : "full",
                    "elements": compact ? remembered.2 : remembered.1,
                    "truncated": records.count >= min(requestInt(
                        request, "maxElements", default: 500), 2_000),
                ]
            case "action":
                if let reference = requestString(request, "reference"),
                   !reference.hasPrefix(generation + ":") {
                    result = refused(request, code: "stale_reference",
                                     message: "Reference belongs to another resident generation",
                                     stale: true)
                    break
                }
                if let reference = requestString(request, "reference"),
                   let cuaReference = cuaReferences[reference] {
                    let action = requestString(request, "action") ?? "press"
                    var arguments: [String: Any] = [
                        "pid": cuaReference.pid, "window_id": cuaReference.windowID,
                        "element_token": cuaReference.token,
                    ]
                    let tool: String
                    if action == "set_value" {
                        guard let text = requestString(request, "text") else {
                            result = refused(request, code: "invalid_request",
                                             message: "text is required for set_value")
                            break
                        }
                        arguments["value"] = text
                        tool = "set_value"
                    } else if action == "press" {
                        arguments["action"] = "press"
                        tool = "click"
                    } else {
                        result = refused(request, code: "unsupported_action",
                                         message: "Cua action supports press or set_value")
                        break
                    }
                    let output = try cuaCall(tool, arguments)
                    result = projectCuaResult(request, providerOperation: tool,
                                              providerResult: output,
                                              route: "guest.user/macos.cua")
                    break
                }
                if let reference = requestString(request, "reference"),
                   reference.contains(":cua:") {
                    result = refused(request, code: "stale_reference",
                                     message: "Cua reference is no longer present in this generation",
                                     route: "guest.user/macos.cua", stale: true)
                    break
                }
                guard AXIsProcessTrusted() else {
                    result = refused(request, code: "authorization_required",
                                     message: "Accessibility access is not granted",
                                     route: "guest.user/macos.ax")
                    break
                }
                guard let reference = requestString(request, "reference") else {
                    result = refused(request, code: "invalid_request",
                                     message: "reference is required",
                                     route: "guest.user/macos.ax")
                    break
                }
                guard reference.hasPrefix(generation + ":"),
                      let element = references[reference] else {
                    result = refused(request, code: "stale_reference",
                                     message: "Reference is not valid for this resident generation",
                                     route: "guest.user/macos.ax", stale: true)
                    break
                }
                let action = requestString(request, "action") ?? "press"
                let before = observationFingerprint()
                var delivery: AXError?
                switch action {
                case "press":
                    delivery = AXUIElementPerformAction(element, kAXPressAction as CFString)
                case "focus":
                    delivery = AXUIElementSetAttributeValue(
                        element, kAXFocusedAttribute as CFString, kCFBooleanTrue)
                case "set_value":
                    guard let value = requestString(request, "text") else {
                        result = refused(request, code: "invalid_request",
                                         message: "text is required for set_value",
                                         route: "guest.user/macos.ax")
                        break
                    }
                    delivery = AXUIElementSetAttributeValue(
                        element, kAXValueAttribute as CFString, value as CFString)
                default:
                    result = refused(request, code: "unsupported_action",
                                     message: "Unsupported AX action: \(action)",
                                     route: "guest.user/macos.ax")
                    break
                }
                guard let delivery else { break }
                guard delivery == .success else {
                    result = refused(request, code: "delivery_failed",
                                     message: "AX action failed with error \(delivery.rawValue)",
                                     route: "guest.user/macos.ax")
                    break
                }
                usleep(180_000)
                let after = observationFingerprint()
                result = base(request, route: "guest.user/macos.ax")
                result["delivery"] = "confirmed"
                result["effect"] = before == after ? "unverifiable" : "confirmed"
                result["uncertainty"] = before == after ? "no_independent_state_change" : "none"
                result["evidence"] = [["kind": "semantic_state",
                                       "summary": before == after ?
                                           "AX delivery acknowledged; no independent change observed" :
                                           "application/window state changed after AX delivery"]]
            case "application.launch":
                guard let query = requestString(request, "applicationId") ??
                        requestString(request, "target") else {
                    result = refused(request, code: "invalid_request",
                                     message: "applicationId or target is required")
                    break
                }
                if useCua(request) {
                    let key = query.contains(".") && !query.contains(" ") ?
                        "bundle_id" : "name"
                    var arguments: [String: Any] = [key: query]
                    if let url = requestString(request, "arguments") {
                        arguments["urls"] = [url]
                    }
                    let output = try cuaCall("launch_app", arguments)
                    result = projectCuaResult(request, providerOperation: "launch_app",
                                              providerResult: output,
                                              route: "guest.user/macos.cua")
                    if let app = try? resolveApplication(query) {
                        result["data"] = ["application": applicationJSON(app)]
                    }
                    break
                }
                let app = try launchApplication(
                    query, argument: requestString(request, "arguments"))
                result = base(request, route: "guest.user/macos.workspace")
                result["delivery"] = "confirmed"
                result["effect"] = "confirmed"
                result["data"] = ["application": applicationJSON(app)]
                result["evidence"] = [["kind": "process_state",
                                       "summary": "Application is running"]]
            case "application.terminate":
                guard let query = requestString(request, "target") else {
                    result = refused(request, code: "invalid_request",
                                     message: "target is required")
                    break
                }
                let app = try resolveApplication(query)
                let pid = app.processIdentifier
                let delivered = app.terminate()
                for _ in 0..<20 where !app.isTerminated { usleep(100_000) }
                result = base(request, route: "guest.user/macos.workspace")
                result["delivery"] = delivered ? "confirmed" : "unknown"
                result["effect"] = app.isTerminated ? "confirmed" : "unknown"
                result["uncertainty"] = app.isTerminated ? "none" : "termination_not_observed"
                result["data"] = ["processId": pid]
            case "application.activate":
                guard let query = requestString(request, "target") else {
                    result = refused(request, code: "invalid_request",
                                     message: "target is required")
                    break
                }
                if useCua(request) {
                    let (pid, _) = try cuaApplication(query)
                    var arguments: [String: Any] = ["pid": pid]
                    if let window = try? cuaWindow(pid: pid),
                       let windowID = (window["window_id"] as? NSNumber)?.intValue {
                        arguments["window_id"] = windowID
                    }
                    let output = try cuaCall("bring_to_front", arguments)
                    result = projectCuaResult(request,
                        providerOperation: "bring_to_front", providerResult: output,
                        route: "guest.user/macos.cua")
                    result["focusConsequence"] = "target_application_activated"
                    break
                }
                let app = try resolveApplication(query)
                let delivered = app.activate()
                usleep(150_000)
                result = base(request, route: "guest.user/macos.workspace")
                result["delivery"] = delivered ? "confirmed" : "unknown"
                result["effect"] = NSWorkspace.shared.frontmostApplication?
                    .processIdentifier == app.processIdentifier ? "confirmed" : "unknown"
                result["focusConsequence"] = "target_application_activated"
            case "window.close":
                guard let query = requestString(request, "target") else {
                    result = refused(request, code: "invalid_request",
                                     message: "target is required")
                    break
                }
                if useCua(request) {
                    let (pid, _) = try cuaApplication(query)
                    let window = try cuaWindow(pid: pid)
                    guard let windowID = (window["window_id"] as? NSNumber)?.intValue else {
                        throw MacUIError.element("Cua window has no native identifier")
                    }
                    let output = try cuaCall("invoke_menu", [
                        "pid": pid, "window_id": windowID,
                        "path": ["File", "Close Window"],
                    ])
                    result = projectCuaResult(request,
                        providerOperation: "invoke_menu", providerResult: output,
                        route: "guest.user/macos.cua")
                    var closed = false
                    for _ in 0..<20 {
                        usleep(100_000)
                        let remaining = try cuaCall("list_windows", [:])["windows"]
                            as? [[String: Any]] ?? []
                        closed = !remaining.contains {
                            ($0["window_id"] as? NSNumber)?.intValue == windowID &&
                            ($0["is_on_screen"] as? Bool) == true
                        }
                        if closed { break }
                    }
                    result["effect"] = closed ? "confirmed" : "unverifiable"
                    result["uncertainty"] = closed ? "none" : "window_still_observable"
                    result["evidence"] = [["kind": "window_state",
                                           "summary": closed ?
                                            "Exact window is no longer on screen" :
                                            "Exact window remains on screen"]]
                    break
                }
                try requireAccessibility()
                let app = try resolveApplication(query)
                let root = AXUIElementCreateApplication(app.processIdentifier)
                let windows = (attribute(root, kAXWindowsAttribute as CFString)
                               as? [AXUIElement]) ?? []
                guard let window = windows.first,
                      let closeButton = attribute(window,
                        kAXCloseButtonAttribute as CFString) else {
                    result = refused(request, code: "window_not_found",
                                     message: "No closeable native window was found",
                                     route: "guest.user/macos.ax")
                    break
                }
                let closeElement = unsafeBitCast(closeButton, to: AXUIElement.self)
                let delivery = AXUIElementPerformAction(
                    closeElement, kAXPressAction as CFString)
                result = base(request, route: "guest.user/macos.ax")
                result["delivery"] = delivery == .success ? "confirmed" : "unknown"
                usleep(180_000)
                let after = (attribute(root, kAXWindowsAttribute as CFString)
                             as? [AXUIElement]) ?? []
                result["effect"] = after.count < windows.count ? "confirmed" : "unknown"
            case "input.key", "input.text", "input.click", "input.move",
                 "input.drag", "input.scroll":
                let providerWasExplicit = requestString(request, "provider") != nil
                let preferCuaText = operation == "input.text" &&
                    !providerWasExplicit && cuaPermissions() != nil
                if preferCuaText || useCua(request) {
                    if !["input.key", "input.text", "input.click"].contains(operation) {
                        result = refused(request, code: "provider_unsupported",
                            message: "Cua does not implement \(operation)",
                            route: "guest.user/macos.cua")
                        break
                    }
                    var arguments: [String: Any] = [:]
                    if let target = requestString(request, "target") {
                        let (pid, _) = try cuaApplication(target)
                        arguments["pid"] = pid
                        if let window = try? cuaWindow(pid: pid),
                           let windowID = (window["window_id"] as? NSNumber)?.intValue {
                            arguments["window_id"] = windowID
                        }
                    } else {
                        arguments["scope"] = "desktop"
                    }
                    if let deliveryMode = requestString(request, "deliveryMode") ??
                            requestString(request, "state") {
                        arguments["delivery_mode"] = deliveryMode
                    }
                    let tool: String
                    if operation == "input.key" {
                        guard let key = requestString(request, "key") else {
                            result = refused(request, code: "invalid_request",
                                             message: "key is required"); break
                        }
                        let keys = key.split(separator: "-").map(String.init)
                        if keys.count == 1 {
                            arguments["key"] = keys[0]
                            tool = "press_key"
                        } else {
                            arguments["keys"] = keys
                            tool = "hotkey"
                        }
                    } else if operation == "input.text" {
                        guard let text = requestString(request, "text") else {
                            result = refused(request, code: "invalid_request",
                                             message: "text is required"); break
                        }
                        arguments["text"] = text
                        tool = "type_text"
                    } else {
                        let x = requestInt(request, "x", default: -1)
                        let y = requestInt(request, "y", default: -1)
                        guard x >= 0, y >= 0 else {
                            result = refused(request, code: "invalid_request",
                                             message: "non-negative x and y are required"); break
                        }
                        arguments["x"] = x; arguments["y"] = y
                        tool = "click"
                    }
                    let output = try cuaCall(tool, arguments)
                    result = projectCuaResult(request, providerOperation: tool,
                                              providerResult: output,
                                              route: "guest.user/macos.cua")
                    result["focusConsequence"] = "provider_reported"
                    result["cursorConsequence"] = "provider_reported"
                    break
                }
                guard AXIsProcessTrusted() else {
                    result = refused(request, code: "authorization_required",
                                     message: "Accessibility access is required for input",
                                     route: "guest.user/macos.coregraphics")
                    break
                }
                _ = try activateTarget(requestString(request, "target"))
                try validateCoordinateSpace(request)
                let before = observationFingerprint()
                var inputData: [String: Any] = [:]
                if operation == "input.key" {
                    guard let key = requestString(request, "key") else {
                        result = refused(request, code: "invalid_request",
                                         message: "key is required"); break
                    }
                    try sendKey(key)
                    inputData["key"] = key
                } else if operation == "input.text" {
                    guard let text = requestString(request, "text") else {
                        result = refused(request, code: "invalid_request",
                                         message: "text is required"); break
                    }
                    try sendText(text)
                    inputData["characters"] = text.count
                } else if operation == "input.scroll" {
                    let deltaX = requestInt(request, "deltaX", default: 0)
                    let deltaY = requestInt(request, "deltaY", default: 0)
                    guard deltaX != 0 || deltaY != 0 else {
                        result = refused(request, code: "invalid_request",
                            message: "non-zero deltaX or deltaY is required")
                        break
                    }
                    guard let event = CGEvent(scrollWheelEvent2Source: nil,
                        units: .pixel, wheelCount: 2,
                        wheel1: Int32(deltaY), wheel2: Int32(deltaX), wheel3: 0) else {
                        throw MacUIError.action("Unable to create scroll event")
                    }
                    event.post(tap: .cghidEventTap)
                    inputData["deltaX"] = deltaX
                    inputData["deltaY"] = deltaY
                } else {
                    let x = requestInt(request, "x", default: -1)
                    let y = requestInt(request, "y", default: -1)
                    let point = CGPoint(x: x, y: y)
                    guard pointIsOnActiveDisplay(point) else {
                        result = refused(request, code: "invalid_request",
                            message: "x and y must identify an active display point")
                        break
                    }
                    inputData["x"] = x
                    inputData["y"] = y
                    if operation == "input.move" {
                        guard let move = CGEvent(mouseEventSource: nil,
                            mouseType: .mouseMoved, mouseCursorPosition: point,
                            mouseButton: .left) else {
                            throw MacUIError.action("Unable to create pointer event")
                        }
                        move.post(tap: .cghidEventTap)
                    } else {
                        let (button, downType, upType) = try pointerButton(
                            requestString(request, "button"))
                        var dragEnd: CGPoint?
                        if operation == "input.drag" {
                            let x2 = requestInt(request, "x2", default: -1)
                            let y2 = requestInt(request, "y2", default: -1)
                            let end = CGPoint(x: x2, y: y2)
                            guard pointIsOnActiveDisplay(end) else {
                                result = refused(request, code: "invalid_request",
                                    message: "x2 and y2 must identify an active display point")
                                break
                            }
                            dragEnd = end
                            inputData["x2"] = x2
                            inputData["y2"] = y2
                        }
                        guard let down = CGEvent(mouseEventSource: nil,
                            mouseType: downType, mouseCursorPosition: point,
                            mouseButton: button) else {
                            throw MacUIError.action("Unable to create pointer event")
                        }
                        down.post(tap: .cghidEventTap)
                        if let end = dragEnd {
                            let dragType: CGEventType = button == .left ?
                                .leftMouseDragged : (button == .right ?
                                    .rightMouseDragged : .otherMouseDragged)
                            guard let drag = CGEvent(mouseEventSource: nil,
                                mouseType: dragType, mouseCursorPosition: end,
                                mouseButton: button),
                                  let up = CGEvent(mouseEventSource: nil,
                                mouseType: upType, mouseCursorPosition: end,
                                mouseButton: button) else {
                                throw MacUIError.action("Unable to create drag event")
                            }
                            usleep(80_000)
                            drag.post(tap: .cghidEventTap)
                            usleep(80_000)
                            up.post(tap: .cghidEventTap)
                        } else {
                            guard let up = CGEvent(mouseEventSource: nil,
                                mouseType: upType, mouseCursorPosition: point,
                                mouseButton: button) else {
                                throw MacUIError.action("Unable to create pointer event")
                            }
                            up.post(tap: .cghidEventTap)
                        }
                        inputData["button"] = requestString(request, "button") ?? "left"
                    }
                }
                usleep(180_000)
                let changed = before != observationFingerprint()
                result = base(request, route: "guest.user/macos.coregraphics")
                result["delivery"] = "confirmed"
                result["effect"] = changed ? "confirmed" : "unverifiable"
                result["uncertainty"] = changed ? "none" : "no_independent_state_change"
                result["focusConsequence"] = requestString(request, "target") == nil ?
                    "current_guest_focus" : "target_application_activated"
                result["cursorConsequence"] = ["input.click", "input.move",
                    "input.drag"].contains(operation) ? "guest_cursor_moved" : "none"
                result["coordinateSpace"] = ["input.click", "input.move",
                    "input.drag"].contains(operation) ?
                    "global_display_points" : "not_applicable"
                result["data"] = inputData
            case "capture":
                let captureScope = requestString(request, "scope") ??
                    (requestString(request, "target") == nil ? "display" : "window")
                guard ["display", "window"].contains(captureScope) else {
                    result = refused(request, code: "invalid_request",
                        message: "capture scope must be display or window")
                    break
                }
                if captureScope == "display" {
                    if requestString(request, "provider") == "cua" {
                        result = refused(request, code: "provider_unsupported",
                            message: "Cua does not implement full-display capture",
                            route: "guest.user/macos.cua")
                        break
                    }
                    guard CGPreflightScreenCaptureAccess() else {
                        _ = CGRequestScreenCaptureAccess()
                        result = refused(request, code: "authorization_required",
                            message: "Screen Recording access is not granted",
                            route: "guest.user/macos.quartz")
                        break
                    }
                    let displays = activeDisplayJSON()
                    guard let main = displays.first(where: {
                        $0["main"] as? Bool == true
                    }) else {
                        result = refused(request, code: "display_not_found",
                            message: "No active main display is available",
                            route: "guest.user/macos.quartz")
                        break
                    }
                    let url = try artifactURL()
                    let process = Process()
                    process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
                    process.arguments = ["-x", "-D", "1", url.path]
                    try process.run(); process.waitUntilExit()
                    guard process.terminationStatus == 0,
                          FileManager.default.fileExists(atPath: url.path) else {
                        result = refused(request, code: "capture_failed",
                            message: "Full-display capture failed",
                            route: "guest.user/macos.quartz")
                        break
                    }
                    let attributes = try FileManager.default.attributesOfItem(
                        atPath: url.path)
                    result = base(request, route: "guest.user/macos.quartz")
                    result["delivery"] = "confirmed"
                    result["effect"] = "confirmed"
                    result["fidelity"] = "full_display"
                    result["coordinateSpace"] = "display_pixels"
                    result["data"] = [
                        "artifactPath": url.path,
                        "bytes": attributes[.size] ?? 0,
                        "display": main,
                        "inputCoordinateSpace": "global_display_points",
                    ]
                    break
                }
                if useCua(request) {
                    guard let target = requestString(request, "target") else {
                        result = refused(request, code: "invalid_request",
                                         message: "target is required for exact-window capture")
                        break
                    }
                    let (pid, _) = try cuaApplication(target)
                    let window = try cuaWindow(pid: pid)
                    guard let windowID = (window["window_id"] as? NSNumber)?.intValue else {
                        throw MacUIError.element("Cua window has no native identifier")
                    }
                    let url = try artifactURL()
                    let output = try cuaCall("get_window_state", [
                        "pid": pid, "window_id": windowID,
                        "include_screenshot": true,
                        "max_depth": 1, "max_elements": 1,
                        "screenshot_out_file": url.path,
                    ])
                    result = projectCuaResult(request,
                        providerOperation: "get_window_state", providerResult: output,
                        route: "guest.user/macos.cua")
                    let attributes = try FileManager.default.attributesOfItem(
                        atPath: url.path)
                    result["data"] = [
                        "artifactPath": url.path,
                        "bytes": attributes[.size] ?? 0,
                        "window": cuaWindowJSON(window),
                    ]
                    result["fidelity"] = "exact_window"
                    result["coordinateSpace"] = "window_pixels"
                    break
                }
                guard CGPreflightScreenCaptureAccess() else {
                    _ = CGRequestScreenCaptureAccess()
                    result = refused(request, code: "authorization_required",
                                     message: "Screen Recording access is not granted",
                                     route: "guest.user/macos.quartz")
                    break
                }
                let app = try requestString(request, "target").map(resolveApplication)
                let windows = windowList(ownerPID: app?.processIdentifier)
                let requestedWindow = requestInt(request, "windowId", default: 0)
                let chosen = requestedWindow == 0 ? windows.first : windows.first {
                    ($0["windowId"] as? NSNumber)?.intValue == requestedWindow
                }
                guard let chosen,
                      let windowId = (chosen["windowId"] as? NSNumber)?.intValue else {
                    result = refused(request, code: "window_not_found",
                                     message: "No capturable window matched",
                                     route: "guest.user/macos.quartz")
                    break
                }
                let url = try artifactURL()
                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
                process.arguments = ["-x", "-o", "-l", String(windowId), url.path]
                try process.run(); process.waitUntilExit()
                guard process.terminationStatus == 0,
                      FileManager.default.fileExists(atPath: url.path) else {
                    result = refused(request, code: "capture_failed",
                                     message: "Exact-window capture failed",
                                     route: "guest.user/macos.quartz")
                    break
                }
                let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
                result = base(request, route: "guest.user/macos.quartz")
                result["delivery"] = "confirmed"
                result["effect"] = "confirmed"
                result["fidelity"] = "exact_window"
                result["coordinateSpace"] = "window_pixels"
                result["data"] = ["artifactPath": url.path,
                                  "bytes": attributes[.size] ?? 0,
                                  "window": chosen]
            case "server.stop":
                result = base(request)
                result["delivery"] = "confirmed"
                result["effect"] = "confirmed"
            default:
                result = refused(request, code: "unsupported_operation",
                                 message: "Unsupported operation: \(operation)")
            }
        } catch let error as MacUIError {
            result = refused(request, code: "operation_failed", message: error.description)
        } catch {
            result = refused(request, code: "operation_failed", message: String(describing: error))
        }
        result["elapsedMs"] = Int((DispatchTime.now().uptimeNanoseconds - started) / 1_000_000)
        return result
    }
}

func encodeJSONLine(_ object: [String: Any]) throws -> Data {
    var data = try JSONSerialization.data(withJSONObject: object,
                                           options: [.sortedKeys])
    data.append(0x0a)
    return data
}

func unixAddress(_ path: String) throws -> (sockaddr_un, socklen_t) {
    let bytes = Array(path.utf8CString)
    var address = sockaddr_un()
    guard bytes.count <= MemoryLayout.size(ofValue: address.sun_path) else {
        throw MacUIError.usage("Unix socket path is too long")
    }
    address.sun_family = sa_family_t(AF_UNIX)
    withUnsafeMutableBytes(of: &address.sun_path) { destination in
        bytes.withUnsafeBytes { source in
            destination.copyBytes(from: source)
        }
    }
    let length = socklen_t(MemoryLayout<sa_family_t>.size + bytes.count)
    return (address, length)
}

func withSockAddr<T>(_ address: inout sockaddr_un, length: socklen_t,
                     _ body: (UnsafePointer<sockaddr>, socklen_t) throws -> T) rethrows -> T {
    try withUnsafePointer(to: &address) {
        try $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            try body($0, length)
        }
    }
}

func readSocket(_ descriptor: Int32, limit: Int = 1_048_576) throws -> Data {
    var result = Data()
    var buffer = [UInt8](repeating: 0, count: 16_384)
    while result.count < limit {
        let count = Darwin.read(descriptor, &buffer, buffer.count)
        if count == 0 { break }
        if count < 0 {
            if errno == EINTR { continue }
            throw MacUIError.action("Socket read failed: \(String(cString: strerror(errno)))")
        }
        result.append(buffer, count: count)
        if result.last == 0x0a { break }
    }
    guard result.count < limit else {
        throw MacUIError.usage("Request exceeded \(limit) bytes")
    }
    return result
}

func writeSocket(_ descriptor: Int32, data: Data) throws {
    try data.withUnsafeBytes { rawBuffer in
        guard var pointer = rawBuffer.baseAddress else { return }
        var remaining = rawBuffer.count
        while remaining > 0 {
            let count = Darwin.write(descriptor, pointer, remaining)
            if count < 0 {
                if errno == EINTR { continue }
                throw MacUIError.action("Socket write failed: \(String(cString: strerror(errno)))")
            }
            remaining -= count
            pointer = pointer.advanced(by: count)
        }
    }
}

func runResidentServer(socketPath: String) throws -> Never {
    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else { throw MacUIError.action("Unable to create Unix socket") }
    unlink(socketPath)
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.bind(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Unable to bind Unix socket: \(String(cString: strerror(errno)))")
    }
    guard chmod(socketPath, S_IRUSR | S_IWUSR) == 0,
          listen(descriptor, 8) == 0 else {
        throw MacUIError.action("Unable to listen on Unix socket")
    }
    let service = ResidentService()
    while true {
        let client = accept(descriptor, nil, nil)
        if client < 0 {
            if errno == EINTR { continue }
            throw MacUIError.action("Socket accept failed: \(String(cString: strerror(errno)))")
        }
        autoreleasepool {
            defer { Darwin.close(client) }
            do {
                let data = try readSocket(client)
                let object = try JSONSerialization.jsonObject(with: data)
                guard let request = object as? [String: Any] else {
                    throw MacUIError.usage("Request must be a JSON object")
                }
                let response: [String: Any]
                if request["operation"] as? String == "authorization.submit" {
                    try writeSocket(client, data: Data([0x06]))
                    var credential = try readSocket(client, limit: 257)
                    defer {
                        credential.resetBytes(in: 0..<credential.count)
                        credential.removeAll(keepingCapacity: false)
                    }
                    response = service.handleCredential(
                        request, credential: credential)
                } else {
                    response = service.handle(request)
                }
                try writeSocket(client, data: encodeJSONLine(response))
                if request["operation"] as? String == "server.stop" {
                    Darwin.close(descriptor)
                    unlink(socketPath)
                    exit(0)
                }
            } catch {
                let response: [String: Any] = [
                    "schema": "machine-control/v0", "operation": "unknown",
                    "requestId": UUID().uuidString.lowercased(), "accepted": false,
                    "actualRoute": "guest.user/macos.resident",
                    "delivery": "refused", "effect": "refused",
                    "uncertainty": "none", "errorCode": "invalid_request",
                    "message": String(describing: error), "elapsedMs": 0,
                ]
                try? writeSocket(client, data: encodeJSONLine(response))
            }
        }
    }
}

func runResidentClient(socketPath: String, requestData: Data) throws {
    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else { throw MacUIError.action("Unable to create Unix socket") }
    defer { Darwin.close(descriptor) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.connect(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Resident service is unavailable")
    }
    var line = requestData
    if line.last != 0x0a { line.append(0x0a) }
    try writeSocket(descriptor, data: line)
    _ = Darwin.shutdown(descriptor, SHUT_WR)
    let response = try readSocket(descriptor)
    FileHandle.standardOutput.write(response)
}

func runCredentialClient(socketPath: String, leaseID: String) throws {
    var credential = FileHandle.standardInput.readDataToEndOfFile()
    defer {
        credential.resetBytes(in: 0..<credential.count)
        credential.removeAll(keepingCapacity: false)
    }
    while credential.last == 0x0a || credential.last == 0x0d {
        credential.removeLast()
    }
    guard !credential.isEmpty, credential.count <= 256 else {
        throw MacUIError.usage("Credential must contain 1 through 256 bytes")
    }

    let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
    guard descriptor >= 0 else {
        throw MacUIError.action("Unable to create Unix socket")
    }
    defer { Darwin.close(descriptor) }
    var (address, length) = try unixAddress(socketPath)
    guard withSockAddr(&address, length: length, {
        Darwin.connect(descriptor, $0, $1)
    }) == 0 else {
        throw MacUIError.action("Resident service is unavailable")
    }
    let request: [String: Any] = [
        "schema": "machine-control/v0",
        "requestId": UUID().uuidString.lowercased(),
        "operation": "authorization.submit",
        "leaseId": leaseID,
    ]
    try writeSocket(descriptor, data: encodeJSONLine(request))
    var acknowledgment: UInt8 = 0
    var count: Int
    repeat {
        count = Darwin.read(descriptor, &acknowledgment, 1)
    } while count < 0 && errno == EINTR
    guard count == 1, acknowledgment == 0x06 else {
        throw MacUIError.action(
            "Resident did not accept the credential channel handshake")
    }
    try writeSocket(descriptor, data: credential)
    _ = Darwin.shutdown(descriptor, SHUT_WR)
    let response = try readSocket(descriptor)
    FileHandle.standardOutput.write(response)
}

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
            try runResidentServer(socketPath: socketPath)
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
