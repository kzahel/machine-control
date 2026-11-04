import Darwin
import Foundation

struct SharedPolicyError: Error, CustomStringConvertible {
    let code: String
    var description: String { code }
}

/// Owned private child; no listener, interpreter discovery or public authority
/// methods. Replies drain independently of main and of provider event handling.
/// The runtime owner must call stop, including after failed initialization.
final class SharedResidentHost {
    typealias Frame = [String: Any]
    typealias Completion = (Result<Frame, Error>) -> Void
    private struct Pending { let complete: Completion; let timeout: DispatchWorkItem }
    private static let maximum = 16 * 1_048_576
    private let process = Process()
    private let input = Pipe(), output = Pipe(), errors = Pipe()
    private let lock = NSCondition()
    private let deadlines = DispatchQueue(label: "machine-control.policy-deadlines")
    private let lifetime = DispatchQueue(label: "machine-control.policy-lifetime")
    private var pending: [String: Pending] = [:]
    private var outgoing: [Data] = []
    private var outputBytes = 0
    private var eventCount = 0
    private var eventBytes = 0
    private var sequence: UInt64 = 0
    private var closed: String?
    private var snapshot: Frame = [:]
    private let receive: (Frame) -> Void
    private let native: (Frame) -> Bool
    private let failed: (String) -> Void

    var processID: pid_t { process.processIdentifier }
    var alive: Bool {
        lock.lock(); defer { lock.unlock() }
        return closed == nil && process.isRunning
    }
    var state: Frame {
        lock.lock(); defer { lock.unlock() }
        return snapshot
    }

    init(executable: URL, arguments: [String], directory: URL,
         receive: @escaping (Frame) -> Void, native: @escaping (Frame) -> Bool,
         failed: @escaping (String) -> Void) throws {
        self.receive = receive; self.native = native; self.failed = failed
        process.executableURL = executable; process.arguments = arguments
        process.currentDirectoryURL = directory
        process.environment = [:]
        process.standardInput = input; process.standardOutput = output
        process.standardError = errors
        for handle in [input.fileHandleForReading, input.fileHandleForWriting,
                       output.fileHandleForReading, output.fileHandleForWriting,
                       errors.fileHandleForReading, errors.fileHandleForWriting] {
            guard fcntl(handle.fileDescriptor, F_SETFD, FD_CLOEXEC) == 0 else {
                throw SharedPolicyError(code: "policy_pipe_setup_failed")
            }
        }
        guard fcntl(input.fileHandleForWriting.fileDescriptor, F_SETNOSIGPIPE, 1) == 0 else {
            throw SharedPolicyError(code: "policy_pipe_setup_failed")
        }
        process.terminationHandler = { [weak self] _ in self?.fail("ipc_closed") }
        try process.run()
        input.fileHandleForReading.closeFile()
        output.fileHandleForWriting.closeFile()
        errors.fileHandleForWriting.closeFile()
        Thread.detachNewThread { [weak self] in self?.readLoop() }
        Thread.detachNewThread { [weak self] in self?.writeLoop() }
        Thread.detachNewThread { [weak self] in
            guard let self else { return }
            let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: 4096)
            defer { buffer.deallocate() }
            while Darwin.read(self.errors.fileHandleForReading.fileDescriptor, buffer, 4096) > 0 { }
        }
        do {
            let hello = try call(["method": "hello", "protocolVersion": 2], timeout: 15)
            guard (hello["protocolVersion"] as? NSNumber)?.intValue == 2,
                  hello["admissionSchema"] as? String == "machine-control-admission/v2" else {
                throw SharedPolicyError(code: "unsupported_policy_protocol")
            }
        } catch { stop(); throw error }
    }

    static func packaged(receive: @escaping (Frame) -> Void, native: @escaping (Frame) -> Bool,
                         failed: @escaping (String) -> Void) throws -> SharedResidentHost {
        guard let root = Bundle.main.resourceURL?.appendingPathComponent("shared-policy") else {
            throw SharedPolicyError(code: "packaged_policy_unavailable")
        }
        let executable = root.appendingPathComponent("node")
        let entry = root.appendingPathComponent("policy/node/main.ts")
        guard FileManager.default.isExecutableFile(atPath: executable.path),
              FileManager.default.fileExists(atPath: entry.path) else {
            throw SharedPolicyError(code: "packaged_policy_unavailable")
        }
        return try SharedResidentHost(executable: executable, arguments: [entry.path],
            directory: root, receive: receive, native: native, failed: failed)
    }

    func call(_ frame: Frame, timeout: TimeInterval = 5) throws -> Frame {
        final class Reply { var value: Result<Frame, Error>? }
        let reply = Reply(), done = DispatchSemaphore(value: 0)
        request(frame, timeout: timeout) { value in reply.value = value; done.signal() }
        // Completion runs on the independent reader/deadline path, never main.
        done.wait()
        return try reply.value!.get()
    }

    func request(_ value: Frame, timeout: TimeInterval = 5, completion: @escaping Completion) {
        guard timeout.isFinite, timeout > 0, timeout <= 120,
              JSONSerialization.isValidJSONObject(value) else {
            completion(.failure(SharedPolicyError(code: "invalid_policy_request"))); return
        }
        lock.lock()
        guard closed == nil, pending.count < 128, sequence < UInt64.max else {
            lock.unlock()
            completion(.failure(SharedPolicyError(code: "control_policy_unavailable"))); return
        }
        sequence += 1
        let id = String(sequence)
        var frame = value; frame["id"] = id
        let deadline = DispatchWorkItem { [weak self] in self?.fail("ipc_reply_timeout") }
        pending[id] = Pending(complete: completion, timeout: deadline)
        lock.unlock()
        deadlines.asyncAfter(deadline: .now() + timeout, execute: deadline)
        do { try enqueue(frame) }
        catch { fail("ipc_write_invalid") }
    }

    private func enqueue(_ frame: Frame) throws {
        guard JSONSerialization.isValidJSONObject(frame) else {
            throw SharedPolicyError(code: "ipc_invalid_frame")
        }
        let body = try JSONSerialization.data(withJSONObject: frame)
        guard !body.isEmpty, body.count <= Self.maximum else {
            throw SharedPolicyError(code: "ipc_frame_size")
        }
        let size = UInt32(body.count)
        var data = Data([UInt8(size & 255), UInt8((size >> 8) & 255),
                         UInt8((size >> 16) & 255), UInt8((size >> 24) & 255)])
        data.append(body)
        lock.lock(); defer { lock.unlock() }
        guard closed == nil, outgoing.count < 64, outputBytes + data.count <= 2 * Self.maximum else {
            throw SharedPolicyError(code: "ipc_write_capacity")
        }
        outgoing.append(data); outputBytes += data.count; lock.signal()
    }

    private func writeLoop() {
        defer { input.fileHandleForWriting.closeFile() }
        while true {
            lock.lock()
            while closed == nil && outgoing.isEmpty { lock.wait() }
            guard closed == nil else { lock.unlock(); return }
            let data = outgoing.removeFirst()
            lock.unlock()
            let watchdog = DispatchWorkItem { [weak self] in self?.fail("ipc_write_timeout") }
            deadlines.asyncAfter(deadline: .now() + 3, execute: watchdog)
            let wrote = data.withUnsafeBytes { bytes -> Bool in
                var offset = 0
                while offset < bytes.count {
                    let count = Darwin.write(input.fileHandleForWriting.fileDescriptor,
                        bytes.baseAddress!.advanced(by: offset), bytes.count - offset)
                    if count < 0 && errno == EINTR { continue }
                    if count <= 0 { return false }
                    offset += count
                }
                return true
            }
            watchdog.cancel()
            lock.lock(); outputBytes -= data.count; lock.unlock()
            if !wrote { fail("ipc_write_failed"); return }
        }
    }

    private func readExactly(_ size: Int) throws -> Data {
        var data = Data(count: size)
        try data.withUnsafeMutableBytes { bytes in
            var offset = 0
            while offset < size {
                let count = Darwin.read(output.fileHandleForReading.fileDescriptor,
                    bytes.baseAddress!.advanced(by: offset), size - offset)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw SharedPolicyError(code: "ipc_closed") }
                offset += count
            }
        }
        return data
    }

    private func readLoop() {
        do {
            while true {
                let header = try readExactly(4)
                let size = Int(UInt32(header[0]) | UInt32(header[1]) << 8 |
                    UInt32(header[2]) << 16 | UInt32(header[3]) << 24)
                guard (1...Self.maximum).contains(size),
                      let frame = try JSONSerialization.jsonObject(with: readExactly(size)) as? Frame,
                      let type = frame["type"] as? String else {
                    throw SharedPolicyError(code: "ipc_invalid_frame")
                }
                if type == "reply" {
                    let id = frame["id"] as? String ?? ""
                    lock.lock(); let waiting = pending.removeValue(forKey: id); lock.unlock()
                    guard let waiting else {
                        if id.hasPrefix("native-reply:") { continue }
                        throw SharedPolicyError(code: "ipc_unknown_reply")
                    }
                    waiting.timeout.cancel()
                    if frame["ok"] as? Bool == true {
                        waiting.complete(.success(frame["data"] as? Frame ?? [:]))
                    } else {
                        waiting.complete(.failure(SharedPolicyError(code:
                            frame["errorCode"] as? String ?? "control_policy_refused")))
                    }
                } else if type == "browser.state", let value = frame["state"] as? Frame {
                    lock.lock(); snapshot = value; lock.unlock()
                } else if ["provider.send", "provider.close", "access.event", "native.check"].contains(type) {
                    let bytes = try JSONSerialization.data(withJSONObject: frame).count
                    lock.lock()
                    eventCount += 1; eventBytes += bytes
                    let full = eventCount > 512 || eventBytes > 2 * Self.maximum
                    lock.unlock()
                    guard !full else { throw SharedPolicyError(code: "ipc_event_capacity") }
                    DispatchQueue.main.async { [weak self] in
                        guard let self else { return }
                        defer {
                            self.lock.lock(); self.eventCount -= 1; self.eventBytes -= bytes; self.lock.unlock()
                        }
                        guard self.alive else { return }
                        if type == "native.check" {
                            guard let id = frame["nativeId"] as? String else { self.fail("ipc_invalid_frame"); return }
                            do { try self.enqueue(["id": "native-reply:" + id, "method": "native.reply",
                                "nativeId": id, "accepted": self.native(frame)]) }
                            catch { self.fail("ipc_write_failed") }
                        } else { self.receive(frame) }
                    }
                } else if type != "request.finished" {
                    throw SharedPolicyError(code: "ipc_invalid_event")
                }
            }
        } catch { fail((error as? SharedPolicyError)?.code ?? "ipc_invalid_json") }
    }

    private func fail(_ code: String) {
        lock.lock()
        guard closed == nil else { lock.unlock(); return }
        closed = code
        let calls = Array(pending.values); pending.removeAll()
        outgoing.removeAll(); lock.broadcast(); lock.unlock()
        for call in calls { call.timeout.cancel(); call.complete(.failure(SharedPolicyError(code: code))) }
        DispatchQueue.main.async { [failed] in failed(code) }
        lifetime.async { [self] in
            if process.isRunning {
                process.terminate()
                let end = ProcessInfo.processInfo.systemUptime + 1
                while process.isRunning && ProcessInfo.processInfo.systemUptime < end { Thread.sleep(forTimeInterval: 0.01) }
                if process.isRunning { Darwin.kill(process.processIdentifier, SIGKILL) }
            }
            process.waitUntilExit()
        }
    }
    func stop() { fail("resident_stopping") }
}
