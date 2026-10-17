"""Synthetic HTTP rehearsal; creates labelled fixture flights, never real sensor evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def run(server):
    def request(path, data=None):
        request = Request(server.rstrip('/') + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    reports = []
    for scenario in ("normal", "readback_error", "setting_error", "unreadable"):
        flight = request('/api/flights/start', {})['flight_id']
        c = request(f'/api/v1/flights/{flight}/clearances', {})['clearance_id']
        request(f'/api/v1/clearances/{c}/validation-settings', {
            "confirmed": True, "confirmed_by": "synthetic-rehearsal", "minimum_model_score": .5,
            "rule_policy": json.loads((ROOT / 'contracts/rule-policy-demo.json').read_text()),
            "atc_context": {"expected_callsign": "RADAR1", "expected_conditions": [], "expected_ordered_actions": []}})
        def send(source, previous=None, uncertain=False):
            body = json.loads((ROOT / 'contracts/examples/observation-v1/normal.json').read_text())
            stamp = datetime.now(timezone.utc).isoformat()
            token = str(uuid4())
            body.update(event_id=f'event-{token}', observation_id=f'obs-{token}', sample_id=f'synthetic-{token}',
                flight_id=flight, clearance_id=c, channel_id=f'synthetic-{source}', source=source,
                captured_at=stamp, processed_at=stamp, input_mode='fixture')
            if source != 'COCKPIT':
                body['speech'] = {"transcript": "synthetic rehearsal", "callsign": "RADAR1",
                    "callsign_reason": None, "role_basis": "labelled_fixture", "conditions": [], "ordered_actions": []}
                for evidence in body['evidence']:
                    evidence.update(kind='audio', roi=None)
            if previous:
                body.update(intent='correction', supersedes_observation_id=previous['observation_id'])
            elif scenario == 'readback_error' and source == 'READBACK':
                body['fields']['heading'].update(value=290, raw_text='290')
            elif scenario == 'setting_error' and source == 'COCKPIT':
                body['fields']['altitude'].update(value=3500, raw_text='3500')
            if uncertain or scenario == 'unreadable' and source == 'COCKPIT':
                body['fields']['altitude'].update(value=None, reason='unreadable', raw_text=None)
            receipt = request('/api/v1/observations', body)
            if not receipt['accepted']:
                raise AssertionError(receipt)
            return body
        send('ATC')
        rb = send('READBACK')
        cp = send('COCKPIT')
        initial = request(f'/api/v1/clearances/{c}')
        expected = 'NORMAL' if scenario == 'normal' else 'UNVERIFIED' if scenario == 'unreadable' else 'MISMATCH'
        assert initial['verdict'] == expected, initial
        if expected == 'MISMATCH':
            current = request(f'/api/v1/flights/{flight}/report')
            incident = current['incidents'][0]
            request(f'/api/v1/incidents/{incident["incident_id"]}/actions', {
                'action': 'ACKNOWLEDGED', 'actor': 'synthetic-rehearsal', 'reason': 'fixture_reviewed'})
            source, previous = ('READBACK', rb) if scenario == 'readback_error' else ('COCKPIT', cp)
            uncertain = send(source, previous, uncertain=True)
            assert request(f'/api/v1/flights/{flight}/report')['incidents'][0]['status'] == 'OPEN'
            send(source, uncertain)
            assert request(f'/api/v1/clearances/{c}')['verdict'] == 'NORMAL'
        request(f'/api/flights/{flight}/end', {})
        report = request(f'/api/v1/flights/{flight}/report.json')
        assert report['terminal']
        reports.append({'scenario': scenario, 'input_kind': 'synthetic_fixture', 'report': report})
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.server)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('PASS: 4 synthetic scenarios, uncertain corrections, fresh resolution and report export')
