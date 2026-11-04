import Darwin
import Foundation
import XCTest
@testable import macui

final class SharedResidentHostTests: XCTestCase {
    // Framing/transport fixture only. It implements no grant, queue or policy.
    private let fixture = """
    import json,os,struct,sys,time
    def read():
        h=sys.stdin.buffer.read(4)
        if len(h)!=4:raise EOFError()
        n=struct.unpack('<I',h)[0]; b=b''
        while len(b)<n:
            c=sys.stdin.buffer.read(n-len(b))
            if not c:raise EOFError()
            b+=c
        return json.loads(b)
    def send(v):
        b=json.dumps(v).encode();d=struct.pack('<I',len(b))+b
        if sys.argv[1]=='partial':
            for c in d:sys.stdout.buffer.write(bytes([c]));sys.stdout.buffer.flush()
        else:sys.stdout.buffer.write(d);sys.stdout.buffer.flush()
    def reply(r,data):
        send(dict(type='reply',id=r['id'],ok=True,data=data))
    r=read();reply(r,dict(protocolVersion=2,admissionSchema='machine-control-admission/v2'))
    if sys.argv[1]=='sink':time.sleep(60)
    while True:
        r=read();m=r['method']
        if m=='close':sys.exit(0)
        if m=='stall':time.sleep(60)
        if m=='invalid':
            sys.stdout.buffer.write(struct.pack('<I',0));sys.stdout.buffer.flush();time.sleep(60)
        if m=='event':
            send(dict(type='access.event',event=dict(event='fixture',surface='desktop')))
        if m=='native':
            send(dict(type='native.check',nativeId='fixture',phase='check'))
            n=read();assert n['method']=='native.reply'
            reply(n,{})
            reply(r,dict(allowed=n['accepted']));continue
        reply(r,dict(method=m,sentinelInherited='MACHINE_CONTROL_TEST_SENTINEL' in os.environ))
    """

    private func host(_ mode: String = "normal",
                      receive: @escaping (SharedResidentHost.Frame) -> Void = { _ in },
                      native: @escaping (SharedResidentHost.Frame) -> Bool = { _ in false },
                      failed: @escaping (String) -> Void = { _ in }) throws -> SharedResidentHost {
        try SharedResidentHost(executable: URL(fileURLWithPath: "/usr/bin/python3"),
            arguments: ["-c", fixture, mode], directory: FileManager.default.temporaryDirectory,
            receive: receive, native: native, failed: failed)
    }
    private func reaped(_ pid: pid_t, timeout: TimeInterval = 3) {
        let end = ProcessInfo.processInfo.systemUptime + timeout
        while kill(pid, 0) == 0 && ProcessInfo.processInfo.systemUptime < end {
            Thread.sleep(forTimeInterval: 0.01)
        }
        XCTAssertNotEqual(kill(pid, 0), 0, "The exact owned child must exit")
    }

    func testPartialFramesAndClearedEnvironment() throws {
        let original = getenv("MACHINE_CONTROL_TEST_SENTINEL").map { String(cString: $0) }
        setenv("MACHINE_CONTROL_TEST_SENTINEL", "fixture-only", 1)
        defer {
            if let original { setenv("MACHINE_CONTROL_TEST_SENTINEL", original, 1) }
            else { unsetenv("MACHINE_CONTROL_TEST_SENTINEL") }
        }
        let value = try host("partial"); defer { value.stop(); reaped(value.processID) }
        let reply = try value.call(["method": "inspect"])
        XCTAssertEqual(reply["method"] as? String, "inspect")
        XCTAssertEqual(reply["sentinelInherited"] as? Bool, false)
    }

    func testRepliesProgressWithoutMainEventDelivery() throws {
        let event = expectation(description: "main event")
        let value = try host(receive: { frame in
            XCTAssertEqual(frame["type"] as? String, "access.event"); event.fulfill()
        })
        defer { value.stop(); reaped(value.processID) }
        // This synchronous call is intentionally on main. Its preceding event
        // cannot run until the call returns; the independent reader must reply.
        XCTAssertEqual(try value.call(["method": "event"])["method"] as? String, "event")
        wait(for: [event], timeout: 1)
    }

    func testNativeCheckCanReplyWhileRequestIsPending() throws {
        let complete = expectation(description: "native reply")
        let value = try host(native: { frame in frame["phase"] as? String == "check" })
        defer { value.stop(); reaped(value.processID) }
        value.request(["method": "native"]) { result in
            XCTAssertEqual((try? result.get())?["allowed"] as? Bool, true); complete.fulfill()
        }
        wait(for: [complete], timeout: 2)
    }

    func testMalformedFrameAndEOFInvalidateTheChild() throws {
        for method in ["invalid", "close"] {
            let value = try host()
            XCTAssertThrowsError(try value.call(["method": method], timeout: 1))
            XCTAssertFalse(value.alive)
            XCTAssertThrowsError(try value.call(["method": "inspect"]))
            value.stop(); reaped(value.processID)
        }
    }

    func testReplyTimeoutKillsWithoutReplayOrRestart() throws {
        let value = try host()
        XCTAssertThrowsError(try value.call(["method": "stall"], timeout: 0.05))
        let original = value.processID
        reaped(original)
        XCTAssertFalse(value.alive)
        XCTAssertThrowsError(try value.call(["method": "inspect"]))
        XCTAssertEqual(value.processID, original)
        value.stop()
    }

    func testBlockedWriteHasAnIndependentWatchdog() throws {
        let complete = expectation(description: "blocked write refused")
        let value = try host("sink")
        defer { value.stop(); reaped(value.processID) }
        value.request(["method": "payload", "body": String(repeating: "x", count: 8 * 1_048_576)],
                      timeout: 10) { result in
            XCTAssertEqual((result.failure as? SharedPolicyError)?.code, "ipc_write_timeout")
            complete.fulfill()
        }
        wait(for: [complete], timeout: 5)
        XCTAssertFalse(value.alive)
    }
}

private extension Result {
    var failure: Failure? { if case let .failure(value) = self { return value }; return nil }
}
