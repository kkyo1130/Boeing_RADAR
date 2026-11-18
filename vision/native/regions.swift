import Foundation
import Vision

guard CommandLine.arguments.count == 2 else { exit(2) }
do {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    request.minimumTextHeight = 0.008
    try VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1])).perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return ["text": candidate.string, "score": candidate.confidence,
                "box": [box.minX, 1-box.maxY, box.maxX, 1-box.minY]]
    }
    let data = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch { exit(1) }
