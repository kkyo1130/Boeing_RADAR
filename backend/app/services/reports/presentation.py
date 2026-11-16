"""Read-only grouping of equivalent consecutive report states; originals stay intact."""
from copy import deepcopy


def _field(row):
    quality=row.get('quality') or {}
    return {key:row.get(key) for key in ('value','unit','validity','reason')} | {
        'input_quality':quality.get('input_quality'),'quality_reason':quality.get('reason'),
        'score_calibrated':quality.get('score_calibrated'),'calibration_ref':quality.get('calibration_ref')}


def _signature(event):
    checks=[{key:row.get(key) for key in ('stage','field','instruction_id','expected','actual','result','reason')}
            for row in event.get('checks',[])]
    checks.sort(key=lambda row:(str(row['stage']),str(row['field']),str(row['instruction_id'])))
    related=[{key:row.get(key) for key in ('occurrence_id','stage','status','resolved_at','warning_completed')}
             for row in event.get('related_incidents',[])]
    related.sort(key=lambda row:str(row['occurrence_id']))
    return dict(event_type=event['event_type'],source=event.get('source'),roi_method=event.get('roi_method'),
        instruction_ids=sorted(event.get('instruction_ids',[])),occurrence_ids=sorted(event.get('occurrence_ids',[])),
        fields={key:_field(row) for key,row in sorted(event.get('fields',{}).items())},checks=checks,
        related_incidents=related,applied=event.get('applied'),reason=event.get('reason'),
        warning_status=event.get('warning_status'),warning_completed=event.get('warning_completed'),
        error_status=event.get('error_status'))


def timeline_groups(timeline,raw_events=()):
    raw={event['sequence']:event.get('snapshot',{}) for event in raw_events}
    groups=[];lanes={};auxiliary=0
    for original in timeline:
        if original['event_type']=='EVIDENCE_STORED':
            auxiliary+=1
            continue
        event=deepcopy(original)
        if event.get('source')=='COCKPIT':
            event['roi_method']=raw.get(event['sequence'],{}).get('payload',{}).get('roi_method')
        if event['event_type']=='INCIDENT_UPDATED':
            check=raw.get(event['sequence'],{}).get('current_check')
            if check:event['checks']=[deepcopy(check)]
            lane=('incident',tuple(sorted(event.get('occurrence_ids',[])))) if check else None
        elif event['event_type']=='INPUT_RECEIVED' and event.get('source')=='COCKPIT':
            lane=('camera',)
        else:
            lane=None
        signature=_signature(event)
        existing=lanes.get(lane) if lane else None
        if existing and existing[0]==signature:
            group=existing[1];group['count']+=1;group['last_at']=event['occurred_at'];group['sequences'].append(event['sequence'])
            continue
        # Any changed state or non-repeatable event ends the current segment.
        if lane is None or existing is not None or lane[0]=='incident':
            lanes.clear()
        group=dict(event=event,count=1,first_at=event['occurred_at'],last_at=event['occurred_at'],sequences=[event['sequence']])
        groups.append(group)
        if lane:lanes[lane]=(signature,group)
    previous_checks={};previous_related={}
    for group in groups:
        changed=[]
        for check in group['event'].get('checks',[]):
            identity=tuple(check.get(key) for key in ('stage','field','instruction_id'))
            state={key:check.get(key) for key in ('expected','actual','result','reason')}
            if previous_checks.get(identity)!=state:changed.append(deepcopy(check))
            previous_checks[identity]=state
        group['display_checks']=changed
        changed_related=[]
        for incident in group['event'].get('related_incidents',[]):
            identity=incident.get('occurrence_id')
            if previous_related.get(identity)!=incident:changed_related.append(deepcopy(incident))
            previous_related[identity]=deepcopy(incident)
        group['display_related_incidents']=changed_related
    return dict(version='report-presentation/1',groups=groups,raw_event_count=len(timeline),
                displayed_group_count=len(groups),evidence_storage_event_count=auxiliary)


def correction_groups(steps,raw_events=()):
    raw={event['sequence']:event.get('snapshot',{}) for event in raw_events}
    groups=[];previous=None
    for step in steps:
        check=raw.get(step.get('event_sequence'),{}).get('current_check')
        signature=({'state':step['state'],'verification':step.get('verification'),
                    'check':{key:check.get(key) for key in ('stage','field','instruction_id','expected','actual','result','reason')}}
                   if step['state']=='CORRECTING' and check else None)
        if signature is not None and signature==previous:
            groups[-1]['count']+=1;groups[-1]['last_at']=step['at']
        else:
            groups.append(dict(step=deepcopy(step),count=1,first_at=step['at'],last_at=step['at']))
        previous=signature
    return groups


def with_presentation(data):
    result=deepcopy(data)
    if 'safety' in result:
        result['safety']['presentation']=timeline_groups(result['safety']['timeline'],result.get('timeline',[]))
        result['safety']['presentation']['error_timeline']=error_timeline(result['safety'].get('correction_trace',[]))
        result['safety']['presentation']['correction_groups']={item['occurrence_id']:correction_groups(item['steps'],result.get('timeline',[])) for item in result['safety'].get('correction_trace',[])}
    return result


def error_timeline(incidents):
    """Four bounded milestones per incident; all source steps stay in detail/JSON."""
    result=[]
    for item in incidents:
        steps=item.get('steps',[])
        warnings=[s for s in steps if s['state']=='WARNED']
        corrections=[s for s in steps if s['state']=='CORRECTING']
        resolved=item['state']=='RESOLVED' and bool(item.get('resolved_at'))
        milestones=[dict(state='DETECTED',at=item.get('detected_at'),count=1),
            dict(state='WARNED',at=warnings[0]['at'] if warnings and item.get('warning_completed') else None,
                 count=len(warnings) if item.get('warning_completed') else 0),
            dict(state='CORRECTING',at=corrections[0]['at'] if corrections else None,
                 last_at=corrections[-1]['at'] if corrections else None,count=len(corrections)),
            dict(state='RESOLVED' if resolved else item['state'],at=item.get('resolved_at') if resolved else None,count=1)]
        result.append(dict(occurrence_id=item['occurrence_id'],stage=item['stage'],field=item['field'],milestones=milestones))
    return result
