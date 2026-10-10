"""Offline synthetic smoke evaluation; labels never enter OCR."""
import argparse
import json
from pathlib import Path
from radar_vision.poc import load_config, recognize

parser = argparse.ArgumentParser()
parser.add_argument('--ocr-binary', required=True)
parser.add_argument('--output-dir', default='vision/output/evaluation')
args = parser.parse_args()
root = Path(__file__).parent
config = load_config(root.parent / 'configs/synthetic.json')
summary = []
for label in json.loads((root / 'labels.json').read_text()):
    observation = recognize(root / 'fixtures' / label['image'], config,
                            args.ocr_binary, args.output_dir)
    actual = {name: field['value'] for name, field in observation['fields'].items()}
    checked = 'evaluate' not in label
    passed = all(actual[name] == label[name] for name in actual) if checked else None
    summary.append({'image':label['image'], 'actual':actual, 'passed':passed,
                    'reasons':{name:field['reason'] for name,field in observation['fields'].items()}})
Path(args.output_dir).mkdir(parents=True, exist_ok=True)
Path(args.output_dir, 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
raise SystemExit(1 if any(row['passed'] is False for row in summary) else 0)
