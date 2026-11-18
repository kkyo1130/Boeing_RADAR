"""Separate previously inspected diagnostics from a new blind final test."""
import json
from pathlib import Path
from yolo_camera_data import load_dataset,disjoint


def require_blind(root):
    meta=Path(root)/'collection.json'
    if not meta.is_file():raise ValueError(f'Blind annotation metadata missing: {root}')
    info=json.loads(meta.read_text())
    if info.get('annotation_mode')!='BLIND' or not info.get('review_complete'):
        raise ValueError(f'Completed independent blind labels required: {root}')
    return info


def retired_records(datasets):
    return [dict(root=data['root'],fingerprint=data['fingerprint'],purpose='DIAGNOSTIC_ONLY',
        image_hashes=sorted(data['hashes']),sessions=sorted(data['sessions'])) for data in datasets]


def check_final_test(test,policy):
    require_blind(test['root'])
    if not policy or not policy.get('retired_tests'):
        raise ValueError('Final test requires a training manifest that explicitly retires previously used tests')
    for old in policy['retired_tests']:
        if set(old['image_hashes'])&test['hashes'] or set(old['sessions'])&set(test['sessions']):
            raise ValueError('Previously inspected test images/sessions are DIAGNOSTIC_ONLY, not a final test')
