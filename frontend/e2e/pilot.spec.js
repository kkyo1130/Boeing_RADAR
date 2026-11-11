import { test, expect } from '@playwright/test';
const row = (field, result, expected, actual, reason = 'VALUE_MISMATCH') => ({ field, result, expected, actual, reason, instruction_id: 'A', observation_id: 'obs' });
const snapshot = () => ({ schema_version: '2', flight_id: 'pilot-test', revision: 1, status: 'ACTIVE', callsign: 'RADAR123', result: 'MISMATCH', targets: {}, current: { READBACK: {}, COCKPIT: {} }, channels: {}, validation: { result: 'MISMATCH', phase: 'READBACK', readback: { result: 'MISMATCH', fields: [row('ALT', 'MISMATCH', 5000, 3000)] }, setting: { result: 'NORMAL', fields: [] } } });
for (const size of [{ width: 480, height: 320 }, { width: 800, height: 480 }, { width: 360, height: 640 }]) {
  test(`compact display ${size.width}x${size.height}: mismatch, stale, disconnect, recovery`, async ({ page }, testInfo) => {
    await page.setViewportSize(size);
    let data = snapshot(), offline = false;
    await page.route('**/api/v2/flights/pilot-test/state', route => offline ? route.abort() : route.fulfill({ json: data }));
    await page.goto('/pilot?flight=pilot-test');
    await expect(page.getByRole('heading', { name: '고도 불일치' })).toBeVisible();
    await expect(page.getByText('5,000 ft')).toBeVisible();
    await expect(page.getByText('3,000 ft')).toBeInViewport({ ratio: 1 });
    await expect(page.getByText('5,000 ft')).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`radar-pilot-${size.width}.png`), fullPage: true });
    data.result = data.validation.result = 'UNVERIFIED';
    data.reason = data.validation.reason = 'LATEST_ATC_NOT_ADOPTED';
    data.validation.phase = 'WAITING_ATC';
    await expect(page.getByText('· 새 관제 지시 확인 대기', { exact: true })).toBeInViewport({ ratio: 1 });
    await expect(page.getByRole('heading', { name: '고도 불일치' })).toBeVisible();
    await expect(page.getByText('3,000 ft')).toBeInViewport({ ratio: 1 });
    await expect(page.getByText('5,000 ft')).toBeInViewport({ ratio: 1 });
    data = snapshot();
    await expect(page.getByText('· 새 관제 지시 확인 대기', { exact: true })).toHaveCount(0);
    data.validation.setting = { result: 'MISMATCH', fields: [row('HDG', 'MISMATCH', 0, 90)] };
    await expect(page.getByRole('heading', { name: '방위 불일치' })).toBeVisible();
    await expect(page.getByText('0°', { exact: true })).toBeVisible();
    data.validation.readback.fields = [row('ALT', 'UNVERIFIED', 5000, 3000, 'STALE_OBSERVATION')];
    await expect(page.getByRole('heading', { name: '고도 확인 불가' })).toBeVisible();
    await expect(page.getByText('3,000 ft')).toHaveCount(0);
    offline = true;
    await expect(page.getByRole('heading', { name: '현재 상태 확인 불가' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '방위 불일치' })).toHaveCount(0);
    offline = false; data = snapshot();
    await page.getByRole('button', { name: '다시 연결' }).click();
    await expect(page.getByRole('heading', { name: '고도 불일치' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: '고도 불일치' })).toBeVisible();
  });
}
test('manual connection binds an explicit flight', async ({ page }) => {
  await page.route('**/api/v2/flights/pilot-test/state', route => route.fulfill({ json: snapshot() }));
  await page.goto('/pilot');
  await expect(page.getByRole('button', { name: '연결', exact: true })).toBeDisabled();
  await page.getByLabel('비행 ID').fill('pilot-test');
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page).toHaveURL(/flight=pilot-test/);
  await expect(page.getByRole('heading', { name: '고도 불일치' })).toBeVisible();
});
