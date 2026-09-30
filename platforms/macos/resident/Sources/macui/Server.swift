import AppKit
import Darwin
import Foundation

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
        autoreleasepool { service.refreshSession() }
        var pending = pollfd(fd: descriptor, events: Int16(POLLIN), revents: 0)
        if poll(&pending, 1, 250) <= 0 { continue }
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
                    if let refusal = service.credentialPreflight(request) {
                        try writeSocket(client, data: encodeJSONLine(refusal))
                        return
                    }
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
