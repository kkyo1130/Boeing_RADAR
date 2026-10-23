import test from 'node:test';
import assert from 'node:assert/strict';
import {wav,base64} from '../src/demo-audio.js';
test('PCM WAV retains silence, sign, clipping and actual sample rate',()=>{
  const bytes=wav(new Float32Array([0,1,-1,2,-2]),48000),v=new DataView(bytes.buffer);
  assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');assert.equal(v.getUint32(24,true),48000);
  assert.equal(v.getUint32(40,true),10);assert.equal(v.getInt16(44,true),0);assert.equal(v.getInt16(46,true),32767);assert.equal(v.getInt16(48,true),-32767);
  assert.deepEqual(Buffer.from(base64(bytes),'base64'),Buffer.from(bytes));
});
