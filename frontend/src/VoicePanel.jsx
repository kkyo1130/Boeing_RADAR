import React, { useEffect, useRef, useState } from 'react';
import { request } from './flight-client.js';
import { AdvisoryPlayer } from './advisory-player.js';
import { audioFocus } from './audio-focus.js';

export default function VoicePanel({ snapshot, connected }) {
  const [view, setView] = useState({ enabled: false, message: '음성 안내를 켜면 현재 유효한 안내부터 재생합니다', inputs: [] });
  const player = useRef(null), latest = useRef({ snapshot, connected }); latest.current = { snapshot, connected };
  useEffect(() => {
    const p = new AdvisoryPlayer({ flightId: snapshot.flight_id, request, notify: setView }); player.current = p;
    const unregister = audioFocus.register(p);
    const timer = setInterval(() => { p.update(latest.current.snapshot, latest.current.connected); p.tick(); }, 250);
    return () => { clearInterval(timer); unregister(); p.close(); player.current = null; };
  }, [snapshot.flight_id]);
  useEffect(() => { player.current?.update(snapshot, connected); }, [snapshot, connected]);
  const inputs = new Map((snapshot.voice?.inputs || []).map(i => [i.token, i]));
  view.inputs.forEach(i => inputs.set(i.token, i));
  const ended = snapshot.status !== 'ACTIVE';
  return <section className="op-panel" aria-label="보조 음성 안내">
    <div className="op-section-heading"><h2>보조 음성 안내</h2><button disabled={ended || !connected} onClick={() => view.enabled ? player.current?.disable() : player.current?.enable()}>{view.enabled ? '음성 안내 끄기' : '음성 안내 켜기'}</button></div>
    <p role="status">{!connected ? '서버 연결 확인 불가 · 음성 안내 보류' : ended ? '비행 종료 · 음성 안내 중지' : view.message}</p>
    {snapshot.voice?.episodes.CAMERA && <p>카메라 연결 끊김 · 새 영상 입력 복구 대기</p>}
    {snapshot.voice?.episodes.VISIBILITY && <p>계기판 가림 · 계기판이 보이도록 해주세요</p>}
    <p>오류를 해결했는지는 새 관측으로 확인합니다. 음성 재생 완료는 오류 해결이 아닙니다.</p>
    {!!inputs.size && <div><p>입력 중 · 안내 보류</p>{[...inputs.values()].map(input => <p key={input.token}>{input.kind} <small>{input.token}</small> <button disabled={!connected || ended} onClick={() => audioFocus.end(input)}>입력 종료 확인</button></p>)}</div>}
    <details><summary>최근 음성 기록</summary><ul>{(snapshot.voice?.history || []).map(item => <li key={item.attempt_id}>{item.text} · { {COMPLETED:'재생 완료',INTERRUPTED:'중단',FAILED:'재생 실패',CANCELLED:'취소',PLAYING:'재생 예약/진행'}[item.status] } <small>{item.attempt_id} · {item.occurrence_ids.join(', ')} · {item.finished_at || item.started_at}</small></li>)}</ul></details>
  </section>;
}
