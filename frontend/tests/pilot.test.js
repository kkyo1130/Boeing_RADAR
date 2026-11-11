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
