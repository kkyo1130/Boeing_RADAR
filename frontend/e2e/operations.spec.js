import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import {groupTimeline} from '../src/report-timeline.js';
import { randomUUID } from 'node:crypto';
const example = name => JSON.parse(readFileSync(new URL(`../../contracts/examples/v2/${name}.json`, import.meta.url)));
const quality = { model_score: .9, input_quality: 'SUFFICIENT', reason: null, score_calibrated: false, calibration_ref: null };
const stamp = offset => new Date(Date.now()+(offset || 0)).toISOString();

test('v2 운영 화면에서 근거·수정·연결 복구·종료 리포트', async ({ page, request },testInfo) => {
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
  await page.locator('.op-diagnostics > summary').click();
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
  for(let i=0;i<35;i++)await camera();
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'비행 종료',exact:true}).click();
  await expect(page).toHaveURL(/\/report\?flight=/);
  await expect(page.getByRole('heading',{name:'비행 종료 리포트'})).toBeVisible();
  await expect(page.getByRole('link',{name:'리포트 JSON 저장'})).toBeVisible();
  const report=await (await page.request.get(base+'/report.json')).json();
  expect(report.summary).toMatchObject({incidents:1,resolved:1,open:0});
  expect(report.snapshot.result).toBe('NORMAL');
  expect(report.safety.timeline.length).toBeGreaterThan(30);
  const groups=groupTimeline(report.safety.timeline,report.safety.presentation);
  await expect(page.locator('.report-timeline > li:visible')).toHaveCount(Math.min(30,groups.length));
  await page.emulateMedia({media:'print'});
  await expect(page.locator('.report-timeline > li:visible')).toHaveCount(groups.length);
  await page.pdf({path:'/tmp/radar-report-print.pdf',format:'A4',printBackground:true});
  await page.emulateMedia({media:'screen'});
  await page.screenshot({path:testInfo.outputPath('flight-report.png'),fullPage:true});
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'PDF 다운로드',exact:true}).first().click();
  const download=await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^Flight_Safety_Report_.*\.pdf$/);
  const stream=await download.createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);
  await download.saveAs('/tmp/radar-report-server.pdf');
  expect(Buffer.concat(chunks).subarray(0,5).toString()).toBe('%PDF-');
  expect(errors).toEqual([]);
});

test('태블릿 MCP 유지',async({page})=>{
  await page.goto('/'); await expect(page.getByText('ALTITUDE',{exact:true})).toBeVisible();
});

test('수동 ROI 좌표 적용과 자동 전환 시 지연 응답 폐기 (모의 카메라)',async({page})=>{
 await page.route('**/api/demo/status',route=>route.fulfill({json:{camera_ready:true,speech_ready:false}}));
 let calibration,release,releaseHealth;const frames=[];
 await page.route('**/api/v2/flights/*/health-events',async route=>{if(route.request().postDataJSON().health?.reason==='camera_capture_stopped')await new Promise(resolve=>{releaseHealth=resolve;});await route.continue();});
 await page.route('**/api/demo/*/calibration',async route=>{calibration=route.request().postDataJSON();await route.fulfill({json:{token:'manual-fixture',image_size:[640,480]}});});
 await page.route('**/api/demo/*/frame',async route=>{frames.push(route.request().postDataJSON());await new Promise(resolve=>{release=resolve;});await route.fulfill({json:{fields:{altitude:{value:12345},heading:{value:123}},captured_at:'fixture'}}).catch(()=>{});});
 await page.goto('/operations');await page.getByLabel('등록된 호출부호').fill('RADAR123');await page.getByRole('button',{name:'START FLIGHT',exact:true}).click();
 await page.getByRole('button',{name:'카메라 연결',exact:true}).click();
 await page.getByRole('button',{name:'영역 직접 설정',exact:true}).click();
 const preview=page.locator('.demo-preview');await expect(preview.locator('video')).toHaveJSProperty('readyState',4);
 const box=await preview.boundingBox();
 for(const [field,x] of [['ALT',.15],['HDG',.55]]){
  await page.getByLabel('선택할 영역').selectOption(field);
  await page.mouse.move(box.x+box.width*x,box.y+box.height*.2);await page.mouse.down();await page.mouse.move(box.x+box.width*(x+.2),box.y+box.height*.4);await page.mouse.up();
 }
 await page.getByRole('button',{name:'영역 적용·인식',exact:true}).click();
 await expect.poll(()=>frames.length).toBe(1);
 expect(calibration.rois.ALT[2]-calibration.rois.ALT[0]).toBeGreaterThan(10);
 expect(calibration.rois.HDG[0]).toBeGreaterThan(calibration.rois.ALT[2]);
 expect(frames[0].media_time).toBeGreaterThanOrEqual(0);
 await page.getByRole('button',{name:'자동 탐지·인식',exact:true}).click();
 await expect(page.getByRole('button',{name:'인식 시작',exact:true})).toBeVisible();
 await expect.poll(()=>typeof releaseHealth).toBe('function');releaseHealth();release();
 await expect(page.getByRole('button',{name:'인식 시작',exact:true})).toBeVisible();
 await expect(page.getByText('최근 OCR:',{exact:false})).toHaveCount(0);
 await page.screenshot({path:'/tmp/radar-roi-ui.png',fullPage:true});
});

test('인식 영역 이동·실패 후 복구와 탭 전환 중 연속 촬영 (모의 카메라)',async({page})=>{
 await page.route('**/api/demo/status',route=>route.fulfill({json:{camera_ready:true,speech_ready:false}}));
 let calibrationCount=0,phase='first',frameCount=0;const health=[];
 const boxes={first:{ALT:[240,50,340,90],HDG:[100,50,160,90]},moved:{ALT:[360,160,460,200],HDG:[240,160,300,200]}};
 await page.route('**/api/v2/flights/*/health-events',async route=>{health.push(route.request().postDataJSON());await route.continue();});
 await page.route('**/api/demo/*/auto-calibration',async route=>{
  calibrationCount++;
  await route.fulfill({json:calibrationCount===1?{status:'SEARCHING',rois:null,token:null}:{status:'READY',rois:boxes.first,token:'moving-camera'}});
 });
 await page.route('**/api/demo/*/frame',async route=>{
  frameCount++;
  const lost=phase==='lost';
  await route.fulfill({json:{rois:lost?null:boxes[phase],tracking_status:lost?'SEARCHING':'TRACKING',fields:{altitude:{value:lost?null:3000,stable_count:lost?0:3},heading:{value:lost?null:270,stable_count:lost?0:3}},captured_at:new Date().toISOString()}});
 });
 await page.goto('/operations');await page.getByLabel('등록된 호출부호').fill('RADAR123');await page.getByRole('button',{name:'START FLIGHT',exact:true}).click();
 await page.getByRole('button',{name:'카메라 연결',exact:true}).click();await page.getByRole('button',{name:'인식 시작',exact:true}).click();
 const hdg=page.locator('[data-roi-field=HDG]');
 await expect(hdg).toBeVisible();const first=await hdg.getAttribute('style');
 phase='moved';await expect.poll(()=>hdg.getAttribute('style')).not.toBe(first);
 phase='lost';await expect(hdg).toHaveCount(0);await expect(page.getByRole('button',{name:'인식 중지',exact:true})).toBeEnabled();
 phase='moved';await expect(hdg).toBeVisible();
 const before=frameCount;
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
 await expect.poll(()=>frameCount).toBeGreaterThan(before);
 expect(health.filter(event=>event.health?.reason==='camera_capture_stopped')).toHaveLength(0);
 await page.getByRole('button',{name:'인식 중지',exact:true}).click();
});
