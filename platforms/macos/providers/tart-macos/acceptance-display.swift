import AppKit
import CoreGraphics
import Foundation
import ImageIO
import ScreenCaptureKit
import UniformTypeIdentifiers

func fail(_ message: String) -> Never {
    fputs(message + "\n", stderr)
    exit(1)
}

let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 4, let owner = Int32(args[1]),
      let width = Int(args[2]), let height = Int(args[3]),
      (1...4096).contains(width), (1...4096).contains(height) else {
    fail("Expected the exact Tart runner and its configured display dimensions")
}
guard #available(macOS 14.2, *), CGPreflightScreenCaptureAccess() else {
    fail("Passive Tart acceptance capture needs existing host Screen Recording access")
}
// ScreenCaptureKit's window filter needs this tool's WindowServer connection.
// Initialize a background application without bringing it forward.
NSApplication.shared.setActivationPolicy(.prohibited)
guard CGDisplayIsAsleep(CGMainDisplayID()) == 0 else { fail("Controller display is asleep") }

do {
    let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
    let windows = content.windows.filter {
        $0.owningApplication?.processID == owner && $0.title == args[0] && $0.windowLayer == 0 && $0.isOnScreen
    }
    guard windows.count == 1, let window = windows.first, window.frame.width > 0, window.frame.height > 28 else {
        fail("Expected exactly one capturable window for the claimed Tart runner")
    }
    let filter = SCContentFilter(desktopIndependentWindow: window)
    let config = SCStreamConfiguration()
    config.ignoreShadowsSingleWindow = true
    config.showsCursor = false
    config.width = width
    config.height = Int((Double(width) * window.frame.height / window.frame.width).rounded())
    guard (1...8192).contains(config.height) else { fail("Invalid Tart acceptance window proportions") }
    let image: CGImage = try await withCheckedThrowingContinuation { continuation in
        SCScreenshotManager.captureImage(contentFilter: filter, configuration: config) { image, error in
            if let image {
                continuation.resume(returning: image)
            } else {
                continuation.resume(throwing: error ?? CocoaError(.fileReadUnknown))
            }
        }
    }

    // Tart's 28-point title bar is host chrome. Keep the whole guest view.
    let titleHeight = Int((28 * Double(image.height) / window.frame.height).rounded())
    guard let guest = image.cropping(to: CGRect(x: 0, y: titleHeight, width: image.width,
                                                height: image.height - titleHeight)) else {
        fail("Could not crop host chrome from the Tart acceptance window")
    }
    let data = NSMutableData()
    guard let destination = CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil) else {
        fail("Could not encode the Tart acceptance frame")
    }
    CGImageDestinationAddImage(destination, guest, nil)
    guard CGImageDestinationFinalize(destination) else { fail("Could not encode the Tart acceptance frame") }
    FileHandle.standardOutput.write(data as Data)
} catch {
    fail("ScreenCaptureKit could not observe the claimed Tart window")
}
