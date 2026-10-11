import AppKit
import Foundation

/// One owner of resident construction and lifecycle, independent of the shell.
/// The serial coordinator stays on main for short state/UI transitions;
/// dependency observations execute in bounded workers.
final class ResidentRuntime {
    let server: ResidentServer
    let approver = DesktopApprover()
    private(set) var running = false
    private var stopped = false
    var updating = false
    var stopShortcutAvailable: () -> Bool = { false }

    init(socketPath: String, policy: DeploymentPolicy = .load(),
         journal: DesktopJournal? = DesktopJournal(), service: ResidentService = ResidentService()) throws {
        // Do not let a second shell unlink the authoritative resident endpoint.
        let existing = try residentSocket()
        defer { Darwin.close(existing) }
        var (address, length) = try unixAddress(socketPath)
        if withSockAddr(&address, length:length, { Darwin.connect(existing, $0, $1) }) == 0 {
            throw MacUIError.action("Another Machine Control resident is already running")
        }
        try FileManager.default.createDirectory(atPath:(socketPath as NSString).deletingLastPathComponent,
            withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
        let broker = GrantBroker(policy:policy)
        broker.journal = journal
        if policy.grantMode == .approval { attachOperatorConsent(broker, socketPath:socketPath) }
        server = ResidentServer(socketPath:socketPath, service:service, broker:broker)
        if policy.grantMode == .approval { server.approver = approver }
        server.activity.respectRecentActivity = UserDefaults.standard.string(forKey:"machineControl.admissionPolicy") != "announce"
        let notice = UserDefaults.standard.integer(forKey:"machineControl.admissionNoticeSeconds")
        server.noticeSeconds = (5...60).contains(notice) ? Double(notice) : 10
    }

    func start() throws {
        guard !stopped else { throw MacUIError.action("A stopped runtime must be relaunched") }
        guard !running else { return }
        try server.start()
        server.devtools.start()
        server.notice = AdmissionNotice(server:server)
        if server.broker.policy.grantMode == .approval { server.activity.enable() }
        running = true
    }
    func stopAccess() {
        if let pending = approver.request {
            try? approver.decide(id:pending.id, scopes:[], duration:0, allow:false)
        }
        server.revoke(reason:"stopped_by_person")
    }
    func stop() {
        guard running else { return }
        server.revoke(reason:"resident_stopping")
        server.stop(); running = false; stopped = true
    }
}
