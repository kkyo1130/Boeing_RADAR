import React, { useEffect, useRef, useState } from 'react';
import { request } from './flight-client.js';

export function selectionFor(snapshot, row) {
  return { flight_id: snapshot.flight_id, observation_id: row.observation_id, instruction_id: row.instruction_id,
    stage: row.stage, field: row.field };
}
export function selectionMatches(snapshot, selected) {
  const group = selected?.stage === 'READBACK' ? 'readback' : 'setting';
  return snapshot?.flight_id === selected?.flight_id && snapshot.validation[group].fields.some(row =>
    row.instruction_id === selected.instruction_id && row.observation_id === selected.observation_id && row.field === selected.field);
}
export function evidenceUrl(selected) {
  const query = new URLSearchParams({ instruction_id: selected.instruction_id, stage: selected.stage, field: selected.field });
  return `/api/v2/flights/${encodeURIComponent(selected.flight_id)}/evidence/${encodeURIComponent(selected.observation_id)}?${query}`;
}
export function safeMediaUrl(url, selected) {
  if (typeof url !== 'string' || !url.startsWith(`/api/v2/flights/${encodeURIComponent(selected.flight_id)}/evidence/${encodeURIComponent(selected.observation_id)}/media/`)) return null;
  if (url.includes('..') || url.includes('\\')) return null;
  return url;
}
export async function recordInteraction(selected, action, eventId) {
  const { flight_id, ...context } = selected;
  return request(`/api/v2/flights/${encodeURIComponent(flight_id)}/interactions`, {
    method: 'POST', body: { ...context, action, event_id: eventId },
  });
}

function MediaAsset({ asset, selected, transcript }) {
  const [failed, setFailed] = useState(false), element = useRef(null);
  const url = safeMediaUrl(asset.url, selected);
  useEffect(() => { const player = element.current; return () => { if (player?.pause) { player.pause(); player.removeAttribute('src'); player.load(); } }; }, []);
  if (asset.kind === 'TRANSCRIPT') return <p>{transcript ? '대본 근거는 위 텍스트로 표시합니다.' : '대본이 제공되지 않았습니다.'}</p>;
  if (!url || failed) return <p role="status">{asset.kind === 'AUDIO' ? '원본 음성을' : '근거 이미지를'} 열 수 없습니다. <small>{failed ? '파일 접근 또는 재생 실패' : asset.unavailable_reason || '근거 참조 확인 불가'}</small></p>;
  return <figure>{asset.kind === 'AUDIO'
    ? <audio ref={element} controls preload="none" src={url} onError={() => setFailed(true)} aria-label="선택한 관측 원본 음성" />
    : <img src={url} onError={() => setFailed(true)} alt={`${selected.field} ${asset.kind === 'ROI' ? 'ROI' : '프레임'} 근거 이미지`} />}
    <figcaption>{asset.kind} · {asset.evidence_id}{asset.roi && ` · ROI ${asset.roi.join(', ')}`}</figcaption></figure>;
}

export function EvidenceContents({ data, selected }) {
  return <>{Object.entries(data.groups).map(([role, group]) => <article className="op-evidence-group" key={role}>
    <h3>{role === 'ATC' ? '관제 지시 원본' : '선택한 관측 원본'}</h3>
    <small>관측 {group.observation_id} · 원본 시각 {group.observed_at || '시각 미상'}</small>
    {group.transcript && <blockquote>{group.transcript}</blockquote>}
    {group.reading && <p>입력 품질: {group.reading.quality?.input_quality || '미상'} · 모델 점수: {group.reading.quality?.model_score ?? '없음'} <small>모델 점수는 검증된 정확도가 아닙니다.</small></p>}
    {!group.assets.length && <p>근거 자료가 없습니다. <small>{group.evidence_unavailable_reason || '근거 미제공'}</small></p>}
    {group.assets.map(asset => <MediaAsset key={asset.evidence_id} asset={asset} selected={selected} transcript={group.transcript} />)}
  </article>)}</>;
}

export default function EvidencePanel({ selected, snapshot, connected, onClose }) {
  const [state, setState] = useState({ data: null, error: '', viewed: '' }), panel = useRef(null);
  const matches = selectionMatches(snapshot, selected);
  const key = JSON.stringify(selected);
  useEffect(() => {
    setState({ data: null, error: '', viewed: '' });
    if (!matches || !connected) return;
    const controller = new AbortController(); let stopped = false;
    panel.current?.focus();
    async function open() {
      try {
        const data = await request(evidenceUrl(selected), { signal: controller.signal });
        if (stopped) return;
        if (data.flight_id !== selected.flight_id || data.observation_id !== selected.observation_id ||
          data.instruction_id !== selected.instruction_id || data.stage !== selected.stage || data.field !== selected.field) throw new Error('선택한 항목과 근거가 일치하지 않습니다.');
        setState({ data, error: '', viewed: '' });
        try {
          await recordInteraction(selected, 'EVIDENCE_OPENED', crypto.randomUUID());
          if (!stopped) setState(previous => ({ ...previous, viewed: '패널 열람 기록 저장됨 · 재생 완료나 오류 해결을 뜻하지 않습니다' }));
        } catch { if (!stopped) setState(previous => ({ ...previous, viewed: '열람 기록 저장 실패 · 근거 확인은 계속할 수 있습니다' })); }
      } catch (e) { if (!stopped) setState({ data: null, error: e.message, viewed: '' }); }
    }
    open();
    return () => { stopped = true; controller.abort(); };
  }, [key, matches, connected]);
  return <aside className="op-panel op-evidence" aria-label="선택 근거 패널" tabIndex={-1} ref={panel}>
    <div className="op-section-heading"><h2>선택한 항목의 근거</h2><button onClick={onClose}>근거 닫기</button></div>
    <p>{selected.stage === 'READBACK' ? '복명복창' : '설정'} · {selected.field} · {selected.instruction_id}</p>
    {!matches ? <p role="status">새 지시 또는 새 관측이 도착했습니다. 최신 항목의 근거를 다시 여세요.</p>
      : !connected ? <p role="status">서버 연결 복구 후 근거를 다시 확인합니다.</p>
      : state.error ? <p role="alert">근거를 열 수 없습니다. {state.error}</p>
      : state.data ? <EvidenceContents data={state.data} selected={selected} /> : <p role="status">근거를 불러오고 있습니다.</p>}
    {matches && connected && state.viewed && <p className="op-muted" role="status">{state.viewed}</p>}
    <p>근거 열람·확인은 수정 시작의 필수 단계가 아닙니다. 해결은 새 유효 관측으로 서버가 확인합니다.</p>
  </aside>;
}
