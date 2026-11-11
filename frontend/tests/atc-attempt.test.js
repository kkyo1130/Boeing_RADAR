import test from 'node:test';
import assert from 'node:assert/strict';
import {readAtcAttempt,writeAtcAttempt} from '../src/atc-attempt.js';
test('attempt survives re-read and remains isolated per flight',t=>{
  const prior=Object.getOwnPropertyDescriptor(globalThis,'localStorage'),data=new Map();
  Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)}});
  t.after(()=>{if(prior)Object.defineProperty(globalThis,'localStorage',prior);else delete globalThis.localStorage;});
  writeAtcAttempt('A','pending');assert.equal(readAtcAttempt('A'),'pending');assert.equal(readAtcAttempt('B'),null);
  writeAtcAttempt('A','accepted-id');assert.equal(readAtcAttempt('A'),'accepted-id');
});
test('unavailable storage holds readback and refuses a new capture',t=>{
  const prior=Object.getOwnPropertyDescriptor(globalThis,'localStorage');
  Object.defineProperty(globalThis,'localStorage',{configurable:true,get(){throw new Error('denied');}});
  t.after(()=>{if(prior)Object.defineProperty(globalThis,'localStorage',prior);else delete globalThis.localStorage;});
  assert.equal(readAtcAttempt('A'),'pending');assert.throws(()=>writeAtcAttempt('A','pending'),/저장할 수 없습니다/);
});
