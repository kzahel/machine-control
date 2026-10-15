import ApplicationServices
import XCTest
@testable import macui

final class NativeIdentityQualificationTests: XCTestCase {
    func testUnchangedReadsAndInsertionReorderKeepOracleIncarnations() {
        let a = NativeIdentityFixture.Element("opaque-a")
        let b = NativeIdentityFixture.Element("opaque-b")
        let fixture = NativeIdentityFixture([a, b])
        let first = fixture.observe()
        let unchanged = fixture.observe()
        XCTAssertNotEqual(first[0].reference, unchanged[0].reference)
        XCTAssertTrue(first[0].oracleMatches(unchanged[0]))
        fixture.elements = [b, .init("opaque-inserted"), a]
        let reordered = fixture.observe()
        XCTAssertTrue(first[0].oracleMatches(reordered[2]))
        XCTAssertTrue(first[1].oracleMatches(reordered[0]))
        XCTAssertFalse(first[0].oracleMatches(reordered[1]))
        XCTAssertTrue(fixture.press(first[0].reference))
        XCTAssertEqual(a.effects, 1)
        XCTAssertEqual(b.effects, 0)
    }

    func testTokenEqualityCannotProveReplacementSafety() {
        let original = NativeIdentityFixture.Element("reusable-opaque-token")
        let fixture = NativeIdentityFixture([original])
        let before = fixture.observe()[0]
        // Replacement deliberately has identical presentation AND token. This
        // is an adversarial model, not live evidence about an AX implementation.
        let replacement = NativeIdentityFixture.Element(original.equalityToken)
        fixture.elements = [replacement]
        let after = fixture.observe()[0]
        XCTAssertEqual(original.label, replacement.label)
        XCTAssertTrue(before.equalityCandidateMatches(after))
        XCTAssertFalse(before.oracleMatches(after))
        XCTAssertFalse(fixture.press(before.reference))
        XCTAssertEqual(replacement.effects, 0)
        XCTAssertTrue(fixture.press(after.reference))
        XCTAssertEqual(replacement.effects, 1)
    }

    func testRemovalRefusesBeforeEffectEvenWithRetainedObject() {
        let original = NativeIdentityFixture.Element("opaque-token")
        let fixture = NativeIdentityFixture([original])
        let before = fixture.observe()[0]
        fixture.elements = []
        XCTAssertTrue(fixture.observe().isEmpty)
        XCTAssertFalse(fixture.press(before.reference))
        XCTAssertEqual(original.effects, 0)
    }

    func testRuntimeDesktopProcessAndWindowRecreationRefuseBeforeEffect() {
        for boundary in ["runtime", "desktop", "process", "window"] {
            let original = NativeIdentityFixture.Element("opaque-token")
            let fixture = NativeIdentityFixture([original])
            let before = fixture.observe()[0]
            switch boundary {
            case "runtime": fixture.scope.runtime = "runtime-2"
            case "desktop": fixture.scope.desktop = "desktop-2"
            case "process": fixture.scope.process = "process-incarnation-2"
            default: fixture.scope.window = "window-incarnation-2"
            }
            let after = fixture.observe()[0]
            XCTAssertFalse(before.equalityCandidateMatches(after), boundary)
            XCTAssertFalse(before.oracleMatches(after), boundary)
            XCTAssertFalse(fixture.press(before.reference), boundary)
            XCTAssertEqual(original.effects, 0, boundary)
        }
    }

    func testNativeApplicationProxyEqualityWithoutDesktopIPC() {
        // These constructors allocate CF proxies only. No AX reads, observers,
        // launches or actions are performed against the host desktop. This
        // establishes equality mechanics, not descendant lifetime guarantees.
        let a = AXUIElementCreateApplication(Int32.max)
        let b = AXUIElementCreateApplication(Int32.max)
        let c = AXUIElementCreateApplication(Int32.max - 1)
        XCTAssertTrue(CFEqual(a, b))
        XCTAssertFalse(CFEqual(a, c))
    }
}
