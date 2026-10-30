import XCTest
import CoreGraphics
@testable import macui

final class InputAndUploadTests: XCTestCase {
    func testLiteralLineEndingsDeliverOneUnmodifiedReturn() throws {
        for character in Array("\n\r\r\n") {
            let events = try literalTextEvents(character)
            for event in [events.0, events.1] {
                XCTAssertEqual(event.getIntegerValueField(.keyboardEventKeycode), 36)
                XCTAssertEqual(event.flags.rawValue, 0)
                var units = [UniChar](repeating: 0, count: 4)
                var count = 0
                event.keyboardGetUnicodeString(maxStringLength: units.count,
                    actualStringLength: &count, unicodeString: &units)
                XCTAssertEqual(Array(units.prefix(count)), [13])
            }
        }
    }

    func testLiteralTextClearsInheritedShortcutsAndPreservesUnicode() throws {
        for character in Array("aAé👩‍💻") {
            let events = try literalTextEvents(character) { down in
                let event = CGEvent(keyboardEventSource:nil, virtualKey:0, keyDown:down)
                event?.flags = [.maskCommand, .maskAlternate, .maskControl, .maskShift, .maskAlphaShift]
                return event
            }
            for event in [events.0, events.1] {
                XCTAssertEqual(event.flags.rawValue, 0)
                var units = [UniChar](repeating:0, count:32)
                var count = 0
                event.keyboardGetUnicodeString(maxStringLength:units.count,
                    actualStringLength:&count, unicodeString:&units)
                XCTAssertEqual(Array(units.prefix(count)), Array(String(character).utf16))
            }
        }
    }

    func testKeyChordAcceptsPlusSeparators() {
        XCTAssertEqual(normalizedKeyChord("cmd+shift+g"), "cmd-shift-g")
        XCTAssertEqual(normalizedKeyChord("cmd-shift-g"), "cmd-shift-g")
        XCTAssertEqual(normalizedKeyChord("+"), "+")
        XCTAssertEqual(normalizedKeyChord("shift++"), "shift-+")
        XCTAssertEqual(normalizedKeyChord("return"), "return")
    }

    func testUploadFilesMustBeNamedReadableRegularFiles() throws {
        let home = FileManager.default.temporaryDirectory
            .appendingPathComponent("mc-upload-\(UUID().uuidString)")
        let hidden = home.appendingPathComponent(".ssh")
        let library = home.appendingPathComponent("Library")
        let documents = home.appendingPathComponent("Documents")
        for directory in [hidden, library, documents] {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        }
        defer { try? FileManager.default.removeItem(at: home) }
        let good = documents.appendingPathComponent("shot.png")
        let secret = hidden.appendingPathComponent("id_ed25519")
        let cache = library.appendingPathComponent("cache.db")
        for file in [good, secret, cache] {
            FileManager.default.createFile(atPath: file.path, contents: Data("x".utf8))
        }
        let link = documents.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: secret)

        func check(_ files: Any?) -> String? {
            switch validatedUploadFiles(files, home: home.path) {
            case .success: return nil
            case let .failure(refusal): return refusal.code
            }
        }
        XCTAssertNil(check([good.path]))
        XCTAssertEqual(try validatedUploadFiles([good.path], home: home.path).get(),
                       [(good.path as NSString).resolvingSymlinksInPath])
        XCTAssertEqual(check([secret.path]), "upload_path_not_permitted")
        XCTAssertEqual(check([cache.path]), "upload_path_not_permitted")
        XCTAssertEqual(check([link.path]), "upload_path_not_permitted")
        XCTAssertEqual(check([documents.path]), "upload_file_unavailable")
        XCTAssertEqual(check(["relative.png"]), "invalid_request")
        XCTAssertEqual(check([]), "invalid_request")
        XCTAssertEqual(check(nil), "invalid_request")
    }
}
