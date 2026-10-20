import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const policy = JSON.parse(readFileSync(new URL('../../contracts/rule-policy-demo.json', import.meta.url)));
const template = JSON.parse(readFileSync(new URL('../../contracts/examples/observation-v1/normal.json', import.meta.url)));

test('서버 판정·수정·리포트와 연결 끊김 보류', async ({ page, request }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/operations-v1');
  await expect(page.getByText('서버 연결됨', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'START FLIGHT' }).click();
  await expect(page.getByRole('button', { name: '새 지시 준비' })).toBeEnabled();
  await page.getByRole('button', { name: '새 지시 준비' }).click();
  await expect(page.getByText('검사 정책·호출부호·지시 문맥 확인')).toBeVisible();
  const flight = await page.getByRole('combobox').inputValue();
  const clearances = await (await request.get(`/api/v1/flights/${flight}/clearances`)).json();
  const c = clearances[0].clearance_id;
  await page.getByText('검사 정책·호출부호·지시 문맥 확인').click();
  await page.getByText('고급 정책·조건·순서 설정', { exact: true }).click();
  await page.getByLabel('검사 설정 JSON').fill(JSON.stringify({ confirmed: true, confirmed_by: 'browser-test',
    rule_policy: policy, minimum_model_score: .5, atc_context: { expected_callsign: 'RADAR1',
      expected_conditions: [], expected_ordered_actions: [] } }));
  await page.getByRole('button', { name: '설정 확인', exact: true }).click();
  await expect(page.getByLabel('검사 설정 JSON')).toHaveCount(0);
  async function send(source, altitude = 3000, previous = null) {
    const body = structuredClone(template), token = randomUUID(), stamp = new Date().toISOString();
    Object.assign(body, { flight_id: flight, clearance_id: c, source, channel_id: source,
      input_mode: 'fixture', event_id: `event-${token}`, observation_id: `obs-${token}`,
      sample_id: `sample-${token}`, captured_at: stamp, processed_at: stamp });
    body.fields.altitude.value = altitude; body.fields.altitude.raw_text = `${altitude}`;
    if (source !== 'COCKPIT') body.speech = { transcript: 'synthetic browser fixture', callsign: 'RADAR1',
      callsign_reason: null, role_basis: 'labelled_fixture', conditions: [], ordered_actions: [] };
    if (source !== 'COCKPIT') for (const e of body.evidence) { e.kind = 'audio'; e.roi = null; }
    let content, media;
    if (source === 'COCKPIT') {
      content = readFileSync(new URL('../../docs/vision/assets/mcp-reference.png', import.meta.url));
      media = 'image/png';
    } else {
      content = Buffer.alloc(32044);
      content.write('RIFF'); content.writeUInt32LE(32036, 4); content.write('WAVEfmt ', 8);
      content.writeUInt32LE(16, 16); content.writeUInt16LE(1, 20); content.writeUInt16LE(1, 22);
      content.writeUInt32LE(16000, 24); content.writeUInt32LE(32000, 28);
      content.writeUInt16LE(2, 32); content.writeUInt16LE(16, 34);
      content.write('data', 36); content.writeUInt32LE(32000, 40); media = 'audio/wav';
    }
    const upload = await request.post(`/api/v1/clearances/${c}/evidence`, { data: content, headers: { 'Content-Type': media } });
    expect(upload.ok()).toBeTruthy();
    const evidence = await upload.json(); body.evidence = [evidence];
    for (const field of Object.values(body.fields)) field.evidence_ids = [evidence.evidence_id];
    if (previous) Object.assign(body, { intent: 'correction', supersedes_observation_id: previous.observation_id });
    const response = await request.post('/api/v1/observations', { data: body });
    expect(response.ok()).toBeTruthy(); expect((await response.json()).accepted).toBe(true);
    return body;
  }
  await send('ATC'); await send('READBACK'); const bad = await send('COCKPIT', 3500);
  await expect(page.getByText('MISMATCH · SETTING_ERROR', { exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: 'COCKPIT 관측 근거' })).toBeVisible();
  await expect(page.locator('audio')).toHaveCount(2);
  await page.getByRole('button', { name: '근거 확인함' }).click();
  await send('COCKPIT', 3000, bad);
  await expect(page.getByText('NORMAL · RESOLVED', { exact: true })).toBeVisible();
  await page.route('**/api/v1/flights**', route => route.abort());
  await expect(page.getByText('판단 보류 — 서버 연결 확인 중')).toBeVisible();
  await expect(page.getByText('NORMAL · RESOLVED', { exact: true })).toHaveCount(0);
  await page.unroute('**/api/v1/flights**');
  await expect(page.getByText('NORMAL · RESOLVED', { exact: true })).toBeVisible();
  await page.route('**/api/v1/flights**', () => {}); // Stalled transport must also expire.
  await expect(page.getByText('판단 보류 — 서버 연결 확인 중')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('NORMAL · RESOLVED', { exact: true })).toHaveCount(0);
  await page.unroute('**/api/v1/flights**');
  await expect(page.getByText('NORMAL · RESOLVED', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'END FLIGHT' }).click();
  await expect(page.getByRole('heading', { name: '종료 시점 리포트' })).toBeVisible();
  const report = await (await request.get(`/api/v1/flights/${flight}/report.json`)).json();
  expect(report.summary).toMatchObject({ incidents: 1, resolved: 1, normal: 1 });
  expect(errors).toEqual([]);
});

test('기존 태블릿 화면 유지', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('ALTITUDE', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'RADAR 운영 화면' })).toHaveCount(0);
});
