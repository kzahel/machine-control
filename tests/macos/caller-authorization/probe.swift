// Isolated authentication experiment. No resident or desktop operations.
import Darwin
import Foundation
import Security

func emit(_ value: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    FileHandle.standardOutput.write(data + Data([10]))
}

func fail(_ stage: String) -> Never {
    emit(["error": stage])
    exit(1)
}

func address(_ path: String) -> sockaddr_un {
    var result = sockaddr_un()
    result.sun_family = sa_family_t(AF_UNIX)
    result.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
    let bytes = Array(path.utf8) + [UInt8(0)]
    guard bytes.count <= MemoryLayout.size(ofValue: result.sun_path) else { fail("path_length") }
    withUnsafeMutableBytes(of: &result.sun_path) { destination in
        destination.copyBytes(from: bytes)
    }
    return result
}

func withAddress<T>(_ value: inout sockaddr_un, _ body: (UnsafePointer<sockaddr>, socklen_t) -> T) -> T {
    withUnsafePointer(to: &value) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            body($0, socklen_t(MemoryLayout<sockaddr_un>.size))
        }
    }
}

func authenticate(_ peer: Int32, requirement: SecRequirement) -> [String: Any] {
    var token = audit_token_t()
    var length = socklen_t(MemoryLayout<audit_token_t>.size)
    guard getsockopt(peer, SOL_LOCAL, LOCAL_PEERTOKEN, &token, &length) == 0,
          length == MemoryLayout<audit_token_t>.size else {
        return ["accepted": false, "stage": "peer_token"]
    }
    let data = withUnsafeBytes(of: &token) { Data($0) }
    var code: SecCode?
    let lookup = SecCodeCopyGuestWithAttributes(nil,
        [kSecGuestAttributeAudit: data] as CFDictionary, [], &code)
    guard lookup == errSecSuccess, let code else {
        return ["accepted": false, "stage": "guest_lookup", "status": lookup]
    }
    let flags = SecCSFlags(rawValue: kSecCSStrictValidate)
    let validity = SecCodeCheckValidity(code, flags, nil)
    guard validity == errSecSuccess else {
        return ["accepted": false, "stage": "code_validity", "status": validity]
    }
    let match = SecCodeCheckValidity(code, flags, requirement)
    return ["accepted": match == errSecSuccess,
            "stage": match == errSecSuccess ? "matched" : "requirement",
            "status": match]
}

let args = CommandLine.arguments
guard args.count >= 3 else { fail("arguments") }
let mode = args[1]
var endpoint = address(args[2])
let descriptor = socket(AF_UNIX, SOCK_STREAM, 0)
guard descriptor >= 0 else { fail("socket") }
defer { close(descriptor) }
var noSignal: Int32 = 1
setsockopt(descriptor, SOL_SOCKET, SO_NOSIGPIPE, &noSignal,
           socklen_t(MemoryLayout<Int32>.size))

if mode == "client" {
    guard withAddress(&endpoint, { connect(descriptor, $0, $1) }) == 0 else { fail("connect") }
    // The gate deliberately reads no caller-provided identity or request bytes.
    var response: UInt8 = 0
    guard read(descriptor, &response, 1) == 1 else { fail("response") }
    exit(0)
}

guard mode == "gate", args.count == 4,
      let text = try? String(contentsOfFile: args[3], encoding: .utf8) else { fail("arguments") }
var requirement: SecRequirement?
guard SecRequirementCreateWithString(text as CFString, [], &requirement) == errSecSuccess,
      let requirement else { fail("requirement_parse") }
umask(0o077)
guard withAddress(&endpoint, { bind(descriptor, $0, $1) }) == 0 else { fail("bind") }
defer { unlink(args[2]) }
guard chmod(args[2], 0o600) == 0 else { fail("socket_mode") }
guard listen(descriptor, 1) == 0 else { fail("listen") }
emit(["ready": true])
var event = pollfd(fd: descriptor, events: Int16(POLLIN), revents: 0)
guard poll(&event, 1, 5000) == 1, event.revents & Int16(POLLIN) != 0 else { fail("accept_timeout") }
let peer = accept(descriptor, nil, nil)
guard peer >= 0 else { fail("accept") }
defer { close(peer) }
let result = authenticate(peer, requirement: requirement)
var response: UInt8 = (result["accepted"] as? Bool == true) ? 1 : 0
_ = write(peer, &response, 1)
emit(result)
