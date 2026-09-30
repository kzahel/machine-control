import Darwin
import Foundation

enum GrantScope: String, CaseIterable, Comparable {
    case observe, control, browser

    static func < (lhs: GrantScope, rhs: GrantScope) -> Bool {
        allCases.firstIndex(of: lhs)! < allCases.firstIndex(of: rhs)!
    }
}

enum GrantMode: String {
    case standing, approval
}

/// Deployment policy chosen by trusted installation. The resident never
/// widens it from request fields, arguments, environment, or user
/// preferences; anything it cannot trust falls back to `workstation`.
struct DeploymentPolicy: Equatable {
    static let defaultPath = "/Library/Application Support/MachineControl/policy.json"
    static let schema = "machine-control-policy/v0"
    static let presets = ["appliance", "unattended", "workstation"]

    var preset: String
    var grantMode: GrantMode
    var protectedOperations: Bool
    var source: String
    var issue: String?

    static func workstation(issue: String?) -> DeploymentPolicy {
        DeploymentPolicy(preset: "workstation", grantMode: .approval,
                         protectedOperations: false, source: "default",
                         issue: issue)
    }

    /// `trustedOwner` exists for tests; production callers use root.
    static func load(path: String = defaultPath,
                     trustedOwner: uid_t = 0) -> DeploymentPolicy {
        var info = stat()
        guard lstat(path, &info) == 0 else {
            return .workstation(issue: errno == ENOENT ? "policy_absent" : "policy_unreadable")
        }
        guard info.st_mode & S_IFMT == S_IFREG, info.st_uid == trustedOwner,
              info.st_mode & 0o022 == 0,
              ancestorsTrusted(path, owner: trustedOwner) else {
            return .workstation(issue: "policy_untrusted")
        }
        guard info.st_size <= 65_536,
              let data = FileManager.default.contents(atPath: path),
              let object = try? JSONSerialization.jsonObject(with: data),
              let document = object as? [String: Any] else {
            return .workstation(issue: "policy_invalid")
        }
        return parse(document) ?? .workstation(issue: "policy_invalid")
    }

    static func parse(_ document: [String: Any]) -> DeploymentPolicy? {
        let known: Set<String> = ["schema", "preset", "protectedOperations", "grantMode"]
        guard document["schema"] as? String == schema,
              Set(document.keys).isSubset(of: known),
              let preset = document["preset"] as? String,
              presets.contains(preset) else { return nil }
        let standingPreset = preset != "workstation"
        var mode: GrantMode = standingPreset ? .standing : .approval
        if let requested = document["grantMode"] {
            // An explicit mode may only make the preset stricter.
            guard let value = requested as? String,
                  let parsed = GrantMode(rawValue: value),
                  parsed == .approval || standingPreset else { return nil }
            mode = parsed
        }
        var protected = standingPreset
        if let requested = document["protectedOperations"] {
            guard let value = requested as? Bool,
                  !value || standingPreset else { return nil }
            protected = value
        }
        return DeploymentPolicy(preset: preset, grantMode: mode,
                                protectedOperations: protected,
                                source: "policy_file", issue: nil)
    }

    private static func ancestorsTrusted(_ path: String, owner: uid_t) -> Bool {
        // Check the resolved chain: a symlinked ancestor is judged by the
        // directories it actually names.
        guard let resolved = realpath((path as NSString).deletingLastPathComponent, nil) else {
            return false
        }
        var directory = String(cString: resolved)
        free(resolved)
        while !directory.isEmpty {
            var info = stat()
            guard lstat(directory, &info) == 0,
                  info.st_mode & S_IFMT == S_IFDIR,
                  info.st_uid == owner || info.st_uid == 0,
                  info.st_mode & 0o022 == 0 else { return false }
            if directory == "/" { break }
            directory = (directory as NSString).deletingLastPathComponent
        }
        return true
    }

    var json: [String: Any] {
        [
            "schema": DeploymentPolicy.schema,
            "preset": preset,
            "grantMode": grantMode.rawValue,
            "protectedOperations": protectedOperations,
            "source": source,
            "issue": issue.map { $0 as Any } ?? NSNull(),
        ]
    }
}
