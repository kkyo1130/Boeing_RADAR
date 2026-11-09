import React, { useState } from 'react';
import { useFlight } from './Operations.jsx';
import { numberLabel } from './flight-client.js';
import './pilot.css';
const labels = { ALT: '고도', HDG: '방위', CALLSIGN: '호출부호' };
const reasons = { STALE_OBSERVATION: '새 관측 대기', CHANNEL_UNAVAILABLE: '입력 장치 확인', INPUT_QUALITY_UNVERIFIED: '입력 품질 확인', INPUT_NOT_AVAILABLE: '입력 대기', TARGET_NOT_AVAILABLE: '관제 지시 대기', READBACK_NOT_CONFIRMED: '복명복창 확인 대기', LATEST_READBACK_UNVERIFIED: '새 복명복창 대기', LATEST_ATC_NOT_ADOPTED: '새 관제 지시 확인 대기' };
export function PilotDisplay({ snapshot, connected }) {
  const ended = snapshot?.status === 'ENDED';
  const usable = connected && snapshot && !ended;
  // Server verdicts only: no numeric comparison or local incident resolution.
  const rows = usable ? [['readback', '복명복창'], ['setting', 'MCP 설정']].flatMap(([key, stage]) => snapshot.validation[key].fields.filter(row => row.result !== 'NORMAL').map(row => ({ ...row, stage, stageKey: key }))) : [];
  rows.sort((a, b) => Number(b.result === 'MISMATCH') - Number(a.result === 'MISMATCH'));
  const devices = usable ? [['CAMERA', '카메라'], ['MICROPHONE', '마이크'], ['SPEECH_API', '음성 처리']].filter(([key]) => ['DISCONNECTED', 'DEGRADED', 'UNKNOWN'].includes(snapshot.channels[key]?.status)) : [];
  const mismatch = rows.some(row => row.result === 'MISMATCH');
  const normal = usable && snapshot.result === 'NORMAL' && !rows.length && !devices.length;
  const heading = !connected ? '연결 확인 필요' : !snapshot ? '비행 상태 확인 중' : ended ? '비행 종료' : mismatch ? '확인 필요' : normal ? '지시와 일치' : '확인 중';
  return <section className={`pilot-display ${normal ? 'pilot-normal' : mismatch ? 'pilot-mismatch' : 'pilot-unverified'}`} aria-label="조종사 상태" aria-live="polite" aria-atomic="true">
    <div className="pilot-status"><span className="pilot-dot" />{heading}</div>
    {!usable ? <div className="pilot-empty"><h1>{ended && connected ? '비행 종료' : '현재 상태 확인 불가'}</h1><p>{ended && connected ? '운영 화면에서 다음 비행을 선택하세요' : '서버 연결 후 다시 확인합니다'}</p></div> : <>
      <div className={`pilot-cards ${rows.length > 1 ? 'pilot-multiple' : ''}`}>{rows.map(row => <article className={`pilot-card pilot-${row.result.toLowerCase()}`} key={`${row.stageKey}/${row.instruction_id}/${row.field}`}>
        <p className="pilot-stage">{row.stage}</p><h1>{labels[row.field]} <span>{row.result === 'MISMATCH' ? '불일치' : row.reason === 'INITIAL_ADJUSTMENT_WAIT' ? '변경 대기' : '확인 불가'}</span></h1>
        {row.result === 'MISMATCH' ? <dl className="pilot-values"><div><dt>{row.stageKey === 'readback' ? '관제' : '지시'}</dt><dd>{numberLabel(row.expected, row.field)}</dd></div><div><dt>{row.stageKey === 'readback' ? '응답' : 'MCP 선택'}</dt><dd>{numberLabel(row.actual, row.field)}</dd></div></dl> : <p className="pilot-reason">{row.reason === 'INITIAL_ADJUSTMENT_WAIT' ? '설정 변경 대기 중' : reasons[row.reason] || '새 입력으로 재확인 필요'}</p>}
      </article>)}</div>
      {!rows.length && <div className="pilot-empty"><h1>{normal ? '지시와 일치' : snapshot.validation.phase === 'WAITING_ATC' ? '관제 지시 대기' : '확인 불가'}</h1><p>{normal ? '복명복창 · MCP 설정' : '새 입력으로 확인합니다'}</p></div>}
      {devices.length > 0 && <div className="pilot-devices">{devices.map(([key, label]) => <p key={key}>{label} · {{ DISCONNECTED: '연결 끊김', DEGRADED: '품질 저하', UNKNOWN: '상태 확인 불가' }[snapshot.channels[key].status]}</p>)}</div>}
    </>}
  </section>;
}
function initialFlight() { return typeof window === 'undefined' ? '' : new URLSearchParams(window.location.search).get('flight') || ''; }
export default function Pilot() {
  const [flightId, setFlightId] = useState(initialFlight), [draft, setDraft] = useState(''), [refresh, setRefresh] = useState(0);
  const { snapshot, connected } = useFlight(flightId, refresh);
  return <main className="pilot-shell"><header className="pilot-header"><a href="/operations">RADAR</a><span>{snapshot?.callsign || 'PILOT DISPLAY'}</span><a href="/operations">운영 화면</a></header>
    {flightId ? <><PilotDisplay snapshot={snapshot} connected={connected} />{!connected && <button className="pilot-reconnect" onClick={() => setRefresh(value => value + 1)}>다시 연결</button>}</> : <form className="pilot-connect" onSubmit={event => { event.preventDefault(); if (draft.trim()) { const id = draft.trim(); window.history.replaceState(null, '', `/pilot?flight=${encodeURIComponent(id)}`); setFlightId(id); } }}>
      <h1>비행 연결</h1><p>운영 화면의 ‘조종사 화면’을 열거나 비행 ID를 입력하세요.</p><label htmlFor="pilot-flight">비행 ID</label><input id="pilot-flight" required value={draft} maxLength={160} onChange={event => setDraft(event.target.value)} /><button disabled={!draft.trim()}>연결</button>
    </form>}<footer className="pilot-footer">모의 환경 · MCP 선택값 기준</footer></main>;
}
