import Darwin
import XCTest
@testable import macui

final class SocketReplyTests: XCTestCase {
    func testNonreadingClientCannotBlockMainOrReuseWriterDescriptor() throws {
        var pair: [Int32] = [-1,-1]
        XCTAssertEqual(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { if pair[0] >= 0 { Darwin.close(pair[0]) }; Darwin.close(pair[1]) }
        var capacity: Int32 = 1024
        XCTAssertEqual(setsockopt(pair[0], SOL_SOCKET, SO_SNDBUF, &capacity, socklen_t(MemoryLayout<Int32>.size)), 0)
        let reply = try SocketReply(client:pair[0], data:Data(repeating:0x61, count:1024 * 1024))
        Darwin.close(pair[0]); pair[0] = -1
        let responsive = expectation(description:"main queue responsive")
        let expired = expectation(description:"slow reader expired")
        reply.completed = { expired.fulfill() }; reply.start(timeout:0.1)
        DispatchQueue.main.async { responsive.fulfill() }
        wait(for:[responsive, expired], timeout:1)
        reply.cancel()
    }
}
