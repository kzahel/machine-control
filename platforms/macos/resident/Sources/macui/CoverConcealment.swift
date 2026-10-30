import AppKit

/// Concealment depends on the fully painted surface, not the compositor's
/// opaque-window optimization hint. Keep alpha and geometry fail-closed.
func coverConcealmentHealthy(visible: Bool, windowAlpha: Double, contentAlpha: Double,
                            contentVisible: Bool, fillsFrame: Bool, painted: Bool) -> Bool {
    visible && windowAlpha == 1 && contentAlpha == 1 && contentVisible && fillsFrame && painted
}

final class LockedCoverContent: NSView {
    static let fillColor = NSColor(calibratedWhite:0.08, alpha:1)
    private(set) var paintedBounds: NSRect?
    override var isOpaque: Bool { true }
    override func draw(_ dirtyRect: NSRect) {
        Self.fillColor.setFill()
        bounds.fill(using:.copy)
        if dirtyRect.contains(bounds) { paintedBounds = bounds }
    }
    func conceals(_ window: NSWindow) -> Bool {
        coverConcealmentHealthy(visible:window.isVisible,
            windowAlpha:Double(window.alphaValue),contentAlpha:Double(alphaValue),
            contentVisible:!isHidden && self.window === window,
            fillsFrame:frame == NSRect(origin:.zero,size:window.frame.size),
            painted:paintedBounds == bounds)
    }
}
