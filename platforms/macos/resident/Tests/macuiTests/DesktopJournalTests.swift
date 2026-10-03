import Foundation
import XCTest
@testable import macui

final class DesktopJournalTests: XCTestCase {
    func temporary() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        return root.appendingPathComponent("logs")
    }
    func testPersistencePrivacyAndInterruptedIntent() throws {
        let root = try temporary()
        let journal = DesktopJournal(root: root)
        XCTAssertTrue(journal.begin(["operation": "input.text", "requestId": "SENTINEL", "text": "SENTINEL"]))
        let restarted = DesktopJournal(root: root)
        let rows = restarted.query()["entries"] as! [[String: Any]]
        XCTAssertTrue(rows.contains { $0["phase"] as? String == "intent" && $0["effect"] as? String == "unknown" })
        let preview = try JSONSerialization.data(withJSONObject: restarted.preview())
        XCTAssertFalse(String(decoding: preview, as: UTF8.self).contains("SENTINEL"))
        let path = try restarted.export()
        XCTAssertFalse(try String(contentsOfFile: path).contains("SENTINEL"))
        XCTAssertEqual((try FileManager.default.attributesOfItem(atPath: path)[.posixPermissions] as! NSNumber).intValue, 0o600)
    }
    func testUnavailableStorageAndSymlinkRefusal() throws {
        let root = try temporary()
        try Data().write(to: root)
        let journal = DesktopJournal(root: root)
        XCTAssertFalse(journal.begin(["operation": "input.click"]))
        XCTAssertEqual(journal.errorCode, "audit_storage_unavailable")
        try FileManager.default.removeItem(at: root)
        XCTAssertTrue(journal.event("storage.recovered"))
        let bad = root.deletingLastPathComponent().appendingPathComponent("redirect")
        try FileManager.default.createSymbolicLink(at: bad, withDestinationURL: root)
        XCTAssertFalse(DesktopJournal(root: bad).health["available"] as! Bool)
    }
    func testPagesFiltersAndAgeRetention() throws {
        let root = try temporary()
        let journal = DesktopJournal(root: root)
        for i in 0..<60 {
            XCTAssertTrue(journal.record(["operation": "input.key", "requestId": String(i), "accepted": i % 2 == 0]))
        }
        let first = journal.query(operation: "input.key")
        let second = journal.query(offset: 50, operation: "input.key")
        XCTAssertEqual((first["entries"] as! [[String: Any]]).count, 50)
        XCTAssertTrue(first["hasMore"] as! Bool)
        XCTAssertEqual((second["entries"] as! [[String: Any]]).count, 10)
        XCTAssertFalse(second["hasMore"] as! Bool)
        XCTAssertEqual((journal.query(operation: "input.key", outcome: "accepted")["entries"] as! [[String: Any]]).count, 30)
        let old = root.appendingPathComponent("audit/00000000000000000000-expired.jsonl")
        try Data("{}\n".utf8).write(to: old)
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSinceNow: -31 * 86400)], ofItemAtPath: old.path)
        journal.event("storage.recovered")
        XCTAssertFalse(FileManager.default.fileExists(atPath: old.path))
    }
    func testRetentionAndPartialRecord() throws {
        let root = try temporary()
        let journal = DesktopJournal(root: root, segmentBytes: 1000, auditBytes: 5000)
        for _ in 0..<100 { XCTAssertTrue(journal.begin(["operation": "input.key"])) }
        let urls = try FileManager.default.contentsOfDirectory(at: root.appendingPathComponent("audit"), includingPropertiesForKeys: nil)
        let bytes = try urls.reduce(0) { $0 + (try FileManager.default.attributesOfItem(atPath: $1.path)[.size] as! NSNumber).intValue }
        XCTAssertLessThanOrEqual(bytes, 5000)
        let handle = try FileHandle(forWritingTo: urls.sorted { $0.path < $1.path }.last!)
        try handle.seekToEnd(); try handle.write(contentsOf: Data("{}\n42\n{partial".utf8)); try handle.close()
        _ = journal.query()
        XCTAssertTrue(journal.historyGap)
        try Data("42\n".utf8).write(to: root.appendingPathComponent("audit/00000000000000000000-invalid.jsonl"))
        XCTAssertTrue(journal.query()["earliestAt"] is NSNull)
    }
}
