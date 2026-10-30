// Independent screenshot analysis for a dedicated guest's real display output.
// This never consults the resident's cover-count or filtered capture metadata.
import AppKit
import Vision

guard CommandLine.arguments.count == 2,
      let image = NSImage(contentsOfFile:CommandLine.arguments[1]),
      let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data:tiff),
      let cg = image.cgImage(forProposedRect:nil, context:nil, hints:nil) else { exit(2) }
var dark = 0
let samples = 24 * 24
for row in 0..<24 {
    for column in 0..<24 {
        let x = bitmap.pixelsWide * (column * 2 + 1) / 48
        let y = bitmap.pixelsHigh * (row * 2 + 1) / 48
        if let color = bitmap.colorAt(x:x, y:y)?.usingColorSpace(.deviceRGB) {
            let values = [color.redComponent,color.greenComponent,color.blueComponent]
            if values.min()! > 0.025 && values.max()! < 0.2 && values.max()! - values.min()! < 0.03 { dark += 1 }
        }
    }
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
try VNImageRequestHandler(cgImage:cg).perform([request])
let text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator:" ")
let covered = text.contains("Machine Control is working") && Double(dark) / Double(samples) > 0.9
let report: [String:Any] = ["coverTextObserved":text.contains("Machine Control is working"),
    "darkSamples":dark, "totalSamples":samples, "sampledConcealment":covered]
print(String(data:try JSONSerialization.data(withJSONObject:report, options:.sortedKeys), encoding:.utf8)!)
exit(covered ? 0 : 1)
