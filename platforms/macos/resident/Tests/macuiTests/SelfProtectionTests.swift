import XCTest
@testable import macui

final class SelfProtectionTests: XCTestCase {
    private let own = OwnInterface(processID: 4242,
                                   identifiers: ["org.machine-control.app", "machine control"],
                                   windowFrames: [CGRect(x: 100, y: 0, width: 30, height: 24),
                                                  CGRect(x: 500, y: 100, width: 400, height: 200)],
                                   hasKeyWindow: false, menuOpen: false,
                                   pointer: CGPoint(x: 10, y: 10))

    private func check(_ request: [String: Any], own: OwnInterface? = nil,
                       referenced: pid_t? = nil) -> String? {
        selfTargetRefusal(request, own: own ?? self.own, referencedProcess: referenced)?.code
    }

    func testRefusesOwnTargetsAndReferences() {
        XCTAssertEqual(check(["operation": "application.activate", "target": "Machine Control"]),
                       "self_target_refused")
        XCTAssertEqual(check(["operation": "input.key", "target": "4242", "key": "return"]),
                       "self_target_refused")
        XCTAssertEqual(check(["operation": "action", "reference": "r"], referenced: 4242),
                       "self_target_refused")
        XCTAssertNil(check(["operation": "action", "reference": "r"], referenced: 99))
        XCTAssertNil(check(["operation": "application.activate", "target": "com.apple.TextEdit"]))
    }

    func testRefusesPointerInsideOwnWindows() {
        XCTAssertEqual(check(["operation": "input.click", "x": 110, "y": 10]), "self_target_refused")
        XCTAssertEqual(check(["operation": "input.drag", "x": 10, "y": 10, "x2": 600, "y2": 150]),
                       "self_target_refused")
        XCTAssertNil(check(["operation": "input.click", "x": 300, "y": 300]))
        var hovering = own
        hovering.pointer = CGPoint(x: 600, y: 150)
        XCTAssertEqual(check(["operation": "input.scroll", "deltaY": -3], own: hovering),
                       "self_target_refused")
    }

    func testRefusesUntargetedKeysToOwnKeyWindowAndOpenMenu() {
        var keyed = own
        keyed.hasKeyWindow = true
        XCTAssertEqual(check(["operation": "input.text", "text": "x"], own: keyed), "self_target_refused")
        XCTAssertNil(check(["operation": "input.text", "text": "x", "target": "com.apple.TextEdit"],
                           own: keyed))
        var menu = own
        menu.menuOpen = true
        XCTAssertEqual(check(["operation": "input.move", "x": 300, "y": 300], own: menu),
                       "self_target_refused")
    }
}
