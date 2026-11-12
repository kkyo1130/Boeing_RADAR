import { before,after,test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
let server,SafetyReport;
before(async()=>{server=await createServer({server:{middlewareMode:true,watch:null,hmr:false,ws:false},appType:'custom'});({SafetyReport}=await server.ssrLoadModule('/src/ReportPanel.jsx'));});
after(async()=>{await server?.close();});
function report(){return {safety:{terminal:true,started_at:'2026-11-12T00:00:00Z',ended_at:'2026-11-12T01:00:00Z',generated_at:'2026-11-12T01:00:00Z',callsign:'RADAR123',provenance:'FIXTURE_PRESENT',missing_data:'미수집은 확인 불가',
summary:{instruction_count:1,normal_instruction_count:0,error_instruction_count:1,unverified_instruction_count:0,incident_count:1,resolved_count:0,unresolved_count:1,superseded_count:0,correction_rate:0},timeline:[],
classification:[{stage:'SETTING',label:'Cockpit Setting Error',count:1,ratio:1}],correction_trace:[{occurrence_id:'one',instruction_id:'atc',stage:'SETTING',field:'HDG',state:'UNRESOLVED',stored_status:'OPEN',expected:0,initial_actual:270,final_actual:null,verification:'UNVERIFIED',resolved_at:null,warning_completed:false,steps:[]}],ai_summary:{source:'RULE_BASED',text:'저장된 사건 1건'}}};}
const render=r=>renderToStaticMarkup(React.createElement(SafetyReport,{report:r,flightId:'flight'}));
test('five sections and unresolved/unknown remain explicit; heading zero preserved',()=>{const html=render(report());for(const label of ['Flight Summary','Error Timeline','Error Classification','Correction Trace','AI Safety Summary'])assert.match(html,new RegExp(label));assert.match(html,/미해결 오류 1건/);assert.match(html,/000°/);assert.match(html,/확인 불가/);assert.match(html,/규칙 기반 요약/);assert.match(html,/SAFETY TRACE/);assert.doesNotMatch(html,/boeing[\s_]+radar/i);});
test('no-error report does not claim unknown inputs are normal',()=>{const r=report();Object.assign(r.safety.summary,{incident_count:0,resolved_count:0,unresolved_count:0,correction_rate:null});r.safety.correction_trace=[];const html=render(r);assert.match(html,/저장된 오류 사건은 0건/);assert.match(html,/미수집·확인 미완료를 정상으로 간주하지 않습니다/);assert.match(html,/해당 없음/);});
test('input transcripts are escaped and long history has pagination',()=>{const r=report();r.safety.timeline=Array.from({length:31},(_,i)=>({sequence:i,occurred_at:'now',event_type:'INPUT_RECEIVED',source:'ATC',transcript:'<script>bad</script>',fields:{},checks:[],instruction_ids:[],occurrence_ids:[]}));const html=render(r);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,/1 \/ 2/);});
