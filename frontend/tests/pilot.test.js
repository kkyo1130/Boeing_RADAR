import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server, Display;
before(async () => { server = await createServer({ server: { middlewareMode: true, watch: null, hmr: false, ws: false }, appType: 'custom' }); Display = (await server.ssrLoadModule('/src/Pilot.jsx')).PilotDisplay; });
after(async () => server?.close());
const row = (field, result, expected, actual, reason = 'VALUE_MISMATCH') => ({ field, result, expected, actual, reason, instruction_id: field });
function render(readback = [], setting = [], options = {}) {
  const snapshot = { status: 'ACTIVE', result: 'MISMATCH', channels: {}, validation: { phase: 'READBACK', readback: { fields: readback }, setting: { fields: setting } }, ...options.snapshot };
  return renderToStaticMarkup(React.createElement(Display, { snapshot, connected: options.connected ?? true }));
}
test('readback and MCP mismatches retain separate source labels, units and heading zero', () => {
  const html = render([row('ALT', 'MISMATCH', 5000, 3000)], [row('HDG', 'MISMATCH', 0, 90)]);
  for (const text of ['Readback', 'MCP setting', 'ATC', 'Readback', 'MCP selected', '5,000 ft', '3,000 ft', '0°', '90°']) assert.ok(html.includes(text), text);
  assert.equal((html.match(/<article /g) || []).length, 2);
});
test('stale and null values never appear as current numeric mismatches', () => {
  const html = render([], [row('ALT', 'UNVERIFIED', 5000, 3000, 'STALE_OBSERVATION'), row('HDG', 'UNVERIFIED', 0, null)]);
  assert.match(html, /Unverified/); assert.match(html, /Awaiting fresh observation/);
  assert.doesNotMatch(html, /Mismatch|3,000|0°/);
});
test('server adjustment wait is distinct from mismatch', () => {
  const html = render([], [row('ALT', 'UNVERIFIED', 5000, 3000, 'INITIAL_ADJUSTMENT_WAIT')]);
  assert.match(html, /Adjustment pending/); assert.doesNotMatch(html, /Mismatch/);
});
test('disconnect and ended sessions remove current values and normal state', () => {
  for (const options of [{ connected: false }, { snapshot: { status: 'ENDED' } }]) {
    const html = render([row('ALT', 'MISMATCH', 5000, 3000)], [], options);
    assert.doesNotMatch(html, /5,000|3,000|pilot-normal|Altitude/);
  }
});
test('normal requires explicit server normal and no unavailable device', () => {
  assert.match(render([], [], { snapshot: { result: 'NORMAL' } }), /pilot-normal/);
  const html = render([], [], { snapshot: { result: 'NORMAL', channels: { CAMERA: { status: 'DISCONNECTED' } } } });
  assert.match(html, /Camera · Disconnected/); assert.doesNotMatch(html, /pilot-normal|Matches ATC/);
});

test('overall hold reason remains visible alongside retained errors or without cards', () => {
  for (const rows of [[row('ALT', 'MISMATCH', 5000, 3000)], []]) {
    const html = render(rows, [], { snapshot: { result: 'UNVERIFIED', reason: 'LATEST_ATC_NOT_ADOPTED' } });
    assert.match(html, /Unverified/); assert.match(html, /Awaiting new ATC review/);
    assert.doesNotMatch(html, /Matches ATC/);
    if (rows.length) { assert.match(html, /Altitude/); assert.match(html, /Mismatch/); assert.match(html, /5,000 ft/); assert.match(html, /3,000 ft/); }
  }
});
test('unknown overall hold reasons have an explicit fallback', () => {
  assert.match(render([], [], { snapshot: { result: 'UNVERIFIED', reason: 'FUTURE_REASON' } }), /Unverified.*Recheck with new input/);
});
test('overall hold message is removed when offline or ended', () => {
  for (const options of [{ connected: false }, { snapshot: { status: 'ENDED' } }]) {
    const html = render([], [], { ...options, snapshot: { result: 'UNVERIFIED', reason: 'LATEST_ATC_NOT_ADOPTED', ...options.snapshot } });
    assert.doesNotMatch(html, /Awaiting new ATC review/);
  }
});

test('initial connection without a snapshot renders safely', () => {
  const html = renderToStaticMarkup(React.createElement(Display, { snapshot: null, connected: false }));
  assert.match(html, /Status unavailable/);
});

function matchedSnapshot() {
  return { status: 'ACTIVE', result: 'UNVERIFIED', reason: 'SETTING_UNVERIFIED', channels: {},
    validation: { phase: 'SETTING', readback: { result: 'NORMAL', fields: [row('ALT', 'NORMAL', 3000, 3000), row('HDG', 'NORMAL', 0, 0), row('CALLSIGN', 'NORMAL', 'RADAR123', 'RADAR123')] },
      setting: { result: 'UNVERIFIED', fields: [row('ALT', 'UNVERIFIED', 3000, null, 'INPUT_NOT_AVAILABLE')] } } };
}
test('completed readback stays visible while camera input is missing, without overall normal', () => {
  const html = render([], [], {snapshot: matchedSnapshot()});
  for (const value of ['Readback matched', '3,000 ft', '0°', 'RADAR123', 'MCP setting not verified', 'Awaiting camera input']) assert.ok(html.includes(value), value);
  assert.doesNotMatch(html, /pilot-normal|Matches ATC/);
});
test('readback success disappears for a new ATC, unverified readback, unavailable speech, disconnect or ended flight', () => {
  const cases = [
    s => {s.validation.phase = 'WAITING_ATC'; s.reason = 'LATEST_ATC_NOT_ADOPTED';},
    s => {s.validation.phase = 'READBACK'; s.reason = 'LATEST_READBACK_UNVERIFIED';},
    s => {s.validation.readback.result = 'UNVERIFIED'; s.validation.readback.fields[0].result = 'UNVERIFIED';},
    s => {s.channels.MICROPHONE = {status: 'DISCONNECTED'};},
    s => {s.channels.SPEECH_API = {status: 'DEGRADED'};},
    s => {s.status = 'ENDED';},
  ];
  for (const change of cases) {const snapshot = matchedSnapshot(); change(snapshot); assert.doesNotMatch(render([], [], {snapshot}), /Readback matched|3,000 ft|0°/);}
  assert.doesNotMatch(render([], [], {snapshot: matchedSnapshot(), connected: false}), /Readback matched|3,000 ft|0°/);
});
