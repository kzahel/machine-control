import ApplicationServices
import Darwin
import XCTest
@testable import macui

final class NativeElementIdentityTests: XCTestCase {
    final class Node {
        var children: [Node] = []
        var readable = true
        var effects = 0
        func press() { effects += 1 }
    }
    final class WeakNode { weak var value: Node?; init(_ value: Node) { self.value = value } }
    let process = NativeProcessStamp(pid: 101, startSeconds: 1, startMicroseconds: 2)
    func cache(capacity: Int = 10) -> NativeObservationIdentity<Node> {
        // Deliberate hash collisions must never establish identity.
        NativeObservationIdentity(capacity: capacity, equal: { $0 === $1 }, hash: { _ in 0 })
    }

    func testUnchangedInsertReorderReplacementRemovalAndReappearance() {
        let value = cache(), a = Node(), b = Node(), window = Node()
        let epoch = value.observe([a, b], process: process, windows: [window], complete: true, now: 0)
        let aID = value.identity(for: a), bID = value.identity(for: b)
        XCTAssertNotEqual(aID, bID)
        XCTAssertEqual(epoch, value.observe([a, b], process: process, windows: [window], complete: true, now: 1))
        XCTAssertEqual(aID, value.identity(for: a))
        let inserted = Node()
        value.observe([b, inserted, a], process: process, windows: [window], complete: true, now: 2)
        XCTAssertEqual(aID, value.identity(for: a)); XCTAssertEqual(bID, value.identity(for: b))
        let replacement = Node()
        value.observe([b, inserted, replacement], process: process, windows: [window], complete: true, now: 3)
        XCTAssertNil(value.identity(for: a)); XCTAssertNotEqual(aID, value.identity(for: replacement))
        value.observe([inserted, replacement], process: process, windows: [window], complete: true, now: 4)
        XCTAssertNil(value.identity(for: b))
        value.observe([b, inserted, replacement], process: process, windows: [window], complete: true, now: 5)
        XCTAssertNotEqual(bID, value.identity(for: b))
    }

    func testScopeResetUnknownProcessIncompleteTTLAndInvalidation() {
        for boundary in ["pid", "birthSeconds", "birthMicroseconds", "window", "incomplete", "unknown", "gap", "clock", "invalidate"] {
            let value = cache(), a = Node(), window = Node()
            let old = value.observe([a], process: process, windows: [window], complete: true, now: 1)
            var stamp: NativeProcessStamp? = process
            var windows = [window], now = 2.0
            if boundary == "pid" { stamp = NativeProcessStamp(pid: 102, startSeconds: 1, startMicroseconds: 2) }
            if boundary == "birthSeconds" { stamp = NativeProcessStamp(pid: 101, startSeconds: 2, startMicroseconds: 2) }
            if boundary == "birthMicroseconds" { stamp = NativeProcessStamp(pid: 101, startSeconds: 1, startMicroseconds: 3) }
            if boundary == "window" { windows = [Node()] }
            if boundary == "unknown" { stamp = nil }
            if boundary == "gap" { now = 32 }
            if boundary == "clock" { now = 0 }
            if boundary == "invalidate" { value.invalidate() }
            let next = value.observe([a], process: stamp, windows: windows, complete: boundary != "incomplete", now: now)
            XCTAssertNotEqual(old, next, boundary)
            if boundary == "unknown" || boundary == "incomplete" {
                XCTAssertNil(next); XCTAssertEqual(value.retainedElementCount, 0)
                XCTAssertNotEqual(old, value.observe([a], process: process, windows: [window], complete: true, now: 3))
            }
        }
    }

    func testWindowOrderIsNotIdentityAndDuplicateEqualityRefuses() {
        let value = cache(), a = Node(), w1 = Node(), w2 = Node()
        let first = value.observe([a], process: process, windows: [w1, w2], complete: true, now: 0)
        XCTAssertEqual(first, value.observe([a], process: process, windows: [w2, w1], complete: true, now: 1))
        XCTAssertNil(value.observe([a, a], process: process, windows: [w1], complete: true, now: 2))
        XCTAssertEqual(value.retainedElementCount, 0)
        XCTAssertNil(value.observe([a], process: process, windows: [w1, w1], complete: true, now: 3))
    }

    func testFreshReferencesCannotBeRevivedByStableObservationIdentity() {
        let refs = NativeSnapshotReferences<Node>(equal: { $0 === $1 })
        let a = Node(), root = Node(); root.children = [a]
        refs.replace(["s1:r": a], paths: ["s1:r": [root, a]], process: process)
        refs.replace(["s2:r": a], paths: ["s2:r": [root, a]], process: process)
        XCTAssertNil(refs["s1:r"])
        XCTAssertEqual(refs.validate("s1:r", process: process, root: root, children: { $0.children }), .stale)
        XCTAssertEqual(refs.validate("s2:r", process: process, root: root, children: { $0.children }), .current)
    }

    func testRetiredValidObjectCannotReceiveAnEffect() {
        let refs = NativeSnapshotReferences<Node>(equal: { $0 === $1 })
        let retired = Node(), replacement = Node(), window = Node(), root = Node()
        for boundary in ["removed", "replacement", "window", "process", "unreadable", "ambiguous"] {
            root.children = [window]; window.children = [retired]
            refs.replace(["current": retired], paths: ["current": [root, window, retired]], process: process)
            var stamp = process
            if boundary == "removed" { window.children = [] }
            if boundary == "replacement" { window.children = [replacement] }
            if boundary == "window" { root.children = [Node()] }
            if boundary == "process" { stamp = NativeProcessStamp(pid: 101, startSeconds: 2, startMicroseconds: 2) }
            if boundary == "ambiguous" { window.children = [retired, retired] }
            let membership = refs.validate("current", process: stamp, root: root) { node in
                    if boundary == "unreadable" { throw MacUIError.element("unreadable") }; return node.children
                }
            if membership == .current { retired.press() }
            XCTAssertNotEqual(membership, .current, boundary)
            if boundary == "unreadable" || boundary == "ambiguous" { XCTAssertEqual(membership, .unverifiable) }
        }
        XCTAssertEqual(retired.effects, 0)
    }

    func testCapacityAndHistoryReleaseObjectsAndWindows() {
        let value = cache(capacity: 4)
        let refs = NativeSnapshotReferences<Node>(capacity: 4, equal: { $0 === $1 })
        var weakNodes: [WeakNode] = []
        for index in 0..<100 {
            let nodes = (0..<4).map { _ in Node() }, window = Node()
            weakNodes += (nodes + [window]).map(WeakNode.init)
            value.observe(nodes, process: process, windows: [window], complete: true, now: Double(index))
            refs.replace(Dictionary(uniqueKeysWithValues: nodes.enumerated().map { ("s\(index):\($0.offset)", $0.element) }),
                         paths: Dictionary(uniqueKeysWithValues: nodes.enumerated().map { ("s\(index):\($0.offset)", [window, $0.element]) }),
                         process: process)
            XCTAssertLessThanOrEqual(value.retainedElementCount, 4)
            XCTAssertEqual(refs.elements.count, 4)
        }
        XCTAssertLessThanOrEqual(weakNodes.filter { $0.value != nil }.count, 5)
        value.invalidate(); refs.invalidate()
        XCTAssertTrue(weakNodes.allSatisfy { $0.value == nil })
        XCTAssertNil(value.observe((0..<5).map { _ in Node() }, process: process, windows: [], complete: true, now: 101))
        XCTAssertEqual(value.retainedElementCount, 0)
        refs.replace(["partial": Node()], paths: [:], process: nil)
        XCTAssertEqual(refs.elements.count, 0); XCTAssertEqual(refs.retainedPathCount, 0)
    }

    func testIncompleteTraversalReportsDepthCountAndReadFailures() {
        enum Failure: Error { case unreadable }
        let root = Node(), child = Node(); root.children = [child]
        func read(depth: Int, limit: Int) -> NativeTreeRead<Node> {
            readNativeTree(root: root, maxDepth: depth, limit: limit) {
                if !$0.readable { throw Failure.unreadable }; return $0.children
            }
        }
        XCTAssertTrue(read(depth: 1, limit: 2).complete)
        XCTAssertEqual(read(depth: 0, limit: 2).incompleteReason, "depth_limit")
        XCTAssertEqual(read(depth: 1, limit: 1).incompleteReason, "element_limit")
        child.readable = false
        XCTAssertEqual(read(depth: 1, limit: 2).incompleteReason, "native_read_failed")
        XCTAssertEqual(read(depth: -1, limit: 0).incompleteReason, "invalid_limits")
    }

    func testActualCFProxyEqualityNotSwiftWrapperAddress() {
        let value = NativeObservationIdentity<AXUIElement>(equal: { CFEqual($0, $1) },
            hash: { Int(truncatingIfNeeded: CFHash($0)) })
        // Allocates proxies only; no reads, actions, app launches or host UI.
        let a = AXUIElementCreateApplication(Int32.max)
        let b = AXUIElementCreateApplication(Int32.max)
        value.observe([a], process: process, windows: [], complete: true, now: 0)
        let identity = value.identity(for: a)
        value.observe([b], process: process, windows: [], complete: true, now: 1)
        XCTAssertEqual(identity, value.identity(for: b))
    }

    func testIncompleteUnrelatedBranchAndUnsupportedLeafDoNotDisableActions() {
        let root = Node(), menu = Node(), leaf = Node(), unavailableBranch = Node()
        root.children = [menu, unavailableBranch]; menu.children = [leaf]
        let refs = NativeSnapshotReferences<Node>(equal: { $0 === $1 })
        refs.replace(["menu-item": leaf], paths: ["menu-item": [root, menu, leaf]], process: process)
        let tree = readNativeTree(root: root, maxDepth: 1, limit: 100) { $0.children }
        XCTAssertEqual(tree.incompleteReason, "depth_limit")
        let result = refs.validate("menu-item", process: process, root: root) { node in
            if node === leaf || node === unavailableBranch { throw MacUIError.element("AXChildren unsupported") }
            return node.children
        }
        XCTAssertEqual(result, .current)
        // AXChildren unsupported/noValue is a valid leaf in identity traversal;
        // the AX adapter translates those statuses to an empty array.
        leaf.children = []
        let onlyLeaf = readNativeTree(root: leaf, maxDepth: 0, limit: 1) { _ in [] as [Node] }
        XCTAssertTrue(onlyLeaf.complete)
    }

    func testDefaultDepthEightStillAllowsActionOnObservedAncestor() {
        let nodes = (0..<10).map { _ in Node() }
        for index in 0..<9 { nodes[index].children = [nodes[index + 1]] }
        let reading = readNativeTree(root: nodes[0], maxDepth: 8, limit: 500) { $0.children }
        XCTAssertEqual(reading.incompleteReason, "depth_limit")
        XCTAssertEqual(reading.elements.count, 9)
        let refs = NativeSnapshotReferences<Node>(equal: { $0 === $1 })
        refs.replace(["depth-eight": nodes[8]], paths: ["depth-eight": Array(nodes.prefix(9))], process: process)
        XCTAssertEqual(refs.validate("depth-eight", process: process, root: nodes[0], children: { $0.children }), .current)
    }

    func testAXUnsupportedAndNoValueLeafStatusMapping() throws {
        for code in [AXError.attributeUnsupported, AXError.noValue] {
            XCTAssertTrue(try nativeChildrenValue(status: code, value: nil, unsupportedLeafIsEmpty: true).isEmpty)
            XCTAssertThrowsError(try nativeChildrenValue(status: code, value: nil, unsupportedLeafIsEmpty: false))
        }
        XCTAssertThrowsError(try nativeChildrenValue(status: .cannotComplete, value: nil, unsupportedLeafIsEmpty: true))
        XCTAssertThrowsError(try nativeChildrenValue(status: .success, value: nil, unsupportedLeafIsEmpty: true))
        XCTAssertTrue(try nativeChildrenValue(status: .success, value: [] as CFArray, unsupportedLeafIsEmpty: false).isEmpty)
    }

    func testKernelStampRejectsUnavailablePartialWrongPIDAndInvalidBirthWithoutFallback() {
        for failure in ["none", "error", "empty", "short", "oversized", "pid", "seconds", "negativeMicroseconds", "microseconds"] {
            var info = kinfo_proc()
            info.kp_proc.p_pid = failure == "pid" ? 102 : 101
            info.kp_proc.p_starttime.tv_sec = failure == "seconds" ? 0 : 123
            info.kp_proc.p_starttime.tv_usec = failure == "microseconds" ? 1_000_000 :
                (failure == "negativeMicroseconds" ? -1 : 456)
            var size = MemoryLayout<kinfo_proc>.stride
            if failure == "empty" { size = 0 }
            if failure == "short" { size -= 1 }
            if failure == "oversized" { size += 1 }
            var calls = 0
            let stamp = nativeKernelProcessStamp(101) { pid in
                calls += 1; XCTAssertEqual(pid, 101)
                return NativeKernelProcessRead(status: failure == "error" ? -1 : 0, byteCount: size, info: info)
            }
            XCTAssertEqual(calls, 1)
            if failure == "none" {
                XCTAssertEqual(stamp, NativeProcessStamp(pid: 101, startSeconds: 123, startMicroseconds: 456))
            } else { XCTAssertNil(stamp, failure) }
        }
        for pid: Int32 in [0, -1] {
            XCTAssertNil(nativeKernelProcessStamp(pid) { _ in
                XCTFail("Invalid PID must not reach kernel lookup")
                return NativeKernelProcessRead(status: 0, byteCount: 0, info: kinfo_proc())
            })
        }
    }

    func testOwnKernelBirthStampIsStableWithoutAppKitOrAXReads() throws {
        // Reads only this test process's kernel metadata, no desktop/UI access.
        let first = try XCTUnwrap(nativeKernelProcessStamp(getpid()))
        XCTAssertEqual(first.pid, getpid())
        XCTAssertGreaterThan(first.startSeconds, 0)
        XCTAssertEqual(first, nativeKernelProcessStamp(getpid()))
        XCTAssertEqual(NativeProcessStamp.source, "darwin.sysctl.kern_proc_pid.start_time.v1")
    }

    func testScopeEvidenceSeparatesProcessAndWindowUncertainty() {
        let window = Node(), changed = NativeProcessStamp(pid: 101, startSeconds: 1, startMicroseconds: 3)
        func reason(_ before: NativeProcessStamp?, _ after: NativeProcessStamp?, _ first: [Node]?, _ last: [Node]?) -> String? {
            nativeScopeIncompleteReason(processBefore: before, processAfter: after,
                windowsBefore: first, windowsAfter: last, equal: { $0 === $1 })
        }
        XCTAssertEqual(reason(nil, process, [window], [window]), "process_stamp_unavailable_before")
        XCTAssertEqual(reason(process, nil, [window], [window]), "process_stamp_unavailable_after")
        XCTAssertEqual(reason(process, changed, [window], [window]), "process_changed_during_read")
        XCTAssertEqual(reason(process, process, nil, [window]), "windows_unavailable_before")
        XCTAssertEqual(reason(process, process, [window], nil), "windows_unavailable_after")
        XCTAssertEqual(reason(process, process, [window], [Node()]), "windows_changed_during_read")
        XCTAssertNil(reason(process, process, [window], [window]))
        XCTAssertNil(reason(process, process, [], []))
    }

    func testProcessExitOrReuseDuringAncestorReadsRefusesBeforeEffect() {
        let refs = NativeSnapshotReferences<Node>(equal: { $0 === $1 })
        let root = Node(), control = Node(); root.children = [control]
        refs.replace(["fresh": control], paths: ["fresh": [root, control]], process: process)
        let replacement = NativeProcessStamp(pid: 101, startSeconds: 1, startMicroseconds: 3)
        for finalProcess in [nil, replacement, process] {
            var readEdge = false
            let membership = refs.validate("fresh", process: process, root: root,
                processAfterValidation: { XCTAssertTrue(readEdge); return finalProcess }) { node in
                    readEdge = true; return node.children
                }
            if finalProcess == process { XCTAssertEqual(membership, .current) }
            else {
                XCTAssertEqual(membership, .stale)
                if membership == .current { control.press() }
            }
        }
        XCTAssertEqual(control.effects, 0)
    }
}
