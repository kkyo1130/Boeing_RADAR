import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {wav} from '../src/demo-audio.js';
// Browser capture is fake here; actual Core Audio tests have separate evidence.
test.use({launchOptions:{...(process.env.RADAR_CHROMIUM_PATH?{executablePath:process.env.RADAR_CHROMIUM_PATH}:{}),args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']}});
const example=name=>JSON.parse(readFileSync(new URL(`../../contracts/examples/v2/${name}.json`,import.meta.url)));

test('ATC and pilot freeze role during capture; cancellation cannot reuse old ATC',async({page,request})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/demo/status',r=>r.fulfill({json:{speech_ready:true,scenarios:{}}}));
  await page.goto('/operations');
  await page.getByLabel('등록된 호출부호').fill('RADAR123');
  const created=page.waitForResponse(r=>r.url().endsWith('/api/v2/flights')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'START FLIGHT',exact:true}).click();
  const flight=(await(await created).json()).flight_id;
  const mode=page.getByLabel('음성 입력 모드');
  await expect(mode).toHaveValue('ATC');
  await mode.selectOption('PILOT');
  await expect(page.getByRole('button',{name:'파일럿 복창 시작',exact:true})).toBeDisabled();
  await mode.selectOption('ATC');
  await page.getByRole('button',{name:'마이크 연결',exact:true}).click();
  const start=page.getByRole('button',{name:'ATC 수음 시작',exact:true});
  await expect(start).toBeEnabled();
  let atcBody,pilotBody;
  await page.route(`**/api/demo/${flight}/atc`,async route=>{
    atcBody=route.request().postDataJSON();
    // Deterministic fake-ASR boundary: create a real server instruction from fixture.
    const seg={...example('speech-complete'),flight_id:flight,segment_id:randomUUID(),attempt_id:randomUUID(),atc_input_id:randomUUID(),role:'ATC',role_basis:'ATC_PLAYBACK',started_at:atcBody.started_at,ended_at:atcBody.ended_at};
    const receipt=await request.post(`/api/v2/flights/${flight}/speech-segments`,{data:seg});expect(receipt.ok(),await receipt.text()).toBeTruthy();
    const obs={...example('atc-full'),flight_id:flight,observation_id:randomUUID(),segment_id:seg.segment_id,attempt_id:seg.attempt_id,atc_input_id:seg.atc_input_id,observed_at:seg.started_at,processed_at:new Date().toISOString()};
    const quality={model_score:.9,input_quality:'SUFFICIENT',reason:null,score_calibrated:false,calibration_ref:null};
    obs.callsign.quality=quality;for(const value of Object.values(obs.fields))value.quality=quality;
    const accepted=await request.post(`/api/v2/flights/${flight}/observations`,{data:obs});expect(accepted.ok(),await accepted.text()).toBeTruthy();
    await route.fulfill({json:{role:'ATC',atc_input_id:seg.atc_input_id,transcript:'ATC fixture transcript',quality_reason:null}});
  });
  const source=Buffer.from(wav(Float32Array.from({length:32000},(_,i)=>.1*Math.sin(i/10)),16000));
  await page.getByLabel('재생할 실제 관제 녹음파일').setInputFiles({name:'synthetic-ui-test.wav',mimeType:'audio/wav',buffer:source});
  await page.getByRole('button',{name:'선택 파일 재생 + 마이크 수음',exact:true}).click();
  await expect(mode).toBeDisabled();
  await expect(page.getByRole('button',{name:'선택 파일 재생 + 마이크 수음',exact:true})).toBeDisabled();
  // Playback completion stops the microphone after the capture tail.
  await expect(page.getByText('ATC fixture transcript',{exact:false})).toBeVisible();
  expect(atcBody.input_mode).toBe('microphone_playback');
  expect(Buffer.from(atcBody.audio,'base64').equals(source)).toBe(false); // actual capture bytes, not selected file upload
  expect(atcBody.transcript).toBeUndefined();expect(atcBody.atc_input_id).toBeUndefined();
  expect(Buffer.from(atcBody.audio,'base64').subarray(0,4).toString()).toBe('RIFF');
  await mode.selectOption('PILOT');
  const pilot=page.getByRole('button',{name:'파일럿 복창 시작',exact:true});
  await expect(pilot).toBeEnabled();
  await page.route(`**/api/demo/${flight}/readback`,route=>{
    pilotBody=route.request().postDataJSON();return route.fulfill({json:{role:'PILOT',atc_input_id:pilotBody.atc_input_id,transcript:'PILOT fixture transcript',quality_reason:null}});
  });
  await pilot.click();await expect(mode).toBeDisabled();
  await page.getByRole('button',{name:'녹음 종료 · 검증',exact:true}).click();
  await expect(page.getByText('PILOT fixture transcript',{exact:false})).toBeVisible();
  expect(pilotBody.atc_input_id).toBeTruthy();expect(pilotBody.input_mode).toBeUndefined();
  await mode.selectOption('ATC');await start.click();
  await page.getByRole('button',{name:'녹음 취소',exact:true}).click();
  await expect(mode).toBeEnabled();await mode.selectOption('PILOT');
  await expect(pilot).toBeDisabled();
  await expect(page.locator('.demo-verdict').first()).toHaveText('판단 보류');
  // A reload must not re-enable a retained instruction after a newer ATC failed.
  const retained=await (await request.get(`/api/v2/flights/${flight}/state`)).json();
  retained.validation.reason='LATEST_ATC_NOT_ADOPTED';
  await page.route(`**/api/v2/flights/${flight}/state`,r=>r.fulfill({json:retained}));
  await page.reload();await page.getByRole('button',{name:'마이크 연결',exact:true}).click();
  await mode.selectOption('PILOT');await expect(pilot).toBeDisabled();
  expect(errors).toEqual([]);
});
