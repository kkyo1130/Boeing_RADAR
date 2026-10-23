import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
const example = name => JSON.parse(readFileSync(new URL(`../../contracts/examples/v2/${name}.json`, import.meta.url)));
const quality = { model_score: .9, input_quality: 'SUFFICIENT', reason: null, score_calibrated: false, calibration_ref: null };
const stamp = offset => new Date(Date.now()+(offset || 0)).toISOString();

test('v2 운영 화면에서 근거·수정·연결 복구·종료 리포트', async ({ page, request }) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/operations');
  await page.getByLabel('등록된 호출부호').fill('RADAR123');
  const started=page.waitForResponse(r => r.url().endsWith('/api/v2/flights') && r.request().method()==='POST');
  await page.getByRole('button',{name:'START FLIGHT',exact:true}).click();
  const flight=(await (await started).json()).flight_id;
  const base=`/api/v2/flights/${flight}`;
  async function post(path,data) {
    const r=await request.post(path,{data}); expect(r.ok(),await r.text()).toBeTruthy(); return r.json();
  }
  async function speech(atc) {
    const segment={...example('speech-complete'),flight_id:flight,segment_id:randomUUID(),attempt_id:randomUUID(),
      atc_input_id:atc?.atc_input_id || randomUUID(),role:atc?'PILOT':'ATC',role_basis:atc?'PILOT_PTT':'ATC_PLAYBACK',
      started_at:stamp(-20),ended_at:stamp(-10)};
    const receipt=await post(base+'/speech-segments',segment);
    const data={...example('atc-full'),flight_id:flight,observation_id:randomUUID(),
      segment_id:segment.segment_id,attempt_id:segment.attempt_id,atc_input_id:segment.atc_input_id,
      observed_at:segment.started_at,processed_at:stamp()};
    for(const value of Object.values(data.fields)) value.quality=quality;
    data.callsign.quality=quality;
    if(atc) Object.assign(data,{source:'READBACK',instruction_id:receipt.instruction_id});
    await post(base+'/observations',data); return receipt;
  }
  const atc=await speech(); await speech(atc);
  // Use repository's verified image bytes rather than browser-generated evidence.
  const image=readFileSync(new URL('../../vision/evaluation/fixtures/normal.png',import.meta.url));
  const upload=await request.post(base+'/media',{data:image,headers:{'Content-Type':'image/png'}});
  expect(upload.ok(),await upload.text()).toBeTruthy();
  const asset=await upload.json();
  async function camera(hdg=270) {
    const state=await (await request.get(base+'/state')).json();
    const data={...example('cockpit-readable'),flight_id:flight,observation_id:randomUUID(),frame_id:randomUUID(),
      observed_at:stamp(),processed_at:stamp(),target_revision:state.revision,
      evidence_refs:[{...asset,kind:'FRAME',field:null,roi:null}],evidence_unavailable_reason:null};
    for(const value of Object.values(data.fields)) value.quality=quality;
    data.fields.HDG.value=hdg; data.fields.HDG.raw_text=String(hdg);
    await post(base+'/observations',data);
  }
  await camera();
  await page.getByText('상세 검증 · 관제 이력 · 음성 안내 · 근거와 장치 상태',{exact:true}).click();
  await expect(page.getByRole('region',{name:'Cockpit 설정',exact:true}).locator('.op-section-heading .op-badge')).toHaveText('일치');
  await camera(90);
  const setting=page.getByRole('region',{name:'Cockpit 설정',exact:true});
  await expect(setting.locator('.op-section-heading .op-badge')).toHaveText('불일치');
  await setting.getByRole('button',{name:'근거 보기'}).last().click();
  await expect(page.locator('.op-evidence img')).toBeVisible();
  await setting.getByRole('button',{name:'확인했음'}).click();
  await expect(page.getByText('확인 기록을 저장했습니다. 해결 여부는 새 유효 관측으로 확인합니다.')).toBeVisible();
  await camera();
  await expect(page.getByRole('region',{name:'Cockpit 설정',exact:true}).locator('.op-section-heading .op-badge')).toHaveText('일치');
  await page.route('**/api/v2/flights/**/state',route=>route.abort());
  await expect(page.getByRole('region',{name:'Cockpit 설정',exact:true}).locator('.op-section-heading .op-badge')).toHaveText('판단 보류');
  await page.unroute('**/api/v2/flights/**/state');
  await expect(page.getByRole('region',{name:'Cockpit 설정',exact:true}).locator('.op-section-heading .op-badge')).toHaveText('일치');
  await page.getByRole('button',{name:'END FLIGHT',exact:true}).click();
  await expect(page.getByRole('heading',{name:'비행 종료 리포트'})).toBeVisible();
  await expect(page.getByRole('link',{name:'리포트 JSON 저장'})).toBeVisible();
  const report=await (await request.get(base+'/report.json')).json();
  expect(report.summary).toMatchObject({incidents:1,resolved:1,open:0});
  expect(report.snapshot.result).toBe('NORMAL');
  expect(errors).toEqual([]);
});

test('태블릿 MCP 유지',async({page})=>{
  await page.goto('/'); await expect(page.getByText('ALTITUDE',{exact:true})).toBeVisible();
});
