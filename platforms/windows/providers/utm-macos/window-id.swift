import CoreGraphics
import Foundation

let vmName = CommandLine.arguments.dropFirst().first ?? "Windows"
let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]

guard let windowInfo = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        as? [[String: Any]] else {
    fputs("Unable to query the macOS window list\n", stderr)
    exit(1)
}

let candidates = windowInfo.compactMap { window -> (id: Int, area: Double)? in
    guard let owner = window[kCGWindowOwnerName as String] as? String,
          owner == "UTM",
          let name = window[kCGWindowName as String] as? String,
          name == vmName,
          let layer = window[kCGWindowLayer as String] as? Int,
          layer == 0,
          let windowID = window[kCGWindowNumber as String] as? Int,
          let bounds = window[kCGWindowBounds as String] as? [String: Any],
          let width = bounds["Width"] as? Double,
          let height = bounds["Height"] as? Double else {
        return nil
    }
    return (windowID, width * height)
}

guard let selected = candidates.max(by: { $0.area < $1.area }) else {
    fputs("No visible UTM window named '\(vmName)' was found\n", stderr)
    exit(1)
}

print(selected.id)
