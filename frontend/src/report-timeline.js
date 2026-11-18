// Group only adjacent, equivalent camera inputs. State transitions remain individual events.
export function groupTimeline(events,presentation){
 if(presentation?.version==='report-presentation/1'&&Array.isArray(presentation.groups)){
  const bySequence=new Map(events.map(event=>[event.sequence,event]));
  return presentation.groups.map(group=>({...group,events:group.sequences.map(sequence=>bySequence.get(sequence)).filter(Boolean)}));
 }
 const groups=[];
 for(const event of events){
  const key=event.event_type==='INPUT_RECEIVED'&&event.source==='COCKPIT'?JSON.stringify([event.instruction_ids,event.fields,event.reason,event.applied]):null;
  const last=groups.at(-1);
  if(key&&last?.key===key)last.events.push(event);
  else groups.push({key,events:[event]});
 }
 return groups;
}

// Bounded incident summary; the full timeline remains available separately.
export function errorTimeline(incidents,presentation){
 if(Array.isArray(presentation?.error_timeline))return presentation.error_timeline;
 return incidents.map(item=>{
  const warnings=(item.steps||[]).filter(s=>s.state==='WARNED');
  const corrections=(item.steps||[]).filter(s=>s.state==='CORRECTING');
  const resolved=item.state==='RESOLVED'&&Boolean(item.resolved_at);
  return {occurrence_id:item.occurrence_id,stage:item.stage,field:item.field,milestones:[
   {state:'DETECTED',at:item.detected_at,count:1},
   {state:'WARNED',at:item.warning_completed?warnings[0]?.at:null,count:item.warning_completed?warnings.length:0},
   {state:'CORRECTING',at:corrections[0]?.at,last_at:corrections.at(-1)?.at,count:corrections.length},
   {state:resolved?'RESOLVED':item.state,at:resolved?item.resolved_at:null,count:1}
  ]};
 });
}
