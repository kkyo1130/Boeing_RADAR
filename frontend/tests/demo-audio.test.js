import test from 'node:test';
import assert from 'node:assert/strict';
import {wav,base64,microphone} from '../src/demo-audio.js';
test('PCM WAV retains silence, sign, clipping and actual sample rate',()=>{
  const bytes=wav(new Float32Array([0,1,-1,2,-2]),48000),v=new DataView(bytes.buffer);
  assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');assert.equal(v.getUint32(24,true),48000);
  assert.equal(v.getUint32(40,true),10);assert.equal(v.getInt16(44,true),0);assert.equal(v.getInt16(46,true),32767);assert.equal(v.getInt16(48,true),-32767);
  assert.deepEqual(Buffer.from(base64(bytes),'base64'),Buffer.from(bytes));
});

test('direct controller and pilot speech enable processing; playback disables it',async t=>{
  const constraints=[];
  const track={applyConstraints:async value=>constraints.push(value),stop(){}};
  const stream={getAudioTracks:()=>[track],getTracks:()=>[track]};
  const oldMedia=Object.getOwnPropertyDescriptor(navigator,'mediaDevices');
  const oldContext=Object.getOwnPropertyDescriptor(globalThis,'AudioContext');
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>stream}});
  const node=()=>({connect(){},disconnect(){},gain:{value:1}});
  globalThis.AudioContext=class {
    destination={};sampleRate=16000;
    async resume(){} close(){} createMediaStreamSource(){return node();}
    createScriptProcessor(){return node();} createGain(){return node();}
  };
  t.after(()=>{
    if(oldMedia)Object.defineProperty(navigator,'mediaDevices',oldMedia);else delete navigator.mediaDevices;
    if(oldContext)Object.defineProperty(globalThis,'AudioContext',oldContext);else delete globalThis.AudioContext;
  });
  const mic=await microphone('',()=>{});
  await mic.setCaptureMode('ATC','microphone_live');
  await mic.setCaptureMode('ATC','microphone_playback');
  await mic.setCaptureMode('PILOT');
  assert.deepEqual(constraints,[{echoCancellation:true,noiseSuppression:true},{echoCancellation:false,noiseSuppression:false},{echoCancellation:true,noiseSuppression:true}]);
  mic.close();
});
