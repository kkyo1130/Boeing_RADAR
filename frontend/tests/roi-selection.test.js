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
import {groupTimeline} from '../src/report-timeline.js';
test('equivalent adjacent camera observations group without hiding transitions or other instructions',()=>{
 const event={event_type:'INPUT_RECEIVED',source:'COCKPIT',instruction_ids:['a'],fields:{ALT:{value:3000,validity:'VALID'}}};
 const groups=groupTimeline([{...event,sequence:1},{...event,sequence:2},{event_type:'INCIDENT_UPDATED',sequence:3},{...event,sequence:4},{...event,instruction_ids:['b'],sequence:5}]);
 assert.deepEqual(groups.map(g=>g.events.length),[2,1,1,1]);
});

test('report uses server grouping across evidence entries and retains raw members',()=>{
 const events=[{sequence:1,event_type:'INPUT_RECEIVED',source:'COCKPIT'},{sequence:2,event_type:'EVIDENCE_STORED'},{sequence:3,event_type:'INPUT_RECEIVED',source:'COCKPIT'}];
 const presentation={version:'report-presentation/1',groups:[{event:events[0],sequences:[1,3],count:2,first_at:'a',last_at:'b',display_checks:[]}]};
 const groups=groupTimeline(events,presentation);
 assert.equal(groups.length,1);assert.deepEqual(groups[0].events.map(e=>e.sequence),[1,3]);assert.equal(events.length,3);
});
