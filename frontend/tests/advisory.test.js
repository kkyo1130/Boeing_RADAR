import test from 'node:test';
import assert from 'node:assert/strict';
import { AdvisoryPlayer } from '../src/advisory-player.js';
import { audioFocus } from '../src/audio-focus.js';
const deferred = () => { let resolve; const promise = new Promise(r => { resolve=r; }); return {promise,resolve}; };
function fixture({ load, failReport = false } = {}) {
  const calls=[], sources=[]; let reports=0;
  const candidate={candidate_id:'ADV-one',text:'고도와 방위 설정을 확인하세요',asset_url:'/voice/both.wav',occurrence_ids:['INC-alt','INC-hdg']};
  const context={state:'running',resume:async()=>{},close:async()=>{},destination:{},decodeAudioData:async()=>({duration:1}),createBufferSource(){
    const source={connect(){},start(){this.started=true;},stop(){this.stopped=true;this.onended?.();}};sources.push(source);return source;
  }};
  const request=async(url,opts)=>{
    calls.push({url,...opts});
    if(url.endsWith('/claims'))return {...candidate,attempt_id:'attempt1',status:'PLAYING',started_at:'2026-10-18T00:00:00Z',lease_until:'2026-10-18T00:00:10Z'};
    if(url.includes('/attempts/')&&failReport&&reports++===0)throw new Error('response lost');
    return {};
  };
  const p=new AdvisoryPlayer({flightId:'flight1',request,contextFactory:()=>context,fetchAudio:load|| (async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(1)}))});
  const snapshot={flight_id:'flight1',status:'ACTIVE',voice:{inputs:[],active_attempt:null,candidates:[candidate]}};
  p.update(snapshot,true);
  return {p,context,calls,sources,snapshot,candidate};
}
test('user enables playback; full combined sentence alone reports completion',async()=>{
  const f=fixture();await f.p.tick();assert.equal(f.calls.length,0);await f.p.enable();await f.p.tick();
  assert.ok(f.sources[0].started);f.sources[0].onended();await Promise.resolve();assert.equal(f.calls.at(-1).body.status,'COMPLETED');f.p.close();
});
test('priority stop is synchronous; input starts only after server accepts',async()=>{
  const f=fixture();await f.p.enable();await f.p.tick();const response=deferred();const original=f.p.request;
  f.p.request=(url,opts)=>url.endsWith('/inputs')?response.promise:original(url,opts);
  let started=false;const begin=f.p.begin('ATC',()=>{started=true;});assert.ok(f.sources[0].stopped);assert.equal(started,false);
  response.resolve({});const input=await begin;assert.equal(started,true);assert.equal(f.calls.at(-1).body.status,'INTERRUPTED');await f.p.end(input);f.p.close();
});
test('interrupt during loading prevents late playback and false completion',async()=>{
  const wait=deferred();const f=fixture({load:()=>wait.promise});await f.p.enable();const tick=f.p.tick();await Promise.resolve();f.p.stop();
  wait.resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(1)});await tick;assert.equal(f.sources.length,0);assert.equal(f.calls.at(-1).body.status,'INTERRUPTED');f.p.close();
});
test('new instruction or lost connection immediately stops source',async()=>{
  const f=fixture();await f.p.enable();await f.p.tick();f.p.update({...f.snapshot,voice:{...f.snapshot.voice,candidates:[]}},true);
  assert.ok(f.sources[0].stopped);assert.equal(f.calls.at(-1).body.status,'INTERRUPTED');f.p.close();
});
test('asset failure stays incomplete until explicit retry',async()=>{
  const f=fixture({load:async()=>({ok:false})});await f.p.enable();await f.p.tick();assert.equal(f.p.enabled,false);
  assert.equal(f.calls.at(-1).body.status,'FAILED');assert.equal(f.sources.length,0);f.p.close();
});
test('autoplay rejection disables guidance',async()=>{
  const f=fixture();f.context.resume=async()=>{throw new Error('blocked');};await f.p.enable();await f.p.tick();assert.equal(f.p.enabled,false);assert.equal(f.calls.length,0);f.p.close();
});
test('lost completion response blocks new claim and retries identical result',async()=>{
  const f=fixture({failReport:true});await f.p.enable();await f.p.tick();f.sources[0].onended();await new Promise(r=>setTimeout(r,0));
  assert.ok(f.p.pendingResult);await f.p.tick();assert.equal(f.calls.filter(c=>c.url.endsWith('/claims')).length,1);
  const results=f.calls.filter(c=>c.url.includes('/attempts/'));assert.equal(results.length,2);assert.deepEqual(results[0].body,results[1].body);f.p.close();
});
test('blocked input neither starts recording nor queues it',async()=>{
  const f=fixture();f.p.request=async()=>{throw Object.assign(new Error('blocked'),{status:409});};let started=false;
  assert.equal(await f.p.begin('PILOT',()=>{started=true;}),null);assert.equal(started,false);assert.equal(f.p.inputs.size,0);f.p.close();
});
test('evidence yields to ATC; guidance stops before evidence begins',async()=>{
  const f=fixture();const unregister=audioFocus.register(f.p);await f.p.enable();await f.p.tick();let paused=0,played=0;
  const media={pause(){paused++;},async play(){played++;}};await audioFocus.startEvidence(media);assert.ok(f.sources[0].stopped);assert.equal(played,1);
  await audioFocus.begin('ATC',()=>{assert.equal(paused,2);});assert.ok(f.calls.some(c=>c.body.kind==='EVIDENCE'&&c.body.action==='END'));unregister();f.p.close();
});
test('device suspension stops audio and never reports completion',async()=>{
  const f=fixture();await f.p.enable();await f.p.tick();f.context.state='suspended';f.context.onstatechange();
  assert.ok(f.sources[0].stopped);assert.equal(f.p.enabled,false);assert.equal(f.calls.at(-1).body.status,'FAILED');f.p.close();
});
test('lost input BEGIN response keeps suppression until explicit END recovery',async()=>{
  const f=fixture();let fail=true;const original=f.p.request;
  f.p.request=(url,opts)=>fail?Promise.reject(new Error('network lost')):original(url,opts);
  let started=false;await f.p.begin('ATC',()=>{started=true;});assert.equal(started,false);assert.equal(f.p.inputs.size,1);
  fail=false;await f.p.end([...f.p.inputs.values()][0]);assert.equal(f.p.inputs.size,0);f.p.close();
});
test('unknown BEGIN can be cleared only after server confirms token absent',async()=>{
  const f=fixture();await f.p.begin('ATC');const input=[...f.p.inputs.values()][0];
  f.p.request=async(url)=>{if(url.endsWith('/inputs'))throw Object.assign(new Error('unknown token'),{status:409});return {...f.snapshot,voice:{...f.snapshot.voice,inputs:[]}};};
  await f.p.end(input);assert.equal(f.p.inputs.size,0);f.p.close();
});
test('input adapter END targets the original owner after flight selection changes',async()=>{
  const a=fixture(),b=fixture();const unregister=audioFocus.register(a.p);const input=await audioFocus.begin('ATC');
  const unregisterB=audioFocus.register(b.p);await audioFocus.end(input);
  assert.equal(a.p.inputs.size,0);assert.equal(b.calls.length,0);unregisterB();unregister();a.p.close();b.p.close();
});
test('evidence cannot play over local or server ATC/PILOT capture or tail',async()=>{
  for(const mode of ['local','server']) {
    const f=fixture();const unregister=audioFocus.register(f.p);let played=0;
    if(mode==='local')await f.p.begin('ATC');else f.p.update({...f.snapshot,voice:{...f.snapshot.voice,inputs:[{token:'remote',kind:'PILOT'}]}},true);
    await audioFocus.startEvidence({pause(){},async play(){played++;}});
    assert.equal(played,0);assert.equal(f.calls.filter(c=>c.body.kind==='EVIDENCE').length,0);unregister();f.p.close();
  }
});
test('accepted BEGIN is ended automatically when adapter startup throws',async()=>{
  const f=fixture();assert.equal(await f.p.begin('PILOT',()=>{throw new Error('microphone unavailable');}),null);
  assert.equal(f.p.inputs.size,0);assert.deepEqual(f.calls.map(c=>c.body.action),['BEGIN','END']);f.p.close();
});
test('startup failure with lost END preserves visible suppression and retry token',async()=>{
  const f=fixture();const original=f.p.request;f.p.request=(url,opts)=>opts?.body.action==='END'?Promise.reject(new Error('lost')):original(url,opts);
  await f.p.begin('ATC',()=>{throw new Error('failed');});assert.equal(f.p.inputs.size,1);
  const input=[...f.p.inputs.values()][0];f.p.request=original;await f.p.end(input);assert.equal(f.p.inputs.size,0);f.p.close();
});
