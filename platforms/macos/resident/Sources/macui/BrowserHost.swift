import Darwin
import Foundation

/// Chrome native-messaging host mode. Chrome starts the bundle executable
/// with the extension origin; this process relays Chrome's length-prefixed
/// messages to the resident socket as JSON lines and back.
func runBrowserHost(origin: String) -> Never {
    let socketPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/MachineControl/control.sock").path
    let resident = socket(AF_UNIX, SOCK_STREAM, 0)
    guard resident >= 0, let unix = try? unixAddress(socketPath) else {
        FileHandle.standardError.write(Data("Machine Control resident is unavailable\n".utf8))
        exit(1)
    }
    var address = unix.0
    guard withSockAddr(&address, length: unix.1, { Darwin.connect(resident, $0, $1) }) == 0 else {
        FileHandle.standardError.write(Data("Machine Control resident is unavailable\n".utf8))
        exit(1)
    }
    var noSignal: Int32 = 1
    setsockopt(resident, SOL_SOCKET, SO_NOSIGPIPE, &noSignal, socklen_t(MemoryLayout.size(ofValue: noSignal)))
    let registration: [String: Any] = ["operation": "browser.provider", "origin": origin,
                                       "protocolVersion": 1]
    guard let line = try? encodeJSONLine(registration),
          (try? writeSocket(resident, data: line)) != nil,
          let reply = readLine(resident),
          let object = try? JSONSerialization.jsonObject(with: reply) as? [String: Any],
          object["type"] as? String == "registered" else {
        FileHandle.standardError.write(Data("Machine Control refused the browser provider\n".utf8))
        exit(1)
    }

    // Chrome to resident.
    Thread.detachNewThread {
        let input = FileHandle.standardInput
        while true {
            let header = input.readData(ofLength: 4)
            guard header.count == 4 else { exit(0) }
            let size = header.withUnsafeBytes { Int(UInt32(littleEndian: $0.loadUnaligned(as: UInt32.self))) }
            guard size > 0, size <= 64 * 1_048_576 else { exit(1) }
            var message = input.readData(ofLength: size)
            guard message.count == size else { exit(0) }
            message.append(0x0a)
            guard (try? writeSocket(resident, data: message)) != nil else { exit(0) }
        }
    }

    // Resident to Chrome.
    let output = FileHandle.standardOutput
    while let message = readLine(resident) {
        var size = UInt32(message.count).littleEndian
        output.write(Data(bytes: &size, count: 4))
        output.write(message)
    }
    exit(0)
}

private var residentBuffer = Data()

/// Reads one newline-terminated message, without the newline.
private func readLine(_ descriptor: Int32) -> Data? {
    var chunk = [UInt8](repeating: 0, count: 65_536)
    while true {
        if let newline = residentBuffer.firstIndex(of: 0x0a) {
            let line = residentBuffer[residentBuffer.startIndex..<newline]
            residentBuffer.removeSubrange(residentBuffer.startIndex...newline)
            return Data(line)
        }
        let count = Darwin.read(descriptor, &chunk, chunk.count)
        if count < 0 && errno == EINTR { continue }
        guard count > 0 else { return nil }
        residentBuffer.append(chunk, count: count)
    }
}
