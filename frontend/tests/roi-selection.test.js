import test from 'node:test';
import assert from 'node:assert/strict';
import {framePoint,selectedBox} from '../src/roi-selection.js';
test('ROI conversion follows scaled video, clamps bounds and supports reverse drag',()=>{
 const rect={left:100,top:50,width:960,height:540};
 assert.deepEqual(framePoint(580,320,rect,1920,1080),[960,540]);
 assert.deepEqual(framePoint(-20,900,rect,1920,1080),[0,1080]);
 assert.deepEqual(selectedBox([100,100],[10,20]),[10,20,100,100]);
 assert.throws(()=>selectedBox([10,10],[15,15]));
 assert.throws(()=>framePoint(0,0,{...rect,width:0},1920,1080));
});
