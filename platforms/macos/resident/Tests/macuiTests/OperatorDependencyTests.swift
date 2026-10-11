import Foundation
import XCTest
@testable import macui

final class OperatorDependencyTests: XCTestCase {
    func testTimeoutKeepsOneWorkerAndDiscardsLateCommitThenRecovers() {
        let value = OperatorDependency()
        let started = expectation(description:"dependency started")
        let expired = expectation(description:"caller deadline")
        let drained = expectation(description:"worker drained")
        let release = DispatchSemaphore(value:0)
        defer { release.signal(); value.cancel() }
        var calls = 0
        value.perform(timeout:0.05, work:{ cancelled in
            started.fulfill(); release.wait()
            XCTAssertNotNil(cancelled())
        }, commit:{ XCTFail("Timed-out dependency committed") }, completion:{ result in
            calls += 1
            XCTAssertEqual(result["error"] as? String, "operator_dependency_timeout")
            expired.fulfill()
        })
        wait(for:[started, expired], timeout:1)
        XCTAssertTrue(value.busy)
        for _ in 0..<1000 {
            value.perform(work:{ _ in XCTFail("Unbounded extra worker") }, commit:{ XCTFail("Extra commit") },
                completion:{ XCTAssertEqual($0["error"] as? String, "operator_dependency_busy") })
        }
        release.signal()
        DispatchQueue.main.asyncAfter(deadline:.now() + 0.1) { drained.fulfill() }
        wait(for:[drained], timeout:1)
        XCTAssertFalse(value.busy); XCTAssertEqual(calls,1)
        let recovered = expectation(description:"next operation succeeds")
        value.perform(work:{ _ in }, commit:{}, completion:{ result in
            XCTAssertEqual(result["ok"] as? Bool, true); recovered.fulfill()
        })
        wait(for:[recovered], timeout:1)
    }
}
