import Foundation

/// Offline qualification fixture, not an AX identity implementation. The
/// independent object incarnation is deliberately unavailable to a hypothetical
/// remote provider. In particular, equalityToken models a reusable opaque token,
/// not a claim that AX does (or does not) reuse one.
final class NativeIdentityFixture {
    struct Scope: Equatable {
        var runtime = "runtime-1"
        var desktop = "desktop-1"
        var process = "process-incarnation-1"
        var window = "window-incarnation-1"
    }

    final class Element {
        let equalityToken: String
        let label: String
        private(set) var effects = 0

        init(_ token: String, label: String = "Same label") {
            equalityToken = token
            self.label = label
        }

        func press() { effects += 1 }
    }

    struct Observation {
        let scope: Scope
        let reference: String
        let element: Element

        func equalityCandidateMatches(_ other: Observation) -> Bool {
            scope == other.scope && element.equalityToken == other.element.equalityToken
        }

        func oracleMatches(_ other: Observation) -> Bool {
            scope == other.scope && element === other.element
        }
    }

    var scope = Scope()
    var elements: [Element]
    private var sequence = 0
    private var references: [String: Observation] = [:]

    init(_ elements: [Element]) { self.elements = elements }

    func observe() -> [Observation] {
        elements.map { element in
            sequence += 1
            let value = Observation(scope: scope, reference: "fixture-reference-\(sequence)", element: element)
            references[value.reference] = value
            return value
        }
    }

    /// Independent effect oracle pins the actual object and every scope. It
    /// never resolves an old reference by equality token, label or tree offset.
    @discardableResult
    func press(_ reference: String) -> Bool {
        guard let value = references[reference], value.scope == scope,
              elements.contains(where: { $0 === value.element }) else { return false }
        value.element.press()
        return true
    }
}
