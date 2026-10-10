"""Generate a small replay fixture; never supply labels to the recognizer."""
import argparse
from pathlib import Path

from radar_vision.capture import opencv


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic replay video from existing PNG fixtures")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codec", choices=["FFV1", "MJPG"], default="FFV1")
    args = parser.parse_args()
    cv = opencv()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv.VideoWriter(str(args.output), cv.VideoWriter_fourcc(*args.codec), 3, (800, 300))
    try:
        if not writer.isOpened():
            raise ValueError("Video codec unavailable")
        root = Path(__file__).parent / "fixtures"
        for name in ["normal.png", "changed.png", "occluded.png", "north.png"]:
            image = cv.imread(str(root / name))
            if image is None:
                raise ValueError(f"Fixture unavailable: {name}")
            for _ in range(3):
                writer.write(image)
    finally:
        writer.release()
    print(args.output)


if __name__ == "__main__":
    main()
