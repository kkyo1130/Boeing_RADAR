import React, { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import cockpitReference from '../../docs/vision/assets/mcp-reference.png';

const initial = { speed: 250, heading: 270, altitude: 3000 };
const instruments = [
  { key: 'speed', title: 'IAS', unit: 'KNOTS', step: 1, min: 0, max: 999, digits: 3, roi: [509, 282, 601, 313] },
  { key: 'heading', title: 'HEADING', unit: 'DEGREES', step: 1, min: 0, max: 359, digits: 3, roi: [692, 282, 786, 314] },
  { key: 'altitude', title: 'ALTITUDE', unit: 'FEET', step: 100, min: 0, max: 99900, digits: 5, roi: [864, 282, 968, 314] },
];

function NumericDisplay({ text }) {
  return <svg className="digital-numbers" viewBox={`0 0 ${text.length * 32} 50`} aria-hidden="true">
    <text x={text.length * 16} y="39" textAnchor="middle" fontFamily="Courier New, monospace" fontSize="48" fontWeight="700">{text}</text>
  </svg>;
}

function App() {
  const [values, setValues] = useState(initial);
  const [hidden, setHidden] = useState({});
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [capture, setCapture] = useState(false);
  const [zoom, setZoom] = useState(true);
  const [fullscreenError, setFullscreenError] = useState('');
  const editorOpener = useRef(null);

  function change(item, direction) {
    setValues(previous => {
      const next = previous[item.key] + direction * item.step;
      return { ...previous, [item.key]: item.key === 'heading'
        ? (next + 360) % 360 : Math.min(item.max, Math.max(item.min, next)) };
    });
  }
  function preset(altitude, heading) {
    setValues(previous => ({ ...previous, altitude, heading }));
    setHidden({});
  }
  function openEditor(item) {
    editorOpener.current = document.activeElement;
    setEditing(item); setDraft(String(values[item.key])); setError('');
  }
  function closeEditor() {
    setEditing(null);
    editorOpener.current?.focus();
  }
  function editorKey(event) {
    if (event.key === 'Escape') closeEditor();
    if (event.key !== 'Tab') return;
    const targets = Array.from(event.currentTarget.querySelectorAll('input, button'));
    const first = targets[0], last = targets[targets.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  }
  function save(event) {
    event.preventDefault();
    const value = Number(draft);
    if (!/^\d+$/.test(draft) || !Number.isInteger(value) || value < editing.min || value > editing.max) {
      setError(`${editing.min}~${editing.max} 사이 정수를 입력하세요.`); return;
    }
    setValues(previous => ({ ...previous, [editing.key]: value }));
    closeEditor();
  }
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else setFullscreenError('이 브라우저에서는 촬영 모드로 전환하고 주소창을 접어주세요.');
    } catch {
      setFullscreenError('전체 화면을 열 수 없습니다. 촬영 모드를 사용하세요.');
    }
  }

  return <main className={capture ? 'capture-mode' : ''}>
    <header>
      <a className="brand" href="#">RADAR<span> / MCP LAB</span></a>
      <span className="simulation">모의 MCP · 수동 조작</span>
      <div className="header-actions">
        <button onClick={fullscreen}>전체 화면</button>
        <button className="primary" aria-pressed={capture} onClick={() => setCapture(!capture)}>
          {capture ? '설정 보기' : '촬영 모드'}
        </button>
      </div>
    </header>
    {fullscreenError && <p className="notice" role="status">{fullscreenError}</p>}
    <section className="intro">
      <p className="eyebrow">TABLET CAMERA DEMO</p>
      <h1>Cockpit을 화면에,<br />선택값은 직접 조작.</h1>
      <p>사진 위 세 숫자 창을 터치해 값을 바꾸세요. 아래 계기 화면은 고정된 참고 이미지입니다.</p>
    </section>
    <div className="view-toolbar">
      <span>COCKPIT REFERENCE / MANUAL MCP</span>
      <button aria-pressed={zoom} onClick={() => setZoom(!zoom)}>{zoom ? '전체 조종석 보기' : 'MCP 확대 보기'}</button>
    </div>
    <section className={`cockpit-scene ${zoom ? 'mcp-closeup' : ''}`} aria-label="사진 기반 모의 MCP 선택 설정값">
      <div className="cockpit-photo">
        <img src={cockpitReference} alt="MCP와 주변 계기·조종간이 보이는 참고 Cockpit 사진" draggable="false" />
        {instruments.map(item => {
          const [left, top, right, bottom] = item.roi;
          return <button key={item.key} className={`readout photo-readout ${hidden[item.key] ? 'covered' : ''}`}
            style={{ left: `${left / 1672 * 100}%`, top: `${top / 941 * 100}%`, width: `${(right - left) / 1672 * 100}%`, height: `${(bottom - top) / 941 * 100}%` }}
            aria-label={`${item.title} ${hidden[item.key] ? '가림' : values[item.key]}, 값 입력`}
            onClick={() => openEditor(item)}>
            {!hidden[item.key] && <NumericDisplay text={String(values[item.key]).padStart(item.digits, '0')} />}
          </button>;
        })}
      </div>
      <span className="scene-label">RADAR · SIMULATED MCP</span>
    </section>
    <section className="instrument-controls" aria-label="MCP 값 수동 조작">
      {instruments.map(item => <article className="instrument" key={item.key}>
          <div className="instrument-label"><h2>{item.title}</h2><span>{item.unit}</span></div>
          <button className="control-value" onClick={() => openEditor(item)} aria-label={`${item.title} 선택값 입력`}>
            {String(values[item.key]).padStart(item.digits, '0')}
          </button>
          <div className="dial">
            <button aria-label={`${item.title} 감소`} onClick={() => change(item, -1)}>−</button>
            <span className="knob" aria-hidden="true"><i /></span>
            <button aria-label={`${item.title} 증가`} onClick={() => change(item, 1)}>+</button>
          </div>
          <button className="cover-button" aria-pressed={!!hidden[item.key]}
            onClick={() => setHidden(previous => ({ ...previous, [item.key]: !previous[item.key] }))}>
            {hidden[item.key] ? '가림 해제' : '숫자 창 가리기'}
          </button>
        </article>)}
    </section>
    <section className="controls" aria-label="수동 데모 시나리오">
      <div><p className="eyebrow">MANUAL SCENARIOS</p><h2>데모 값 전환</h2><p>선택값만 변경합니다. 정상·오류 판정은 서버에서 수행합니다.</p></div>
      <div className="presets">
        <button onClick={() => preset(3000, 270)}><strong>기준값</strong><span>03000 / 270</span></button>
        <button onClick={() => preset(3500, 270)}><strong>ALT 변경</strong><span>03500 / 270</span></button>
        <button onClick={() => preset(3000, 290)}><strong>HDG 변경</strong><span>03000 / 290</span></button>
        <button onClick={() => { setValues(initial); setHidden({}); }}><strong>초기화</strong><span>IAS 250 포함</span></button>
      </div>
    </section>
    <footer>촬영 전 화면 회전·밝기를 고정하세요. 가림·흐림·반사는 실제 촬영에서도 확인하세요.</footer>
    {editing && <div className="modal-backdrop" onClick={closeEditor}>
      <form className="editor" role="dialog" aria-modal="true" aria-labelledby="editor-title"
        onSubmit={save} onClick={event => event.stopPropagation()} onKeyDown={editorKey}>
        <h2 id="editor-title">{editing.title} 선택값</h2>
        <label htmlFor="selected-value">{editing.unit} · {editing.min}~{editing.max}</label>
        <input id="selected-value" autoFocus inputMode="numeric" value={draft}
          onChange={event => setDraft(event.target.value)} />
        {error && <p role="alert">{error}</p>}
        <div><button type="button" onClick={closeEditor}>취소</button><button className="primary" type="submit">적용</button></div>
      </form>
    </div>}
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
