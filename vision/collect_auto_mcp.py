"""Auto-change tablet MCP via Vite, then collect 150 HDG/ALT pairs (300 crops).

The tablet must have the CockpitVision auto-control hook enabled.
Use a NEW output directory; manually inspect saved images and labels.
"""
import argparse
import csv
import json
import random
import time
import urllib.request
from pathlib import Path


def request(base, endpoint, data=None):
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base.rstrip('/') + '/api/mcp-auto/' + endpoint,
                                 data=payload,
                                 headers={'Content-Type': 'application/json'},
                                 method='POST' if payload is not None else 'GET')
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server', default='http://127.0.0.1:5174')
    p.add_argument('--source', default='0')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pairs', type=int, default=150)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--settle', type=float, default=1.2)
    p.add_argument('--ack-timeout', type=float, default=8)
    args = p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        p.error('Use a NEW empty output directory to avoid overwriting images')
    if args.pairs < 1 or args.settle < 0:
        p.error('Invalid pairs/settle')
    import cv2
    from PIL import Image
    from auto_detect_mcp import detect_readouts
    from camera_digit_preprocess import camera_to_amber
    from preprocess_mcp_ocr import align
    rng = random.Random(args.seed)
    # Many distinct altitudes, including confusing 0/3/4/5/8 positions.
    altitudes = [0, 300, 400, 500, 800, 1200, 1500, 1800, 3000, 3500,
                 4000, 4500, 4800, 5000, 5800, 6700, 8000, 8500,
                 10500, 12000, 15000, 18000, 20000, 25000, 28000, 29500]
    headings = [0, 45, 67, 87, 90, 120, 180, 250, 270, 290, 315, 359]
    source = int(args.source) if args.source.isdecimal() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        p.error('Cannot open camera')
    args.output.mkdir(parents=True, exist_ok=True)
    fields = ['image_path', 'kind', 'text', 'split', 'session_id', 'source_image']
    labels = args.output / 'labels.csv'
    count = 0
    try:
        with labels.open('w', newline='', encoding='utf-8') as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            writer.writeheader()
            for i in range(args.pairs):
                h = headings[i % len(headings)]
                a = altitudes[i % len(altitudes)]
                # Shuffle only between complete cycles for balanced coverage.
                if i % len(altitudes) == 0:
                    rng.shuffle(altitudes)
                if i % len(headings) == 0:
                    rng.shuffle(headings)
                desired = request(args.server, 'set', {'heading': h, 'altitude': a})
                seq = desired['seq']
                deadline = time.monotonic() + args.ack_timeout
                while time.monotonic() < deadline:
                    current = request(args.server, 'state')
                    if current.get('ack') == seq:
                        break
                    time.sleep(.15)
                else:
                    raise RuntimeError('Tablet did not acknowledge update. Keep /cockpit open on tablet.')
                time.sleep(args.settle)
                # Discard old buffered frames after screen updates.
                for _ in range(4):
                    cap.grab()
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError('Camera frame unavailable')
                boxes = detect_readouts(frame)
                if not {'hdg', 'alt'}.issubset(boxes):
                    print(f'Skipping pair {i}: readouts not detected')
                    continue
                crops = {}
                for kind in ('hdg', 'alt'):
                    x, y, w, height = boxes[kind]
                    image = Image.fromarray(cv2.cvtColor(frame[y:y+height, x:x+w], cv2.COLOR_BGR2RGB))
                    aligned = align(camera_to_amber(image), kind)
                    if aligned is None:
                        break
                    crops[kind] = aligned
                if len(crops) != 2:
                    print(f'Skipping pair {i}: crop alignment failed')
                    continue
                for kind, text in (('hdg', f'{h:03d}'), ('alt', f'{a:05d}')):
                    rel = f'train/{kind}/{count:05d}.png'
                    path = args.output / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    crops[kind].save(path)
                    writer.writerow({'image_path': rel, 'kind': kind, 'text': text,
                                     'split': 'train', 'session_id': f'auto_{i:04d}',
                                     'source_image': f'webcam_{i:05d}'})
                fp.flush()
                count += 1
                print(f'{count}/{args.pairs} pairs | HDG {h:03d} ALT {a:05d}', flush=True)
    finally:
        cap.release()
    print(f'Saved {count * 2} crops. Check labels.csv and sample images before training.')


if __name__ == '__main__':
    main()
