import Darwin
import XCTest
@testable import macui

final class SocketReplyTests: XCTestCase {
    func testSlowReaderFloodHasBoundedWritersAndRecoversCapacity() throws {
        signal(SIGPIPE, SIG_IGN)
        let baseline = SocketReply.activeCount
        var peers: [Int32] = []
        var replies: [SocketReply] = []
        defer { replies.forEach { $0.cancel() }; peers.forEach { Darwin.close($0) } }
        let payload = Data(repeating:0x61, count:1024 * 1024)
        for _ in baseline..<SocketReply.limit {
            var pair: [Int32] = [-1,-1]
            XCTAssertEqual(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
            peers.append(pair[1])
            var capacity: Int32 = 1024
            XCTAssertEqual(setsockopt(pair[0], SOL_SOCKET, SO_SNDBUF, &capacity, socklen_t(MemoryLayout<Int32>.size)), 0)
            let reply = try SocketReply(client:pair[0], data:payload)
            Darwin.close(pair[0]); replies.append(reply); reply.start(timeout:0.1)
        }
        XCTAssertEqual(SocketReply.activeCount, SocketReply.limit)
        for _ in 0..<1000 { XCTAssertThrowsError(try SocketReply(client:-1, data:payload)) }
        let responsive = expectation(description:"main queue responsive under slow-reader flood")
        let drained = expectation(description:"slow readers timed out")
        DispatchQueue.main.async { responsive.fulfill() }
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.2) { drained.fulfill() }
        wait(for:[responsive, drained], timeout:1)
        XCTAssertEqual(SocketReply.activeCount, baseline)
        var pair: [Int32] = [-1,-1]
        XCTAssertEqual(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { pair.forEach { Darwin.close($0) } }
        let recovered = try SocketReply(client:pair[0], data:Data("ok\n".utf8))
        recovered.start()
        XCTAssertEqual(try readSocket(pair[1]), Data("ok\n".utf8))
        XCTAssertEqual(SocketReply.activeCount, baseline)
    }
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

    func testNonFiniteNumbersEncodeAsNullInsteadOfAborting() throws {
        let line = try encodeJSONLine([
            "bounds": ["x": Double.nan, "y": CGFloat.infinity, "width": 3.5],
            "elements": [["value": NSNumber(value: -Double.infinity)], ["value": 1]],
        ])
        let decoded = try XCTUnwrap(JSONSerialization.jsonObject(with: line) as? [String: Any])
        let bounds = try XCTUnwrap(decoded["bounds"] as? [String: Any])
        XCTAssertTrue(bounds["x"] is NSNull)
        XCTAssertTrue(bounds["y"] is NSNull)
        XCTAssertEqual(bounds["width"] as? Double, 3.5)
        let elements = try XCTUnwrap(decoded["elements"] as? [[String: Any]])
        XCTAssertTrue(elements[0]["value"] is NSNull)
        XCTAssertEqual(elements[1]["value"] as? Int, 1)
    }
}
