import Foundation
import SwiftUI

@MainActor
final class FixtureState: ObservableObject {
    @Published private(set) var count = 0

    private var stateURL: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("machine-control-swiftui-fixture/state.json")
    }

    init() {
        persist()
    }

    func increment() {
        count += 1
        persist()
    }

    func reset() {
        count = 0
        persist()
    }

    private func persist() {
        let payload: [String: Any] = [
            "framework": "SwiftUI",
            "count": count,
            "effect": count == 0 ? "reset" : "incremented",
        ]
        guard let data = try? JSONSerialization.data(
                withJSONObject: payload, options: [.sortedKeys]) else { return }
        do {
            try FileManager.default.createDirectory(
                at: stateURL.deletingLastPathComponent(),
                withIntermediateDirectories: true)
            try data.write(to: stateURL, options: .atomic)
        } catch {
            fputs("SwiftUI fixture state write failed: \(error)\n", stderr)
        }
    }
}

struct FixtureView: View {
    @ObservedObject var state: FixtureState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("SwiftUI semantic fixture")
                .font(.title2)
                .accessibilityIdentifier("swiftui-fixture.heading")
            Text("SwiftUI count: \(state.count)")
                .accessibilityIdentifier("swiftui-fixture.count")
            Button("Increment SwiftUI") {
                state.increment()
            }
            .accessibilityIdentifier("swiftui-fixture.increment")
            Button("Reset SwiftUI") {
                state.reset()
            }
            .accessibilityIdentifier("swiftui-fixture.reset")
        }
        .padding(28)
        .frame(width: 360, height: 220, alignment: .topLeading)
    }
}

@main
struct MachineControlSwiftUIFixture: App {
    @StateObject private var state = FixtureState()

    var body: some Scene {
        WindowGroup("Machine Control SwiftUI Fixture") {
            FixtureView(state: state)
        }
        .defaultSize(width: 360, height: 220)
    }
}
