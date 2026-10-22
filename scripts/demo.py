"""Synthetic v2 HTTP rehearsal, using the existing independent mock producer."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests/integration'))
from mock_producer import MockProducer


def run(server):
    reports = []
    with TemporaryDirectory(prefix='radar-demo-') as folder:
        for name in ('normal', 'readback_error', 'setting_error', 'unreadable'):
            p = MockProducer(server, Path(folder)/f'{name}.json')
            try:
                p.start()
                atc = p.segment()
                p.send(p.speech(atc))
                pilot = p.segment(atc)
                rb = p.speech(pilot)
                if name == 'readback_error':
                    rb['fields']['ALT'].update(value=4000, raw_text='4000')
                    rb['transcript'] = rb['transcript'].replace('three thousand', 'four thousand').replace('three zero zero zero', 'four zero zero zero')
                p.send(rb)
                camera = p.camera()
                camera['fields']['HDG'].update(value=270, raw_text='270')
                p.send(camera)
                if name == 'setting_error':
                    camera = p.camera()
                    camera['fields']['HDG'].update(value=90, raw_text='90')
                    p.send(camera)
                if name == 'unreadable':
                    camera = p.camera('cockpit-unreadable.json')
                    p.send(camera)
                expected = 'NORMAL' if name == 'normal' else 'UNVERIFIED' if name == 'unreadable' else 'MISMATCH'
                assert p.state()['result'] == expected, p.state()
                if expected == 'MISMATCH':
                    if name == 'readback_error':
                        p.send(p.speech(p.segment(atc)))
                    else:
                        fixed = p.camera()
                        fixed['fields']['HDG'].update(value=270, raw_text='270')
                        p.send(fixed)
                    assert p.state()['result'] == 'NORMAL', p.state()
                    assert any(i['status'] == 'RESOLVED' for i in p.state()['incidents'])
                p.request('POST', p.path+'/end', {})
                report = p.request('GET', p.path+'/report.json')
                assert report['terminal']
                reports.append(dict(scenario=name, input_kind='synthetic_fixture', report=report))
            finally:
                p.client.close()
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.server), ensure_ascii=False, indent=2)+'\n')
    print('PASS: four v2 synthetic scenarios, fresh resolution and report export')
