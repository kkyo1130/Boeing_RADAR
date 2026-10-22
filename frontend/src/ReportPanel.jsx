import React, { useEffect, useState } from 'react';
import { request } from './flight-client.js';

export default function ReportPanel({ flightId, ended, connected }) {
  const [report, setReport] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    const abort = new AbortController();
    setReport(null); setError('');
    if (ended && connected) request(`/api/v2/flights/${encodeURIComponent(flightId)}/report`, { signal: abort.signal })
      .then(data => { if (!abort.signal.aborted) setReport(data); })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [flightId, ended, connected]);
  if (!ended) return null;
  return <section className="op-panel" aria-label="비행 종료 리포트">
    <h2>비행 종료 리포트</h2>
    <p>종료 시점에 기록한 마지막 판정입니다. 현재 운항 판단이나 모델 정확도가 아닙니다.</p>
    {error && <p role="alert">리포트를 불러오지 못했습니다: {error}</p>}
    {report && connected ? <>
      <p>종료 직전 판정: {report.snapshot.result} · 발생 {report.summary.incidents}건 · 해결 {report.summary.resolved}건 · 미해결 {report.summary.open}건 · 대체 {report.summary.superseded}건</p>
      <a href={`/api/v2/flights/${encodeURIComponent(flightId)}/report.json`} download>리포트 JSON 저장</a>
    </> : !error && <p>리포트를 확인하고 있습니다.</p>}
  </section>;
}
