import Darwin
import Foundation

/// A stalled initial frame must not block the resident's main queue, pause
/// enforcement, activation offers or other callers. Ownership transfers only
/// after a complete bounded frame; pipelining before that handshake is refused.
final class RequestHandshake {
    let descriptor: Int32
    private var source: DispatchSourceRead?
    private var timeout: DispatchWorkItem?
    private var buffer = Data()
    private var finished = false
    var completion: ((Data?) -> Void)?
    init(_ descriptor: Int32) { self.descriptor = descriptor }
    func start() throws {
        let flags = fcntl(descriptor, F_GETFL)
        guard flags >= 0, fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == 0 else { throw MacUIError.action("transport_unavailable") }
        let source = DispatchSource.makeReadSource(fileDescriptor:descriptor, queue:.main)
        source.setEventHandler { [weak self] in self?.readable() }
        self.source = source; source.resume()
        let timeout = DispatchWorkItem { [weak self] in self?.finish(nil) }
        self.timeout = timeout
        DispatchQueue.main.asyncAfter(deadline:.now() + 5, execute:timeout)
    }
    private func readable() {
        var bytes = [UInt8](repeating:0, count:16384)
        while !finished {
            let count = Darwin.read(descriptor, &bytes, bytes.count)
            if count == 0 { finish(nil); return }
            if count < 0 {
                if errno == EINTR { continue }
                if errno != EAGAIN && errno != EWOULDBLOCK { finish(nil) }
                return
            }
            buffer.append(bytes, count:count)
            if buffer.count >= 1_048_576 { finish(nil); return }
            if let newline = buffer.firstIndex(of:0x0a) {
                guard newline == buffer.index(before:buffer.endIndex) else { finish(nil); return }
                finish(buffer); return
            }
        }
    }
    private func finish(_ data: Data?) {
        guard !finished else { return }; finished = true
        source?.cancel(); timeout?.cancel()
        let flags = fcntl(descriptor, F_GETFL)
        if flags >= 0 { _ = fcntl(descriptor, F_SETFL, flags & ~O_NONBLOCK) }
        let callback = completion; completion = nil; callback?(data)
    }
    func cancel() {
        guard !finished else { return }; finished = true
        source?.cancel(); timeout?.cancel(); completion = nil
        Darwin.close(descriptor)
    }
    deinit { cancel() }
}
