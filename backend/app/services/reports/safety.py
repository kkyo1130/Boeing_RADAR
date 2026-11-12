"""Read-only presentation of stored decisions; no new safety verdicts."""
from copy import deepcopy
from app.services.reports.summary import summarize

STAGES={'READBACK':'Readback Error','SETTING':'Cockpit Setting Error'}

def build(data,flight,instructions,*,allow_ai=True):
    observations=data['observations'];events=data['timeline']
    applied_atc={r['payload'].get('atc_input_id') for r in observations if r['applied'] and r['payload'].get('source')=='ATC'}
    instruction_map={i.atc_input_id:i.instruction_id for i in instructions}
    ids={instruction_map[x] for x in applied_atc if x in instruction_map}
    incidents=list({i['occurrence_id']:i for i in data['incidents']}.values())
    by_id={i['occurrence_id']:i for i in incidents}
    ever_matched=set()
    for event in events:
        validation=event['snapshot'].get('validation',{})
        rb=validation.get('readback',{}).get('fields',[]);setting=validation.get('setting',{}).get('fields',[])
        for iid in ids:
            a=[r for r in rb if r['instruction_id']==iid];b=[r for r in setting if r['instruction_id']==iid]
            if a and b and all(r['result']=='NORMAL' for r in a+b):ever_matched.add(iid)
    error_ids={i['instruction_id'] for i in incidents}
    resolved=[i for i in incidents if i['status']=='RESOLVED' and i.get('resolution_evidence')]
    resolved_ids={i['occurrence_id'] for i in resolved}
    facts=dict(instruction_count=len(ids),normal_instruction_count=len(ever_matched-error_ids),
        error_instruction_count=len(error_ids&ids),unverified_instruction_count=len(ids-error_ids-ever_matched),
        incident_count=len(incidents),resolved_count=len(resolved),unresolved_count=len(incidents)-len(resolved),
        superseded_count=sum(i['status']=='SUPERSEDED' for i in incidents),
        readback_error_count=sum(i['stage']=='READBACK' for i in incidents),
        setting_error_count=sum(i['stage']=='SETTING' for i in incidents),
        correction_rate=(len(resolved)/len(incidents) if incidents else None))
    classification=[dict(stage=stage,label=label,count=sum(i['stage']==stage for i in incidents),
        ratio=(sum(i['stage']==stage for i in incidents)/len(incidents) if incidents else 0)) for stage,label in STAGES.items()]
    timeline=[];progress={i['occurrence_id']:[] for i in incidents};last_evidence={};recorded_incidents={}
    for event in events:
        snap=event['snapshot'];payload=snap.get('payload',{});kind=event['event_type']
        checks=[row for group in ('readback','setting') for row in snap.get('validation',{}).get(group,{}).get('fields',[])]
        linked={r.get('instruction_id') for r in checks if r.get('instruction_id')}
        if payload.get('atc_input_id') in instruction_map:linked.add(instruction_map[payload['atc_input_id']])
        if payload.get('instruction_id'):linked.add(payload['instruction_id'])
        occurrences=[]
        if kind=='INCIDENT_UPDATED' and snap.get('occurrence_id') in by_id:
            occurrence=snap['occurrence_id'];occurrences=[occurrence];linked.add(snap['instruction_id'])
            recorded_incidents[occurrence]=deepcopy(snap)
            steps=progress[occurrence]
            if not steps:steps.append(dict(state='DETECTED',at=snap['detected_at'],event_sequence=event['sequence']))
            proof=snap.get('latest_evidence') or {}
            observation=proof.get('observation_id')
            if observation and observation!=last_evidence.get(occurrence) and snap.get('reobserved_at') and snap['status'] in ('OPEN','RESOLVED'):
                steps.append(dict(state='CORRECTING',at=event['occurred_at'],verification=snap.get('current_check',{}).get('result'),event_sequence=event['sequence']))
            last_evidence[occurrence]=observation
            if snap['status']=='RESOLVED' and occurrence in resolved_ids and not any(s['state']=='RESOLVED' for s in steps):
                steps.append(dict(state='RESOLVED',at=snap['resolved_at'],event_sequence=event['sequence']))
        voice=snap.get('result',{}) if kind.startswith('VOICE_') else {}
        warning_completed=kind=='VOICE_RESULT' and voice.get('status')=='COMPLETED'
        for occurrence in voice.get('occurrence_ids',[]):
            if occurrence in by_id:
                occurrences.append(occurrence);linked.add(by_id[occurrence]['instruction_id'])
                if warning_completed and not any(x['state']=='WARNED' for x in progress[occurrence]):
                    progress[occurrence].append(dict(state='WARNED',at=voice.get('finished_at') or event['occurred_at'],event_sequence=event['sequence']))
        for check in checks:
            for occurrence,item in recorded_incidents.items():
                if (item['instruction_id'],item['stage'],item['field'])==(check.get('instruction_id'),check.get('stage'),check.get('field')):
                    if item['status']=='OPEN' or item.get('current_check',{}).get('observation_id')==check.get('observation_id'):
                        occurrences.append(occurrence)
        related=[dict(occurrence_id=occurrence,stage=recorded_incidents[occurrence]['stage'],
            status=recorded_incidents[occurrence]['status'],resolved_at=recorded_incidents[occurrence].get('resolved_at'),
            warning_completed=any(step['state']=='WARNED' for step in progress[occurrence]))
            for occurrence in sorted(set(occurrences)) if occurrence in recorded_incidents]
        timeline.append(dict(sequence=event['sequence'],occurred_at=event['occurred_at'],event_type=kind,
            instruction_ids=sorted(linked),occurrence_ids=sorted(set(occurrences)),source=payload.get('source'),
            transcript=payload.get('transcript'),fields=deepcopy(payload.get('fields',{})),checks=deepcopy(checks),
            applied=snap.get('applied'),reason=snap.get('reason'),related_incidents=related,warning_completed=warning_completed,
            warning_status=voice.get('status'),error_status=snap.get('status') if kind=='INCIDENT_UPDATED' else None))
    traces=[]
    for item in incidents:
        occurrence=item['occurrence_id'];steps=progress[occurrence]
        if not steps:steps.append(dict(state='DETECTED',at=item['detected_at'],event_sequence=None))
        # Only recorded successful playback is a warning; eligibility or disappearance is not.
        if item.get('voice_completed_at') and not any(s['state']=='WARNED' for s in steps):
            steps.append(dict(state='WARNED',at=item['voice_completed_at'],event_sequence=None))
        terminal_state='RESOLVED' if occurrence in resolved_ids else 'UNRESOLVED' if data['terminal'] else 'CORRECTING' if item.get('reobserved_at') else 'DETECTED'
        if terminal_state=='UNRESOLVED':steps.append(dict(state='UNRESOLVED',at=flight.ended_at,event_sequence=None))
        traces.append(dict(occurrence_id=occurrence,instruction_id=item['instruction_id'],stage=item['stage'],
            field=item['field'],state=terminal_state,stored_status=item['status'],detected_at=item['detected_at'],
            resolved_at=item.get('resolved_at') if occurrence in resolved_ids else None,
            warning_completed=any(s['state']=='WARNED' for s in steps),
            expected=item['first_check'].get('expected'),initial_actual=item['first_check'].get('actual'),
            final_actual=item['current_check'].get('actual'),verification=item['current_check']['result'],
            close_reason=item.get('close_reason'),steps=sorted(steps,key=lambda x:x['at'] or '')))
    fixture=any('fixture' in str(r['payload'].get('evidence_unavailable_reason','')).lower() for r in observations)
    result=dict(version='flight-safety/1',flight_id=data['flight_id'],callsign=data['callsign'],started_at=flight.started_at,
        ended_at=flight.ended_at,generated_at=data['generated_at'],terminal=data['terminal'],summary=facts,
        provenance='FIXTURE_PRESENT' if fixture else 'STORED_INPUTS_UNVERIFIED_ORIGIN',
        classification=classification,timeline=timeline,correction_trace=traces,
        missing_data='미수집 항목은 확인 불가입니다. 경고 후보와 음성 재생 완료를 구분합니다. 실제 항공 운항의 안전 인증이 아닙니다.')
    result['ai_summary']=summarize(facts,[dict(event_type=e['event_type'],occurred_at=e['occurred_at']) for e in timeline],allow_ai=allow_ai and data['terminal'])
    return result
