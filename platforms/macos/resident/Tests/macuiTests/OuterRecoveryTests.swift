import Darwin
import XCTest
@testable import macui

final class OuterRecoveryTests: XCTestCase {
    private var directory = ""
    private var binding: OuterClaimBinding!
    private var record: [String:Any] = [:]
    private var effects = 0
    private var window = OuterRecovery.Window(id:1, pid:123, bounds:CGRect(x:10,y:20,width:640,height:508))
    override func setUpWithError() throws {
        directory = NSTemporaryDirectory() + "mc-outer-" + UUID().uuidString
        try FileManager.default.createDirectory(atPath:directory, withIntermediateDirectories:false, attributes:[.posixPermissions:0o700])
        binding = OuterClaimBinding(directory:directory, provider:"tart-macos", resource:"fixture", claim:"c-" + String(repeating:"a",count:24), windowName:"fixture", width:640, height:480, generation:1)
        let now = Date(), format = ISO8601DateFormatter()
        record = ["schema":"machine-control-target-claim-record/v0", "resource":["provider":"tart-macos", "id":"fixture"], "generation":1,
            "active":["claimId":binding.claim, "generation":1, "mode":"exclusive", "useClass":"disruptive",
                "acquiredAt":format.string(from:now.addingTimeInterval(-1)), "expiresAt":format.string(from:now.addingTimeInterval(60))]]
        try save()
    }
    override func tearDown() { try? FileManager.default.removeItem(atPath:directory) }
    private func save() throws {
        let path = directory + "/resource-" + binding.digest + ".json"
        try JSONSerialization.data(withJSONObject:record).write(to:URL(fileURLWithPath:path), options:.atomic)
        XCTAssertEqual(chmod(path, 0o600), 0)
    }
    private func controller() -> OuterRecovery {
        let value = OuterRecovery(binding:binding, input:{ [weak self] _ in self?.effects += 1 })
        value.resolve = { [weak self] in self!.window }
        value.consoleUnlocked = { true }; value.activate = { _ in true }; value.foreground = { _ in true }
        return value
    }
    func testExactBorrowAndAtomicEffectDoNotReplaceVmClaim() throws {
        let value = controller(), before = try Data(contentsOf:URL(fileURLWithPath:directory + "/resource-" + binding.digest + ".json"))
        let reference = try value.prepare()["reference"]!
        try value.begin(["reference":reference])
        var locked = false
        value.input = { [weak self] _ in
            var info = stat(); locked = lstat(self!.directory + "/.operation.lock", &info) == 0
            self?.effects += 1
        }
        try value.step(["reference":reference, "kind":"click", "x":10, "y":10])
        XCTAssertTrue(locked); XCTAssertEqual(effects, 1)
        XCTAssertEqual(try Data(contentsOf:URL(fileURLWithPath:directory + "/resource-" + binding.digest + ".json")), before)
        XCTAssertFalse(FileManager.default.fileExists(atPath:directory + "/.operation.lock"))
    }
    func testChangedClaimFocusGeometryConsoleAndFenceRefuseBeforeEffect() throws {
        let value = controller(), reference = try value.prepare()["reference"]!
        let action: [String:Any] = ["reference":reference, "kind":"click", "x":10,"y":10]
        value.consoleUnlocked = { false }; XCTAssertThrowsError(try value.step(action)); value.consoleUnlocked = { true }
        value.foreground = { _ in false }; XCTAssertThrowsError(try value.step(action)); value.foreground = { _ in true }
        window = OuterRecovery.Window(id:1,pid:123,bounds:CGRect(x:11,y:20,width:640,height:508))
        XCTAssertThrowsError(try value.step(action))
        window = OuterRecovery.Window(id:1,pid:123,bounds:CGRect(x:10,y:20,width:640,height:508))
        value.fence = { throw MacUIError.action("stale_control_session") }; XCTAssertThrowsError(try value.step(action)); value.fence = { }
        record["generation"] = 2; try save(); XCTAssertThrowsError(try value.step(action))
        XCTAssertEqual(effects, 0)
    }
    func testBusyStoreInvalidCoordinateAndWrongReferenceRefuse() throws {
        let value = controller(), reference = try value.prepare()["reference"]!
        XCTAssertEqual(mkdir(directory + "/.operation.lock", 0o700), 0)
        XCTAssertThrowsError(try value.step(["reference":reference,"kind":"key","key":"a"]))
        rmdir(directory + "/.operation.lock")
        XCTAssertThrowsError(try value.step(["reference":reference,"kind":"click","x":640,"y":0]))
        XCTAssertThrowsError(try value.step(["reference":"wrong","kind":"key","key":"a"]))
        XCTAssertEqual(effects, 0)
    }
    func testInterruptedDragOnlyReleasesOwnHeldButton() throws {
        let value = controller(), reference = try value.prepare()["reference"]!
        var kinds: [String] = []
        value.input = { kinds.append($0["kind"] as! String) }
        try value.step(["reference":reference,"kind":"dragStart","x":10,"y":10])
        try value.step(["reference":reference,"kind":"dragMove","x":20,"y":20])
        value.cleanup(); value.cleanup()
        XCTAssertEqual(kinds, ["dragStart","dragMove","dragEnd"])
        XCTAssertThrowsError(try value.step(["reference":reference,"kind":"dragMove","x":30,"y":30]))
    }
    func testNewSessionNeedsFreshOuterGeometryReference() throws {
        let value = controller(), old = try value.prepare()["reference"]!
        value.invalidate()
        XCTAssertThrowsError(try value.begin(["reference":old]))
        let fresh = try value.prepare()["reference"]!
        XCTAssertNotEqual(old as? String, fresh as? String)
        XCTAssertThrowsError(try value.step(["reference":old,"kind":"key","key":"a"]))
        XCTAssertEqual(effects, 0)
    }
    func testQueueLeaseAndOrdinaryClassCannotAuthorizeBorrow() throws {
        var active = record["active"] as! [String:Any]; active["useClass"] = "ordinary"; record["active"] = active; try save()
        XCTAssertThrowsError(try binding.validate())
        active["useClass"] = "disruptive"; record["active"] = active; try save()
        let queue: [String:Any] = ["schema":"machine-control-claim-queue-record/v1", "entries":[["claimId":binding.claim,"state":"active","pid":getpid(),"heartbeat":Date().timeIntervalSince1970 - 1]]]
        let path = directory + "/queue.json"
        try JSONSerialization.data(withJSONObject:queue).write(to:URL(fileURLWithPath:path)); chmod(path, 0o600)
        XCTAssertThrowsError(try binding.validate())
        XCTAssertEqual(effects, 0)
    }
}
