import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server, module;
const selected = { flight_id: 'FLT-a', instruction_id: 'A', observation_id: 'obs', stage: 'READBACK', field: 'ALT' };
before(async () => {
  server = await createServer({ server: { middlewareMode: true, watch: null, ws: false }, appType: 'custom' });
  module = await server.ssrLoadModule('/src/EvidencePanel.jsx');
});
after(async () => { await server?.close(); });
test('panel binds flight, stage, field, instruction and observation, never another source', () => {
  const snapshot = { flight_id: 'FLT-a', validation: { readback: { fields: [{ ...selected }] } } };
  assert.equal(module.selectionMatches(snapshot, selected), true);
  for (const key of Object.keys(selected)) {
    const changed = { ...selected, [key]: key === 'stage' ? 'SETTING' : 'other' };
    if (key === 'stage') snapshot.validation.setting = { fields: [] };
    assert.equal(module.selectionMatches(snapshot, changed), false);
  }
});
test('media URLs must be scoped same-origin API paths; external/active URLs are rejected', () => {
  for (const url of ['https://example.com/x.png','javascript:alert(1)','data:image/png,xxx','/api/v2/flights/other/evidence/obs/media/x','/api/v2/flights/FLT-a/evidence/old/media/x']) {
    assert.equal(module.safeMediaUrl(url, selected), null);
  }
  const url = '/api/v2/flights/FLT-a/evidence/obs/media/OBSERVED/image?stage=READBACK';
  assert.equal(module.safeMediaUrl(url, selected), url);
});
test('missing evidence remains explicit without blocking correction guidance', () => {
  const group = { observation_id: 'obs', observed_at: null, transcript: 'Radar <script>one</script>', reading: null, assets: [], evidence_unavailable_reason: 'fixture_has_no_media' };
  const html = renderToStaticMarkup(React.createElement(module.EvidenceContents, { selected, data: { groups: { OBSERVED: group } } }));
  assert.match(html, /근거 자료가 없습니다/); assert.match(html, /시각 미상/);
  assert.doesNotMatch(html, /<script>/); assert.match(html, /&lt;script&gt;/);
});
test('audio uses explicit native controls and never autoplays; unavailable image is explained', () => {
  const group = { observation_id: 'obs', observed_at: 'time', assets: [
    { evidence_id: 'audio', kind: 'AUDIO', url: '/api/v2/flights/FLT-a/evidence/obs/media/OBSERVED/audio' },
    { evidence_id: 'image', kind: 'ROI', url: null, unavailable_reason: 'MEDIA_NOT_AVAILABLE' },
    { evidence_id: 'roi', kind: 'ROI', roi: [0,0,20,20], url: '/api/v2/flights/FLT-a/evidence/obs/media/OBSERVED/roi' } ] };
  const html = renderToStaticMarkup(React.createElement(module.EvidenceContents, { selected, data: { groups: { OBSERVED: group } } }));
  assert.match(html, /<audio/); assert.match(html, /controls=""/); assert.doesNotMatch(html, /autoPlay/);
  assert.match(html, /MEDIA_NOT_AVAILABLE/); assert.match(html, /ALT ROI 근거 이미지/); assert.match(html, /ROI 0, 0, 20, 20/);
});
