"""Capture one calibration frame, or manually select numeric ROIs from an image."""
import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from .capture import LatestCamera, opencv
from .stream import positive


def main():
    parser = argparse.ArgumentParser(description="Tablet camera snapshot and manual ROI setup")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--camera", type=int, help="Save one camera frame")
    source.add_argument("--image", type=Path, help="Select numeric regions from this saved frame")
    parser.add_argument("--output", type=Path, required=True, help="Snapshot PNG or ROI config JSON")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--timeout", type=positive, default=10)
    parser.add_argument("--speed", action="store_true", help="Include IAS numeric region (knots)")
    args = parser.parse_args()
    camera = None
    try:
        if args.camera is not None:
            if args.camera < 0 or min(args.width, args.height) <= 0:
                raise ValueError("Camera index must be >=0 and dimensions positive")
            if args.output.suffix.lower() != ".png":
                raise ValueError("Snapshot output must end in .png")
            camera = LatestCamera(args.camera, args.width, args.height).start()
            deadline = monotonic() + args.timeout
            reason = "camera_starting"
            while monotonic() < deadline:
                frame, reason, _ = camera.snapshot(3)
                if frame:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    frame.image.save(args.output)
                    metadata = {"captured_at": frame.received_at, "capture_time_basis": "host_receive",
                                "image_size": list(frame.image.size), "evidence": str(args.output)}
                    args.output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2))
                    print(json.dumps(metadata, indent=2))
                    return
                sleep(0.05)
            raise ValueError(f"No camera frame before timeout: {reason}")
        if args.output.suffix.lower() != ".json":
            raise ValueError("ROI config output must end in .json")
        cv = opencv()
        image = cv.imread(str(args.image))
        if image is None:
            raise ValueError("Cannot open calibration image")
        config = {"image_size": [image.shape[1], image.shape[0]], "minimum_model_score": 0.5}
        fields = [("altitude", "feet"), ("heading", "degrees")]
        if args.speed:
            fields.append(("speed", "knots"))
        try:
            for name, unit in fields:
                title = f"{name}: select DIGITS ONLY, Enter to confirm, Escape to cancel"
                x, y, width, height = cv.selectROI(title, image, showCrosshair=True, fromCenter=False)
                cv.destroyWindow(title)
                if width <= 0 or height <= 0:
                    raise ValueError("ROI selection cancelled; config not written")
                config[name] = {"roi": [int(x), int(y), int(x + width), int(y + height)], "unit": unit}
        finally:
            cv.destroyAllWindows()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(config, indent=2))
        print(json.dumps(config, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(2, f"Setup error: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Setup cancelled\n")
    finally:
        if camera:
            camera.close()


if __name__ == "__main__":
    main()
