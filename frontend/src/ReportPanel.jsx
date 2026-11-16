import React, { useEffect, useState } from 'react';
import { request } from './flight-client.js';
import './report.css';
import {groupTimeline,errorTimeline} from './report-timeline.js';

const value = v => v === null || v === undefined ? '확인 불가' : String(v);
const stateLabel = { DETECTED:'오류 탐지', WARNED:'경고 재생 완료', CORRECTING:'수정 관측·재검증', RESOLVED:'수정·재검증 완료', UNRESOLVED:'미해결 종료' };
const number = (field,v) => v === null || v === undefined ? '확인 불가' : field === 'ALT' ? `${v} ft` : field === 'HDG' ? `${String(v).padStart(3,'0')}°` : String(v);

export function SafetyReport({ report, flightId, connected=true }) {
  const [page,setPage]=useState(0),[downloadError,setDownloadError]=useState(''),[downloading,setDownloading]=useState(false);
  useEffect(()=>{
    let opened=[];
    const prepare=()=>{opened=[...document.querySelectorAll('.flight-report details:not(.report-raw-observations):not(.report-full-timeline):not([open])')];opened.forEach(node=>{node.open=true;});};
    const restore=()=>{opened.forEach(node=>{node.open=false;});opened=[];};
    window.addEventListener('beforeprint',prepare);window.addEventListener('afterprint',restore);
    return()=>{restore();window.removeEventListener('beforeprint',prepare);window.removeEventListener('afterprint',restore);};
  },[]);
  const safety=report.safety;
  if (!safety) return <p role="alert">이 기록에는 상세 리포트 정보가 없습니다.</p>;
  const groups=groupTimeline(safety.timeline,safety.presentation);
  const facts=safety.summary, size=30, pages=Math.max(1,Math.ceil(groups.length/size));
  async function download() {
    setDownloading(true);setDownloadError('');
    try {
      const response=await fetch(`/api/v2/flights/${encodeURIComponent(flightId)}/report.pdf`,{credentials:'same-origin'});
      if (!response.ok) throw new Error(`PDF 요청 실패 (${response.status})`);
      if (!(response.headers.get('Content-Type')||'').includes('application/pdf')) throw new Error('PDF 응답을 확인할 수 없습니다.');
      const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=`Flight_Safety_Report_${safety.ended_at?.slice(0,10)||'unknown'}.pdf`;
      document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error) { setDownloadError(error.message); }
    finally {setDownloading(false);}
  }
  const button=()=> <button type="button" className="primary" disabled={!connected||!safety.terminal||downloading} onClick={download}>{downloading?'PDF 생성 중…':'PDF 다운로드'}</button>;
  return <article className="flight-report" aria-label="Flight Safety Report">
    <header className="report-heading"><div><p className="eyebrow">SAFETY TRACE</p><h2>Flight Safety Report</h2><p>{safety.callsign}</p></div>{button()}<button type="button" disabled={!safety.terminal} onClick={()=>window.print()}>인쇄</button></header>
    <p>시작 {value(safety.started_at)} · 종료 {value(safety.ended_at)} · 모든 시각 UTC</p>
    <p className="op-notice">{safety.provenance==='FIXTURE_PRESENT'?'Fixture 입력이 포함된 검증 기록입니다.':'저장된 시스템 입력 기반입니다. 실제 촬영·음성 출처가 확인되지 않은 입력을 실물 검증으로 간주하지 않습니다.'}</p>
    <p>{safety.missing_data}</p>
    {!safety.terminal&&<p role="alert">아직 종료되지 않은 세션입니다. PDF는 종료 후 다운로드할 수 있습니다.</p>}
    {downloadError&&<p className="op-error" role="alert">{downloadError}</p>}
    <section aria-label="Flight Summary"><h3>1. 비행 요약</h3><div className="report-cards">
      {[["총 관제 지시",facts.instruction_count],["오류 없는 전체 일치 지시",facts.normal_instruction_count],["오류 발생 지시",facts.error_instruction_count],
        ["확인 미완료 지시",facts.unverified_instruction_count],["오류 사건",facts.incident_count],["수정 완료",facts.resolved_count],
        ["미해결",facts.unresolved_count],["그중 새 지시로 대체",facts.superseded_count],["오류 수정률",facts.correction_rate===null?'해당 없음':`${(facts.correction_rate*100).toFixed(1)}%`]].map(([label,n])=>
        <div key={label}><span>{label}</span><strong>{n}</strong></div>)}
      </div><p>ALT 오류 {safety.correction_trace.filter(i=>i.field==='ALT').length}건 · HDG 오류 {safety.correction_trace.filter(i=>i.field==='HDG').length}건</p>{facts.incident_count===0&&<p>저장된 오류 사건은 0건입니다. 미수집·확인 미완료를 정상으로 간주하지 않습니다.</p>}
      {facts.unresolved_count>0&&<p className="report-unresolved" role="status">미해결 오류 {facts.unresolved_count}건이 있습니다. 지시 대체는 수정 완료가 아닙니다.</p>}
    </section>
    <section aria-label="Error Classification"><h3>ALT·HDG 오류 현황</h3>{safety.classification.map(item=><div className="report-classification" key={item.stage}>
      <span>{item.label}</span><meter min="0" max="1" value={item.ratio} aria-label={`${item.label} 비율`}/><strong>{item.count}건 ({(item.ratio*100).toFixed(1)}%)</strong>
    </div>)}</section>
    <section aria-label="Correction Trace"><h3>2. 오류 및 수정 이력</h3>{!safety.correction_trace.length?<p>저장된 오류 사건이 없습니다.</p>:safety.correction_trace.map(item=><article className={`report-incident report-${item.state}`} key={item.occurrence_id}>
      <h4>{item.stage==='READBACK'?'Readback Error':'Cockpit Setting Error'} · {item.field} · {stateLabel[item.state]||item.state}</h4>
      <p>발생 {value(item.detected_at)} · 해결 소요 {item.resolved_at&&item.detected_at?`${Math.max(0,(Date.parse(item.resolved_at)-Date.parse(item.detected_at))/1000).toFixed(1)}초`:'미해결'}</p><p>목표 {number(item.field,item.expected)} · 최초 관측 {number(item.field,item.initial_actual)} → 마지막 관측 {number(item.field,item.final_actual)}</p>
      <p>발생 당시 복명복창 {number(item.field,item.readback_actual)} · 조종석 인식 {number(item.field,item.cockpit_actual)}</p><p>마지막 검증 {item.verification} · 경고 재생 완료 {item.warning_completed?'기록 있음':'확인 불가'} · 해결 시각 {value(item.resolved_at)}</p>
      <details className="report-raw-observations"><summary>수정 관측 상세 펼치기 ({item.steps.length}건)</summary><ol>{(safety.presentation?.correction_groups?.[item.occurrence_id]||item.steps.map(step=>({step,count:1}))).map(({step,count,last_at},index)=><li key={index}>{step.at}{count>1&&` ~ ${last_at} · 동일 상태 ${count}회`} · {step.state} ({stateLabel[step.state]}) {step.verification||''}</li>)}</ol></details>
      <small>사건 {item.occurrence_id} · 지시 {item.instruction_id} · 원본 상태 {item.stored_status}</small>
    </article>)}</section>
    <section aria-label="Error Timeline"><h3>3. 오류 사건 타임라인</h3>
      {!safety.correction_trace.length&&<p>저장된 오류 사건이 없습니다. 확인 미완료 입력은 비행 요약과 전체 기록에서 확인하세요.</p>}
      {errorTimeline(safety.correction_trace,safety.presentation).map(item=><article className="report-incident" key={item.occurrence_id}>
        <h4>{item.stage==='READBACK'?'Readback Error':'Cockpit Setting Error'} · {item.field}</h4>
        <ol className="report-milestones">{item.milestones.map((step,i)=><li key={i}><strong>{i===3?'최종 상태: ':''}{stateLabel[step.state]||step.state}</strong><span>{value(step.at)}</span>{i===1&&!step.at&&<small>경고 재생 완료 기록 없음</small>}{i===2&&<small>{step.count?`수정·재검증 관측 ${step.count}회${step.last_at&&step.last_at!==step.at?` · 마지막 ${step.last_at}`:''}`:'수정 관측 기록 없음'}</small>}</li>)}</ol>
      </article>)}
      <details className="report-full-timeline"><summary>전체 입력·검증 기록 펼치기 ({groups.length}개 구간)</summary>{safety.presentation&&<p>원본 {safety.presentation.raw_event_count}건 → 표시 {groups.length}개 구간 · 근거 저장 {safety.presentation.evidence_storage_event_count}건은 원본 JSON에서 확인할 수 있습니다.</p>}<p>입력·검증·경고 기록을 연결합니다. 숫자 단위: ALT feet / HDG degrees.</p>
      <ol className="report-timeline">{groups.map((group,index)=>{const event=group.event||group.events[0],checks=group.display_checks??event.checks;return <li key={event.sequence} value={index+1} className={Math.floor(index/size)===page?'':'report-print-only'}>
        {group.events.length>1&&<><p className="report-repeat">동일 상태 {group.events.length}회 · {group.first_at||event.occurred_at} ~ {group.last_at||group.events.at(-1).occurred_at}</p><details className="report-raw-observations"><summary>원본 관측 펼치기</summary><ol>{group.events.map(original=><li key={original.sequence}>#{original.sequence} · {original.occurred_at} · {Object.entries(original.fields).map(([key,row])=>`${key}: ${number(key,row.value)} [${row.validity}]`).join(' / ')}</li>)}</ol></details></>}
        <div><time>{event.occurred_at}</time><strong>{event.event_type}</strong></div>
        {event.source&&<p>{event.source==='COCKPIT'?'카메라 관측':`${event.source}: ${event.transcript||'음성 전사 기록 없음'}`}</p>}
        {Object.keys(event.fields).length>0&&<p>인식 입력: {Object.entries(event.fields).map(([field,row])=>`${field} ${number(field,row.value)} [${row.validity}]`).join(' / ')}</p>}
        {checks.length>0&&<div className="op-table-scroll"><table><thead><tr><th>단계·항목</th><th>관제 목표</th><th>인식값</th><th>검증</th></tr></thead><tbody>{checks.map((row,i)=><tr key={i}>
          <td>{row.stage} / {row.field}</td><td>{number(row.field,row.expected)}</td><td>{number(row.field,row.actual)}</td><td className={`report-${row.result}`}>{row.result}<small>{row.reason}</small></td>
        </tr>)}</tbody></table></div>}
        {event.warning_status&&<p>음성 안내 {event.warning_status} · 완료 기록 {event.warning_completed?'있음':'없음'}</p>}
        {(group.display_related_incidents??event.related_incidents)?.map(item=><p key={item.occurrence_id}>{item.stage==='READBACK'?'Readback Error':'Cockpit Setting Error'} · {item.status} · 경고 완료 {item.warning_completed?'있음':'확인 불가'} · 해결 시각 {value(item.resolved_at)}</p>)}
        {event.error_status&&<p>저장 오류 상태: {event.error_status}</p>}
        <details><summary>연결된 지시·오류 식별자</summary><p>{event.instruction_ids.join(', ')||'지시 연결 없음'}</p><p>{event.occurrence_ids.join(', ')||'오류 사건 연결 없음'}</p></details>
      </li>;})}</ol>
      {!safety.timeline.length&&<p>저장된 이벤트가 없습니다.</p>}
      <nav className="report-pagination" aria-label="리포트 타임라인 페이지"><button disabled={page===0} onClick={()=>setPage(p=>p-1)}>이전</button><span>{page+1} / {pages}</span><button disabled={page>=pages-1} onClick={()=>setPage(p=>p+1)}>다음</button></nav>
      </details>
    </section>
    <section aria-label="AI Safety Summary"><h3>4. AI Safety Summary</h3><p className="eyebrow">{safety.ai_summary.source==='AI_ASSISTED_FACTS'?'AI 보조 사실 요약':'규칙 기반 요약 · AI 미설정 또는 응답 검증 실패'}</p><p>{safety.ai_summary.text}</p><small>판정은 저장된 검증 엔진 결과입니다. AI가 판정하거나 오류를 해결하지 않습니다.</small></section>
    <footer><p>{safety.terminal?'운항 종료 기록':'진행 중 기록'} · 리포트 생성 {safety.generated_at}</p>{button()} <a href={`/api/v2/flights/${encodeURIComponent(flightId)}/report.json`} download>리포트 JSON 저장</a></footer>
  </article>;
}

export default function ReportPanel({ flightId, ended, connected }) {
  const [report,setReport]=useState(null),[error,setError]=useState('');
  useEffect(()=>{
    const abort=new AbortController();setReport(null);setError('');
    if(ended&&connected) request(`/api/v2/flights/${encodeURIComponent(flightId)}/report`,{signal:abort.signal})
      .then(data=>{if(!abort.signal.aborted)setReport(data);}).catch(e=>{if(!abort.signal.aborted)setError(e.message);});
    return()=>abort.abort();
  },[flightId,ended,connected]);
  if(!ended)return null;
  return <section className="op-panel" aria-label="비행 종료 리포트"><h2>비행 종료 리포트</h2>
    {error&&<p role="alert">리포트를 불러오지 못했습니다: {error}</p>}
    {report&&connected?<SafetyReport key={flightId} report={report} flightId={flightId}/>:!error&&<p>리포트를 확인하고 있습니다.</p>}
  </section>;
}

export function ReportPage(){
  const [token,setToken]=useState(''),[error,setError]=useState('');
  async function recover(event){event.preventDefault();setError('');try{await request(`/api/v2/flights/${encodeURIComponent(id)}/report-access`,{method:'POST',body:{token}});window.location.reload();}catch(e){setError(e.message);}}
  const id=new URLSearchParams(window.location.search).get('flight')||'';
  return <main className="operations"><header className="op-header"><a className="brand" href="/operations">RADAR / FLIGHT MONITOR</a></header>
    {id?<><ReportPanel flightId={id} ended connected/><details className="op-panel"><summary>기존 세션 접근 코드</summary><p>권한이 없는 과거 기록은 로컬 관리자가 발급한 접근 코드가 필요합니다. 코드를 URL에 넣지 마세요. 다른 브라우저 권한으로 전환하면 기존 브라우저의 다른 세션은 접근할 수 없을 수 있습니다.</p><form onSubmit={recover}><label htmlFor="report-access-code">리포트 접근 코드</label><input id="report-access-code" type="password" autoComplete="off" required minLength={64} maxLength={64} value={token} onChange={e=>setToken(e.target.value)}/><button>접근 권한 확인</button></form>{error&&<p role="alert">{error}</p>}</details></>:<p role="alert">리포트의 세션 ID가 필요합니다.</p>}</main>;
}
