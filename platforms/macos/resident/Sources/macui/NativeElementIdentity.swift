import AppKit
import ApplicationServices
import Darwin
import Foundation

/// Observation continuity, not bearer authority or a promise of eternal AX IDs.
struct NativeProcessStamp: Equatable {
    // One source only: never compare an AppKit date with a kernel timestamp.
    static let source = "darwin.sysctl.kern_proc_pid.start_time.v1"
    let pid: Int32
    let startSeconds: Int64
    let startMicroseconds: Int32
}

struct NativeKernelProcessRead {
    let status: Int32
    let byteCount: Int
    let info: kinfo_proc
}

func readNativeKernelProcess(_ pid: Int32) -> NativeKernelProcessRead {
    var info = kinfo_proc()
    var size = MemoryLayout<kinfo_proc>.stride
    var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
    let status = sysctl(&mib, 4, &info, &size, nil, 0)
    return NativeKernelProcessRead(status: status, byteCount: size, info: info)
}

func nativeKernelProcessStamp(_ pid: Int32,
    read: (Int32) -> NativeKernelProcessRead = readNativeKernelProcess) -> NativeProcessStamp? {
    guard pid > 0 else { return nil }
    let result = read(pid)
    let birth = result.info.kp_proc.p_starttime
    guard result.status == 0, result.byteCount == MemoryLayout<kinfo_proc>.stride,
          result.info.kp_proc.p_pid == pid, birth.tv_sec > 0,
          birth.tv_usec >= 0, birth.tv_usec < 1_000_000 else { return nil }
    return NativeProcessStamp(pid: pid, startSeconds: Int64(birth.tv_sec), startMicroseconds: Int32(birth.tv_usec))
}

func nativeScopeIncompleteReason<Element>(processBefore: NativeProcessStamp?, processAfter: NativeProcessStamp?,
    windowsBefore: [Element]?, windowsAfter: [Element]?, equal: (Element, Element) -> Bool) -> String? {
    guard let processBefore else { return "process_stamp_unavailable_before" }
    guard let processAfter else { return "process_stamp_unavailable_after" }
    guard processBefore == processAfter else { return "process_changed_during_read" }
    guard let windowsBefore else { return "windows_unavailable_before" }
    guard let windowsAfter else { return "windows_unavailable_after" }
    guard nativeSameSet(windowsBefore, windowsAfter, equal: equal) else { return "windows_changed_during_read" }
    return nil
}

func nativeSameSet<Element>(_ lhs: [Element], _ rhs: [Element],
                            equal: (Element, Element) -> Bool) -> Bool {
    lhs.count == rhs.count && lhs.allSatisfy { item in
        rhs.filter { equal(item, $0) }.count == 1
    } && rhs.allSatisfy { item in lhs.filter { equal(item, $0) }.count == 1 }
}

/// Retains only the last complete tree for one app. Hashes bucket candidates;
/// CFEqual (supplied by the AX adapter) must establish every actual match.
final class NativeObservationIdentity<Element> {
    private struct Entry { let element: Element; let identity: String }
    private var entries: [Int: [Entry]] = [:]
    private var process: NativeProcessStamp?
    private var windows: [Element] = []
    private var observedAt: TimeInterval?
    private(set) var generation: String?
    let capacity: Int
    let maximumGap: TimeInterval
    let windowCapacity = 64
    private let equal: (Element, Element) -> Bool
    private let hash: (Element) -> Int

    init(capacity: Int = 2000, maximumGap: TimeInterval = 30,
         equal: @escaping (Element, Element) -> Bool, hash: @escaping (Element) -> Int) {
        self.capacity = capacity; self.maximumGap = maximumGap
        self.equal = equal; self.hash = hash
    }

    var retainedElementCount: Int { entries.values.reduce(0) { $0 + $1.count } }
    var retainedWindowCount: Int { windows.count }

    func invalidate() {
        entries.removeAll(); windows.removeAll(); process = nil
        observedAt = nil; generation = nil
    }

    @discardableResult
    func observe(_ elements: [Element], process nextProcess: NativeProcessStamp?,
                 windows nextWindows: [Element], complete: Bool, now: TimeInterval) -> String? {
        guard complete, let nextProcess, elements.count <= capacity,
              nextWindows.count <= windowCapacity,
              nativeSameSet(nextWindows, nextWindows, equal: equal) else {
            invalidate(); return nil
        }
        if process != nextProcess || !nativeSameSet(windows, nextWindows, equal: equal) ||
            observedAt == nil || now < observedAt! || now - observedAt! > maximumGap {
            invalidate()
        }
        var next: [Int: [Entry]] = [:]
        for element in elements {
            let bucket = hash(element)
            guard !(next[bucket] ?? []).contains(where: { equal($0.element, element) }) else {
                invalidate(); return nil
            }
            let matches = (entries[bucket] ?? []).filter { equal($0.element, element) }
            guard matches.count <= 1 else { invalidate(); return nil }
            let identity = matches.first?.identity ?? UUID().uuidString.lowercased()
            next[bucket, default: []].append(Entry(element: element, identity: identity))
        }
        entries = next; windows = nextWindows; process = nextProcess; observedAt = now
        if generation == nil { generation = UUID().uuidString.lowercased() }
        return generation
    }

    func identity(for element: Element) -> String? {
        let matches = (entries[hash(element)] ?? []).filter { equal($0.element, element) }
        return matches.count == 1 ? matches[0].identity : nil
    }
}

/// Fresh references own action lookup. Observation identities are deliberately
/// absent from this type; even a retained valid AX proxy can name a retired UI.
enum NativeMembershipResult: Equatable { case current, stale, unverifiable }

final class NativeSnapshotReferences<Element> {
    private(set) var elements: [String: Element] = [:]
    private var paths: [String: [Element]] = [:]
    private var process: NativeProcessStamp?
    private let equal: (Element, Element) -> Bool
    private let capacity: Int

    init(capacity: Int = 2000,
         equal: @escaping (Element, Element) -> Bool) {
        self.capacity = capacity; self.equal = equal
    }

    subscript(reference: String) -> Element? { elements[reference] }
    var retainedPathCount: Int { paths.values.reduce(0) { $0 + $1.count } }

    func invalidate() {
        elements.removeAll(); paths.removeAll(); process = nil
    }

    func replace(_ values: [String: Element], paths: [String: [Element]],
                 process: NativeProcessStamp?) {
        invalidate()
        guard values.count <= capacity, Set(values.keys) == Set(paths.keys),
              values.allSatisfy({ key, element in
                  guard let path = paths[key], !path.isEmpty, path.count <= 31 else { return false }
                  return equal(path.last!, element) && nativeSameSet(path, path, equal: equal)
              }) else { return }
        self.elements = values; self.paths = paths; self.process = process
    }

    func validate(_ reference: String, process: NativeProcessStamp?, root: Element,
                  processAfterValidation: (() -> NativeProcessStamp?)? = nil,
                  children: (Element) throws -> [Element]) -> NativeMembershipResult {
        guard elements[reference] != nil, let path = paths[reference], let first = path.first else { return .stale }
        guard let process, self.process != nil else { return .unverifiable }
        guard process == self.process, equal(root, first) else { return .stale }
        do {
            // Re-read every observed edge. Completeness of unrelated branches
            // is irrelevant; unsupported children on the target leaf are never
            // queried. A retired window/control fails its edge from the root.
            for (parent, child) in zip(path, path.dropFirst()) {
                let current = try children(parent)
                guard current.count <= capacity else { return .unverifiable }
                let count = current.filter { equal(child, $0) }.count
                if count == 0 { return .stale }
                if count != 1 { return .unverifiable }
            }
            // Narrow process exit/reuse while reading edges. AX validation and
            // dispatch still cannot form an atomic OS operation.
            if let processAfterValidation, processAfterValidation() != process { return .stale }
            return .current
        } catch { return .unverifiable }
    }
}

/// Bounded traversal reports missing children, depth and count limits rather
/// than turning failed reads into empty, identity-preserving trees.
struct NativeTreeRead<Element> {
    let elements: [(element: Element, depth: Int)]
    let incompleteReason: String?
    var complete: Bool { incompleteReason == nil }
}

func readNativeTree<Element>(root: Element, maxDepth: Int, limit: Int,
                             children: (Element) throws -> [Element]) -> NativeTreeRead<Element> {
    var output: [(element: Element, depth: Int)] = []
    var reason: String?
    func visit(_ element: Element, depth: Int) {
        guard output.count < limit else { reason = reason ?? "element_limit"; return }
        output.append((element, depth))
        do {
            let descendants = try children(element)
            guard depth < maxDepth || descendants.isEmpty else { reason = reason ?? "depth_limit"; return }
            for child in descendants {
                guard output.count < limit else { reason = reason ?? "element_limit"; break }
                visit(child, depth: depth + 1)
            }
        } catch { reason = reason ?? "native_read_failed" }
    }
    if limit > 0 && maxDepth >= 0 { visit(root, depth: 0) } else { reason = "invalid_limits" }
    return NativeTreeRead(elements: output, incompleteReason: reason)
}

struct NativeApplicationRead {
    let records: [ElementRecord]
    let process: NativeProcessStamp?
    let windows: [AXUIElement]
    let scopeComplete: Bool
    let scopeDiagnostics: [String: Any]
    let incompleteReason: String?
    var complete: Bool { scopeComplete && incompleteReason == nil }
}

func nativeChildrenValue(status: AXError, value: CFTypeRef?, unsupportedLeafIsEmpty: Bool) throws -> [AXUIElement] {
    if unsupportedLeafIsEmpty && (status == .noValue || status == .attributeUnsupported) { return [] }
    guard status == .success, let elements = value as? [AXUIElement] else {
        throw MacUIError.element("native_children_unavailable")
    }
    return elements
}

func nativeProcessStamp(_ app: NSRunningApplication) -> NativeProcessStamp? {
    guard !app.isTerminated else { return nil }
    return nativeKernelProcessStamp(app.processIdentifier)
}

/// Native AX window membership is compared as a set so window enumeration
/// reordering alone does not manufacture a new lifetime.
func readNativeApplication(_ app: NSRunningApplication, maxDepth: Int, limit: Int) -> NativeApplicationRead {
    let process = nativeProcessStamp(app)
    let root = AXUIElementCreateApplication(app.processIdentifier)
    func windows() -> (elements: [AXUIElement]?, diagnostics: [String: Any]) {
        var value: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(root, kAXWindowsAttribute as CFString, &value)
        var detail: [String: Any] = ["axStatus": status.rawValue]
        guard status == .success, let result = value as? [AXUIElement] else {
            detail["validation"] = status == .success ? "invalid_value" : "ax_error"
            return (nil, detail)
        }
        detail["count"] = result.count
        guard result.count <= 64 else { detail["validation"] = "capacity_exceeded"; return (nil, detail) }
        guard nativeSameSet(result, result, equal: { CFEqual($0, $1) }) else {
            detail["validation"] = "ambiguous_equality"; return (nil, detail)
        }
        detail["validation"] = "valid"
        return (result, detail)
    }
    let before = windows()
    var crossProcess = false
    let tree = readNativeTree(root: root, maxDepth: maxDepth, limit: limit) { element in
        var role: CFTypeRef?
        var pid: pid_t = 0
        guard AXUIElementGetPid(element, &pid) == .success, pid > 0,
              AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &role) == .success,
              let role = role as? String, !role.isEmpty else { throw MacUIError.element("native_role_unavailable") }
        if pid != app.processIdentifier { crossProcess = true }
        var raw: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &raw)
        return try nativeChildrenValue(status: status, value: raw, unsupportedLeafIsEmpty: true)
    }
    let records = tree.elements.enumerated().map { index, node in
        record(node.element, reference: index, depth: node.depth)
    }
    let after = windows()
    let afterProcess = nativeProcessStamp(app)
    let processCurrent = process != nil && afterProcess == process
    let scopeReason = nativeScopeIncompleteReason(processBefore: process, processAfter: afterProcess,
        windowsBefore: before.elements, windowsAfter: after.elements, equal: { CFEqual($0, $1) })
    let scopeComplete = scopeReason == nil
    let windowsUnchanged = before.elements != nil && after.elements != nil &&
        nativeSameSet(before.elements!, after.elements!, equal: { CFEqual($0, $1) })
    return NativeApplicationRead(records: records, process: processCurrent ? process : nil,
        windows: scopeComplete ? after.elements! : [], scopeComplete: scopeComplete,
        scopeDiagnostics: ["processStampSource": NativeProcessStamp.source,
            "processStampAvailableBefore": process != nil, "processStampAvailableAfter": afterProcess != nil,
            "processStampUnchanged": processCurrent, "windowsBefore": before.diagnostics,
            "windowsAfter": after.diagnostics, "windowSetUnchanged": windowsUnchanged],
        incompleteReason: tree.incompleteReason ?? scopeReason ??
            (crossProcess ? "cross_process_identity_unqualified" : nil))
}
