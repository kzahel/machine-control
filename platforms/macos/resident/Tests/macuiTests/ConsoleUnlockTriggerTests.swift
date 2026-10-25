import ApplicationServices
import XCTest
@testable import macui

final class ConsoleUnlockTriggerTests: XCTestCase {
    private final class Node {
        var attributes: [String: Any] = [:]
        init(_ attributes: [String: Any] = [:]) { self.attributes = attributes }
    }
    private func field(enabled: Bool = true, focused: Bool = true) -> Node {
        Node([kAXRoleAttribute: "AXTextField", kAXSubroleAttribute: "AXSecureTextField",
              kAXIdentifierAttribute: "UserPasswordTextField", kAXEnabledAttribute: enabled,
              kAXFocusedAttribute: focused])
    }
    private func app(_ children: [Node]) -> Node {
        Node([kAXWindowsAttribute: [Node([kAXIdentifierAttribute: "login", kAXChildrenAttribute: children])]])
    }
    private func issue(_ app: Node) -> String? {
        ConsoleUnlockTrigger.passwordPanelIssue(app: app) { node, attribute in
            XCTAssertNotEqual(attribute, kAXValueAttribute, "Never read a password value")
            XCTAssertTrue([kAXWindowsAttribute, kAXIdentifierAttribute, kAXRoleAttribute,
                           kAXSubroleAttribute, kAXEnabledAttribute, kAXFocusedAttribute,
                           kAXChildrenAttribute].contains(attribute))
            return node.attributes[attribute]
        }
    }
    func testOnlyExactEnabledFocusedSecureFieldIsReady() {
        XCTAssertNil(issue(app([field()])))
        XCTAssertEqual(issue(app([field(enabled: false)])), "password_field_disabled")
        XCTAssertEqual(issue(app([field(focused: false)])), "password_field_unfocused")
        let ordinary = field(); ordinary.attributes[kAXSubroleAttribute] = "AXTextField"
        XCTAssertEqual(issue(app([ordinary])), "password_field_absent")
        let foreign = field(); foreign.attributes[kAXIdentifierAttribute] = "other"
        XCTAssertEqual(issue(app([foreign])), "password_field_absent")
        XCTAssertEqual(issue(app([field(), field()])), "password_field_ambiguous")
    }
    func testWindowDiscoveryFailuresAreDistinct() {
        XCTAssertEqual(issue(Node()), "windows_unavailable")
        XCTAssertEqual(issue(Node([kAXWindowsAttribute: [Node]()])), "login_window_absent")
        let window = Node([kAXIdentifierAttribute: "login"])
        XCTAssertEqual(issue(Node([kAXWindowsAttribute: [window, window]])), "password_field_absent")
    }
    func testMultipleDisplayWindowsRequireExactlyOneReadySecureField() {
        let passive = Node([kAXIdentifierAttribute:"login", kAXChildrenAttribute:[field(focused:false)]])
        let active = Node([kAXIdentifierAttribute:"login", kAXChildrenAttribute:[field()]])
        for windows in [[passive, active], [active, passive]] {
            XCTAssertNil(issue(Node([kAXWindowsAttribute:windows])))
        }
        XCTAssertEqual(issue(Node([kAXWindowsAttribute:[active, active]])), "password_field_ambiguous")
        XCTAssertEqual(issue(Node([kAXWindowsAttribute:Array(repeating:passive, count:9)])), "login_window_limit")
    }
    func testReadFailureCannotAuthorizeAnOtherwiseReadyField() {
        enum Failure: Error { case read }
        let unreadable = Node()
        let root = app([field(), unreadable])
        let result = ConsoleUnlockTrigger.passwordPanelIssue(app: root) { node, attribute in
            if node === unreadable { throw Failure.read }
            return node.attributes[attribute]
        }
        XCTAssertEqual(result, "ax_read_failed")
    }
    func testTraversalLimitsStayBoundedAndExplainMissingField() {
        var deep = field()
        for _ in 0..<7 { deep = Node([kAXChildrenAttribute: [deep]]) }
        XCTAssertEqual(issue(app([deep])), "depth_limit")
        XCTAssertEqual(issue(app(Array(repeating: Node(), count: 256) + [field()])), "node_limit")
        XCTAssertEqual(issue(app([field()] + Array(repeating: Node(), count: 255))), "node_limit")
    }
}
