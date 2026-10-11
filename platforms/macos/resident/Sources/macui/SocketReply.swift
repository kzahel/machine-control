import Darwin
import Foundation

/// Owns a duplicate of a one-shot client. Slow readers never block the UI and
/// caller cleanup cannot close/reuse the descriptor underneath the writer.
final class SocketReply {
    private var descriptor: Int32
    private let data: Data
    private var offset = 0
    private var timer: DispatchSourceTimer?
    private var expiry: DispatchWorkItem?
    var completed: (() -> Void)?

    init(client: Int32, data: Data) throws {
        descriptor = Darwin.dup(client); self.data = data
        guard descriptor >= 0 else { throw MacUIError.action("reply_transport_unavailable") }
        do {
            try closeOnExec(descriptor)
            let flags = fcntl(descriptor, F_GETFL)
            guard flags >= 0, fcntl(descriptor, F_SETFL, flags | O_NONBLOCK) == 0 else {
                throw MacUIError.action("reply_transport_unavailable")
            }
        } catch { Darwin.close(descriptor); descriptor = -1; throw error }
    }
    func start(timeout: TimeInterval = 5) {
        let expiry = DispatchWorkItem { [weak self] in self?.cancel() }
        self.expiry = expiry
        DispatchQueue.main.asyncAfter(deadline:.now() + timeout, execute:expiry)
        let timer = DispatchSource.makeTimerSource(queue:.main)
        timer.schedule(deadline:.now(), repeating:.milliseconds(25))
        timer.setEventHandler { [weak self] in self?.flush() }
        self.timer = timer; timer.resume()
        flush()
    }
    private func flush() {
        guard descriptor >= 0 else { return }
        while offset < data.count {
            let count = data.withUnsafeBytes { Darwin.write(descriptor, $0.baseAddress!.advanced(by:offset), data.count - offset) }
            if count > 0 { offset += count; continue }
            if count < 0 && errno == EINTR { continue }
            if count < 0 && [EAGAIN, EWOULDBLOCK].contains(errno) { return }
            cancel(); return
        }
        cancel()
    }
    func cancel() {
        guard descriptor >= 0 else { return }
        Darwin.close(descriptor); descriptor = -1
        timer?.cancel(); timer = nil; expiry?.cancel(); expiry = nil
        let completion = completed; completed = nil; completion?()
    }
    deinit { timer?.cancel(); expiry?.cancel(); if descriptor >= 0 { Darwin.close(descriptor) } }
}
