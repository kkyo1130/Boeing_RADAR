import test from 'node:test';
import assert from 'node:assert/strict';
import {advance} from '../src/ocr-stability.js';
test('three consecutive equal frames including zero stabilize; failures and gaps reset',()=>{
 let s=advance([],'000',100,0);assert.equal(s.status,'CHECK');
 s=advance(s.history,'000',200,100);s=advance(s.history,'000',300,200);assert.equal(s.status,'STABLE');
 assert.equal(advance(s.history,null,400,300).value,null);
 assert.equal(advance(s.history,'000',2000,300).status,'CHECK');
 assert.equal(advance(s.history,'001',400,300).status,'CHECK');
});
