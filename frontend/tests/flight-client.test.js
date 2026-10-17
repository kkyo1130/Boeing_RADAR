import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SnapshotGate, dueRevalidations, numberLabel, statusLabel, request, restartFlightState, readingFor, reconciledActionError } from '../src/flight-client.js';

const field = (overrides = {}) => ({ field: 'ALT', instruction_id: 'A', expected: 3000, actual: 3000,
  result: 'NORMAL', reason: 'VALUE_MATCH', wait_until: null, ...overrides });
function snapshot(overrides = {}) {
  return { schema_version: '2', flight_id: 'FLT2-a', revision: 3, status: 'ACTIVE', callsign: 'RADAR123',
    result: 'NORMAL', targets: {}, current: { READBACK: {}, COCKPIT: {} }, channels: {},
    validation: { result: 'NORMAL', phase: 'MONITORING', readback: { result: 'NORMAL', fields: [field()] },
      setting: { result: 'NORMAL', fields: [field()] } }, ...overrides };
}

test('older revisions and delayed requests cannot replace newer snapshot', () => {
  const gate = new SnapshotGate('FLT2-a');
  assert.equal(gate.accept(snapshot(), 4), true);
  assert.equal(gate.accept(snapshot({ revision: 2 }), 5), false);
  assert.equal(gate.accept(snapshot({ revision: 4 }), 3), false);
  assert.equal(gate.snapshot.revision, 3);
});
test('same revision permits newer server freshness result', () => {
  const gate = new SnapshotGate('FLT2-a'); gate.accept(snapshot(), 1);
  assert.equal(gate.accept(snapshot({ result: 'UNVERIFIED' }), 2), true);
  assert.equal(gate.snapshot.result, 'UNVERIFIED');
});
test('another flight and invalid shape are rejected', () => {
  const gate = new SnapshotGate('FLT2-a');
  for (const data of [null, {}, snapshot({ flight_id: 'FLT2-b' }), snapshot({ revision: -1 }), snapshot({ result: 'VERIFIED' })]) {
    assert.throws(() => gate.accept(data, 1));
  }
});
test('ended session cannot revert to active', () => {
  const gate = new SnapshotGate('FLT2-a'); gate.accept(snapshot({ status: 'ENDED' }), 1);
  assert.equal(gate.accept(snapshot({ revision: 4 }), 2), false);
});
test('transport loss hides every normal badge without changing server result', () => {
  assert.equal(statusLabel('NORMAL', false), '판단 보류');
  assert.equal(statusLabel('MISMATCH', false), '판단 보류');
  assert.equal(statusLabel('UNVERIFIED'), '판단 보류');
});
test('zero heading and null are distinct; feet never implicitly becomes FL', () => {
  assert.equal(numberLabel(0, 'HDG'), '0°');
  assert.equal(numberLabel(null, 'ALT'), '확인 불가');
  assert.equal(numberLabel(4000, 'ALT'), '4,000 ft');
});
test('timer requests server revalidation once per instruction/deadline, never local verdict', () => {
  const s = snapshot(), completed = new Set();
  s.validation.setting.fields = [field({ wait_until: '2026-10-18T00:00:05Z' }),
    field({ field: 'HDG', wait_until: '2026-10-18T00:00:05Z' })];
  assert.deepEqual(dueRevalidations(s, completed), []); // Browser clock cannot end the wait.
  s.validation.setting.fields.forEach(row => { row.reason = 'ADJUSTMENT_DEADLINE_MISMATCH'; });
  const due = dueRevalidations(s, completed);
  assert.equal(due.length, 1); due.forEach(key => completed.add(key));
  assert.deepEqual(dueRevalidations(s, completed), []);
  assert.deepEqual(dueRevalidations({ ...s, status: 'ENDED' }, new Set()), []);
});
test('HTTP errors retain server rejection and do not silently become success', async () => {
  const previous = global.fetch;
  global.fetch = async () => new Response(JSON.stringify({ message: 'Available: RADAR123' }), { status: 422 });
  try { await assert.rejects(request('/api/v2/flights'), /Available: RADAR123/); }
  finally { global.fetch = previous; }
});
test('request timeout and cancellation abort a stuck connection', async () => {
  const previous = global.fetch;
  global.fetch = (_, { signal }) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))));
  try { await assert.rejects(request('/api/v2/flights/x/state', { timeout: 10 }), /서버 응답/); }
  finally { global.fetch = previous; }
});
test('same flight retry preserves historical snapshot and time but clears current connection', () => {
  const previous = { snapshot: snapshot(), connected: false, error: 'offline', receivedAt: 't0' };
  const retry = restartFlightState(previous, 'FLT2-a');
  assert.equal(retry.snapshot, previous.snapshot); assert.equal(retry.receivedAt, 't0');
  assert.equal(retry.connected, false);
  assert.equal(restartFlightState(previous, 'FLT2-b').snapshot, null);
});
test('confirmed END reconciles an action timeout; active/offline does not clear it', () => {
  assert.equal(reconciledActionError('timeout', snapshot({ status: 'ENDED' }), true), '');
  assert.equal(reconciledActionError('timeout', snapshot(), true), 'timeout');
  assert.equal(reconciledActionError('timeout', snapshot({ status: 'ENDED' }), false), 'timeout');
});
test('callsign-only attempt has its own observation timestamp without numeric fields', () => {
  const s = snapshot({ readbacks: { A: { observation_id: 'call', observed_at: 'capture-time' } } });
  const verdict = field({ field: 'CALLSIGN', observation_id: 'call' });
  assert.equal(readingFor(s, 'READBACK', verdict).observed_at, 'capture-time');
  assert.equal(readingFor(s, 'READBACK', { ...verdict, observation_id: 'other' }), null);
});
