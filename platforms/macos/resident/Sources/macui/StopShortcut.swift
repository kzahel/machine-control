import AppKit
import Carbon.HIToolbox

/// One native emergency chord for both shells, resolved like ordinary input.
/// A failed registration is unavailable; it is never reported as installed.
final class StopShortcut {
    static let label = "⌃⌥⌘."
    private static let identifier = EventHotKeyID(signature: OSType(0x4D43_5354), id: 1)
    private var hotKey: EventHotKeyRef?
    private var handler: EventHandlerRef?
    private var layoutObserver: NSObjectProtocol?
    private let action: () -> Void
    var available: Bool { hotKey != nil }

    static func key(in layout: KeyboardLayoutSnapshot) throws -> ResolvedKeyboardKey {
        try resolveKeyboardChord("ctrl-alt-cmd-.", layout:layout)
    }
    init(action: @escaping () -> Void) {
        precondition(Thread.isMainThread)
        self.action = action
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard),
                                 eventKind: UInt32(kEventHotKeyPressed))
        let installed = InstallEventHandler(GetApplicationEventTarget(), { _, event, context in
            guard let context, let event else { return OSStatus(eventNotHandledErr) }
            var identifier = EventHotKeyID()
            guard GetEventParameter(event, EventParamName(kEventParamDirectObject),
                EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size,
                nil, &identifier) == noErr,
                identifier.signature == StopShortcut.identifier.signature,
                identifier.id == StopShortcut.identifier.id else { return OSStatus(eventNotHandledErr) }
            let value = Unmanaged<StopShortcut>.fromOpaque(context).takeUnretainedValue()
            value.action()
            return noErr
        }, 1, &spec, Unmanaged.passUnretained(self).toOpaque(), &handler)
        guard installed == noErr else { handler = nil; return }
        refresh()
        layoutObserver = DistributedNotificationCenter.default().addObserver(
            forName:Notification.Name(kTISNotifySelectedKeyboardInputSourceChanged as String),
            object:nil, queue:.main) { [weak self] _ in self?.refresh() }
    }
    private func refresh() {
        precondition(Thread.isMainThread)
        if let hotKey { UnregisterEventHotKey(hotKey); self.hotKey = nil }
        guard let layout = try? KeyboardLayoutSnapshot.current(), let key = try? Self.key(in:layout) else { return }
        var modifiers = UInt32(controlKey | optionKey | cmdKey)
        if key.flags.contains(.maskShift) { modifiers |= UInt32(shiftKey) }
        if RegisterEventHotKey(UInt32(key.code), modifiers, Self.identifier,
            GetApplicationEventTarget(), 0, &hotKey) != noErr { hotKey = nil }
    }
    deinit {
        if let layoutObserver { DistributedNotificationCenter.default().removeObserver(layoutObserver) }
        if let hotKey { UnregisterEventHotKey(hotKey) }
        if let handler { RemoveEventHandler(handler) }
    }
}
