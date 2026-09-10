import Foundation
import Security
import Darwin

// This executable is an explicit administrator tool, never a setuid program
// or broker operation. Only fixed owned destinations and policy names mutate.
let state = "/var/db/machine-control-unlock"
let bundle = "/Library/Security/SecurityAgentPlugins/MCUnlock.bundle"
let label = "org.machine-control.unlock"
let daemon = "/Library/LaunchDaemons/\(label).plist"
let publicStatus = "/Library/Preferences/org.machine-control.unlock.plist"
let rightName = "org.machine-control.screen-unlock"
let fm = FileManager.default
struct Failure: Error { let code: String }
func run(_ command: String, _ args: [String], input: Data? = nil, allowFailure: Bool = false) throws -> Data {
    let task = Process(); task.executableURL = URL(fileURLWithPath: command); task.arguments = args
    let output = Pipe(); let errors = Pipe(); task.standardOutput = output; task.standardError = errors
    let pipe = Pipe(); task.standardInput = pipe
    try task.run()
    if let input { pipe.fileHandleForWriting.write(input) }; try pipe.fileHandleForWriting.close()
    let data = output.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    if task.terminationStatus != 0 && !allowFailure { throw Failure(code: "installer_command_failed") }
    return data
}
func load(_ path: String) throws -> [String: Any] {
    guard let value = try PropertyListSerialization.propertyList(from: Data(contentsOf: URL(fileURLWithPath: path)), format: nil) as? [String: Any] else { throw Failure(code: "invalid_receipt") }
    return value
}
func save(_ object: [String: Any], _ path: String, mode: mode_t = 0o600) throws {
    let data = try PropertyListSerialization.data(fromPropertyList: object, format: .xml, options: 0)
    try data.write(to: URL(fileURLWithPath: path), options: .atomic)
    guard chmod(path, mode) == 0, chown(path, 0, 0) == 0 else { throw Failure(code: "ownership_failed") }
    if path == state + "/receipt.plist" {
        try save(["enabled": object["enabled"] as? Bool ?? false, "version": 1], publicStatus, mode: 0o644)
    }
}
func policy(_ name: String) throws -> [String: Any] {
    let data = try run("/usr/bin/security", ["authorizationdb", "read", name])
    guard var value = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else { throw Failure(code: "invalid_policy") }
    value.removeValue(forKey: "created"); value.removeValue(forKey: "modified")
    return value
}
func equal(_ a: [String: Any], _ b: [String: Any]) -> Bool { NSDictionary(dictionary: a).isEqual(to: b) }
func writePolicy(_ name: String, _ value: [String: Any]) throws {
    _ = try run("/usr/bin/security", ["authorizationdb", "write", name], input: PropertyListSerialization.data(fromPropertyList: value, format: .xml, options: 0))
    guard equal(try policy(name), value) else { throw Failure(code: "policy_readback_failed") }
}
func secureDirectory(_ path: String) throws {
    var s = stat()
    if lstat(path, &s) != 0 {
        guard mkdir(path, 0o700) == 0 else { throw Failure(code: "state_directory_failed") }; return
    }
    guard s.st_mode & S_IFMT == S_IFDIR, s.st_uid == 0, s.st_mode & 0o077 == 0 else { throw Failure(code: "state_directory_unsafe") }
}
func cdhash(_ path: String) throws -> Data {
    var code: SecStaticCode?
    guard SecStaticCodeCreateWithPath(URL(fileURLWithPath: path) as CFURL, [], &code) == errSecSuccess,
          let code, SecStaticCodeCheckValidity(code, SecCSFlags(rawValue: kSecCSStrictValidate), nil) == errSecSuccess else { throw Failure(code: "signature_invalid") }
    var info: CFDictionary?
    guard SecCodeCopySigningInformation(code, SecCSFlags(rawValue: kSecCSSigningInformation), &info) == errSecSuccess,
          let values = info as? [String: Any], let hash = values[kSecCodeInfoUnique as String] as? Data else { throw Failure(code: "signature_missing") }
    return hash
}
func stop() throws {
    unlink(state + "/grant.plist")
    _ = try run("/bin/launchctl", ["bootout", "system/" + label], allowFailure: true)
}
func start() throws { _ = try run("/bin/launchctl", ["bootstrap", "system", daemon]) }
func restore(_ receipt: [String: Any]) throws {
    guard let original = receipt["originalPolicy"] as? [String: Any],
          let installed = receipt["installedPolicy"] as? [String: Any] else { throw Failure(code: "invalid_receipt") }
    let current = try policy("system.login.screensaver")
    guard equal(current, original) || equal(current, installed) else { throw Failure(code: "unlock_policy_conflict") }
    try writePolicy("system.login.screensaver", original)
}
let args = Array(CommandLine.arguments.dropFirst())
do {
    guard geteuid() == 0 else { throw Failure(code: "root_required") }
    guard let operation = args.first, ["install", "inspect", "disable", "uninstall"].contains(operation) else { throw Failure(code: "usage") }
    let receiptPath = state + "/receipt.plist"
    let present = fm.fileExists(atPath: receiptPath)
    if operation == "inspect" {
        guard args.count == 1 else { throw Failure(code: "usage") }
        if !present { print("{\"installation\":\"missing\"}"); exit(0) }
        try secureDirectory(state)
        let receipt = try load(receiptPath)
        let installed = receipt["installedPolicy"] as? [String: Any] ?? [:]
        let enabled = receipt["enabled"] as? Bool == true
        let expected = enabled ? installed : receipt["originalPolicy"] as? [String: Any] ?? [:]
        let healthy = equal(try policy("system.login.screensaver"), expected)
            && (try? cdhash(bundle)) == receipt["pluginCDHash"] as? Data
            && (try? cdhash(state + "/broker")) == receipt["brokerCDHash"] as? Data
        print("{\"installation\":\"\(healthy ? "healthy" : "inconsistent")\",\"policy\":\"\(enabled ? "enabled" : "disabled")\"}")
        exit(healthy ? 0 : 1)
    }
    if operation == "disable" || operation == "uninstall" {
        guard args.count == 1 else { throw Failure(code: "usage") }
        if !present { print("{\"installation\":\"missing\"}"); exit(0) }
        try secureDirectory(state)
        var receipt = try load(receiptPath)
        // Refuse conflicts before modifying policy. Disable the grant path even
        // if external policy drift prevents completing removal.
        receipt["enabled"] = false; try save(receipt, receiptPath)
        try stop(); try restore(receipt)
        if operation == "uninstall" {
            let dedicated = receipt["dedicatedPolicy"] as? [String: Any] ?? [:]
            if let current = try? policy(rightName) {
                guard equal(current, dedicated) else { throw Failure(code: "unlock_policy_conflict") }
                _ = try run("/usr/bin/security", ["authorizationdb", "remove", rightName])
            }
            for path in [bundle, daemon, publicStatus, state, "/var/run/machine-control-unlock"] where fm.fileExists(atPath: path) { try fm.removeItem(atPath: path) }
        }
        print("{\"completed\":true}"); exit(0)
    }
    guard args.count == 4, args[1] == "--appliance-uid", let uid = UInt32(args[2]), uid > 0,
          args[3].hasPrefix("/") else { throw Failure(code: "usage_install_requires_appliance_uid_and_resident_binary") }
    let resident = args[3]
    let hash = try cdhash(resident)
    let source = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent()
    let sourceBundle = source.appendingPathComponent("MCUnlock.bundle").path
    let sourceBroker = source.appendingPathComponent("mc-unlock-broker").path
    let pluginHash = try cdhash(sourceBundle); let brokerHash = try cdhash(sourceBroker)
    try secureDirectory(state)
    let previous = present ? try load(receiptPath) : nil
    let current = try policy("system.login.screensaver")
    var original = current
    if let previous {
        guard let old = previous["originalPolicy"] as? [String: Any],
              let installed = previous["installedPolicy"] as? [String: Any],
              equal(current, old) || equal(current, installed) else { throw Failure(code: "unlock_policy_conflict") }
        original = old
    } else {
        guard current["class"] as? String == "rule", current["rule"] as? [String] == ["use-login-window-ui"],
              (current["k-of-n"] as? Int ?? 1) == 1,
              !fm.fileExists(atPath: bundle), !fm.fileExists(atPath: daemon),
              (try? policy(rightName)) == nil else { throw Failure(code: "unlock_policy_conflict") }
    }
    var installed = original; installed["rule"] = [rightName, "use-login-window-ui"]; installed["k-of-n"] = 1
    let dedicated: [String: Any] = ["class":"evaluate-mechanisms", "mechanisms":["MCUnlock:unlock,privileged"], "shared":false, "tries":1, "version":0,
        "identifier":"com.apple.security", "requirement":"identifier \"com.apple.security\" and anchor apple"]
    if let existing = try? policy(rightName), !equal(existing, dedicated) { throw Failure(code: "unlock_policy_conflict") }
    var receipt: [String: Any] = ["version":1, "enabled":false, "allowedUID":uid, "residentCDHash":hash,
        "originalPolicy":original, "installedPolicy":installed, "dedicatedPolicy":dedicated,
        "pluginCDHash":pluginHash, "brokerCDHash":brokerHash]
    // The receipt precedes all policy writes, so interrupted setup can be removed.
    try save(receipt, receiptPath)
    do {
        try stop(); try restore(receipt)
        // Stage a complete bundle before replacing the disabled owned copy.
        let staging = state + "/staged.bundle"
        if fm.fileExists(atPath: staging) { try fm.removeItem(atPath: staging) }
        _ = try run("/usr/bin/ditto", [sourceBundle, staging])
        _ = try run("/usr/sbin/chown", ["-R", "root:wheel", staging])
        _ = try run("/bin/chmod", ["-R", "go-w", staging])
        _ = try cdhash(staging)
        if fm.fileExists(atPath: bundle) { try fm.removeItem(atPath: bundle) }
        try fm.moveItem(atPath: staging, toPath: bundle)
        let brokerData = try Data(contentsOf: URL(fileURLWithPath: sourceBroker))
        try brokerData.write(to: URL(fileURLWithPath: state + "/broker"), options: .atomic)
        guard chmod(state + "/broker", 0o700) == 0 else { throw Failure(code: "ownership_failed") }
        _ = try cdhash(state + "/broker")
        try save(["Label":label, "ProgramArguments":[state + "/broker"], "RunAtLoad":true, "KeepAlive":true,
                  "ProcessType":"Background", "ThrottleInterval":2], daemon, mode: 0o644)
        try writePolicy(rightName, dedicated)
        try start()
        try writePolicy("system.login.screensaver", installed)
        receipt["enabled"] = true; try save(receipt, receiptPath)
    } catch {
        receipt["enabled"] = false; try? save(receipt, receiptPath)
        try? stop(); try? restore(receipt)
        throw error
    }
    print("{\"completed\":true,\"profile\":\"opted_in_appliance\"}")
} catch {
    let code = (error as? Failure)?.code ?? "installer_failed"
    print("{\"errorCode\":\"\(code)\"}"); exit(1)
}
