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
    private let presentationStore: PresentationStore
    private let presentationObservation: BackgroundObservation<PresentationPreference>
    private var presentationTimer: DispatchSourceTimer?
    private let presentationWriter = DispatchQueue(label:"machine-control.presentation-write", qos:.utility)
    private(set) var presentationWriteInFlight = false
    private var presentationOverride: PresentationProfile?
    private(set) var presentation: PresentationPreference
    var presentationJSON: [String:Any] {
        var value = presentation.json
        func webviews(_ view: NSView) -> Int {
            (NSClassFromString("WKWebView").map { view.isKind(of:$0) } == true ? 1 : 0) + view.subviews.reduce(0) { $0 + webviews($1) }
        }
        value["settingsWebViews"] = NSApp?.windows.reduce(0) { $0 + ($1.contentView.map(webviews) ?? 0) } ?? 0
        value["setting"] = presentationWriteInFlight
        value["temporaryOverride"] = presentationOverride != nil
        return value
    }
    var updating = false
    let operatorDependency = OperatorDependency()
    // A typed test seam; never exposed through launch arguments or IPC.
    var resumeHelper: (([String:Any], @escaping () -> String?) throws -> Void)
    var stopShortcutAvailable: () -> Bool = { false }

    init(socketPath: String, policy: DeploymentPolicy = .load(),
         journal: DesktopJournal? = DesktopJournal(), service: ResidentService = ResidentService(),
         presentationOverride: PresentationProfile? = nil,
         preferences: UserDefaults = .standard) throws {
        // Do not let a second shell unlink the authoritative resident endpoint.
        let existing = try residentSocket()
        defer { Darwin.close(existing) }
        var (address, length) = try unixAddress(socketPath)
        if withSockAddr(&address, length:length, { Darwin.connect(existing, $0, $1) }) == 0 {
            throw MacUIError.action("Another Machine Control resident is already running")
        }
        try FileManager.default.createDirectory(atPath:(socketPath as NSString).deletingLastPathComponent,
            withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
        let store = PresentationStore(socketPath:socketPath)
        presentationStore = store
        self.presentationOverride = presentationOverride
        let saved = store.load()
        presentation = PresentationPreference(profile:presentationOverride ?? saved.profile, diagnostic:saved.diagnostic)
        presentationObservation = BackgroundObservation(label:"machine-control.presentation", interval:1, timeout:1, lifetime:3,
            unknown:{ PresentationPreference(profile:.personal, diagnostic:"presentation_observation_unavailable") }, read:{ store.load() })
        let broker = GrantBroker(policy:policy)
        broker.journal = journal
        if policy.grantMode == .approval { attachOperatorConsent(broker, socketPath:socketPath) }
        server = ResidentServer(socketPath:socketPath, service:service, broker:broker, preferences:preferences)
        resumeHelper = { observation, cancelled in
            try service.resumeCoveredAvailability(observation:observation, cancellation:cancelled)
        }
        server.presentationStatus = { [weak self] in self?.presentationJSON ?? [:] }
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
        let timer = DispatchSource.makeTimerSource(queue:.main)
        timer.schedule(deadline:.now() + 1, repeating:.seconds(1))
        timer.setEventHandler { [weak self] in self?.refreshPresentation() }
        presentationTimer = timer; timer.resume()
        running = true
    }
    func refreshPresentation() {
        presentationObservation.refresh()
        guard presentationOverride == nil, approver.request == nil, server.broker.pending == nil else { return }
        // Keep initial preference until the first completed observation.
        guard presentationObservation.metadata["available"] as? Bool == true else { return }
        presentation = presentationObservation.value
    }
    func configurePresentation(_ profile: PresentationProfile, completion: ((Bool) -> Void)? = nil) throws {
        guard approver.request == nil, server.broker.pending == nil, !updating, !presentationWriteInFlight else {
            throw MacUIError.action("Finish the pending approval or update before changing presentation")
        }
        presentationWriteInFlight = true
        let store = presentationStore
        presentationWriter.async { [weak self] in
            let error: String?
            do { try store.save(profile); error = nil } catch let failure { error = String(describing:failure) }
            DispatchQueue.main.async {
                guard let self else { return }
                self.presentationWriteInFlight = false
                guard error == nil else {
                    self.presentation = PresentationPreference(profile:self.presentation.profile, diagnostic:error)
                    completion?(false); return
                }
                self.presentationOverride = nil
                self.presentationObservation.invalidate()
                if self.approver.request == nil && self.server.broker.pending == nil {
                    self.presentation = PresentationPreference(profile:profile, diagnostic:nil)
                }
                completion?(true)
            }
        }
    }
    func stopAccess() {
        operatorDependency.cancel("stopped_by_person")
        if let pending = approver.request {
            try? approver.decide(id:pending.id, scopes:[], duration:0, allow:false)
        }
        // Standing authority comes from trusted policy; Stop adds a local
        // pause without rewriting or weakening that policy.
        if server.broker.policy.grantMode == .standing { try? server.broker.pause() }
        server.revoke(reason:"stopped_by_person")
    }
    func stop() {
        guard running else { return }
        operatorDependency.cancel("resident_stopping")
        server.revoke(reason:"resident_stopping")
        presentationTimer?.cancel(); presentationTimer = nil; presentationObservation.stop()
        server.stop(); running = false; stopped = true
    }
}
