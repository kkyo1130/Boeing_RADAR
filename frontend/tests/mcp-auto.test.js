import test from 'node:test';
import assert from 'node:assert/strict';
import { createMcpState } from '../src/mcpAutoPlugin.js';
test('only exact selected display ACK unlocks; timeout, update, restart invalidate', () => {
 let now=100; const store=createMcpState(()=>now);
 const a=store.set({heading:120,altitude:5500,client:'tablet'});
 assert.equal(a.ready,false);
 for(const patch of [{client:'desktop'},{heading:270},{seq:'old'},{altitude:3000}])
   assert.throws(()=>store.ack({...a,...patch}));
 assert.equal(store.ack(a).ready,true);
 now+=1200; assert.equal(store.get().ready,false);
 assert.equal(store.ack(a).ready,true);
 const b=store.set({heading:6,altitude:36000,client:'tablet'});
 assert.equal(b.ready,false); assert.throws(()=>store.ack(a));
 assert.notEqual(createMcpState().set({heading:6,altitude:36000,client:'tablet'}).seq,b.seq);
});
test('invalid values and absent target rejected',()=>{
 const s=createMcpState();
 for(const data of [{heading:360,altitude:5500,client:'t'},{heading:120,altitude:100000,client:'t'},
 {heading:120,altitude:5500}]) assert.throws(()=>s.set(data));
});
