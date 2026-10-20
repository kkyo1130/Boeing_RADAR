import React, { useEffect, useRef, useState } from 'react';
import './operations-v1.css';
import demoPolicy from '../../contracts/rule-policy-demo.json';

async function api(path, body) {
  const response = await fetch(path, { signal: AbortSignal.timeout(5000), ...(body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}

export default function Operations() {
  const [flights, setFlights] = useState([]), [flight, setFlight] = useState('');
  const [report, setReport] = useState(null), [connected, setConnected] = useState(false);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [voice, setVoice] = useState(false), [critical, setCritical] = useState(true);
  const [manualRadio, setRadio] = useState(false), [actor, setActor] = useState('operator');
  const [playing, setPlaying] = useState({});
  const radio = manualRadio || Object.values(playing).some(Boolean) || Boolean(report?.input_active);
  const [settings, setSettings] = useState(''), [evidenceErrors, setEvidenceErrors] = useState({});
  const [callsign, setCallsign] = useState('RADAR1'), [targetAltitude, setTargetAltitude] = useState('3000');
  const [targetHeading, setTargetHeading] = useState('270'), [score, setScore] = useState('0.5');
  const [policyAcknowledged, setPolicyAcknowledged] = useState('');
  const seen = useRef(new Set()), generation = useRef(0);
  const policy = useRef(null);
  policy.current = { voice, critical, radio, flight, connected };
  const policyKey = JSON.stringify([flight, connected, voice, critical, radio, actor]);
  useEffect(() => {
    const token = ++generation.current;
    let cancelled = false;
    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      try {
        const list = await api('/api/v1/flights');
        if (flight && list.find(f => f.flight_id === flight)?.status === 'ACTIVE')
          await api(`/api/v1/flights/${flight}/refresh`, {});
        const data = flight ? await api(`/api/v1/flights/${flight}/report`) : null;
        if (!cancelled && token === generation.current) {
          setFlights(list); setReport(data); setConnected(true);
        }
      } catch (e) {
        if (!cancelled) { setConnected(false); setReport(null); setError(e.message); speechSynthesis.cancel(); }
      } finally { refreshing = false; }
    }
    setReport(null); setConnected(false); refresh();
    const timer = setInterval(refresh, 1500);
    return () => { cancelled = true; clearInterval(timer); speechSynthesis.cancel(); };
  }, [flight]);

  async function perform(action) {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function incidentAction(id, action, reason) {
    return api(`/api/v1/incidents/${id}/actions`, { action, actor, reason });
  }
  useEffect(() => {
    let cancelled = false;
    setPolicyAcknowledged('');
    if (!flight || !connected || !flights.some(f => f.flight_id === flight && f.status === 'ACTIVE') || !actor.trim()) return;
    api(`/api/v1/flights/${flight}/advisory-policy`, {
      voice_enabled: voice, critical_phase: critical, radio_active: radio, actor,
    }).then(() => { if (!cancelled) setPolicyAcknowledged(policyKey); }).catch(e => setError(e.message));
    return () => { cancelled = true; };
  }, [flight, connected, voice, critical, radio, actor]);
  useEffect(() => {
    if (!connected || !report || report.terminal || policyAcknowledged !== policyKey) return;
    for (const incident of report.incidents.filter(i => i.status === 'OPEN')) {
      if (seen.current.has(incident.incident_id)) continue;
      const clearance = report.clearances.find(c => c.clearance_id === incident.clearance_id);
      // Never speak an old mismatch after inputs have become uncertain.
      if (!clearance || clearance.stages[incident.stage].verdict !== 'MISMATCH') continue;
      if (!voice || critical || radio || speechSynthesis.speaking) {
        const reason = !voice ? 'voice_disabled' : critical ? 'critical_phase' : radio ? 'radio_active' : 'voice_busy';
        incidentAction(incident.incident_id, 'VOICE_SUPPRESSED', reason).catch(() => {});
        continue;
      }
      seen.current.add(incident.incident_id);
      incidentAction(incident.incident_id, 'VOICE_REQUESTED', 'operator_enabled').then(result => {
        if (!result.recorded) return;
        const now = policy.current;
        if (!now.voice || now.critical || now.radio || !now.connected || now.flight !== flight) return;
        const utterance = new SpeechSynthesisUtterance('설정과 지시를 다시 확인해 주세요.');
        utterance.onstart = () => incidentAction(incident.incident_id, 'VOICE_PLAYED', 'browser_started').catch(e => setError(e.message));
        utterance.onerror = () => incidentAction(incident.incident_id, 'VOICE_SUPPRESSED', 'browser_playback_failed').catch(() => {});
        utterance.lang = 'ko-KR'; speechSynthesis.speak(utterance);
      }).catch(e => setError(e.message));
    }
  }, [report, connected, voice, critical, radio, actor, policyAcknowledged, policyKey]);
  useEffect(() => { if (!voice || critical || radio) speechSynthesis.cancel(); }, [voice, critical, radio]);

  const active = flights.find(f => f.flight_id === flight)?.status === 'ACTIVE';
  return <main className="operations-v1">
    <header><div><h1>RADAR 운영 화면</h1><p>모의 환경 · 조종사 재확인 보조 · 자동 설정 변경 없음</p></div><a href="/">태블릿 MCP</a></header>
    <p role="status" className={connected ? 'connection' : 'hold'}>{connected ? '서버 연결됨' : '판단 보류 — 서버 연결 확인 중'}</p>
    {error && <p role="alert" className="hold">{error}</p>}
    <section className="toolbar">
      <button disabled={busy || !connected} onClick={() => perform(async () => { const f = await api('/api/flights/start', {}); setFlight(f.flight_id); })}>START FLIGHT</button>
      <label>비행 <select value={flight} onChange={e => setFlight(e.target.value)}><option value="">선택</option>{flights.map(f => <option key={f.flight_id}>{f.flight_id}</option>)}</select></label>
      <button disabled={busy || !active || !connected} onClick={() => perform(() => api(`/api/v1/flights/${flight}/clearances`, {}))}>새 지시 준비</button>
      <button disabled={busy || !active || !connected} onClick={() => perform(() => api(`/api/flights/${flight}/end`, {}))}>END FLIGHT</button>
    </section>
    <section className="toolbar"><label>확인자 <input value={actor} onChange={e => setActor(e.target.value)} /></label>
      <label><input type="checkbox" checked={voice} onChange={e => setVoice(e.target.checked)} />보조 음성 허용</label>
      <label><input type="checkbox" checked={critical} onChange={e => setCritical(e.target.checked)} />중요 비행 단계 — 음성 억제</label>
      <label><input type="checkbox" checked={manualRadio} onChange={e => setRadio(e.target.checked)} />교신/마이크 사용 중 — 음성 억제</label>
      {radio && <p>원본 음성 재생·마이크 입력 또는 교신 설정으로 보조 음성 억제 중</p>}</section>
    {report && <>
      <section><h2>{report.terminal ? '종료 시점 리포트' : '현재 비행'}</h2><p>{Object.entries(report.summary).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p>
        <a href={`/api/v1/flights/${flight}/report.json`} download>리포트 JSON 저장</a></section>
      {report.clearances.map(c => <section key={c.clearance_id}>
        <h2>{c.clearance_id}</h2><p className={c.verdict === 'NORMAL' ? 'normal' : c.verdict === 'MISMATCH' ? 'mismatch' : 'hold'}>{c.verdict} · {c.status}{!c.active && ' · 이전 지시'}</p>
        <p>{c.reasons.join(' · ')}</p>
        {!c.validation_context && c.active && active && <details><summary>검사 정책·호출부호·지시 문맥 확인</summary>
          <p>관측을 보내기 전에 호출부호와 기대 지시를 확인합니다. 아래 기준은 모의 예시이며 운용 기준이 아닙니다. 조건부 지시는 고급 설정에서 문맥을 명시합니다.</p>
          <label>호출부호 <input value={callsign} onChange={e => setCallsign(e.target.value)} /></label>
          <label>지시 고도 (feet, 미지시 시 비움) <input type="number" min="0" max="60000" value={targetAltitude} onChange={e => setTargetAltitude(e.target.value)} /></label>
          <label>지시 방위 (0–359, 미지시 시 비움) <input type="number" min="0" max="359" value={targetHeading} onChange={e => setTargetHeading(e.target.value)} /></label>
          <label>최소 모델 점수 (정확도 아님) <input type="number" min="0" max="1" step="0.01" value={score} onChange={e => setScore(e.target.value)} /></label>
          <p>순서: 고도 → 방위 · 최대 고도 {demoPolicy.max_altitude_feet}ft · {demoPolicy.change_window_seconds}초 내 고도 변화 {demoPolicy.max_altitude_change_feet}ft/방위 변화 {demoPolicy.max_heading_change_degrees}도 초과 시 보류</p>
          <details><summary>고급 정책·조건·순서 설정</summary><textarea aria-label="검사 설정 JSON" rows={8} value={settings} onChange={e => setSettings(e.target.value)} /></details>
          <button disabled={busy || !actor.trim()} onClick={() => perform(() => {
            if (!settings.trim() && (!callsign.trim() || ![targetAltitude, targetHeading].some(v => v !== '') ||
                ![targetAltitude, targetHeading].every(v => v === '' || /^\d+$/.test(v)) ||
                Number(targetAltitude) > 60000 || Number(targetHeading) > 359 || score === '' || Number(score) < 0 || Number(score) > 1))
              throw new Error('호출부호·지시 범위·모델 점수를 확인하세요.');
            return api(`/api/v1/clearances/${c.clearance_id}/validation-settings`, settings.trim() ? JSON.parse(settings) : {
              confirmed: true, confirmed_by: actor, rule_policy: demoPolicy, minimum_model_score: Number(score),
              atc_context: { expected_callsign: callsign.trim(), expected_conditions: [], expected_ordered_actions:
                [['altitude', targetAltitude], ['heading', targetHeading]].filter(([, value]) => value !== '').map(([key, value]) => `${key} ${Number(value)}`) },
            });
          })}>설정 확인</button></details>}
        <div className="sources">{['ATC', 'READBACK', 'COCKPIT'].map(source => {
          const o = c.observations[source]; const stage = c.stages[source.toLowerCase()];
          return <article key={source}><h3>{source} · {stage.verdict}</h3><p>{stage.reasons.join(' · ')}</p>
            {!o ? <p>입력 없음</p> : <><p>입력: {o.input_mode}<br />관측 {o.captured_at ?? '시각 불명'}<br />채널 {o.health.status} · {o.health.reason}</p>
              {Object.entries(o.fields).map(([name, field]) => <p key={name}>{name}: {field?.value ?? '판독 불가'} {field?.unit}<br />{field?.reason} · 품질 {field?.quality.status} · 모델 점수 {field?.model_score ?? '없음'} (정확도 아님)</p>)}
              {o.speech && <p>원문: {o.speech.transcript ?? '없음'}</p>}
              {o.evidence.map(e => {
                const safe = e.reference.startsWith(`/api/v1/clearances/${c.clearance_id}/evidence/`);
                return <div key={e.evidence_id}>{!safe || e.availability !== 'available' || evidenceErrors[e.evidence_id] ? <p>근거 접근 불가: {e.evidence_id}</p> : e.kind === 'audio' ? <audio controls src={e.reference}
                  onPlay={() => setPlaying(v => ({ ...v, [e.evidence_id]: true }))}
                  onPause={() => setPlaying(v => ({ ...v, [e.evidence_id]: false }))}
                  onEnded={() => setPlaying(v => ({ ...v, [e.evidence_id]: false }))}
                  onError={() => setEvidenceErrors(v => ({ ...v, [e.evidence_id]: true }))} /> : <img alt={`${source} 관측 근거`} src={e.reference} onError={() => setEvidenceErrors(v => ({ ...v, [e.evidence_id]: true }))} />}<p>ROI: {e.roi?.join(', ') ?? '전체 원본'}</p></div>;
              })}</>}
          </article>;
        })}</div>
      </section>)}
      <section><h2>사건·수정 이력</h2>{report.incidents.map(i => <article key={i.incident_id}><p>{i.stage} · {i.status} · {i.detected_at} → {i.resolved_at ?? '미해결'} {i.resolution_seconds !== null && `(${i.resolution_seconds}초)`}</p>
        <pre>{JSON.stringify(i.errors, null, 2)}</pre>{active && i.status === 'OPEN' && <button disabled={busy || !actor.trim()} onClick={() => perform(() => incidentAction(i.incident_id, 'ACKNOWLEDGED', 'operator_reviewed'))}>근거 확인함</button>}</article>)}</section>
      <section><h2>모의 세션 피드백</h2>{report.training_feedback.map(item => <p key={item.incident_id}>{item.stage} · {item.fields.join(', ')}: {item.message}<br />{item.limitation}</p>)}</section>
      <details><summary>Safety Trace ({report.timeline.length})</summary>{report.timeline.map(e => <p key={e.id}>{e.timestamp} · {e.kind} · {JSON.stringify(e.data)}</p>)}</details>
    </>}
  </main>;
}
