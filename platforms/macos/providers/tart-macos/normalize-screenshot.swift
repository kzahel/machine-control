import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

enum NormalizeError: Error, CustomStringConvertible {
    case usage
    case unreadableImage
    case invalidGeometry
    case cropFailed
    case contextFailed
    case writeFailed

    var description: String {
        switch self {
        case .usage:
            return "Usage: normalize-screenshot.swift INPUT OUTPUT DISPLAY_W DISPLAY_H WINDOW_W WINDOW_H"
        case .unreadableImage: return "Unable to read the raw Tart screenshot"
        case .invalidGeometry: return "Invalid screenshot or Tart window geometry"
        case .cropFailed: return "Unable to crop the Tart title bar"
        case .contextFailed: return "Unable to create the normalized image context"
        case .writeFailed: return "Unable to write the normalized PNG"
        }
    }
}

func fail(_ error: Error) -> Never {
    fputs("\(error)\n", stderr)
    exit(1)
}

let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 6,
      let displayWidth = Int(args[2]),
      let displayHeight = Int(args[3]),
      let windowWidth = Double(args[4]),
      let windowHeight = Double(args[5]),
      displayWidth > 0, displayHeight > 0,
      windowWidth > 0, windowHeight >= Double(displayHeight) else {
    fail(NormalizeError.usage)
}

do {
    let input = URL(fileURLWithPath: args[0]) as CFURL
    let output = URL(fileURLWithPath: args[1]) as CFURL
    guard let source = CGImageSourceCreateWithURL(input, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NormalizeError.unreadableImage
    }

    let scaleX = Double(image.width) / windowWidth
    let scaleY = Double(image.height) / windowHeight
    guard scaleX > 0, scaleY > 0 else {
        throw NormalizeError.invalidGeometry
    }

    let titlePixels = Int(round((windowHeight - Double(displayHeight)) * scaleY))
    let guestPixelsHigh = image.height - titlePixels
    guard titlePixels >= 0, guestPixelsHigh > 0 else {
        throw NormalizeError.invalidGeometry
    }

    // CGImage cropping uses the image's upper-left pixel coordinate space.
    let cropRect = CGRect(x: 0, y: titlePixels,
                          width: image.width, height: guestPixelsHigh)
    guard let cropped = image.cropping(to: cropRect) else {
        throw NormalizeError.cropFailed
    }

    let colorSpace = CGColorSpaceCreateDeviceRGB()
    guard let context = CGContext(
        data: nil,
        width: displayWidth,
        height: displayHeight,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else {
        throw NormalizeError.contextFailed
    }
    context.interpolationQuality = .high
    context.draw(cropped, in: CGRect(x: 0, y: 0,
                                     width: displayWidth, height: displayHeight))
    guard let normalized = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(
              output, UTType.png.identifier as CFString, 1, nil
          ) else {
        throw NormalizeError.writeFailed
    }
    CGImageDestinationAddImage(destination, normalized, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw NormalizeError.writeFailed
    }
} catch {
    fail(error)
}
