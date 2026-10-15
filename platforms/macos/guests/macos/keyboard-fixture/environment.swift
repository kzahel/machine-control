// Guest-only configuration helper. Never run layout/remapping experiments on
// a workstation. Its mutation guard requires Apple's virtual Mac model.
import AppKit
import Carbon
import CoreGraphics
import Darwin

func sourceID(_ source: TISInputSource) -> String {
    guard let p = TISGetInputSourceProperty(source, kTISPropertyInputSourceID) else { return "unknown" }
    return Unmanaged<CFString>.fromOpaque(p).takeUnretainedValue() as String
}
func sources() -> [TISInputSource] { TISCreateInputSourceList(nil, true).takeRetainedValue() as! [TISInputSource] }
func select(_ id: String) throws {
    guard let source = sources().first(where: { sourceID($0) == id }),
          TISEnableInputSource(source) == noErr, TISSelectInputSource(source) == noErr else {
        throw NSError(domain: "keyboard_source_unavailable", code: 1)
    }
    usleep(250_000)
    guard sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue()) == id else {
        throw NSError(domain: "keyboard_source_not_selected", code: 1)
    }
}
func run(_ path: String, _ args: [String]) throws -> Data {
    let p = Process(), pipe = Pipe(); p.executableURL = URL(fileURLWithPath: path)
    p.arguments = args; p.standardOutput = pipe; try p.run()
    let data = pipe.fileHandleForReading.readDataToEndOfFile(); p.waitUntilExit()
    guard p.terminationStatus == 0 else { throw NSError(domain: "keyboard_environment_command_failed", code: Int(p.terminationStatus)) }
    return data
}
func requireGuest() throws {
    let model = String(decoding: try run("/usr/sbin/sysctl", ["-n", "hw.model"]), as: UTF8.self)
    guard model.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix("VirtualMac") else {
        throw NSError(domain: "keyboard_configuration_requires_virtual_mac", code: 1)
    }
}
let mappings: [[String: UInt64]] = [(0xe2,0xe3),(0xe3,0xe2),(0xe6,0xe7),(0xe7,0xe6),(0x39,0xe0)].map {
    ["HIDKeyboardModifierMappingSrc": 0x700000000 | UInt64($0.0), "HIDKeyboardModifierMappingDst": 0x700000000 | UInt64($0.1)]
}
func remap(_ value: Bool) throws {
    let data = try JSONSerialization.data(withJSONObject: ["UserKeyMapping": value ? mappings : []])
    _ = try run("/usr/bin/hidutil", ["property", "--set", String(decoding: data, as: UTF8.self)])
}
func profile() throws {
    for id in ["com.apple.keylayout.US", "com.apple.keylayout.Dvorak", "com.apple.keylayout.DVORAK-QWERTYCMD"] {
        guard let source = sources().first(where: { sourceID($0) == id }), TISEnableInputSource(source) == noErr else {
            throw NSError(domain: "keyboard_profile_layout_missing", code: 1)
        }
    }
    try select("com.apple.keylayout.Dvorak"); try remap(true)
}
func installProfile() throws {
    let root = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/machine-control-keyboard")
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    let binary = root.appendingPathComponent("environment")
    let executable = URL(fileURLWithPath: CommandLine.arguments[0]).standardizedFileURL
    if executable != binary {
        if FileManager.default.fileExists(atPath: binary.path) { try FileManager.default.removeItem(at: binary) }
        try FileManager.default.copyItem(at: executable, to: binary)
    }
    let agents = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/LaunchAgents")
    try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
    let plist: [String: Any] = ["Label": "org.machine-control.keyboard-profile", "RunAtLoad": true,
        "ProgramArguments": [binary.path, "profile"], "LimitLoadToSessionType": "Aqua"]
    try PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0)
        .write(to: agents.appendingPathComponent("org.machine-control.keyboard-profile.plist"), options: .atomic)
    try profile()
}
func status() throws {
    let active = sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue())
    let layout = sourceID(TISCopyCurrentKeyboardLayoutInputSource().takeRetainedValue())
    let raw = try run("/usr/bin/hidutil", ["property", "--get", "UserKeyMapping"])
    var entries: [[String: UInt64]] = []
    if String(decoding: raw, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines) != "(null)" {
        guard let values = try PropertyListSerialization.propertyList(from: raw, format: nil) as? [[String: Any]] else {
            throw NSError(domain: "keyboard_mapping_unreadable", code: 1)
        }
        for value in values {
            var entry: [String: UInt64] = [:]
            for key in ["HIDKeyboardModifierMappingSrc", "HIDKeyboardModifierMappingDst"] {
                guard let raw = value[key], let number = UInt64(String(describing: raw)) else {
                    throw NSError(domain: "keyboard_mapping_usage_invalid", code: 1)
                }
                entry[key] = number
            }
            entries.append(entry)
        }
    }
    let available = sources()
    let enabled = available.filter { source in
        guard let value = TISGetInputSourceProperty(source, kTISPropertyInputSourceIsEnabled) else { return false }
        return CFBooleanGetValue(Unmanaged<CFBoolean>.fromOpaque(value).takeUnretainedValue())
    }.map(sourceID)
    let result: [String: Any] = ["inputSourceId": active, "layoutId": layout,
        "enabledLayouts": enabled,
        "hidFlags": CGEventSource.flagsState(.hidSystemState).rawValue,
        "sessionFlags": CGEventSource.flagsState(.combinedSessionState).rawValue,
        "modifierProfile": entries.isEmpty ? "standard" : (entries == mappings ? "alternate" : "custom"),
        "modifierMapping": entries]
    print(String(decoding: try JSONSerialization.data(withJSONObject: result, options: .sortedKeys), as: UTF8.self))
}
do {
    let args = CommandLine.arguments
    let command = args.count > 1 ? args[1] : "status"
    if command != "status" { try requireGuest() }
    switch command {
    case "status": break
    case "select": guard args.count == 3 else { throw NSError(domain: "layout_id_required", code: 1) }; try select(args[2])
    case "remap": guard args.count == 3, ["default", "swapped"].contains(args[2]) else { throw NSError(domain: "mapping_required", code: 1) }; try remap(args[2] == "swapped")
    case "profile": try profile()
    case "install-profile": try installProfile()
    default: throw NSError(domain: "unknown_keyboard_environment_command", code: 1)
    }
    try status()
} catch { fputs("\(error)\n", stderr); exit(1) }
