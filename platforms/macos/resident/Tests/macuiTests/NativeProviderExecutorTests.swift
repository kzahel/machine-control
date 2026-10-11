import Darwin
import XCTest
@testable import macui

final class NativeProviderExecutorTests: XCTestCase {
    func testInvalidatedPreflightCannotAdoptNewAuthority() {
        let value = NativeProviderExecutor()
        let started = expectation(description:"preflight started")
        let completed = expectation(description:"old request refused")
        let release = DispatchSemaphore(value:0)
        defer { release.signal(); value.stop() }
        value.readSession = { started.fulfill(); release.wait(); return ["desktopState":"unlocked"] }
        value.execute(["operation":"action"], coveredWindows:[], cancellation:{ nil },
            observed:{ _ in }, authorize:{ nil },
            custom:{ _ in XCTFail("An old request adopted fresh authority after Stop"); return ["accepted":true] },
            completion:{ result in
                XCTAssertEqual(result["accepted"] as? Bool, false)
                XCTAssertEqual(result["errorCode"] as? String, "control_generation_changed")
                completed.fulfill()
            })
        wait(for:[started], timeout:1)
        // Stop followed by new approval: current authorization alone cannot
        // distinguish this old request from one admitted under the new grant.
        value.invalidate()
        release.signal(); wait(for:[completed], timeout:1)
    }
    func testBlockedProviderLeavesMainResponsiveAndLateEffectIsUncertain() {
        let value = NativeProviderExecutor()
        value.readSession = { ["desktopState":"unlocked"] }
        let started = expectation(description:"provider started")
        let stopped = expectation(description:"main queue Stop")
        let completed = expectation(description:"late provider completion")
        let release = DispatchSemaphore(value:0)
        defer { release.signal(); value.stop() }
        value.execute(["operation":"input.key"], coveredWindows:[], cancellation:{ nil },
            observed:{ _ in }, authorize:{ nil }, custom:{ _ in
                started.fulfill(); release.wait()
                return ["accepted":true, "delivery":"confirmed", "effect":"observed"]
            }, completion:{ result in
                XCTAssertEqual(result["accepted"] as? Bool, false)
                XCTAssertEqual(result["delivery"] as? String, "confirmed")
                XCTAssertEqual(result["uncertainty"] as? String, "interrupted_after_possible_dispatch")
                completed.fulfill()
            })
        wait(for:[started], timeout:1)
        value.execute(["operation":"snapshot"], coveredWindows:[], cancellation:{ nil },
            observed:{ _ in }, authorize:{ nil }, custom:{ _ in XCTFail("Unbounded second worker"); return [:] },
            completion:{ XCTAssertEqual($0["errorCode"] as? String, "native_provider_busy") })
        DispatchQueue.main.async { value.invalidate(); stopped.fulfill() }
        wait(for:[stopped], timeout:1)
        release.signal(); wait(for:[completed], timeout:1)
        XCTAssertFalse(value.busy)
    }

    func testAuthorityIsRecheckedAfterSlowPreflightBeforeEffects() {
        let value = NativeProviderExecutor()
        let started = expectation(description:"preflight started")
        let completed = expectation(description:"request refused")
        let release = DispatchSemaphore(value:0)
        defer { release.signal(); value.stop() }
        var allowed = true
        value.readSession = { started.fulfill(); release.wait(); return ["desktopState":"unlocked"] }
        value.execute(["operation":"action"], coveredWindows:[], cancellation:{ nil }, observed:{ _ in },
            authorize:{ allowed ? nil : GrantRefusal("approval_required", "Access revoked") },
            custom:{ _ in XCTFail("An effect followed revoked preflight"); return [:] },
            completion:{ XCTAssertEqual($0["errorCode"] as? String, "approval_required"); completed.fulfill() })
        wait(for:[started], timeout:1)
        allowed = false; release.signal(); wait(for:[completed], timeout:1)
    }

    func testUncertainCredentialFieldRefusesBeforeRequestingSecret() throws {
        let value = NativeProviderExecutor()
        value.readSession = { ["desktopState":"unknown"] }
        var pair: [Int32] = [-1,-1]
        XCTAssertEqual(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { pair.forEach { Darwin.close($0) }; value.stop() }
        let completed = expectation(description:"credential refused")
        value.execute(["operation":"authorization.submit", "leaseId":"unknown"], coveredWindows:[],
            cancellation:{ nil }, observed:{ _ in }, authorize:{ nil }, credentialSocket:pair[0],
            completion:{ XCTAssertEqual($0["accepted"] as? Bool, false); completed.fulfill() })
        wait(for:[completed], timeout:2)
        var ready = pollfd(fd:pair[1], events:Int16(POLLIN), revents:0)
        XCTAssertEqual(poll(&ready, 1, 0), 0, "No secret ACK may be sent before exact field discovery")
    }
    func testProviderSharesRuntimeIdentityWithCoordinatorResults() {
        let coordinator = ResidentService()
        let worker = NativeProviderExecutor(runtimeGeneration:coordinator.generation)
        worker.readSession = { ["desktopState":"unlocked"] }
        let done = expectation(description:"provider refusal")
        worker.execute(["operation":"unsupported_fixture"], coveredWindows:[], cancellation:{ nil },
            observed:{ _ in }, authorize:{ nil }, completion:{ result in
                XCTAssertEqual(result["generation"] as? String,
                    coordinator.acceptance(["operation":"grant.status"], data:[:])["generation"] as? String)
                done.fulfill()
            })
        wait(for:[done], timeout:2); worker.stop()
    }

}
