import CoreGraphics
import Foundation

struct UTMWindow: Codable {
    let id: Int
    let width: Double
    let height: Double
    let isOnScreen: Bool
}

let arguments = Array(CommandLine.arguments.dropFirst())
let vmName = arguments.first ?? "Windows"
let jsonOutput = arguments.dropFirst().contains("--json")
// Keep windows from every macOS Space in scope. A VM console can move to a
// different Space while UTM input automation and guest control remain usable,
// and `screencapture -l` can still capture that window by ID.
let options: CGWindowListOption = [.excludeDesktopElements]

guard let windowInfo = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        as? [[String: Any]] else {
    fputs("Unable to query the macOS window list\n", stderr)
    exit(1)
}

let candidates = windowInfo.compactMap { window -> UTMWindow? in
    guard let owner = window[kCGWindowOwnerName as String] as? String,
          owner == "UTM",
          let name = window[kCGWindowName as String] as? String,
          name == vmName,
          let layer = window[kCGWindowLayer as String] as? Int,
          layer == 0,
          let windowID = window[kCGWindowNumber as String] as? Int,
          let bounds = window[kCGWindowBounds as String] as? [String: Any],
          let width = (bounds["Width"] as? NSNumber)?.doubleValue,
          let height = (bounds["Height"] as? NSNumber)?.doubleValue else {
        return nil
    }
    let isOnScreen = (window[kCGWindowIsOnscreen as String] as? NSNumber)?
        .boolValue ?? false
    return UTMWindow(
        id: windowID,
        width: width,
        height: height,
        isOnScreen: isOnScreen
    )
}

guard let selected = candidates.max(by: {
    if $0.isOnScreen != $1.isOnScreen {
        return !$0.isOnScreen && $1.isOnScreen
    }
    return $0.width * $0.height < $1.width * $1.height
}) else {
    fputs("No UTM window named '\(vmName)' was found\n", stderr)
    exit(1)
}

if jsonOutput {
    do {
        let data = try JSONEncoder().encode(selected)
        print(String(decoding: data, as: UTF8.self))
    } catch {
        fputs("Unable to encode UTM window geometry: \(error)\n", stderr)
        exit(1)
    }
} else {
    print(selected.id)
}
