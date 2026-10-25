import AppKit
import ApplicationServices
import Foundation

/// A typed choice of a location in an AppKit Open or Save panel.
///
/// The panel's own Go-to sheet does the navigation. Nothing is confirmed
/// until the panel shows the requested folder, and a follow-up prompt such
/// as Replace is reported rather than answered.
struct PanelChoiceRefusal: Error {
    let code: String
    let message: String
    var data: [String: Any] = [:]
}

struct PanelChooser {
    /// Sends one key chord, such as "cmd-shift-g", to the panel's application.
    var sendKey: (String) throws -> Void
    /// Types literal text into the focused field.
    var typeText: (String) throws -> Void
    var timeout: TimeInterval = 3
    var fileManager = FileManager.default

    static let panelKinds = ["open-panel": "open", "save-panel": "save"]

    func choose(application: AXUIElement, path: String, confirm: Bool) throws -> [String: Any] {
        let (panel, kind) = try findPanel(application)
        let target = try resolve(path, kind: kind)
        var data: [String: Any] = ["panel": kind, "folder": target.folder.path, "confirmed": false]
        if let name = target.name { data["name"] = name }

        data["pathEntry"] = try navigate(panel, to: target.destination)
        let expected = fileManager.displayName(atPath: target.folder.path)
        guard let location = descendant(of: panel, identifier: "where popup", depth: 3),
              waitUntil({ stringAttribute(location, kAXValueAttribute as CFString) == expected }) else {
            throw PanelChoiceRefusal(code: "dialog_location_unverified",
                message: "The panel did not show the requested folder; nothing was confirmed",
                data: data)
        }
        data["locationVerified"] = "folder_name"

        if kind == "save", let name = target.name {
            guard let field = descendant(of: panel, identifier: "saveAsNameTextField", depth: 3),
                  AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString,
                                               name as CFString) == .success,
                  waitUntil({ stringAttribute(field, kAXValueAttribute as CFString) == name }) else {
                throw PanelChoiceRefusal(code: "dialog_name_entry_failed",
                    message: "The panel's file name did not take the requested value", data: data)
            }
        }
        guard confirm else { return data }

        let confirmationStarted = ProcessInfo.processInfo.systemUptime
        var confirmButton: AXUIElement?
        guard waitUntil({
            guard let candidate = descendant(of: panel, identifier: "OKButton", depth: 3),
                  boolAttribute(candidate, kAXEnabledAttribute as CFString) == true else { return false }
            confirmButton = candidate; return true
        }), let button = confirmButton else {
            data["confirmWaitMs"] = Int((ProcessInfo.processInfo.systemUptime - confirmationStarted) * 1000)
            throw PanelChoiceRefusal(code: "dialog_confirm_unavailable",
                message: "The panel's confirm button is disabled for this location; it was left open",
                data: data)
        }
        data["confirmWaitMs"] = Int((ProcessInfo.processInfo.systemUptime - confirmationStarted) * 1000)
        guard stringAttribute(location, kAXValueAttribute as CFString) == expected else {
            throw PanelChoiceRefusal(code:"dialog_location_unverified",
                message:"The panel's folder changed while confirmation became ready; nothing was confirmed", data:data)
        }
        if kind == "save", let name = target.name {
            guard let field = descendant(of:panel, identifier:"saveAsNameTextField", depth:3),
                  stringAttribute(field, kAXValueAttribute as CFString) == name else {
                throw PanelChoiceRefusal(code:"dialog_name_entry_failed",
                    message:"The panel's file name changed while confirmation became ready; nothing was confirmed", data:data)
            }
        }
        // A press that opens a modal follow-up can report an error even
        // though it was delivered; judge by what the panel does next.
        let pressed = AXUIElementPerformAction(button, kAXPressAction as CFString) == .success
        var prompts: [AXUIElement] = []
        let settled = waitUntil({
            if !isPresent(panel) { return true }
            prompts = followUpSheets(panel)
            return !prompts.isEmpty
        })
        guard settled || pressed else {
            throw PanelChoiceRefusal(code: "delivery_failed",
                message: "The panel's confirm button did not accept the press", data: data)
        }
        data["confirmed"] = true
        data["panelClosed"] = !isPresent(panel)
        if !prompts.isEmpty {
            // A follow-up prompt such as Replace stays for the caller to decide.
            data["followUp"] = prompts.map { texts(in: $0).joined(separator: " ") }
        }
        return data
    }

    // MARK: - Steps

    struct Target {
        let destination: String
        let folder: URL
        let name: String?
    }

    func resolve(_ path: String, kind: String) throws -> Target {
        let expanded = (path as NSString).expandingTildeInPath
        guard expanded.hasPrefix("/") else {
            throw PanelChoiceRefusal(code: "invalid_request", message: "path must be absolute")
        }
        let url = URL(fileURLWithPath: expanded).standardizedFileURL
        var isDirectory: ObjCBool = false
        let exists = fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory)
        if kind == "open" {
            guard exists else {
                throw PanelChoiceRefusal(code: "path_not_found", message: "No item exists at path")
            }
            // Panels select packages such as .app bundles like files.
            let folderLike = isDirectory.boolValue && !NSWorkspace.shared.isFilePackage(atPath: url.path)
            return Target(destination: url.path,
                          folder: folderLike ? url : url.deletingLastPathComponent(),
                          name: nil)
        }
        let folder = url.deletingLastPathComponent()
        var folderIsDirectory: ObjCBool = false
        guard !(exists && isDirectory.boolValue), !url.lastPathComponent.isEmpty else {
            throw PanelChoiceRefusal(code: "invalid_request",
                message: "A save path names a file, not an existing folder")
        }
        guard fileManager.fileExists(atPath: folder.path, isDirectory: &folderIsDirectory),
              folderIsDirectory.boolValue else {
            throw PanelChoiceRefusal(code: "path_not_found", message: "The save folder does not exist")
        }
        return Target(destination: folder.path, folder: folder, name: url.lastPathComponent)
    }

    /// Opens Go-to, enters the path and returns how it was entered.
    private func navigate(_ panel: AXUIElement, to destination: String) throws -> String {
        try sendKey("cmd-shift-g")
        var sheet: AXUIElement?
        guard waitUntil({
            sheet = descendant(of: panel, identifier: "GoToWindow", depth: 2)
            return sheet != nil
        }), let sheet, let field = descendant(of: sheet, identifier: "PathTextField", depth: 3) else {
            throw PanelChoiceRefusal(code: "dialog_goto_unavailable",
                message: "The panel did not open its Go to Folder sheet")
        }
        var entry = "accessibility_value"
        _ = AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString,
                                         destination as CFString)
        if !waitUntil({ stringAttribute(field, kAXValueAttribute as CFString) == destination },
                      within: 0.5) {
            // Some hosts ignore an accessibility value; type it instead.
            entry = "typed_text"
            _ = AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue)
            try sendKey("cmd-a")
            try typeText(destination)
        }
        guard waitUntil({ stringAttribute(field, kAXValueAttribute as CFString) == destination }) else {
            try? sendKey("escape")
            throw PanelChoiceRefusal(code: "dialog_path_entry_failed",
                message: "The Go to Folder field did not take the requested path")
        }
        try sendKey("return")
        guard waitUntil({ descendant(of: panel, identifier: "GoToWindow", depth: 2) == nil }) else {
            try? sendKey("escape")
            throw PanelChoiceRefusal(code: "dialog_navigation_failed",
                message: "The Go to Folder sheet did not accept the path")
        }
        return entry
    }

    // MARK: - Accessibility

    private func findPanel(_ application: AXUIElement) throws -> (AXUIElement, String) {
        let windows = attribute(application, kAXWindowsAttribute as CFString) as? [AXUIElement] ?? []
        let panels = windows.flatMap { window in
            ([window] + descendants(of: window, depth: 2)).compactMap { element -> (AXUIElement, String)? in
                Self.panelKinds[stringAttribute(element, "AXIdentifier" as CFString)].map { (element, $0) }
            }
        }
        guard let panel = panels.first else {
            throw PanelChoiceRefusal(code: "dialog_not_found",
                message: "The application shows no Open or Save panel")
        }
        guard panels.count == 1 else {
            throw PanelChoiceRefusal(code: "dialog_ambiguous",
                message: "The application shows more than one Open or Save panel")
        }
        return panel
    }

    private func descendants(of element: AXUIElement, depth: Int) -> [AXUIElement] {
        guard depth > 0 else { return [] }
        return childElements(element).flatMap { [$0] + descendants(of: $0, depth: depth - 1) }
    }

    private func descendant(of element: AXUIElement, identifier: String, depth: Int) -> AXUIElement? {
        descendants(of: element, depth: depth).first {
            stringAttribute($0, "AXIdentifier" as CFString) == identifier
        }
    }

    private func texts(in element: AXUIElement) -> [String] {
        descendants(of: element, depth: 4).compactMap {
            stringAttribute($0, kAXRoleAttribute as CFString) == "AXStaticText" ?
                stringAttribute($0, kAXValueAttribute as CFString) : nil
        }.filter { !$0.isEmpty }
    }

    private func followUpSheets(_ panel: AXUIElement) -> [AXUIElement] {
        descendants(of: panel, depth: 2).filter {
            stringAttribute($0, kAXRoleAttribute as CFString) == "AXSheet" &&
                stringAttribute($0, "AXIdentifier" as CFString) != "GoToWindow"
        }
    }

    private func isPresent(_ element: AXUIElement) -> Bool {
        var value: CFTypeRef?
        return AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &value) == .success
    }

    private func waitUntil(_ condition: () -> Bool, within: TimeInterval? = nil) -> Bool {
        let deadline = Date().addingTimeInterval(within ?? timeout)
        repeat {
            if condition() { return true }
            usleep(50_000)
        } while Date() < deadline
        return condition()
    }
}
