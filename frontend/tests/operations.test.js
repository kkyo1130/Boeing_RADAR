// Render the actual React components through Vite's JSX loader, without a second UI implementation.
import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server, Operations, Verdicts;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, watch: null, hmr: false, ws: false }, appType: 'custom' });
  ({ default: Operations, Verdicts } = await server.ssrLoadModule('/src/Operations.jsx'));
});
after(async () => { await server?.close(); });
const row = (field, expected, actual, result, reason = 'VALUE_MATCH', iid = 'A') =>
  ({ field, expected, actual, result, reason, instruction_id: iid, observation_id: 'obs', wait_until: null });
function render(rows, connected = true, source = 'COCKPIT', ended = false) {
  const snapshot = { current: { COCKPIT: { ALT: { observed_at: '2026-10-18T00:00:00Z' } }, READBACK: {} } };
  return renderToStaticMarkup(React.createElement(Verdicts, { title: '설정',
    group: { result: 'MISMATCH', fields: rows }, source, snapshot, connected, ended }));
}
test('start requires callsign and provides independent MCP link', () => {
  const html = renderToStaticMarkup(React.createElement(Operations));
  assert.match(html, /id="callsign"/); assert.match(html, /disabled="">START FLIGHT/);
  assert.match(html, /href="\/" target="_blank"/);
});
test('server mismatch and another unreadable field stay distinct', () => {
  const html = render([row('ALT', 3000, 2000, 'MISMATCH', 'ADJUSTMENT_DEADLINE_MISMATCH'),
    row('HDG', 270, null, 'UNVERIFIED', 'STALE_OBSERVATION')]);
  assert.match(html, /3,000 ft/); assert.match(html, /2,000 ft/);
  assert.match(html, /op-MISMATCH/); assert.match(html, /op-UNVERIFIED/);
  assert.match(html, /관측이 오래되어/);
});
test('offline fixture retains numbers as history with no normal badge', () => {
  const html = render([row('ALT', 3000, 3000, 'NORMAL')], false);
  assert.match(html, /3,000 ft/); assert.doesNotMatch(html, /op-NORMAL/);
  assert.match(html, /판단 보류/);
});
test('partial instruction provenance remains separate and heading zero is readable', () => {
  const html = render([row('ALT', 4000, null, 'UNVERIFIED', 'READBACK_NOT_CONFIRMED', 'B'), row('HDG', 0, 0, 'NORMAL')]);
  assert.match(html, /4,000 ft/); assert.match(html, /0°/); assert.match(html, /지시 B/); assert.match(html, /지시 A/);
});
test('server adjustment wait is shown without declaring a numeric mismatch', () => {
  const html = render([row('ALT', 4000, 3000, 'UNVERIFIED', 'INITIAL_ADJUSTMENT_WAIT')]);
  assert.match(html, /설정 변경 대기 중/); assert.match(html, /4,000 ft/);
});
test('ended view labels historical observations without current normal or reconnect request', () => {
  const html = render([row('ALT', 3000, 3000, 'NORMAL')], true, 'COCKPIT', true);
  assert.match(html, /종료 기록/); assert.match(html, /종료 시점의 관측 기록/);
  assert.doesNotMatch(html, /op-NORMAL/); assert.doesNotMatch(html, /연결 복구 후/);
});
