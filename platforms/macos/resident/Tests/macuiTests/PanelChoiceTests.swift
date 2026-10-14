import XCTest
@testable import macui

final class PanelChoiceTests: XCTestCase {
    private var root: URL!
    private let chooser = PanelChooser(sendKey: { _ in }, typeText: { _ in })

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("mc-panel-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("folder"),
                                                withIntermediateDirectories: true)
        try Data("x".utf8).write(to: root.appendingPathComponent("folder/file.txt"))
    }
    override func tearDownWithError() throws { try FileManager.default.removeItem(at: root) }

    private func refusal(_ path: String, _ kind: String) -> String? {
        do { _ = try chooser.resolve(path, kind: kind); return nil }
        catch let refusal as PanelChoiceRefusal { return refusal.code }
        catch { return "unexpected" }
    }

    func testOpenTargetsAFolderOrSelectsAFileInItsFolder() throws {
        let folder = try chooser.resolve(root.appendingPathComponent("folder").path, kind: "open")
        XCTAssertEqual(folder.folder.lastPathComponent, "folder")
        XCTAssertNil(folder.name)
        let file = try chooser.resolve(root.appendingPathComponent("folder/./file.txt").path, kind: "open")
        XCTAssertEqual(file.destination, root.appendingPathComponent("folder/file.txt").standardizedFileURL.path)
        XCTAssertEqual(file.folder.lastPathComponent, "folder")
    }

    func testOpenSelectsAPackageInItsFolder() throws {
        let package = root.appendingPathComponent("folder/Example.app")
        try FileManager.default.createDirectory(at: package.appendingPathComponent("Contents"),
                                                withIntermediateDirectories: true)
        let target = try chooser.resolve(package.path, kind: "open")
        XCTAssertEqual(target.folder.lastPathComponent, "folder")
        XCTAssertEqual(target.destination, package.standardizedFileURL.path)
    }

    func testSaveNavigatesToTheFolderAndNamesTheFile() throws {
        let target = try chooser.resolve(root.appendingPathComponent("folder/new.txt").path, kind: "save")
        XCTAssertEqual(target.destination, root.appendingPathComponent("folder").standardizedFileURL.path)
        XCTAssertEqual(target.name, "new.txt")
        XCTAssertEqual(try chooser.resolve("~/new.txt", kind: "save").folder.path,
                       FileManager.default.homeDirectoryForCurrentUser.standardizedFileURL.path)
    }

    func testRefusesBeforeTouchingThePanel() {
        XCTAssertEqual(refusal("relative/path", "open"), "invalid_request")
        XCTAssertEqual(refusal(root.appendingPathComponent("missing").path, "open"), "path_not_found")
        XCTAssertEqual(refusal(root.appendingPathComponent("folder").path, "save"), "invalid_request")
        XCTAssertEqual(refusal(root.appendingPathComponent("missing/new.txt").path, "save"), "path_not_found")
    }
}
