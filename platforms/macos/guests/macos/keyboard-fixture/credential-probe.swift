// Test-only sender links the production resolver/emitter, uses a fixed public
// dummy, and refuses any application other than the frontmost keyboard fixture.
import AppKit
import CoreGraphics

enum MacUIError: Error { case action(String), usage(String) }
func normalizedKeyChord(_ chord: String) -> String { chord.replacingOccurrences(of:"+",with:"-") }
@main struct CredentialProbe {
    static func main() throws {
        guard CommandLine.arguments.count == 2,
              ["session","pid"].contains(CommandLine.arguments[1]),
              let app = NSWorkspace.shared.frontmostApplication,
              app.bundleIdentifier == "org.machine-control.keyboard-fixture" else {
            throw MacUIError.action("keyboard_fixture_not_frontmost")
        }
        let layout = try KeyboardLayoutSnapshot.current()
        try credentialLayoutPreflight(layout)
        let dummy = Data("Fake2Pass!@#[]{}+-_=;:'\",.<>/?\\|`~".utf8)
        let plan = try credentialKeyboardPlan(dummy,layout:layout)
        for key in plan {
            try layout.verifyCurrent()
            guard NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier else {
                throw MacUIError.action("keyboard_fixture_lost_focus")
            }
            try postKeyboardKey(key,processID:CommandLine.arguments[1] == "pid" ? app.processIdentifier : nil)
            usleep(18_000)
        }
        usleep(300_000)
        print("{\"dummyDispatched\":true}")
    }
}
