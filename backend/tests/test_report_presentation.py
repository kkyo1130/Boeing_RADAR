from copy import deepcopy
from app.services.reports.presentation import timeline_groups,with_presentation


def camera(sequence,value=270,result='NORMAL',instruction='a',score=.9):
    return dict(sequence=sequence,occurred_at=str(sequence),event_type='INPUT_RECEIVED',source='COCKPIT',
        instruction_ids=[instruction],occurrence_ids=[],fields={'HDG':dict(value=value,unit='deg',validity='VALID' if value is not None else 'UNREADABLE',reason=None if value is not None else 'blur',quality={'model_score':score,'input_quality':'SUFFICIENT' if value is not None else 'INSUFFICIENT'})},
        checks=[dict(stage='SETTING',field='HDG',instruction_id=instruction,expected=270,actual=value,result=result,reason=result,observation_id=f'obs{sequence}')],related_incidents=[],applied=True,reason='accepted')


def event(sequence,kind):return dict(sequence=sequence,occurred_at=str(sequence),event_type=kind)


def test_same_camera_state_groups_across_evidence_and_score_jitter_without_mutation():
    rows=[camera(1),event(2,'EVIDENCE_STORED'),camera(3,score=.85),event(4,'FLIGHT_ENDED')];original=deepcopy(rows)
    out=timeline_groups(rows)
    assert [g['count'] for g in out['groups']]==[2,1]
    assert out['groups'][0]['sequences']==[1,3]
    assert out['groups'][0]['first_at']=='1' and out['groups'][0]['last_at']=='3'
    assert out['evidence_storage_event_count']==1 and rows==original


def test_changes_recurrence_instruction_and_warning_are_never_global_deduplicated():
    rows=[camera(1,90,'MISMATCH'),camera(2,270),camera(3,90,'MISMATCH'),camera(4,None,'UNVERIFIED'),camera(5,90,'MISMATCH',instruction='b'),event(6,'VOICE_RESULT'),camera(7,90,'MISMATCH',instruction='b')]
    out=timeline_groups(rows)
    assert len(out['groups'])==len(rows)
    assert [g['display_checks'][0]['actual'] if g['display_checks'] else 'unchanged' for g in out['groups']][:5]==[90,270,90,None,90]


def test_repeated_incident_updates_group_only_with_same_actual_lifecycle_and_proof_context():
    rows=[];raw=[]
    for n in (1,3):
        rows.append(dict(sequence=n,occurred_at=str(n),event_type='INCIDENT_UPDATED',occurrence_ids=['incident'],error_status='OPEN'))
        raw.append(dict(sequence=n,snapshot={'current_check':camera(n,90,'MISMATCH')['checks'][0]}))
        rows.append(camera(n+1,90,'MISMATCH'))
    groups=timeline_groups(rows,raw)['groups']
    assert [g['count'] for g in groups]==[2,2]
    raw[-1]['snapshot']['current_check']['actual']=80
    assert len(timeline_groups(rows,raw)['groups'])==4


def test_repeated_verification_tables_display_changes_only_and_raw_report_is_intact():
    rows=[camera(1),event(2,'SEGMENT_REGISTERED'),camera(3),camera(4,90,'MISMATCH')]
    result=timeline_groups(rows)
    assert [len(g['display_checks']) for g in result['groups']]==[1,0,0,1]
    report={'safety':{'timeline':rows},'timeline':[]};original=deepcopy(report)
    projected=with_presentation(report)
    assert report==original and projected['safety']['timeline']==rows
    assert projected['safety']['presentation']['raw_event_count']==4


def test_speech_and_evidence_deletion_remain_distinct():
    a=camera(1);a.update(source='ATC',transcript='same words')
    b=deepcopy(a);b['sequence']=2
    assert len(timeline_groups([a,b])['groups'])==2
    assert len(timeline_groups([camera(1),event(2,'EVIDENCE_DELETED'),camera(3)])['groups'])==3


def test_correction_reobservations_group_but_changed_actual_and_recurrence_do_not():
    from app.services.reports.presentation import correction_groups
    steps=[];raw=[]
    for sequence,actual in [(1,90),(2,90),(3,80),(4,90)]:
        steps.append(dict(state='CORRECTING',verification='MISMATCH',at=str(sequence),event_sequence=sequence))
        raw.append(dict(sequence=sequence,snapshot={'current_check':camera(sequence,actual,'MISMATCH')['checks'][0]}))
    groups=correction_groups(steps,raw)
    assert [group['count'] for group in groups]==[2,1,1]
    assert groups[0]['last_at']=='2'
    assert len(correction_groups(steps))==4


def test_incident_summary_is_bounded_and_does_not_promote_unknown_or_superseded():
    from app.services.reports.presentation import error_timeline
    steps=[dict(state='CORRECTING',at=str(i),verification='UNVERIFIED') for i in range(100)]
    incident=dict(occurrence_id='one',stage='SETTING',field='ALT',detected_at='start',
        state='UNRESOLVED',resolved_at=None,warning_completed=False,steps=steps)
    original=deepcopy(incident)
    out=error_timeline([incident])
    assert len(out)==1 and len(out[0]['milestones'])==4
    assert out[0]['milestones'][1]['at'] is None
    assert out[0]['milestones'][2]['count']==100
    assert out[0]['milestones'][2]['last_at']=='99'
    assert out[0]['milestones'][3]['state']=='UNRESOLVED'
    assert incident==original
    second=deepcopy(incident);second.update(occurrence_id='recurrence',state='RESOLVED',resolved_at='end',warning_completed=True)
    second['steps'].append(dict(state='WARNED',at='warning'))
    out=error_timeline([incident,second])
    assert len(out)==2
    assert out[1]['milestones'][1]['at']=='warning'
    assert out[1]['milestones'][3]==dict(state='RESOLVED',at='end',count=1)
