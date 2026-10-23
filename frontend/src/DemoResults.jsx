import React from 'react';
import {numberLabel, statusLabel} from './flight-client.js';
import './demo.css';
const names = {ALT:'고도', HDG:'방위', CALLSIGN:'호출부호'};
const explanations = {
  READBACK_NOT_CONFIRMED: '복창 확인이 먼저 필요합니다. 카메라 값은 계속 갱신 중입니다.',
  INPUT_NOT_AVAILABLE: '아직 확인할 수 있는 입력이 없습니다.',
  callsign_not_recognized: '호출부호를 인식하지 못했습니다. Radar one two three부터 다시 복창하세요.',
  CALLSIGN_PREFIX_NOT_UNIQUE: '호출부호를 인식하지 못했습니다. Radar one two three부터 다시 복창하세요.',
  INITIAL_ADJUSTMENT_WAIT: '아이패드 설정 변경 대기 중입니다.',
  STALE_OBSERVATION: '입력이 오래되었습니다. 새 입력으로 다시 확인하세요.',
  CHANNEL_UNAVAILABLE: '입력 장치가 중단되었습니다. 장치 연결과 연속 OCR을 확인하세요.',
  INPUT_QUALITY_UNVERIFIED: '입력을 명확하게 인식하지 못했습니다. 다시 입력하세요.',
};
export default function DemoResults({snapshot, connected, transcript = '', pending = false}) {
  const live = connected && snapshot.status === 'ACTIVE';
  const check = snapshot.structure_checks?.READBACK;
  const issue = check?.checks?.find(c => c.result !== 'PASS');
  return <section className="demo-results" aria-label="시연 실시간 결과">
    <div className="demo-result-grid">{[['readback','1. 복명복창','조종사 복창'],['setting','2. 아이패드 설정','카메라 인식']].map(([key,title,source]) => {
      const group=snapshot.validation[key];
      const result=live && !pending ? group.result : 'UNVERIFIED';
      const reason=key==='readback' && issue ? issue.reason : group.fields.find(r=>r.result!=='NORMAL')?.reason;
      const detail=!live ? '현재 연결을 확인할 수 없습니다. 아래 숫자는 마지막 기록입니다.' : pending ? '복창 녹음·인식 중입니다. 새 결과를 기다리세요.' : explanations[reason] || (result==='MISMATCH' ? '표시된 항목이 관제 지시와 다릅니다. 다시 확인하세요.' : result==='NORMAL' ? '관제 지시와 일치합니다.' : '발화 전체를 해석할 수 없습니다. 아래 인식 문장을 확인하고 다시 복창하세요.');
      return <article key={key} className={`demo-result op-${result}`}>
        <div className="op-section-heading"><h2>{title}</h2><strong className="demo-verdict" role="status">{statusLabel(result)}</strong></div>
        <p className="demo-result-help">{detail}</p>
        <div className="demo-values">{group.fields.map(row=><div key={row.field} className={live && !pending ? `op-${row.result}` : 'op-UNVERIFIED'}>
          <span>{names[row.field]}</span><small>관제 {numberLabel(row.expected,row.field)}</small>
          <strong>{numberLabel(row.actual,row.field)}</strong><small>{source} · {live && !pending ? statusLabel(row.result) : '판단 보류'}</small>
        </div>)}</div>
        {!group.fields.length && <p>관제 지시를 재생하고 복창을 시작하세요.</p>}
        {key==='readback' && <p className="demo-transcript"><b>실제 인식 문장</b><br/>{pending ? '새 복창을 처리하고 있습니다…' : transcript || '아직 이 화면에서 녹음한 문장이 없습니다.'}</p>}
        {key==='setting' && <p className="op-muted">아이패드 숫자를 바꾸면 카메라 인식값이 갱신됩니다. 동일 값 3회 관측 후 반영됩니다.</p>}

      </article>;
    })}</div>
  </section>;
}
