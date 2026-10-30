// One-shot verification of the current dedicated VM user's stored password.
// No credential or account identity is printed, persisted or passed in argv.
import Foundation
import OpenDirectory
import SystemConfiguration

func reply(_ code: String, verified: Bool = false) -> Never {
    print("{\"schema\":\"machine-control-appliance-credential-check/v0\",\"code\":\"\(code)\",\"verified\":\(verified)}")
    exit(verified || code == "ready" ? 0 : 1)
}
guard CommandLine.arguments.count == 2,
      ["--preflight", "--verify"].contains(CommandLine.arguments[1]) else { reply("invalid_request") }
var size = 0
guard sysctlbyname("hw.model", nil, &size, nil, 0) == 0, size > 0, size < 256 else { reply("platform_unavailable") }
var model = [CChar](repeating:0, count:size)
guard sysctlbyname("hw.model", &model, &size, nil, 0) == 0,
      String(cString:model).hasPrefix("VirtualMac") else { reply("dedicated_virtual_mac_required") }
var uid: uid_t = 0, gid: gid_t = 0
guard getuid() != 0, SCDynamicStoreCopyConsoleUser(nil, &uid, &gid) != nil,
      uid == getuid() else { reply("exact_console_user_required") }
let record: ODRecord
do {
    let node = try ODNode(session:ODSession.default(), type:UInt32(kODNodeTypeLocalNodes))
    record = try node.record(withRecordType:kODRecordTypeUsers, name:NSUserName(), attributes:nil)
} catch { reply("local_record_unavailable") }
if CommandLine.arguments[1] == "--preflight" { reply("ready") }
// Provider/current-principal discovery completed before reading the secret.
var data = Data()
while data.count <= 4096 {
    let part = FileHandle.standardInput.readData(ofLength:4097-data.count)
    if part.isEmpty { break }
    data.append(part)
}
guard !data.isEmpty, data.count <= 4096 else { reply("credential_size_invalid") }
if data.last == 10 { data.removeLast(); if data.last == 13 { data.removeLast() } }
guard !data.isEmpty, let password = String(data:data, encoding:.utf8),
      !password.contains("\0"), !password.contains("\n"), !password.contains("\r") else { reply("credential_invalid") }
do {
    try record.verifyPassword(password)
    reply("verified", verified:true)
} catch { reply("credential_not_verified") }
