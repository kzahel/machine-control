import AppKit
import ApplicationServices
import Foundation

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
