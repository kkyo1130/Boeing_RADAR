"""Optional constrained AI fact selection. No generated numbers or verdicts are trusted."""
import hashlib
import json
import os
import httpx

def english_summary(facts, fact_ids=None):
    """Render the same frozen facts in English without an AI call or revalidation."""
    instruction_noun='instruction' if facts['instruction_count']==1 else 'instructions'
    incident_noun='incident' if facts['incident_count']==1 else 'incidents'
    incident_verb='is' if facts['incident_count']==1 else 'are'
    resolved_phrase='incident was' if facts['resolved_count']==1 else 'incidents were'
    unresolved_phrase='incident remains' if facts['unresolved_count']==1 else 'incidents remain'
    superseded_phrase='incident closed by a replacement instruction is' if facts['superseded_count']==1 else 'incidents closed by replacement instructions are'
    clauses={
        'instructions':f"The stored record contains {facts['instruction_count']} ATC {instruction_noun}. Instructions with a complete match and no recorded incident: {facts['normal_instruction_count']}. Unverified instructions: {facts['unverified_instruction_count']}.",
        'errors':f"There {incident_verb} {facts['incident_count']} mismatch {incident_noun}: {facts['readback_error_count']} readback error(s) and {facts['setting_error_count']} cockpit setting error(s).",
        'corrections':f"{facts['resolved_count']} {resolved_phrase} resolved by revalidation of new valid observations; {facts['unresolved_count']} {unresolved_phrase} unresolved. {facts['superseded_count']} {superseded_phrase} not counted as resolved.",
        'scope':'This summary describes stored validation records. It is not a certification of safety for actual flight operations.',
    }
    order=fact_ids if isinstance(fact_ids,list) and len(fact_ids)==len(clauses) and all(isinstance(x,str) for x in fact_ids) and set(fact_ids)==set(clauses) else list(clauses)
    return ' '.join(clauses[key] for key in order)


def summarize(facts,events,*,allow_ai=True):
    clauses={
        'instructions':f"저장된 관제 지시는 {facts['instruction_count']}건이며, 오류 없는 전체 일치 기록은 {facts['normal_instruction_count']}건, 확인 미완료는 {facts['unverified_instruction_count']}건입니다.",
        'errors':f"불일치 사건 {facts['incident_count']}건 중 복명복창 오류는 {facts['readback_error_count']}건, Cockpit 설정 오류는 {facts['setting_error_count']}건입니다.",
        'corrections':f"새 유효 관측으로 재검증된 해결은 {facts['resolved_count']}건, 미해결은 {facts['unresolved_count']}건입니다. 지시 대체 {facts['superseded_count']}건은 해결로 계산하지 않습니다.",
        'scope':'이 요약은 저장된 검증 기록의 설명이며 실제 항공 운항의 안전 인증이 아닙니다.',
    }
    baseline={'source':'RULE_BASED','text':' '.join(clauses.values()),'reason':'AI_NOT_CONFIGURED','verified_facts':facts,'text_en':english_summary(facts),'fact_ids':list(clauses)}
    url=os.getenv('RADAR_REPORT_AI_URL') if allow_ai else None
    if not url:return baseline
    fingerprint=hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()
    try:
        headers={'Authorization':'Bearer '+os.environ['RADAR_REPORT_AI_TOKEN']} if os.getenv('RADAR_REPORT_AI_TOKEN') else {}
        with httpx.Client(timeout=httpx.Timeout(2,connect=1),follow_redirects=False,trust_env=False) as client:
            response=client.post(url,json=dict(task='Select and order only the supplied fact IDs. Return fact_ids and facts_digest. Do not generate claims.',
                facts=facts,clauses=clauses,events=events[:100],facts_digest=fingerprint),headers=headers)
            response.raise_for_status()
            if len(response.content)>16384:raise ValueError('Oversized AI response')
            output=response.json();ids=output['fact_ids']
            if (output.get('facts_digest')!=fingerprint or not isinstance(ids,list) or
                len(ids)!=len(clauses) or any(not isinstance(x,str) for x in ids) or set(ids)!=set(clauses)):
                raise ValueError('Unverified AI facts')
        return dict(source='AI_ASSISTED_FACTS',text=' '.join(clauses[x] for x in ids),reason=None,verified_facts=facts,text_en=english_summary(facts,ids),fact_ids=ids)
    except Exception:
        return {**baseline,'reason':'AI_FAILED_OR_UNVERIFIED'}
