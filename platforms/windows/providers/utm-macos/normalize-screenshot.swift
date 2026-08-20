import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

enum NormalizeError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case let .message(value): return value
        }
    }
}

func fail(_ error: Error) -> Never {
    fputs("\(error)\n", stderr)
    exit(1)
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard arguments.count == 7,
      let windowWidth = Double(arguments[4]),
      let windowHeight = Double(arguments[5]),
      let titlebarHeight = Double(arguments[6]),
      windowWidth > 0, windowHeight > titlebarHeight,
      titlebarHeight >= 0 else {
    fail(NormalizeError.message(
        "Usage: normalize INPUT OUTPUT [DISPLAY_W DISPLAY_H] WINDOW_W WINDOW_H TITLEBAR_H"
    ))
}

let configuredWidth = Int(arguments[2])
let configuredHeight = Int(arguments[3])
guard (configuredWidth == nil && configuredHeight == nil) ||
      (configuredWidth ?? 0) > 0 && (configuredHeight ?? 0) > 0 else {
    fail(NormalizeError.message(
        "DISPLAY_W and DISPLAY_H must both be empty or positive"
    ))
}
let displayWidth = configuredWidth ?? Int(round(windowWidth))
let displayHeight = configuredHeight ?? Int(round(windowHeight - titlebarHeight))

do {
    guard let source = CGImageSourceCreateWithURL(
        URL(fileURLWithPath: arguments[0]) as CFURL, nil
    ), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NormalizeError.message("Unable to read raw UTM screenshot")
    }

    let scaleY = Double(image.height) / windowHeight
    let titlePixels = Int(round(titlebarHeight * scaleY))
    let guestHeight = image.height - titlePixels
    guard titlePixels >= 0, guestHeight > 0,
          let cropped = image.cropping(to: CGRect(
              x: 0, y: titlePixels, width: image.width, height: guestHeight
          )) else {
        throw NormalizeError.message("Unable to derive the UTM guest viewport")
    }

    guard let context = CGContext(
        data: nil,
        width: displayWidth,
        height: displayHeight,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else {
        throw NormalizeError.message("Unable to create image context")
    }
    context.interpolationQuality = .high
    context.draw(cropped, in: CGRect(
        x: 0, y: 0, width: displayWidth, height: displayHeight
    ))

    guard let normalized = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(
              URL(fileURLWithPath: arguments[1]) as CFURL,
              UTType.png.identifier as CFString,
              1,
              nil
          ) else {
        throw NormalizeError.message("Unable to prepare normalized PNG")
    }
    CGImageDestinationAddImage(destination, normalized, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw NormalizeError.message("Unable to write normalized PNG")
    }
} catch {
    fail(error)
}
