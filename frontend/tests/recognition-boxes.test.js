import test from 'node:test';
import assert from 'node:assert/strict';
import { recognitionBoxes } from '../src/recognition-boxes.js';

test('three labelled boxes enclose the observed windows and project each axis', () => {
  const boxes = recognitionBoxes({hdg:[20,30,60,50],alt:[100,30,160,50]},[200,100],[1000,400]);
  assert.deepEqual(boxes.map(b => b.label), ['MCP · ALT/HDG','HDG','ALT']);
  assert.deepEqual(boxes[1].box,[100,120,300,200]);
  assert.deepEqual(boxes[2].box,[500,120,800,200]);
  assert.ok(boxes[0].box[0] < boxes[1].box[0] && boxes[0].box[2] > boxes[2].box[2]);
});
test('missing, invalid or out-of-frame observations never produce boxes', () => {
  for (const rois of [null,{}, {hdg:[1,1,5,5]}, {hdg:[1,1,5,5],alt:[8,1,20,5]}]) {
    assert.deepEqual(recognitionBoxes(rois,[10,10],[100,100]),[]);
  }
});
test('group box stays inside the video at frame edges', () => {
  const boxes=recognitionBoxes({hdg:[0,0,3,3],alt:[4,0,10,3]},[10,10],[100,100]);
  assert.equal(boxes[0].box[0],0);assert.equal(boxes[0].box[1],0);assert.equal(boxes[0].box[2],100);
});
