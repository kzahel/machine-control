import XCTest
@testable import macui

final class PackageTests: XCTestCase {
    func testEncodesJSONLine() throws {
        let line = try encodeJSONLine(["b": 1, "a": "x"])
        XCTAssertEqual(String(decoding: line, as: UTF8.self), "{\"a\":\"x\",\"b\":1}\n")
    }
}
