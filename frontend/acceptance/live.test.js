// Consume new, real HTTP snapshots; render the actual application components.
import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server, Verdicts, VoicePanel, EvidenceContents, bundles;
before(async()=>{
  const root=process.env.RADAR_INTERFACE_ACCEPTANCE_DIR;
  assert.ok(root,'Set RADAR_INTERFACE_ACCEPTANCE_DIR to THIS test run output directory');
  const files=(await readdir(root)).filter(f=>f.endsWith('.json'));assert.equal(files.length,3,'Use a fresh output directory with exactly the three WI-04 HTTP bundles');
  bundles=await Promise.all(files.map(async f=>JSON.parse(await readFile(`${root}/${f}`,'utf8'))));
  assert.equal(new Set(bundles.map(b=>b.run_id)).size,3);
  server=await createServer({server:{middlewareMode:true,watch:null,hmr:false,ws:false},appType:'custom'});
  ({Verdicts}=await server.ssrLoadModule('/src/Operations.jsx'));
  ({default:VoicePanel}=await server.ssrLoadModule('/src/VoicePanel.jsx'));
  ({EvidenceContents}=await server.ssrLoadModule('/src/EvidencePanel.jsx'));
});
after(async()=>{await server?.close();});
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
const find=name=>bundles.flatMap(b=>b.cases).find(c=>c.name===name);
test('all HTTP cases preserve flight and occurrence identity; no device acceptance is inferred',()=>{
  assert.ok(bundles.every(b=>b.environment==='synthetic_http'&&!b.hardware_acceptance));
  assert.ok(bundles.every(b=>Number.isFinite(Date.parse(b.captured_at)) && Date.now()-Date.parse(b.captured_at)<15*60*1000 && Date.parse(b.captured_at)<=Date.now()),'Regenerate HTTP bundles; evidence must be from the current verification session');
  for(const b of bundles)for(const c of b.cases){
    const s=c.snapshot;assert.equal(s.flight_id,b.flight_id);assert.ok(b.trace.length);
    for(const item of s.voice.history)assert.ok(item.occurrence_ids.length&&item.attempt_id);
    for(const group of ['readback','setting'])assert.doesNotThrow(()=>render(Verdicts,{title:group,group:s.validation[group],source:group==='setting'?'COCKPIT':'READBACK',snapshot:s,connected:true,ended:s.status==='ENDED'}));
  }
});
test('disconnect and AVAILABLE without a frame have no camera NORMAL badges',()=>{
  for(const name of ['camera_disconnected','camera_open_without_new_frame']){
    const s=find(name).snapshot;
    const html=render(Verdicts,{title:'설정',group:s.validation.setting,source:'COCKPIT',snapshot:s,connected:true});
    assert.doesNotMatch(html,/op-NORMAL/);assert.match(html,/판단 보류/);assert.match(html,/확인 불가/);
  }
});
test('visibility then heading produces completed/interrupted/completed UI history',()=>{
  const s=find('only_second_sentence_restarted').snapshot;
  const html=render(VoicePanel,{snapshot:s,connected:true});assert.match(html,/계기판이 보이도록/);assert.match(html,/방위 설정을/);assert.match(html,/중단/);assert.match(html,/재생 완료/);
  const before=find('visibility_before_five_seconds').snapshot;
  const text=render(VoicePanel,{snapshot:before,connected:true});assert.match(text,/계기판 가림/);
});
test('live evidence carries the same reading and media URL as its verdict',()=>{
  const c=find('media_backed_mismatch'),s=c.snapshot,data=c.evidence;
  const selected={flight_id:s.flight_id,observation_id:data.observation_id,instruction_id:data.instruction_id,stage:data.stage,field:data.field};
  const html=render(EvidenceContents,{data,selected});assert.match(html,/<img/);assert.ok(html.includes(data.observation_id));
  assert.equal(data.verdict.actual,290);assert.match(html,/모델 점수는 검증된 정확도가 아닙니다/);
});
test('server restoration and END are rendered without invented current normal state',()=>{
  const restored=find('fresh_frame_recovery_silent').snapshot;assert.equal(restored.result,'NORMAL');assert.equal(restored.voice.candidates.length,0);
  const s=find('ended_no_playback').snapshot;const html=render(Verdicts,{title:'설정',group:s.validation.setting,source:'COCKPIT',snapshot:s,connected:true,ended:true});
  assert.match(html,/종료 기록/);assert.doesNotMatch(html,/op-NORMAL/);
});
