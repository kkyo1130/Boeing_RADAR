import test from 'node:test';
import assert from 'node:assert/strict';
import {clickGesture} from '../src/click-gesture.js';
const p=(pointerId,x=0,y=0,button=0)=>({pointerId,clientX:x,clientY:y,button});
test('single click still edits; drag returning to start does not',()=>{
 const g=clickGesture();g.down(p(1));assert.equal(g.up(p(1)),true);
 g.down(p(1));g.move(p(1,30));assert.equal(g.up(p(1)),false);
});
test('every finger in a multi-touch gesture is suppressed, then a new click works',()=>{
 for(const order of [[1,2],[2,1]]){
  const g=clickGesture();g.down(p(1));g.down(p(2));g.move(p(1,30));
  for(const id of order)assert.equal(g.up(p(id)),false);
  g.down(p(3));assert.equal(g.up(p(3)),true);
 }
});
test('unknown pointer, cancellation, lost capture and blur never activate',()=>{
 const g=clickGesture();g.down(p(1));assert.equal(g.up(p(2)),false);
 g.cancel(p(1));assert.equal(g.up(p(1)),false);
 g.down(p(1));g.down(p(2));g.cancel(p(1));assert.equal(g.up(p(2)),false);
 g.down(p(1));g.clear();assert.equal(g.up(p(1)),false);
 g.down(p(1,0,0,2));assert.equal(g.up(p(1,0,0,2)),false);
});
