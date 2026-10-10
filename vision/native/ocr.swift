import Foundation
import Vision

// One cropped field per invocation. JSON only on stdout.
guard CommandLine.arguments.count == 2 else { exit(2) }
do {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
    try handler.perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        return ["text": candidate.string, "score": candidate.confidence]
    }
    let data = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch {
    FileHandle.standardError.write(Data("OCR failed: \(error)\n".utf8))
    exit(1)
}
