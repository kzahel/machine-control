import AppKit
import CryptoKit
import Darwin
import Foundation

/// A cooperative, controller-local borrow of an existing exact VM claim.
/// This is neither a second VM lease nor authenticated caller containment.
struct OuterClaimBinding {
    let directory, provider, resource, claim, windowName: String
    let width, height: Int
    let generation: Int
    var digest: String { SHA256.hash(data:Data((provider + "\0" + resource).utf8)).map { String(format:"%02x", $0) }.joined() }
    static func parse(_ value: Any?) throws -> OuterClaimBinding {
        guard let v = value as? [String:Any], Set(v.keys) == Set(["schema", "directory", "provider", "resource", "claimId", "generation", "windowName", "displayWidth", "displayHeight"]),
              v["schema"] as? String == "machine-control-outer-borrow/v1",
              let directory = v["directory"] as? String, directory.hasPrefix("/"), !directory.contains("\0"), directory.utf8.count <= 4096,
              let provider = v["provider"] as? String, ["tart-macos", "utm-macos"].contains(provider),
              let resource = v["resource"] as? String, !resource.isEmpty, resource.count <= 512, !resource.contains("\0"),
              let claim = v["claimId"] as? String, claim.range(of:"^c-[a-f0-9]{24}$", options:.regularExpression) != nil,
              let generation = admissionInteger(v["generation"]), generation > 0,
              let name = v["windowName"] as? String, !name.isEmpty, name.count <= 512, !name.contains("\0"),
              let width = admissionInteger(v["displayWidth"]), (1...32768).contains(width),
              let height = admissionInteger(v["displayHeight"]), (1...32768).contains(height) else { throw MacUIError.usage("invalid_outer_binding") }
        guard provider != "tart-macos" || resource == name else { throw MacUIError.usage("outer_target_binding_mismatch") }
        let result = OuterClaimBinding(directory:directory, provider:provider, resource:resource, claim:claim,
            windowName:name, width:width, height:height, generation:generation)
        try result.validate(); return result
    }
    private func read(_ name: String, maximum: Int) throws -> [String:Any] {
        let fd = Darwin.open(directory + "/" + name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw MacUIError.action("outer_claim_unavailable") }
        defer { Darwin.close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG,
              info.st_uid == getuid(), info.st_mode & 0o777 == 0o600, info.st_nlink == 1,
              info.st_size > 0, info.st_size <= maximum else { throw MacUIError.action("outer_claim_invalid") }
        var data = Data(); var bytes = [UInt8](repeating:0, count:16384)
        while true {
            let count = Darwin.read(fd, &bytes, bytes.count)
            if count == 0 { break }
            if count < 0 { if errno == EINTR { continue }; throw MacUIError.action("outer_claim_unavailable") }
            data.append(bytes, count:count)
            guard data.count <= maximum else { throw MacUIError.action("outer_claim_invalid") }
        }
        guard let value = try JSONSerialization.jsonObject(with:data) as? [String:Any] else { throw MacUIError.action("outer_claim_invalid") }
        return value
    }
    func validate(now: Date = Date()) throws {
        var info = stat()
        guard lstat(directory, &info) == 0, info.st_mode & S_IFMT == S_IFDIR,
              info.st_uid == getuid(), info.st_mode & 0o777 == 0o700 else { throw MacUIError.action("outer_claim_store_untrusted") }
        let record = try read("resource-" + digest + ".json", maximum:65536)
        guard record["schema"] as? String == "machine-control-target-claim-record/v0",
              let binding = record["resource"] as? [String:Any], binding["provider"] as? String == provider,
              binding["id"] as? String == resource, admissionInteger(record["generation"]) == generation,
              let active = record["active"] as? [String:Any], active["claimId"] as? String == claim,
              admissionInteger(active["generation"]) == generation,
              active["mode"] as? String == "exclusive", active["useClass"] as? String == "disruptive",
              let expiry = active["expiresAt"] as? String, let acquired = active["acquiredAt"] as? String,
              let expiration = Self.date(expiry), let issued = Self.date(acquired), issued <= now, now < expiration else {
            throw MacUIError.action("outer_claim_changed_or_expired")
        }
        if lstat(directory + "/queue.json", &info) == 0 {
            let queue = try read("queue.json", maximum:2 * 1024 * 1024)
            guard queue["schema"] as? String == "machine-control-claim-queue-record/v1",
                  let entries = queue["entries"] as? [[String:Any]], entries.count <= 256 else { throw MacUIError.action("outer_claim_invalid") }
            if let owner = entries.first(where:{ $0["claimId"] as? String == claim }) {
                guard ["active", "activating"].contains(owner["state"] as? String ?? ""),
                      let pid = admissionInteger(owner["pid"]), pid > 0, pid <= Int(Int32.max),
                      kill(Int32(pid), 0) == 0 || errno == EPERM,
                      let heartbeat = owner["heartbeat"] as? NSNumber, CFGetTypeID(heartbeat) != CFBooleanGetTypeID(),
                      heartbeat.doubleValue.isFinite, heartbeat.doubleValue > now.timeIntervalSince1970,
                      heartbeat.doubleValue <= now.timeIntervalSince1970 + 5.1 else { throw MacUIError.action("outer_claim_owner_ended") }
            }
        } else if errno != ENOENT { throw MacUIError.action("outer_claim_unavailable") }
    }
    private static func date(_ value: String) -> Date? {
        let format = ISO8601DateFormatter(); format.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = format.date(from:value) { return date }
        format.formatOptions = [.withInternetDateTime]; return format.date(from:value)
    }
    /// Same operation-lock protocol as the authoritative claim store. Claim
    /// release/replacement cannot race a native activation or event posted here.
    /// Busy locks refuse immediately; this never waits on the operator thread.
    func transaction<T>(_ effect: () throws -> T) throws -> T {
        var info = stat()
        guard lstat(directory, &info) == 0, info.st_mode & S_IFMT == S_IFDIR,
              info.st_uid == getuid(), info.st_mode & 0o777 == 0o700 else { throw MacUIError.action("outer_claim_store_untrusted") }
        let lock = directory + "/.operation.lock"
        guard mkdir(lock, 0o700) == 0 else { throw MacUIError.action("claim_store_busy") }
        defer { unlink(lock + "/pid"); rmdir(lock) }
        let fd = Darwin.open(lock + "/pid", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw MacUIError.action("outer_claim_store_untrusted") }
        let bytes = Array((String(getpid()) + "\n").utf8)
        let written = bytes.withUnsafeBytes { Darwin.write(fd, $0.baseAddress, bytes.count) }
        Darwin.close(fd)
        guard written == bytes.count else { throw MacUIError.action("outer_claim_store_untrusted") }
        try validate(); return try effect()
    }
}

/// Typed native effects only. No arbitrary executable, script or provider
/// dispatch can be supplied by an outer client.
final class OuterRecovery {
    struct Window: Equatable {
        let id: Int, pid: Int32
        let bounds: CGRect
    }
    let binding: OuterClaimBinding
    private var window: Window?
    private var reference: String?
    private var held: [String:Any]?
    var resolve: () throws -> Window
    var consoleUnlocked: () -> Bool = { nativeSessionObservation()["desktopState"] as? String == "unlocked" }
    var activate: (Int32) -> Bool = { NSRunningApplication(processIdentifier:$0)?.activate(options:[.activateAllWindows]) == true }
    var foreground: (Int32) -> Bool = { NSWorkspace.shared.frontmostApplication?.processIdentifier == $0 }
    var input: ([String:Any]) throws -> Void
    var fence: () throws -> Void = { }
    init(binding: OuterClaimBinding, input: @escaping ([String:Any]) throws -> Void) {
        self.binding = binding; self.input = input
        resolve = {
            let owner = binding.provider == "tart-macos" ? "Tart" : "UTM"
            let all = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String:Any]] ?? []
            let matches = all.filter { $0[kCGWindowOwnerName as String] as? String == owner &&
                $0[kCGWindowName as String] as? String == binding.windowName &&
                ($0[kCGWindowLayer as String] as? NSNumber)?.intValue == 0 }
            guard matches.count == 1, let v = matches.first,
                  let id = admissionInteger(v[kCGWindowNumber as String]),
                  let pid = admissionInteger(v[kCGWindowOwnerPID as String]), pid > 0, pid <= Int(Int32.max),
                  let b = v[kCGWindowBounds as String] as? [String:Any],
                  let x = b["X"] as? Double, let y = b["Y"] as? Double,
                  let width = b["Width"] as? Double, let height = b["Height"] as? Double,
                  [x,y,width,height].allSatisfy({ $0.isFinite }), width > 0, height > 28 else { throw MacUIError.action("outer_window_unavailable_or_ambiguous") }
            if binding.provider == "tart-macos" {
                let arguments = try processArguments(Int32(pid))
                guard arguments.first.map({ URL(fileURLWithPath:$0).lastPathComponent.lowercased() == "tart" }) == true,
                      arguments.contains("run"), arguments.last == binding.resource else { throw MacUIError.action("outer_provider_target_mismatch") }
            } else {
                // UTM drag is offered only after the authoritative adapter has
                // verified its pinned UUID against this name. Window identity,
                // process and geometry remain bound for this finite session.
                guard NSRunningApplication(processIdentifier:Int32(pid))?.bundleIdentifier == "com.utmapp.UTM" else { throw MacUIError.action("outer_provider_target_mismatch") }
            }
            return Window(id:id, pid:Int32(pid), bounds:CGRect(x:x,y:y,width:width,height:height))
        }
    }
    private func check() throws {
        try fence()
        guard consoleUnlocked() else { throw MacUIError.action("outer_requires_unlocked_host") }
    }
    func prepare() throws -> [String:Any] {
        try binding.transaction {
            try check(); let value = try resolve()
            window = value; reference = UUID().uuidString.lowercased()
            return ["reference":reference!, "coordinateSpace":"guest_display_pixels", "geometryFidelity":"provider_titlebar_projection",
                "displayWidth":binding.width, "displayHeight":binding.height, "hostInterference":"focus_cursor_keyboard"]
        }
    }
    func begin(_ request: [String:Any]) throws {
        guard let window, request["reference"] as? String == reference else { throw MacUIError.action("stale_outer_reference") }
        try binding.transaction {
            try check(); guard try resolve() == window else { throw MacUIError.action("outer_geometry_changed") }
            guard activate(window.pid) else { throw MacUIError.action("outer_focus_unverified") }
        }
    }
    /// Called for every actual input primitive after focus has settled. The
    /// owner/console/geometry/VM fences and event delivery share one transaction.
    func step(_ request: [String:Any]) throws {
        guard let window, request["reference"] as? String == reference else { throw MacUIError.action("stale_outer_reference") }
        try binding.transaction {
            try check()
            guard try resolve() == window, foreground(window.pid) else { throw MacUIError.action("outer_focus_or_geometry_changed") }
            guard Set(request.keys).isSubset(of:["operation", "requestId", "reference", "kind", "key", "x", "y", "button", "clickCount"]),
                  let kind = request["kind"] as? String,
                  ["key", "click", "dragStart", "dragMove", "dragEnd"].contains(kind) else { throw MacUIError.usage("invalid_outer_input") }
            if kind == "key" {
                guard request["key"] is String, request["x"] == nil, request["y"] == nil,
                      request["button"] == nil, request["clickCount"] == nil else { throw MacUIError.usage("invalid_outer_input") }
            } else {
                guard request["key"] == nil, request["button"] == nil || request["button"] is String,
                      request["clickCount"] == nil || admissionInteger(request["clickCount"]) != nil else { throw MacUIError.usage("invalid_outer_input") }
            }
            var event = request
            event.removeValue(forKey:"reference"); event.removeValue(forKey:"operation"); event.removeValue(forKey:"requestId")
            if kind != "key", admissionInteger(event["x"]) == nil || admissionInteger(event["y"]) == nil { throw MacUIError.usage("invalid_outer_coordinate") }
            if kind == "dragStart" && held != nil || ["dragMove", "dragEnd"].contains(kind) && held == nil { throw MacUIError.action("invalid_outer_drag_state") }
            if let x = admissionInteger(event["x"]), let y = admissionInteger(event["y"]) {
                guard x >= 0, y >= 0, x < binding.width, y < binding.height else { throw MacUIError.usage("invalid_outer_coordinate") }
                let title = binding.provider == "tart-macos" ? 28.0 : max(0, window.bounds.height - Double(binding.height))
                event["x"] = window.bounds.minX + Double(x) * window.bounds.width / Double(binding.width)
                event["y"] = window.bounds.minY + title + Double(y) * (window.bounds.height - title) / Double(binding.height)
            }
            try input(event)
            if ["dragStart", "dragMove"].contains(kind) { held = event }
            if kind == "dragEnd" { held = nil }
        }
    }
    /// Cancellation releases only this handler's held button; it never posts a
    /// new down event, changes focus or continues an interrupted drag.
    func cleanup() {
        guard var event = held else { return }
        held = nil; event["kind"] = "dragEnd"
        try? input(event)
    }
    func invalidate() { cleanup(); window = nil; reference = nil }
    deinit { cleanup() }
    static func emitNative(_ value: [String:Any]) throws {
        guard AXIsProcessTrusted(), CGPreflightPostEventAccess() else { throw MacUIError.permission("outer_input_permission_unavailable") }
        guard let kind = value["kind"] as? String else { throw MacUIError.usage("invalid_outer_input") }
        if kind == "key" {
            guard let chord = value["key"] as? String else { throw MacUIError.usage("invalid_outer_key") }
            let parts = chord.lowercased().split(separator:"-").map(String.init)
            let codes: [String:CGKeyCode] = ["a":0,"s":1,"d":2,"f":3,"h":4,"g":5,"z":6,"x":7,"c":8,"v":9,"b":11,"q":12,"w":13,"e":14,"r":15,"y":16,"t":17,"1":18,"2":19,"3":20,"4":21,"6":22,"5":23,"=":24,"9":25,"7":26,"minus":27,"8":28,"0":29,
                "]":30,"o":31,"u":32,"[":33,"i":34,"p":35,"enter":36,"return":36,"l":37,"j":38,"'":39,"k":40,";":41,"\\":42,",":43,"/":44,"n":45,"m":46,".":47,"tab":48,"space":49,"`":50,"delete":51,"escape":53,"left":123,"right":124,"down":125,"up":126]
            guard let key = parts.last, let code = codes[key] else { throw MacUIError.usage("invalid_outer_key") }
            var flags: CGEventFlags = []
            for modifier in parts.dropLast() {
                if ["cmd", "command"].contains(modifier) { flags.insert(.maskCommand) }
                else if modifier == "shift" { flags.insert(.maskShift) }
                else { throw MacUIError.usage("outer_key_modifier_unsupported") }
            }
            guard let down = CGEvent(keyboardEventSource:nil, virtualKey:code, keyDown:true),
                  let up = CGEvent(keyboardEventSource:nil, virtualKey:code, keyDown:false) else { throw MacUIError.action("outer_input_unavailable") }
            down.flags = flags; up.flags = flags
            down.post(tap:.cghidEventTap); up.post(tap:.cghidEventTap); return
        }
        guard let x = value["x"] as? Double, let y = value["y"] as? Double, x.isFinite, y.isFinite else { throw MacUIError.usage("invalid_outer_coordinate") }
        let point = CGPoint(x:x,y:y)
        let name = value["button"] as? String ?? "left"
        guard ["left", "right", "middle"].contains(name), kind == "click" || name == "left" else { throw MacUIError.usage("invalid_outer_button") }
        let button: CGMouseButton = name == "right" ? .right : name == "middle" ? .center : .left
        let down: CGEventType = name == "right" ? .rightMouseDown : name == "middle" ? .otherMouseDown : .leftMouseDown
        let up: CGEventType = name == "right" ? .rightMouseUp : name == "middle" ? .otherMouseUp : .leftMouseUp
        func post(_ type: CGEventType) throws {
            guard let event = CGEvent(mouseEventSource:nil, mouseType:type, mouseCursorPosition:point, mouseButton:button) else { throw MacUIError.action("outer_input_unavailable") }
            if kind == "click" {
                let count = admissionInteger(value["clickCount"]) ?? 1
                guard (1...2).contains(count) else { throw MacUIError.usage("invalid_outer_click_count") }
                event.setIntegerValueField(.mouseEventClickState, value:Int64(count))
            }
            event.post(tap:.cghidEventTap)
        }
        switch kind {
        case "click":
            guard let press = CGEvent(mouseEventSource:nil, mouseType:down, mouseCursorPosition:point, mouseButton:button),
                  let release = CGEvent(mouseEventSource:nil, mouseType:up, mouseCursorPosition:point, mouseButton:button) else { throw MacUIError.action("outer_input_unavailable") }
            let count = admissionInteger(value["clickCount"]) ?? 1
            guard (1...2).contains(count) else { throw MacUIError.usage("invalid_outer_click_count") }
            press.setIntegerValueField(.mouseEventClickState,value:Int64(count))
            release.setIntegerValueField(.mouseEventClickState,value:Int64(count))
            press.post(tap:.cghidEventTap); release.post(tap:.cghidEventTap)
        case "dragStart": try post(down)
        case "dragMove": try post(.leftMouseDragged)
        case "dragEnd": try post(up)
        default: throw MacUIError.usage("invalid_outer_input")
        }
    }
}

/// Kernel-owned process arguments bind a visible Tart runner to its exact VM,
/// rather than accepting a window title or owner display name by itself.
private func processArguments(_ pid: Int32) throws -> [String] {
    var mib: [Int32] = [CTL_KERN, KERN_PROCARGS2, pid]
    var size = 0
    guard sysctl(&mib, u_int(mib.count), nil, &size, nil, 0) == 0, size > 4, size <= 1024 * 1024 else { throw MacUIError.action("outer_provider_identity_unavailable") }
    var data = Data(count:size)
    let result = data.withUnsafeMutableBytes { sysctl(&mib, u_int(mib.count), $0.baseAddress, &size, nil, 0) }
    guard result == 0, size <= data.count else { throw MacUIError.action("outer_provider_identity_unavailable") }
    data = data.prefix(size)
    let argc = data.withUnsafeBytes { $0.loadUnaligned(as:Int32.self) }
    guard argc > 0, argc <= 4096 else { throw MacUIError.action("outer_provider_identity_unavailable") }
    var offset = 4
    while offset < data.count && data[offset] != 0 { offset += 1 }
    while offset < data.count && data[offset] == 0 { offset += 1 }
    var values: [String] = []
    for _ in 0..<argc {
        let start = offset
        while offset < data.count && data[offset] != 0 { offset += 1 }
        guard offset < data.count, let value = String(data:data[start..<offset], encoding:.utf8) else { throw MacUIError.action("outer_provider_identity_unavailable") }
        values.append(value); offset += 1
    }
    return values
}
