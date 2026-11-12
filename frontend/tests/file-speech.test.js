import test from 'node:test';
import assert from 'node:assert/strict';
import {mixToMono,decodeAudioFile,fileSpeechBody} from '../src/file-speech.js';

test('stereo is mixed from actual samples, and pilot payload binds to a specific ATC',()=>{
  assert.deepEqual([...mixToMono([new Float32Array([1,-1]),new Float32Array([-1,1])])],[0,0]);
  const atc=fileSpeechBody('ATC','bytes','start','end');
  assert.equal(atc.input_mode,'file_upload');assert.equal(atc.atc_input_id,undefined);assert.equal(atc.transcript,undefined);
  assert.equal(fileSpeechBody('PILOT','bytes','start','end','atc-123').atc_input_id,'atc-123');
  assert.throws(()=>fileSpeechBody('PILOT','bytes','start','end'),/먼저 관제/);
});

test('file decoding produces mono PCM16 WAV without requesting microphone or playback',async()=>{
  const samples=new Float32Array(1600).fill(.25);
  class Offline {
    destination={};
    async decodeAudioData(){return {length:samples.length,sampleRate:16000,numberOfChannels:2,getChannelData:()=>samples};}
    createBuffer(){const data=new Float32Array(1600);return {getChannelData:()=>data};}
    createBufferSource(){const source={connect(){},start(){}};this.source=source;return source;}
    async startRendering(){return this.source.buffer;}
  }
  const result=await decodeAudioFile({size:100,arrayBuffer:async()=>new ArrayBuffer(100)},Offline);
  const view=new DataView(result.bytes.buffer);
  assert.equal(result.duration,.1);assert.equal(view.getUint16(22,true),1);assert.equal(view.getUint32(24,true),16000);
  assert.equal(view.getInt16(44,true),8192);
});

test('oversized, unreadable and overlong files are rejected rather than truncated',async()=>{
  await assert.rejects(decodeAudioFile({size:11*1024*1024}),/10MB/);
  class Bad {async decodeAudioData(){throw Error('codec');}}
  await assert.rejects(decodeAudioFile({size:10,arrayBuffer:async()=>new ArrayBuffer(10)},Bad),/읽을 수 없습니다/);
  class Long {async decodeAudioData(){return {length:16000*31,sampleRate:16000};}}
  await assert.rejects(decodeAudioFile({size:10,arrayBuffer:async()=>new ArrayBuffer(10)},Long),/30초/);
});
