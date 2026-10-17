import React, { useEffect, useRef, useState } from 'react';
import { request, SnapshotGate, dueRevalidations, POLL_MS, statusLabel, numberLabel, restartFlightState, readingFor, reconciledActionError } from './flight-client.js';
import './operations.css';

const STORAGE_KEY = 'radar.v2.flight-id';
const readFlight = () => { if (typeof window === 'undefined') return ''; try { return window.localStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; } };
const phases = { WAITING_ATC: '관제 지시 대기', READBACK: '복명복창 확인', SETTING: '설정 확인',
  MONITORING: '일치 · 계속 감시 중', ENDED: '비행 종료' };
const fields = { ALT: '고도', HDG: '방위', CALLSIGN: '호출부호' };
const reasons = {
  ALL_REQUIRED_FIELDS_MATCH: '필수 복창과 설정 항목이 모두 일치합니다', READBACK_MISMATCH: '복명복창 내용을 확인하세요',
  SETTING_MISMATCH: '표시된 설정 항목을 확인하세요', SETTING_UNVERIFIED: '설정 확인에 필요한 관측 대기',
  READBACK_UNVERIFIED: '복명복창 확인에 필요한 입력 대기', FLIGHT_ENDED: '종료 시점의 기록입니다',
  INPUT_NOT_AVAILABLE: '새 관측 대기', VALUE_MATCH: '지시와 일치', VALUE_MISMATCH: '재확인이 필요합니다',
  INITIAL_ADJUSTMENT_WAIT: '설정 변경 대기 중', READBACK_NOT_CONFIRMED: '복명복창 확인 대기',
  STALE_OBSERVATION: '관측이 오래되어 확인 불가', TARGET_NOT_AVAILABLE: '관제 지시 대기',
  ADJUSTMENT_DEADLINE_MISMATCH: '설정을 확인하세요', SETTING_DEVIATED_AFTER_MATCH: '설정을 다시 확인하세요',
  LATEST_READBACK_UNVERIFIED: '새 지시의 복명복창 대기', LATEST_ATC_NOT_ADOPTED: '새 관제 지시 확인 대기',
  CHANNEL_UNAVAILABLE: '입력 장치를 사용할 수 없습니다', INPUT_QUALITY_UNVERIFIED: '입력 품질 확인 필요',
};

function useFlight(flightId, refresh) {
  const [state, setState] = useState({ snapshot: null, connected: false, error: '', receivedAt: null });
  const sessionRef = useRef(null);
  useEffect(() => {
    setState(previous => restartFlightState(previous, flightId));
    if (!flightId) { sessionRef.current = null; return; }
    const abort = new AbortController();
    if (sessionRef.current?.gate.flightId !== flightId) sessionRef.current = { gate: new SnapshotGate(flightId), completed: new Set() };
    const { gate, completed } = sessionRef.current;
    let stopped = false, timer, serial = gate.serial;
    async function poll() {
      try {
        let data = await request(`/api/v2/flights/${encodeURIComponent(flightId)}/state`, { signal: abort.signal });
        if (stopped) return;
        if (!gate.accept(data, ++serial)) throw new Error('이전 버전의 응답입니다. 최신 상태를 다시 확인합니다.');
        const due = dueRevalidations(data, completed);
        if (due.length) {
          data = await request(`/api/v2/flights/${encodeURIComponent(flightId)}/revalidate`, { method: 'POST', signal: abort.signal });
          if (stopped) return;
          if (!gate.accept(data, ++serial)) throw new Error('재검증 응답의 버전을 확인할 수 없습니다.');
          due.forEach(key => completed.add(key));
        }
        setState({ snapshot: data, connected: true, error: '', receivedAt: new Date().toISOString() });
      } catch (error) {
        if (stopped) return;
        setState(previous => ({ ...previous, connected: false, error: error.message }));
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS);
    }
    poll();
    return () => { stopped = true; clearTimeout(timer); abort.abort(); };
  }, [flightId, refresh]);
  return { ...state, snapshot: state.snapshot?.flight_id === flightId ? state.snapshot : null };
}

function Badge({ result, connected = true, ended = false }) {
  const effective = connected && !ended ? result : 'UNVERIFIED';
  return <span className={`op-badge op-${effective}`}>{ended ? '종료 기록' : statusLabel(result, connected)}</span>;
}

function Stamp({ value }) { return value ? <time dateTime={value}>{value}</time> : <span>시각 미상</span>; }

export function Verdicts({ title, group, source, snapshot, connected, ended = false }) {
  return <section className="op-panel" aria-label={title}>
    <div className="op-section-heading"><h2>{title}</h2><Badge result={group.result} connected={connected} ended={ended} /></div>
    <div className="op-table-scroll"><table>
      <thead><tr><th>항목</th><th>관제 지시</th><th>{source === 'COCKPIT' ? '카메라 관측' : '조종사 복창'}</th><th>서버 확인</th></tr></thead>
      <tbody>{group.fields.map(row => {
        const reading = readingFor(snapshot, source, row);
        return <tr key={`${row.instruction_id}/${row.field}`}>
          <th scope="row">{fields[row.field]}</th>
          <td>{numberLabel(row.expected, row.field)}</td><td>{numberLabel(row.actual, row.field)}</td>
          <td><Badge result={row.result} connected={connected} ended={ended} /><p>{ended ? '종료 시점의 관측 기록입니다' : connected ? reasons[row.reason] || '확인이 필요합니다' : '연결 복구 후 다시 확인합니다'}</p>
            <small>관측 <Stamp value={reading?.observed_at} /></small>
            {row.wait_until && <small>대기 종료 <Stamp value={row.wait_until} /></small>}
            <details><summary>지시·관측 식별자</summary><p>서버 사유 {row.reason}</p><p>지시 {row.instruction_id || '없음'}</p><p>관측 {row.observation_id || '없음'}</p></details>
          </td>
        </tr>;
      })}</tbody>
    </table></div>
    {!group.fields.length && <p className="op-muted">{ended ? '종료 시점에 확인된 항목이 없습니다.' : '관제 지시와 새 관측을 기다리고 있습니다.'}</p>}
  </section>;
}

export default function Operations() {
  const [flightId, setFlightId] = useState(readFlight);
  const [callsign, setCallsign] = useState('');
  const [resumeId, setResumeId] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [refresh, setRefresh] = useState(0);
  const actionRef = useRef(false);
  const { snapshot, connected, error: connectionError, receivedAt } = useFlight(flightId, refresh);
  const ended = snapshot?.status === 'ENDED';
  useEffect(() => { setError(previous => reconciledActionError(previous, snapshot, connected)); }, [ended, connected]);
  function attach(id) {
    try { id ? localStorage.setItem(STORAGE_KEY, id) : localStorage.removeItem(STORAGE_KEY); } catch { /* Session works without browser storage. */ }
    setError(''); setFlightId(id);
  }
  async function start(event) {
    event.preventDefault();
    if (!callsign.trim() || actionRef.current) return;
    actionRef.current = true; setBusy(true); setError('');
    try {
      const session = await request('/api/v2/flights', { method: 'POST', body: { callsign: callsign.trim() } });
      if (typeof session.flight_id !== 'string' || session.schema_version !== '2') throw new Error('비행 시작 응답을 확인할 수 없습니다.');
      attach(session.flight_id);
    } catch (e) { setError(e.message); }
    finally { actionRef.current = false; setBusy(false); }
  }
  async function end() {
    if (actionRef.current || !connected || ended) return;
    actionRef.current = true; setBusy(true); setError('');
    try {
      await request(`/api/v2/flights/${encodeURIComponent(flightId)}/end`, { method: 'POST' });
      setRefresh(value => value + 1);
    } catch (e) { setError(e.message); setRefresh(value => value + 1); }
    finally { actionRef.current = false; setBusy(false); }
  }
  return <main className="operations">
    <header className="op-header"><a className="brand" href="/operations">RADAR<span> / FLIGHT MONITOR</span></a>
      <nav aria-label="화면 선택"><a href="/" target="_blank" rel="noreferrer">모의 MCP 열기 ↗</a></nav>
      <span className="op-muted">모의 환경 · 설정은 직접 조작</span></header>
    <div className="op-intro"><p className="eyebrow">FLIGHT OPERATIONS</p><h1>비행 상태 확인</h1><p>관제 지시와 복명복창, 카메라가 읽은 설정값을 함께 확인하세요.</p></div>
    {error && <p className="op-error" role="alert">{error}</p>}
    {!flightId ? <section className="op-panel op-start">
      <h2>대상 항공기</h2><form onSubmit={start}><label htmlFor="callsign">등록된 호출부호</label>
        <div className="op-inline"><input id="callsign" value={callsign} maxLength={160} required autoComplete="off" onChange={e => setCallsign(e.target.value)} disabled={busy} />
          <button className="primary" disabled={!callsign.trim() || busy}>{busy ? '시작 확인 중…' : 'START FLIGHT'}</button></div>
        <p className="op-muted">호출부호는 비행 중 고정됩니다. 등록 여부는 서버에서 확인합니다.</p></form>
      <details><summary>기존 비행 다시 연결</summary><form onSubmit={e => { e.preventDefault(); if (resumeId.trim()) attach(resumeId.trim()); }}>
        <label htmlFor="resume-id">비행 ID</label><div className="op-inline"><input id="resume-id" value={resumeId} required maxLength={160} onChange={e => setResumeId(e.target.value)} /><button>연결</button></div>
      </form></details>
    </section> : <>
      <section className="op-panel op-session" aria-label="비행 세션">
        <div><p className="eyebrow">{ended ? 'ENDED FLIGHT' : 'CURRENT FLIGHT'}</p><h2>{snapshot?.callsign || '세션 확인 중'}</h2><p className="op-id">{flightId}</p></div>
        <div className="op-session-actions"><span className={`op-connection ${connected ? 'is-connected' : ''}`} role="status">{connected ? '서버 연결됨' : '서버 확인 불가 · 판단 보류'}</span>
          <button onClick={() => setRefresh(value => value + 1)} disabled={busy}>다시 연결</button>
          {!ended && <button className="op-end" onClick={end} disabled={!connected || busy || !snapshot}>{busy ? '종료 확인 중…' : 'END FLIGHT'}</button>}
          {!connected && <button disabled={busy} onClick={() => attach('')}>비행 선택으로</button>}
          {ended && <button onClick={() => attach('')}>새 비행 준비</button>}</div>
      </section>
      {connectionError && <div className="op-error" role="alert"><strong>서버 상태를 확인할 수 없습니다.</strong><p>{connectionError}</p><p>표시된 값은 마지막 수신 기록입니다. 현재 일치 여부는 판단 보류입니다.</p></div>}
      {snapshot ? <>
        <section className={`op-overview op-${connected ? snapshot.result : 'UNVERIFIED'}`} aria-label="전체 서버 판정">
          <div><p className="eyebrow">{ended ? '비행이 종료되었습니다' : 'SERVER VALIDATION'}</p><h2>{connected ? phases[snapshot.validation.phase] || '상태 확인' : '연결 복구 후 재확인 필요'}</h2>
            <p>{connected ? reasons[snapshot.reason] || '서버에서 상태를 확인하고 있습니다' : '이전 일치 상태를 현재 상태로 사용하지 않습니다.'}</p></div>
          <Badge result={snapshot.result} connected={connected} ended={ended} />
        </section>
        <p className="op-meta">마지막 응답 <Stamp value={receivedAt} /> · 상태 버전 {snapshot.revision} · 시각 UTC</p>
        <section className="op-panel" aria-label="현재 관제 지시"><div className="op-section-heading"><h2>현재 관제 지시</h2><span className="op-muted">항목별 유효 지시</span></div>
          <div className="op-targets">{['ALT', 'HDG'].map(field => <article key={field}><h3>{fields[field]}</h3>
            <strong>{numberLabel(snapshot.targets[field]?.value, field)}</strong><p className="op-id">{snapshot.targets[field]?.instruction_id || '지시 대기'}</p>
            <small>채택 <Stamp value={snapshot.targets[field]?.adopted_at} /></small></article>)}</div>
          <p>이번 복창 항목: {snapshot.readback_required ? `${snapshot.readback_required.fields.map(field => fields[field]).join(' · ')} · 호출부호` : '지시 확인 대기'}</p>
        </section>
        <Verdicts title="복명복창" group={snapshot.validation.readback} source="READBACK" snapshot={snapshot} connected={connected} ended={ended} />
        <Verdicts title="Cockpit 설정" group={snapshot.validation.setting} source="COCKPIT" snapshot={snapshot} connected={connected} ended={ended} />
        <section className="op-panel" aria-label="장치 상태"><h2>입력 장치</h2><div className="op-health">{[['CAMERA', '카메라'], ['MICROPHONE', '마이크'], ['SPEECH_API', '음성 처리']].map(([key, label]) => {
          const health = snapshot.channels[key];
          return <article key={key}><h3>{label}</h3><p>{!connected ? '서버 확인 불가' : { AVAILABLE: '사용 가능', DISCONNECTED: '연결 끊김', DEGRADED: '품질 저하', UNKNOWN: '확인 불가' }[health?.status] || '상태 수신 대기'}</p>
            <small>{health?.reason ? reasons[health.reason] || '입력 장치 확인 필요' : '별도 장애 정보 없음'}</small><small><Stamp value={health?.observed_at} /></small></article>;
        })}</div></section>
        <section className="op-panel" aria-label="오류 발생 기록"><h2>오류 발생 기록</h2>
          {(snapshot.incidents || []).length ? <ul className="op-incidents">{snapshot.incidents.map(item => <li key={item.occurrence_id}>
            <strong>{fields[item.field]} · {item.stage === 'READBACK' ? '복명복창' : '설정'}</strong><span>{ { OPEN: '미해결', RESOLVED: '새 관측으로 해결', SUPERSEDED: '새 지시로 대체', ENDED_UNRESOLVED: '미해결 종료' }[item.status] || item.status }</span>
            <small>최초 탐지 <Stamp value={item.detected_at} /></small>{item.status === 'OPEN' && <small>현재 확인: {statusLabel(item.current_check.result, connected && !ended)}</small>}
          </li>)}</ul> : <p className="op-muted">저장된 오류 발생 기록이 없습니다.</p>}
        </section>
      </> : <p className="op-panel" role="status">비행 상태를 확인하고 있습니다. 아직 현재 판정을 표시할 수 없습니다.</p>}
    </>}
    <footer>실제 항공기를 제어하지 않는 모의 환경 보조 화면입니다.</footer>
  </main>;
}
