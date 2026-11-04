import AppKit
import ApplicationServices
import Carbon.HIToolbox

/// The menu bar presence of the resident: grant state, Stop, manual arming,
/// recent activity, and permission setup. Enforcement stays in the broker.
final class StatusMenuController: NSObject, NSMenuDelegate {
    static let stopShortcut = "⌃⌥⌘."

    let broker: GrantBroker
    let approval: ApprovalPanelController
    let setup: SetupWindowController
    var onRevoke: ((String) -> Void)?
    var onResume: (() throws -> Void)?
    var trustedAccess: () -> Bool = { false }
    var onConfigure: ((String, String, Int?, [String]) throws -> Void)?
    var browserProfiles: () -> [[String:Any]] = { [] }
    private var chosenProfiles = Set<String>()

    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private var refreshTimer: Timer?
    private var hotKey: EventHotKeyRef?
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
        registerStopHotKey()
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

    private var approvalMode: Bool { broker.policy.grantMode == .approval }

    func updateIcon() {
        guard let button = statusItem.button else { return }
        let state = broker.admission.status
        let requests = state["requests"] as? [[String:Any]] ?? []
        let pending = requests.contains { $0["state"] as? String == "waiting_for_approval" }
        let armed = broker.admission.enabled("desktop") || broker.admission.enabled("browser")
        let active = (state["active"] as? Int ?? 0) > 0
        let symbol = pending ? "questionmark.circle.fill" : active ? "cursorarrow.motionlines" : "cursorarrow"
        var image = NSImage(systemSymbolName:symbol, accessibilityDescription:"Machine Control")
        if pending || active {
            image = image?.withSymbolConfiguration(.init(paletteColors:[pending ? .systemOrange : .systemRed]))
            image?.isTemplate = false
        } else { image?.isTemplate = true }
        button.image = image; button.title = armed ? " On" : ""
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
            let name = surface.capitalized, value = surfaces[surface] ?? [:]
            let mode = value["mode"] as? String ?? "off"
            let parent = NSMenuItem(title:name + ": " + mode.replacingOccurrences(of:"_", with:" ").capitalized, action:nil, keyEquivalent:"")
            let choices = NSMenu()
            if surface == "browser" {
                choices.addItem(disabled("Select exact browser profiles:"))
                for profile in browserProfiles() {
                    guard let id = profile["profileId"] as? String else { continue }
                    let label = profile["name"] as? String ?? "Browser profile"
                    let item = add(label + (profile["connected"] as? Bool == true ? "" : " (disconnected)"), #selector(selectProfile(_:)), to:choices)
                    item.representedObject = id; item.toolTip = id
                    item.state = chosenProfiles.contains(id) ? .on : .off
                }
                choices.addItem(.separator())
            }
            for (label, next) in [("Off", "off"), ("Ask First", "ask"), ("Automatic", "automatic")] {
                let item = NSMenuItem(title:label, action:nil, keyEquivalent:"")
                if next == "off" {
                    item.action = #selector(configureSurface(_:)); item.target = self
                    item.representedObject = ["surface":surface, "mode":next]; item.tag = 0
                } else {
                    let durations = NSMenu()
                    for (title, seconds) in [("15 Minutes",900), ("1 Hour",3600), ("Until I Stop",0)] {
                        let duration = add(title, #selector(configureSurface(_:)), to:durations)
                        duration.representedObject = ["surface":surface, "mode":next]; duration.tag = seconds
                        duration.isEnabled = surface != "browser" || !chosenProfiles.isEmpty
                    }
                    item.submenu = durations
                }
                item.state = mode == next ? .on : .off; choices.addItem(item)
            }
            let reasons = (value["pauses"] as? [[String:Any]] ?? []).compactMap { $0["reason"] as? String }
            if !reasons.isEmpty { choices.addItem(disabled("Paused: " + reasons.joined(separator:", "))) }
            parent.submenu = choices; menu.addItem(parent)
        }
        menu.addItem(.separator())
        add("Stop Access (" + Self.stopShortcut + ")", #selector(stopAccess), to:menu)
        let pauses = NSMenuItem(title:"Pause Access", action:nil, keyEquivalent:"")
        let choices = NSMenu()
        for (title, seconds) in [("30 Seconds",30), ("1 Minute",60), ("Until I Resume",0)] {
            add(title, #selector(pauseAccess(_:)), to:choices).tag = seconds
        }
        pauses.submenu = choices; menu.addItem(pauses)
        add("Resume Access", #selector(resumeAccess), to:menu)
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

    @objc private func pauseAccess(_ sender: NSMenuItem) {
        do { try broker.pause(seconds:sender.tag == 0 ? nil : sender.tag) }
        catch { broker.journal?.diagnostic("operator.pause", code:"pause_storage_unavailable") }
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

    private func registerStopHotKey() {
        var handlerSpec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard),
                                        eventKind: UInt32(kEventHotKeyPressed))
        let context = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(GetApplicationEventTarget(), { _, _, context in
            guard let context else { return noErr }
            let controller = Unmanaged<StatusMenuController>.fromOpaque(context).takeUnretainedValue()
            DispatchQueue.main.async { controller.stopFromHotKey() }
            return noErr
        }, 1, &handlerSpec, context, nil)
        let identifier = EventHotKeyID(signature: OSType(0x4D43_5354), id: 1)
        RegisterEventHotKey(UInt32(kVK_ANSI_Period),
                            UInt32(controlKey | optionKey | cmdKey),
                            identifier, GetApplicationEventTarget(), 0, &hotKey)
    }
}
