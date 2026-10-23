import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server, Results;
before(async()=>{server=await createServer({server:{middlewareMode:true,watch:null,hmr:false,ws:false},appType:'custom'});Results=(await server.ssrLoadModule('/src/DemoResults.jsx')).default;});
after(async()=>{await server?.close();});
function render(result, reason, connected=true, pending=false){
  const group={result,fields:[{field:'HDG',expected:270,actual:260,result,reason}]};
  return renderToStaticMarkup(React.createElement(Results,{snapshot:{status:'ACTIVE',validation:{readback:group,setting:group}},connected,pending,transcript:'heading 260'}));
}
test('different setting remains pending until server confirms readback',()=>{const h=render('UNVERIFIED','READBACK_NOT_CONFIRMED');assert.match(h,/복창 확인이 먼저/);assert.match(h,/270°/);assert.match(h,/260°/);assert.doesNotMatch(h,/op-MISMATCH/);});
test('server mismatch highlights both values and recognized sentence',()=>{const h=render('MISMATCH','VALUE_MISMATCH');assert.match(h,/op-MISMATCH/);assert.match(h,/불일치/);assert.match(h,/heading 260/);});
test('disconnection and new recording remove previous normal presentation',()=>{for(const h of [render('NORMAL','VALUE_MATCH',false),render('NORMAL','VALUE_MATCH',true,true)]){assert.doesNotMatch(h,/op-NORMAL/);assert.match(h,/판단 보류/);}});
test('unrecognized callsign gives actionable explanation',()=>{assert.match(render('UNVERIFIED','callsign_not_recognized'),/호출부호를 인식하지 못했습니다/);});
