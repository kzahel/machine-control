import XCTest
import CoreGraphics
@testable import macui

final class KeyboardInputTests: XCTestCase {
    func testCurrentLayoutFromProviderWorker() {
        let completed = expectation(description: "Worker copied the current keyboard layout")
        DispatchQueue(label: "machine-control.keyboard-regression").async {
            defer { completed.fulfill() }
            XCTAssertFalse(Thread.isMainThread)
            do {
                // Use real HIToolbox properties: a synthetic translation table
                // cannot detect its dispatch assertion in dialog.choose.
                let snapshot = try KeyboardLayoutSnapshot.current()
                XCTAssertFalse(snapshot.id.isEmpty)
                XCTAssertFalse(snapshot.inputSourceID.isEmpty)
                XCTAssertEqual(try resolveKeyboardChord("cmd-shift-g", layout: snapshot).flags,
                               [.maskCommand, .maskShift])
                XCTAssertNoThrow(try snapshot.verifyCurrent())
            } catch {
                XCTFail("Worker layout lookup failed: \(error)")
            }
        }
        wait(for: [completed], timeout: 10)
    }

    private func layout(_ table: [UInt16: [UInt64: String]]) -> KeyboardLayoutSnapshot {
        KeyboardLayoutSnapshot(id: "fixture", inputSourceID: "fixture", keyboardType: 0) { code, flags in
            table[code]?[flags.rawValue]
        }
    }
    func testDvorakAndCommandSpecificLayoutResolution() throws {
        let command = CGEventFlags.maskCommand.rawValue
        let shiftCommand = CGEventFlags([.maskShift, .maskCommand]).rawValue
        // Dvorak uses physical P for l; hybrid switches to physical L for Cmd.
        let dvorak = layout([35: [0:"l",command:"l",shiftCommand:"L"],37:[0:"n",command:"n"]])
        XCTAssertEqual(try resolveKeyboardChord("cmd+l", layout:dvorak).code, 35)
        let hybrid = layout([35:[0:"l",command:"p"],37:[0:"n",command:"l",shiftCommand:"L"]])
        let resolved = try resolveKeyboardChord("cmd+shift+l", layout:hybrid)
        XCTAssertEqual(resolved.code, 37)
        XCTAssertEqual(resolved.flags, [.maskCommand, .maskShift])
    }
    func testPunctuationSeparatorsAndNamedKeys() throws {
        let l = layout([27:[0:"-",CGEventFlags.maskCommand.rawValue:"-"],24:[0:"=",CGEventFlags.maskShift.rawValue:"+"],
                        44:[0:"/",CGEventFlags.maskShift.rawValue:"?"]])
        XCTAssertEqual(try resolveKeyboardChord("-",layout:l).code,27)
        XCTAssertEqual(try resolveKeyboardChord("cmd--",layout:l).code,27)
        XCTAssertEqual(try resolveKeyboardChord("shift++",layout:l).code,24)
        XCTAssertEqual(try resolveKeyboardChord("?",layout:l).flags,.maskShift)
        XCTAssertEqual(try resolveKeyboardChord("ctrl+left",layout:l).code,123)
        XCTAssertEqual(try resolveKeyboardChord("f12",layout:l).code,111)
        XCTAssertThrowsError(try resolveKeyboardChord("bogus+a",layout:l))
        XCTAssertThrowsError(try resolveKeyboardChord("ab",layout:l))
    }
    func testCredentialRejectsWholePlanWithoutDeadKeysOrFallback() throws {
        let l = layout([0:[0:"a"],1:[0:"b"],2:[CGEventFlags.maskAlternate.rawValue:"@"]])
        XCTAssertEqual(try credentialKeyboardPlan(Data("ab@".utf8),layout:l).map(\.code),[0,1,2])
        XCTAssertThrowsError(try credentialKeyboardPlan(Data("ab!".utf8),layout:l))
        XCTAssertThrowsError(try credentialKeyboardPlan(Data("é".utf8),layout:l))
        XCTAssertThrowsError(try credentialLayoutPreflight(l))
        XCTAssertThrowsError(try credentialKeyboardPlan(Data(),layout:l))
    }
    func testCredentialPreflightRequiresEverySupportedByte() throws {
        let codes = (CGKeyCode(0)..<128).filter { !KeyboardLayoutSnapshot.nonCharacterCodes.contains($0) }
        let bytes = Array(UInt8(32)...126)
        let table = Dictionary(uniqueKeysWithValues: zip(codes, bytes).map { ($0.0, [UInt64(0): String(UnicodeScalar($0.1))]) })
        let complete = layout(table)
        XCTAssertNoThrow(try credentialLayoutPreflight(complete))
        var missing = table
        missing.removeValue(forKey: codes[60])
        XCTAssertThrowsError(try credentialLayoutPreflight(layout(missing)))
    }
    func testLayoutChangeRefusesRatherThanRetargeting() throws {
        XCTAssertThrowsError(try layout([:]).verifyCurrent()) { error in
            XCTAssertEqual(error as? KeyboardInputError, .layoutChanged)
        }
    }
    func testInputMethodCannotMasqueradeAsUnderlyingASCIILayout() throws {
        let inputMethod = KeyboardLayoutSnapshot(id:"fixture", inputSourceID:"fixture-ime", keyboardType:0) { _, _ in "a" }
        XCTAssertThrowsError(try credentialLayoutPreflight(inputMethod))
        XCTAssertThrowsError(try credentialKeyboardPlan(Data("a".utf8), layout:inputMethod))
        XCTAssertThrowsError(try resolveKeyboardChord("a", layout:inputMethod))
        XCTAssertEqual(try resolveKeyboardChord("return", layout:inputMethod).code,36)
    }
    func testKeyboardEventsHaveExplicitFlagsAndRealKeyCodes() throws {
        let key = ResolvedKeyboardKey(code:35,flags:[.maskCommand,.maskShift],layoutID:"fixture",fallback:false)
        let events = try keyboardEvents(key,source:privateInputSource())
        for event in [events.0, events.1] {
            XCTAssertEqual(event.flags,key.flags)
            XCTAssertEqual(event.getIntegerValueField(.keyboardEventKeycode),35)

        }
    }
    func testCancellationPreventsEveryEvent() throws {
        let key = ResolvedKeyboardKey(code:0,flags:.maskCommand,layoutID:"fixture",fallback:false)
        XCTAssertThrowsError(try postKeyboardKey(key,cancellation:{ "fixture_cancelled" }))
    }
}
