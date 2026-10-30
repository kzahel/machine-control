import XCTest
@testable import macui

final class CoverConcealmentTests: XCTestCase {
    func testUnpaintedHiddenTranslucentOrIncompleteSurfaceRefuses() {
        func healthy(_ visible: Bool = true, _ window: Double = 1, _ content: Double = 1,
                     _ shown: Bool = true, _ fills: Bool = true, _ painted: Bool = true) -> Bool {
            coverConcealmentHealthy(visible:visible,windowAlpha:window,contentAlpha:content,
                contentVisible:shown,fillsFrame:fills,painted:painted)
        }
        XCTAssertTrue(healthy())
        XCTAssertFalse(healthy(false))
        XCTAssertFalse(healthy(true,0.999))
        XCTAssertFalse(healthy(true,1,0.999))
        XCTAssertFalse(healthy(true,1,1,false))
        XCTAssertFalse(healthy(true,1,1,true,false))
        XCTAssertFalse(healthy(true,1,1,true,true,false))
        XCTAssertFalse(healthy(true,.nan))
    }
}
