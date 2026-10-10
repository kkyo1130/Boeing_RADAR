import argparse
import json
from .poc import load_config, recognize


def main():
    parser = argparse.ArgumentParser(description="ALT/HDG still-image OCR PoC")
    parser.add_argument("image")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ocr-binary", required=True)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--captured-at", help="Actual capture time, ISO 8601 with timezone")
    args = parser.parse_args()
    try:
        result = recognize(args.image, load_config(args.config), args.ocr_binary,
                           args.output_dir, args.captured_at)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Input/config error: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
