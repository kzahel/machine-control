import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

enum NormalizeError: Error, CustomStringConvertible {
    case message(String)
    var description: String {
        switch self { case let .message(value): return value }
    }
}

func fail(_ error: Error) -> Never {
    fputs("\(error)\n", stderr)
    exit(1)
}

let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 6, let outputWidth = Int(args[2]),
      let outputHeight = Int(args[3]), let windowWidth = Double(args[4]),
      let windowHeight = Double(args[5]), outputWidth > 0, outputHeight > 0,
      windowWidth > 0, windowHeight >= Double(outputHeight) else {
    fail(NormalizeError.message(
        "Usage: normalize INPUT OUTPUT DISPLAY_W DISPLAY_H WINDOW_W WINDOW_H"))
}

do {
    guard let source = CGImageSourceCreateWithURL(
        URL(fileURLWithPath: args[0]) as CFURL, nil),
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NormalizeError.message("Unable to read raw UTM screenshot")
    }
    let scaleY = Double(image.height) / windowHeight
    let titlePixels = Int(round((windowHeight - Double(outputHeight)) * scaleY))
    let guestHeight = image.height - titlePixels
    guard titlePixels >= 0, guestHeight > 0,
          let cropped = image.cropping(to: CGRect(x: 0, y: titlePixels,
                                                   width: image.width,
                                                   height: guestHeight)) else {
        throw NormalizeError.message("Unable to derive the UTM guest viewport")
    }
    guard let context = CGContext(
        data: nil, width: outputWidth, height: outputHeight,
        bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
        throw NormalizeError.message("Unable to create image context")
    }
    context.interpolationQuality = .high
    context.draw(cropped, in: CGRect(x: 0, y: 0,
                                     width: outputWidth, height: outputHeight))
    guard let normalized = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(
              URL(fileURLWithPath: args[1]) as CFURL,
              UTType.png.identifier as CFString, 1, nil) else {
        throw NormalizeError.message("Unable to prepare normalized PNG")
    }
    CGImageDestinationAddImage(destination, normalized, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw NormalizeError.message("Unable to write normalized PNG")
    }
} catch { fail(error) }
