import Foundation
import Darwin
import XCTest
@testable import macui

final class DesktopCrashDiagnosticsTests: XCTestCase {
    func directory() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:root, withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
        addTeardownBlock { try? FileManager.default.removeItem(at:root) }
        return root
    }
    func report(_ root: URL, _ name: String = "macui-2026-10-24-120000.ips", bundle: String = "org.machine-control.app", text: String = "PRIVATE OS REPORT") throws -> URL {
        let path = root.appendingPathComponent(name)
        let header = try JSONSerialization.data(withJSONObject:["bundleID":bundle])
        let body = try JSONSerialization.data(withJSONObject:["bundleInfo":["CFBundleIdentifier":bundle], "detail":text])
        try (header + Data([10]) + body).write(to:path)
        return path
    }
    func testUncleanRestartHasBoundedUnfinishedOperationAndBuildIdentity() throws {
        let root = try directory().appendingPathComponent("logs")
        let first = DesktopJournal(root:root)
        first.startRuntime(instance:"fixture-socket")
        XCTAssertTrue(first.begin(["operation":"input.text", "requestId":"private", "text":"SENTINEL"]))
        XCTAssertTrue(first.record(["operation":"input.text", "requestId":"private", "accepted":true]))
        XCTAssertTrue(first.begin(["operation":"dialog.choose", "requestId":"private", "path":"SENTINEL"]))
        let second = DesktopJournal(root:root)
        second.startRuntime(instance:"fixture-socket")
        let rows = second.query()["entries"] as! [[String:Any]]
        let exit = try XCTUnwrap(rows.first { $0["operation"] as? String == "resident.previous_exit_unclean" })
        XCTAssertEqual(exit["unfinishedOperations"] as? [String], ["dialog.choose"])
        XCTAssertNotNil((exit["build"] as? [String:Any])?["executableUUID"])
        XCTAssertFalse(String(decoding:try JSONSerialization.data(withJSONObject:second.preview()),as:UTF8.self).contains("SENTINEL"))
        XCTAssertTrue(second.health["previousExitUnclean"] as! Bool)
        // A retiring instance must not remove the replacement marker.
        first.finishRuntime()
        let third = DesktopJournal(root:root); third.startRuntime(instance:"fixture-socket")
        XCTAssertTrue(third.health["previousExitUnclean"] as! Bool)
        third.finishRuntime()
        let clean = DesktopJournal(root:root); clean.startRuntime(instance:"fixture-socket")
        XCTAssertFalse(clean.health["previousExitUnclean"] as! Bool)
        clean.finishRuntime()
    }
    func testInstancesDoNotReportEachOthersExitAndUnsafeMarkerDoesNotBlockAudit() throws {
        let root = try directory().appendingPathComponent("logs")
        let first = DesktopJournal(root:root); first.startRuntime(instance:"first")
        let second = DesktopJournal(root:root); second.startRuntime(instance:"second")
        XCTAssertFalse(second.health["previousExitUnclean"] as! Bool)
        let victim = try directory().appendingPathComponent("victim")
        try Data("SENTINEL".utf8).write(to:victim)
        let marker = DesktopExitMarker(root:root,instance:"unsafe",runtime:UUID().uuidString)
        try FileManager.default.createSymbolicLink(at:marker.path,withDestinationURL:victim)
        let unsafe = DesktopJournal(root:root); unsafe.startRuntime(instance:"unsafe")
        XCTAssertFalse(unsafe.health["unexpectedExitTrackingAvailable"] as! Bool)
        XCTAssertTrue(unsafe.begin(["operation":"input.click"]))
        XCTAssertEqual(try String(contentsOf:victim),"SENTINEL")
        first.finishRuntime(); second.finishRuntime()
    }
    func testMarkerContentionFailsWithoutWaitingOrChangingOwner() throws {
        let root = try directory().appendingPathComponent("logs")
        let first = DesktopJournal(root:root); first.startRuntime(instance:"shared")
        let marker = DesktopExitMarker(root:root,instance:"shared",runtime:UUID().uuidString)
        let before = try Data(contentsOf:marker.path)
        let lock = marker.path.deletingPathExtension().appendingPathExtension("lock")
        let fd = open(lock.path,O_RDWR | O_NOFOLLOW)
        XCTAssertGreaterThanOrEqual(fd,0)
        defer { Darwin.close(fd) }
        XCTAssertEqual(flock(fd,LOCK_EX | LOCK_NB),0)
        let contended = DesktopJournal(root:root)
        contended.startRuntime(instance:"shared")
        XCTAssertFalse(contended.health["unexpectedExitTrackingAvailable"] as! Bool)
        XCTAssertTrue(contended.begin(["operation":"input.click"]))
        first.finishRuntime()
        XCTAssertEqual(try Data(contentsOf:marker.path),before)
        XCTAssertEqual(flock(fd,LOCK_UN),0)
        let replacement = DesktopJournal(root:root); replacement.startRuntime(instance:"shared")
        let current = try Data(contentsOf:marker.path)
        first.finishRuntime()
        XCTAssertEqual(try Data(contentsOf:marker.path),current)
        replacement.finishRuntime()
    }
    func testCrashReportsRequireExplicitPreviewAndExportExactlyReviewedBytes() throws {
        let root = try directory(), reports = try directory()
        let source = try report(reports)
        let journal = DesktopJournal(root:root.appendingPathComponent("logs"))
        journal.crashReports.directory = reports
        XCTAssertNil(journal.preview()["osCrashReports"])
        XCTAssertFalse(try String(contentsOfFile:journal.export()).contains("PRIVATE OS REPORT"))
        let preview = journal.previewWithCrashReports()
        let content = preview["preview"] as! [String:Any]
        XCTAssertEqual((content["osCrashReports"] as! [[String:Any]]).count,1)
        try Data("CHANGED AFTER REVIEW".utf8).write(to:source)
        let path = try journal.exportCrashPreview(id:preview["previewId"] as! String)
        let saved = try String(contentsOfFile:path)
        XCTAssertTrue(saved.contains("PRIVATE OS REPORT"))
        XCTAssertFalse(saved.contains("CHANGED AFTER REVIEW"))
        XCTAssertThrowsError(try journal.exportCrashPreview(id:preview["previewId"] as! String))
        XCTAssertEqual((try FileManager.default.attributesOfItem(atPath:path)[.posixPermissions] as! NSNumber).intValue,0o600)
    }
    func testCrashCatalogRejectsOtherAppsLinksOversizeAndExpiredPreviews() throws {
        let reports = try directory(), root = try directory()
        let valid = try report(reports)
        _ = try report(reports,"macui-other.ips",bundle:"org.example.unrelated")
        try FileManager.default.createSymbolicLink(at:reports.appendingPathComponent("macui-link.ips"),withDestinationURL:valid)
        try FileManager.default.linkItem(at:valid,to:reports.appendingPathComponent("macui-hardlink.ips"))
        XCTAssertTrue(DesktopCrashReports(directory:reports).read().isEmpty)
        try FileManager.default.removeItem(at:reports.appendingPathComponent("macui-hardlink.ips"))
        let large = reports.appendingPathComponent("macui-large.ips")
        try Data(repeating:65,count:2_097_153).write(to:large)
        XCTAssertEqual(DesktopCrashReports(directory:reports).read().count,1)
        // Long-lived app processes apply the cutoff when previewing, rather
        // than keeping the date at which the resident first started.
        let future = DesktopCrashReports(directory:reports, now:{ Date(timeIntervalSinceNow:31*86400) })
        XCTAssertTrue(future.read().isEmpty)
        let journal = DesktopJournal(root:root.appendingPathComponent("logs"))
        journal.crashReports.directory = reports
        var clock = 100.0; journal.previewClock = { clock }
        let preview = journal.previewWithCrashReports(); clock += 301
        XCTAssertThrowsError(try journal.exportCrashPreview(id:preview["previewId"] as! String))
        let fresh = journal.previewWithCrashReports(); journal.cancelCrashPreview()
        XCTAssertThrowsError(try journal.exportCrashPreview(id:fresh["previewId"] as! String))
    }
    func testDiagnosticRetentionKeepsPreviousWeeksWithinThirtyDayCap() throws {
        let root = try directory().appendingPathComponent("logs"), journal = DesktopJournal(root:root)
        journal.diagnostic("fixture",code:"failure")
        let dir = root.appendingPathComponent("diagnostics")
        for days in [8,31] {
            let path = dir.appendingPathComponent("0000000000000000000\(days).jsonl")
            try Data("{}\n".utf8).write(to:path)
            try FileManager.default.setAttributes([.modificationDate:Date(timeIntervalSinceNow:Double(-days*86400))],ofItemAtPath:path.path)
        }
        journal.diagnostic("fixture",code:"failure")
        XCTAssertTrue(FileManager.default.fileExists(atPath:dir.appendingPathComponent("00000000000000000008.jsonl").path))
        XCTAssertFalse(FileManager.default.fileExists(atPath:dir.appendingPathComponent("000000000000000000031.jsonl").path))
        XCTAssertEqual(journal.health["diagnosticDays"] as? Int,30)
        XCTAssertNotNil(DesktopBuildIdentity.imageUUID(0))
    }
}
