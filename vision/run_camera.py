"""Run: python -m vision.run_camera --roi vision/roi.example.json --clearance CLR-001

Keys: c = confirm and submit current stable OCR; q = quit.
"""
import argparse
import json
import cv2
from vision.core import Regions, TesseractReader, Stabilizer, recognize
from vision.api_client import RadarClient

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roi", required=True, help="JSON with heading/altitude [x,y,w,h]")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--clearance", help="Clearance ID; omit for OCR-only mode")
    parser.add_argument("--min-confidence", type=float, default=0.65)
    args = parser.parse_args()
    with open(args.roi, encoding="utf-8") as f:
        regions = Regions.from_json(json.load(f))
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise RuntimeError("Camera unavailable")
    client = RadarClient(args.url, args.clearance) if args.clearance else None
    stabilizer, reader = Stabilizer(), TesseractReader()
    last_message = "Press c to submit a stable reading; q to quit"
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Failed to read camera frame")
            try:
                reading = recognize(frame, regions, reader, args.min_confidence)
            except ValueError as exc:
                raise RuntimeError(f"Invalid ROI: {exc}") from exc
            stable = stabilizer.push(reading)
            for label, roi in (("HDG", regions.heading), ("ALT", regions.altitude)):
                x, y, w, h = roi
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 220, 0), 2)
                cv2.putText(frame, label, (x, max(18, y-5)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 220, 0), 2)
            msg = (f"STABLE ALT={stable.altitude} HDG={stable.heading} "
                   f"score={stable.confidence:.2f}") if stable else "UNREADABLE / UNSTABLE"
            cv2.putText(frame, msg, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (0, 255, 255), 2)
            cv2.putText(frame, last_message[:85], (12, 58), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (255, 255, 255), 1)
            cv2.imshow("RADAR Vision PoC", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                if client is None:
                    last_message = "OCR-only mode: --clearance required for API submission"
                elif stable is None:
                    last_message = "Not submitted: reading is unstable"
                else:
                    try:
                        last_message = str(client.submit(stable))
                    except httpx.HTTPError as exc:
                        last_message = f"API error: {exc}"
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if client:
            client.close()

if __name__ == "__main__":
    import httpx
    main()
