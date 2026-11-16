// Group only adjacent, equivalent camera inputs. State transitions remain individual events.
export function groupTimeline(events){
 const groups=[];
 for(const event of events){
  const key=event.event_type==='INPUT_RECEIVED'&&event.source==='COCKPIT'?JSON.stringify([event.instruction_ids,event.fields,event.reason,event.applied]):null;
  const last=groups.at(-1);
  if(key&&last?.key===key)last.events.push(event);
  else groups.push({key,events:[event]});
 }
 return groups;
}
