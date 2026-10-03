import Darwin
import XCTest
@testable import macui

final class HelperUpdateTests: XCTestCase {
    private let installation: [String:Any] = ["version":2, "management":"service_managed", "profile":"locked_use", "enabled":true]
    private let helper: [String:Any] = ["installation":"healthy", "profile":"locked_use", "policy":"enabled",
        "callerEligibility":"denied", "coveredSession":false, "lockedUsePaused":false]
    private var console: [String:Any] { ["desktopState":"unlocked", "uid":getuid(), "uuid":"console", "boot":123] }

    private func eligible(approved: Bool = true, prepared: Bool = true,
                          installation: [String:Any]? = nil, helper: [String:Any]? = nil,
                          console: [String:Any]? = nil) -> Bool {
        HelperUpdatePolicy.eligible(approved:approved, capturePrepared:prepared,
            installation:installation ?? self.installation, helper:helper ?? self.helper, console:console ?? self.console)
    }

    func testApprovedInstalledUpdateIsEligible() { XCTAssertTrue(eligible()) }

    func testSameBuildLaunchDoesNotRepair() {
        var helper = self.helper; helper["callerEligibility"] = "allowed"
        XCTAssertFalse(eligible(helper:helper))
    }

    func testInitialSetupAndMissingOSApprovalCannotBeAutomatic() {
        XCTAssertFalse(eligible(approved:false))
        XCTAssertFalse(eligible(prepared:false))
        XCTAssertFalse(HelperUpdatePolicy.eligible(approved:true, capturePrepared:true,
            installation:nil, helper:helper, console:console))
    }

    func testLegacyDisabledAndApplianceInstallationsCannotBeRefreshed() {
        for (key,value) in [("management","legacy" as Any), ("profile","appliance"), ("enabled",false), ("version",1)] {
            var installation = self.installation; installation[key] = value
            XCTAssertFalse(eligible(installation:installation))
        }
    }

    func testActivePausedOrUnhealthyHelperCannotBeRestarted() {
        for (key,value) in [("coveredSession",true as Any), ("lockedUsePaused",true),
                            ("installation","inconsistent"), ("profile","appliance"), ("policy","disabled")] {
            var helper = self.helper; helper[key] = value
            XCTAssertFalse(eligible(helper:helper))
        }
    }

    func testUnknownHelperStateDoesNotAuthorizeMaintenance() {
        for key in helper.keys {
            var helper = self.helper; helper.removeValue(forKey:key)
            XCTAssertFalse(eligible(helper:helper))
        }
    }

    func testLockedUnknownAndOtherUserConsoleCannotTriggerMaintenance() {
        for state in ["locked", "unknown", "no_session"] {
            var console = self.console; console["desktopState"] = state
            XCTAssertFalse(eligible(console:console))
        }
        var otherUser = console; otherUser["uid"] = getuid() + 1
        XCTAssertFalse(eligible(console:otherUser))
        XCTAssertFalse(eligible(console:[:]))
    }
}
