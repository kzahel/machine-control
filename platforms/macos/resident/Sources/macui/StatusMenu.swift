import AppKit
import ApplicationServices
import Carbon.HIToolbox

/// The menu bar presence of the resident: grant state, Stop, manual arming,
/// recent activity, and permission setup. Enforcement stays in the broker.
final class StatusMenuController: NSObject, NSMenuDelegate {
    static let stopShortcut = StopShortcut.label

    let broker: GrantBroker
    let approval: ApprovalPanelController
    let setup: SetupWindowController
    var onRevoke: ((String) -> Void)?
    var onResume: (() throws -> Void)?
    var onResumeSurface: ((String) throws -> Void)?
    var trustedAccess: () -> Bool = { false }
    var onConfigure: ((String, String, Int?, [String]) throws -> Void)?
    var browserProfiles: () -> [[String:Any]] = { [] }
    private var chosenProfiles = Set<String>()

    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private var refreshTimer: Timer?
    private var hotKey: StopShortcut?
    var stopShortcutAvailable: Bool { hotKey?.available == true }
    private(set) var menuOpen = false

    init(broker: GrantBroker, approval: ApprovalPanelController, setup: SetupWindowController) {
        self.broker = broker
        self.approval = approval
        self.setup = setup
        super.init()
        menu.delegate = self
        menu.autoenablesItems = false
        statusItem.menu = menu
        statusItem.button?.toolTip = "Machine Control"
        hotKey = StopShortcut { [weak self] in self?.stopFromHotKey() }
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.updateIcon()
        }
        updateIcon()
    }

    /// Windows the resident draws outside its own panels, such as the status
    /// item, for self-targeting checks.
    var interfaceWindows: [NSWindow] {
        [statusItem.button?.window].compactMap { $0 }
    }


    func updateIcon() {
        guard let button = statusItem.button else { return }
        let state = broker.admission.status
        let requests = state["requests"] as? [[String:Any]] ?? []
        let pending = requests.contains { $0["state"] as? String == "waiting_for_approval" }
        let armed = broker.admission.enabled("desktop") || broker.admission.enabled("browser")
        let active = (state["active"] as? Int ?? 0) > 0
        let desktopActive = requests.contains { $0["state"] as? String == "active" && ($0["surfaces"] as? [String] ?? []).contains("desktop") }
        let starting = requests.first { $0["state"] as? String == "announcing" }
        let yielding = requests.contains { $0["state"] as? String == "paused" && ($0["blockingReasons"] as? [String] ?? []).contains("physical_takeover") }
        let label = desktopActive ? "Desktop" : active ? "Browser" : pending ? "Approval" : starting != nil ? "\(Int(ceil((starting?["noticeRemainingSeconds"] as? NSNumber)?.doubleValue ?? 0)))s" : yielding ? "Waiting" : armed ? "On" : "Off"
        let symbol = desktopActive ? "cursorarrow.motionlines" : active ? "globe" : pending ? "questionmark.circle" : starting != nil || yielding ? "hourglass" : "cursorarrow"
        let image = NSImage(systemSymbolName:symbol, accessibilityDescription:"Machine Control — " + label)
        image?.isTemplate = true
        button.image = image; button.title = " " + label; button.toolTip = "Machine Control — " + label
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        menu.addItem(disabled("Machine Control"))
        setup.refresh()
        if !setup.state.complete { add("Finish Setup…", #selector(showSetup), to:menu) }
        let state = broker.admission.status
        if state["available"] as? Bool == false { menu.addItem(disabled("Control policy unavailable — access is Off")) }
        let surfaces = state["surfaces"] as? [String:[String:Any]] ?? [:]
        let selected = surfaces["browser"]?["profileIds"] as? [String] ?? []
        if chosenProfiles.isEmpty { chosenProfiles = Set(selected) }
        for surface in ["desktop", "browser"] {
            let value = surfaces[surface] ?? [:]
            let on = (value["mode"] as? String ?? "off") != "off" && value["expired"] as? Bool != true
            let parent = NSMenuItem(title:surface.capitalized + ": " + (on ? "On" : "Off"), action:nil, keyEquivalent:"")
            let options = NSMenu(); options.autoenablesItems = false; parent.submenu = options
            if surface == "browser" {
                for profile in browserProfiles() {
                    guard let id = profile["profileId"] as? String else { continue }
                    let item = add(profile["name"] as? String ?? "Browser profile", #selector(selectProfile(_:)), to:options)
                    item.representedObject = id; item.state = chosenProfiles.contains(id) ? .on : .off
                }
                options.addItem(.separator())
            }
            let automatic = (value["noticeSeconds"] as? NSNumber)?.doubleValue == 0 ? "Start immediately" : "Give me a heads-up"
            for (label, mode) in [("Wait for my approval", "ask"), (automatic, "automatic")] {
                let choice = NSMenuItem(title:label, action:nil, keyEquivalent:""); let durations = NSMenu(); durations.autoenablesItems = false; choice.submenu = durations
                choice.state = value["mode"] as? String == mode ? .on : .off
                for (title, seconds) in [("15 minutes",900),("1 hour",3600),("Until turned off",0)] {
                    let item = add(title,#selector(configureSurface(_:)),to:durations)
                    item.representedObject = ["surface":surface,"mode":mode]; item.tag = seconds
                    item.isEnabled = surface != "browser" || !chosenProfiles.isEmpty
                }
                options.addItem(choice)
            }
            let off = add("Turn off " + surface,#selector(configureSurface(_:)),to:options)
            off.representedObject = ["surface":surface,"mode":"off"]
            if (value["pauses"] as? [[String:Any]] ?? []).contains(where: { $0["scope"] as? String != "all" && ["manual", "operator_deferral", "local_use_episode", "physical_takeover"].contains($0["reason"] as? String ?? "") }) {
                let resume = add("Resume " + surface,#selector(resumeSurface(_:)),to:options); resume.representedObject = surface
            }
            menu.addItem(parent)
        }
        menu.addItem(.separator())
        add("Turn Off Access (" + Self.stopShortcut + ")", #selector(stopAccess), to:menu)
        if !(state["globalPauses"] as? [[String:Any]] ?? []).isEmpty || !(state["deferrals"] as? [[String:Any]] ?? []).isEmpty {
            add("Resume Held Access", #selector(resumeAccess), to:menu)
        }
        menu.addItem(disabled("Tasks: \(state["active"] ?? 0) active · \(state["waiting"] ?? 0) waiting"))
        menu.addItem(.separator())
        let activity = NSMenuItem(title:"Recent Activity", action:nil, keyEquivalent:"")
        let entries = NSMenu()
        for entry in broker.audit.suffix(15).reversed() {
            entries.addItem(disabled(entry.operation + (entry.accepted ? " ✓" : " — " + (entry.errorCode ?? "refused"))))
        }
        if entries.items.isEmpty { entries.addItem(disabled("No activity yet")) }
        activity.submenu = entries; menu.addItem(activity)
        add("Setup and Permissions…", #selector(showSetup), to:menu)
        add("Quit Machine Control", #selector(quit), to:menu)
    }
    @discardableResult
    private func add(_ title:String, _ action:Selector, to menu:NSMenu) -> NSMenuItem {
        let item = NSMenuItem(title:title, action:action, keyEquivalent:"")
        item.target = self; menu.addItem(item); return item
    }
    @objc private func selectProfile(_ sender:NSMenuItem) {
        guard let id = sender.representedObject as? String else { return }
        if !chosenProfiles.insert(id).inserted { chosenProfiles.remove(id) }
    }
    @objc private func configureSurface(_ sender:NSMenuItem) {
        guard let value = sender.representedObject as? [String:String],
              let surface = value["surface"], let mode = value["mode"] else { return }
        do { try onConfigure?(surface, mode, sender.tag == 0 ? nil : sender.tag,
            surface == "browser" && mode != "off" ? chosenProfiles.sorted() : []) }
        catch { broker.journal?.diagnostic("operator.surface", code:"configuration_refused") }
    }

    func menuWillOpen(_ menu: NSMenu) { menuOpen = true }
    func menuDidClose(_ menu: NSMenu) { menuOpen = false }

    private func disabled(_ title: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.isEnabled = false
        return item
    }

    @objc func stopAccess() {
        onRevoke?("stopped_from_menu")
    }

    func stopFromHotKey() {
        onRevoke?("stopped_by_hotkey")
    }

    @objc private func resumeSurface(_ sender: NSMenuItem) {
        guard let surface = sender.representedObject as? String else { return }
        do { try onResumeSurface?(surface) }
        catch { broker.journal?.diagnostic("operator.resume", code:"pause_recovery_required") }
    }
    @objc private func resumeAccess() {
        do { try onResume?() }
        catch { broker.journal?.diagnostic("operator.resume", code:"pause_recovery_required") }
    }
    @objc private func showSetup() {
        setup.show()
    }

    @objc private func quit() {
        onRevoke?("operator_quit")
        NSApp.terminate(nil)
    }

}
