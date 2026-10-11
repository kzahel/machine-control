import AppKit
import Darwin
import XCTest
@testable import macui

final class RuntimeLoadTests: XCTestCase {
    func testSocketLoadAndStopStayResponsiveWithThreeBlockedDependencies() throws {
        _ = NSApplication.shared
        signal(SIGPIPE, SIG_IGN)
        let root = URL(fileURLWithPath:"/tmp").appendingPathComponent("mc-load-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at:root, withIntermediateDirectories:false,
            attributes:[.posixPermissions:0o700])
        defer { try? FileManager.default.removeItem(at:root) }
        let service = ResidentService()
        let helperStarted = expectation(description:"helper blocked")
        let sessionStarted = expectation(description:"session blocked")
        let providerStarted = expectation(description:"provider preflight blocked")
        let releaseHelper = DispatchSemaphore(value:0)
        let releaseSession = DispatchSemaphore(value:0)
        let releaseProvider = DispatchSemaphore(value:0)
        defer { releaseHelper.signal(); releaseSession.signal(); releaseProvider.signal() }
        let console: [String:Any] = ["desktopState":"unlocked", "uuid":"fixture", "boot":123, "uid":getuid()]
        service.helperObservation = BackgroundObservation(label:"test.load.helper", timeout:0.05,
            unknown:{ ["installation":"unknown", "lockedUsePaused":true] },
            read:{ helperStarted.fulfill(); releaseHelper.wait(); return ["installation":"healthy"] })
        service.sessionObservation = BackgroundObservation(label:"test.load.session", timeout:0.05,
            unknown:{ console }, read:{ sessionStarted.fulfill(); releaseSession.wait(); return console })
        let value = try ResidentRuntime(socketPath:root.appendingPathComponent("control.sock").path,
            policy:.workstation(issue:nil), journal:nil, service:service)
        try value.start(); defer { value.stop() }
        value.server.refreshAdmission()
        wait(for:[helperStarted, sessionStarted], timeout:1)
        value.server.nativeProvider.readSession = {
            providerStarted.fulfill(); releaseProvider.wait(); return console
        }
        let oldRequest = expectation(description:"invalidated provider request finished")
        value.server.nativeProvider.execute(["operation":"action"], coveredWindows:[], cancellation:{ nil },
            observed:{ _ in }, authorize:{ nil },
            custom:{ _ in XCTFail("Old provider request executed after Stop"); return [:] },
            completion:{ result in
                XCTAssertEqual(result["errorCode"] as? String, "control_generation_changed"); oldRequest.fulfill()
            })
        wait(for:[providerStarted], timeout:1)
        value.server.grantConsoleObservation = { console }
        value.server.broker.issue(scopes:[.observe,.control], durationSeconds:60,
            reason:"fixture", requester:"fixture", approver:"fixture")
        XCTAssertNotNil(value.server.broker.grant)
        var ticks = 0
        let timer = DispatchSource.makeTimerSource(queue:.main)
        timer.schedule(deadline:.now(), repeating:.milliseconds(10))
        timer.setEventHandler { ticks += 1 }; timer.resume()
        defer { timer.cancel() }
        let load = expectation(description:"eight concurrent socket clients")
        load.expectedFulfillmentCount = 8
        let path = value.server.socketPath
        for _ in 0..<8 {
            DispatchQueue.global().async {
                defer { load.fulfill() }
                for _ in 0..<100 {
                    do {
                        let fd = try residentSocket(); defer { Darwin.close(fd) }
                        var (address, length) = try unixAddress(path)
                        XCTAssertEqual(withSockAddr(&address, length:length, { Darwin.connect(fd, $0, $1) }), 0)
                        var timeout = timeval(tv_sec:3, tv_usec:0)
                        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue:timeout)))
                        try writeSocket(fd, data:encodeJSONLine(["operation":"grant.status"]))
                        _ = Darwin.shutdown(fd, SHUT_WR)
                        let response = try JSONSerialization.jsonObject(with:readSocket(fd)) as? [String:Any]
                        XCTAssertEqual(response?["accepted"] as? Bool, true)
                    } catch { XCTFail("Socket discovery failed under bounded load: \(error)"); return }
                }
            }
        }
        let stop = expectation(description:"Stop remains responsive during load")
        DispatchQueue.main.async {
            let started = ProcessInfo.processInfo.systemUptime
            value.stopAccess()
            XCTAssertLessThan(ProcessInfo.processInfo.systemUptime - started, 0.25)
            XCTAssertNil(value.server.broker.grant)
            stop.fulfill()
        }
        wait(for:[load, stop], timeout:10)
        XCTAssertGreaterThan(ticks,0)
        XCTAssertTrue(value.server.nativeProvider.busy)
        XCTAssertTrue(service.helperObservation.metadata["refreshing"] as? Bool == true)
        XCTAssertTrue(service.sessionObservation.metadata["refreshing"] as? Bool == true)
        releaseProvider.signal(); releaseHelper.signal(); releaseSession.signal()
        wait(for:[oldRequest], timeout:1)
        XCTAssertFalse(value.server.nativeProvider.busy)
    }
}
