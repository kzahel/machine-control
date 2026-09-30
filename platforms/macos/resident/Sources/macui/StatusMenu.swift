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
        let symbol: String
        var tint: NSColor?
        if !approvalMode {
            symbol = "cursorarrow.rays"
        } else if broker.pending != nil {
            symbol = "questionmark.circle.fill"
            tint = .systemOrange
        } else if broker.activeGrant != nil {
            symbol = "cursorarrow.motionlines"
            tint = .systemRed
        } else {
            symbol = "cursorarrow"
        }
        var image = NSImage(systemSymbolName: symbol, accessibilityDescription: "Machine Control")
        if let tint {
            // Menu bar buttons ignore tint on template images, so render the
            // active and pending states in color.
            image = image?.withSymbolConfiguration(.init(paletteColors: [tint]))
            image?.isTemplate = false
        } else {
            image?.isTemplate = true
        }
        button.image = image
        if let grant = broker.activeGrant, approvalMode {
            let minutes = Int(ceil(grant.expiresAt.timeIntervalSinceNow / 60))
            button.title = " \(minutes)m"
        } else {
            button.title = ""
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let policy = broker.policy
        let heading = approvalMode ? "Machine Control — \(policy.preset.capitalized)" :
            "Machine Control — \(policy.preset.capitalized), always allowed"
        menu.addItem(disabled(heading))
        setup.refresh()
        if !setup.state.complete {
            let finish = NSMenuItem(
                title: "⚠︎ Finish Setup (\(setup.state.requiredDone) of \(SetupState.requiredCount) permissions)…",
                action: #selector(showSetup), keyEquivalent: "")
            finish.target = self
            menu.addItem(finish)
        }
        if let issue = policy.issue, issue != "policy_absent" {
            menu.addItem(disabled("Policy fallback: \(issue.replacingOccurrences(of: "_", with: " "))"))
        }
        if approvalMode {
            if let pending = broker.pending {
                menu.addItem(disabled("Waiting for approval: \(pending.caller.summary)"))
            } else if let grant = broker.activeGrant {
                let scopes = grant.scopes.sorted().map(\.rawValue).joined(separator: ", ")
                let minutes = Int(ceil(grant.expiresAt.timeIntervalSinceNow / 60))
                menu.addItem(disabled("Active: \(scopes) · \(minutes) min left"))
                menu.addItem(disabled("For: \(grant.requester)"))
                menu.addItem(disabled("Reason: \(grant.reason)"))
            } else {
                menu.addItem(disabled("Off — agents must ask for access"))
            }
            menu.addItem(.separator())
            let stop = NSMenuItem(title: "Stop Access (\(Self.stopShortcut))",
                                  action: #selector(stopAccess), keyEquivalent: "")
            stop.target = self
            stop.isEnabled = broker.activeGrant != nil
            menu.addItem(stop)
            let arm = NSMenuItem(title: "Allow Full Access For", action: nil, keyEquivalent: "")
            let durations = NSMenu()
            for (title, seconds) in [("15 Minutes", 900), ("1 Hour", 3600), ("4 Hours", 14_400)] {
                let item = NSMenuItem(title: title, action: #selector(armManually(_:)),
                                      keyEquivalent: "")
                item.target = self
                item.tag = seconds
                durations.addItem(item)
            }
            arm.submenu = durations
            arm.isEnabled = broker.pending == nil
            menu.addItem(arm)
        }
        menu.addItem(.separator())
        let activity = NSMenuItem(title: "Recent Activity", action: nil, keyEquivalent: "")
        let entries = NSMenu()
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        for entry in broker.audit.suffix(15).reversed() {
            let mark = entry.accepted ? "✓" : "✗ \(entry.errorCode ?? "refused")"
            entries.addItem(disabled("\(formatter.string(from: entry.at))  \(entry.operation) \(mark) — \(entry.caller)"))
        }
        if entries.items.isEmpty { entries.addItem(disabled("No activity yet")) }
        activity.submenu = entries
        menu.addItem(activity)
        let setupItem = NSMenuItem(title: "Setup and Permissions…", action: #selector(showSetup),
                                   keyEquivalent: "")
        setupItem.target = self
        menu.addItem(setupItem)
        if approvalMode {
            menu.addItem(.separator())
            let quit = NSMenuItem(title: "Quit Machine Control", action: #selector(quit),
                                  keyEquivalent: "")
            quit.target = self
            menu.addItem(quit)
        }
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

    @objc private func armManually(_ sender: NSMenuItem) {
        broker.issue(scopes: Set(GrantScope.allCases), durationSeconds: sender.tag,
                     reason: "Armed from the menu bar", requester: "person at this Mac",
                     approver: "menu")
    }

    @objc private func showSetup() {
        setup.show()
    }

    @objc private func quit() {
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
