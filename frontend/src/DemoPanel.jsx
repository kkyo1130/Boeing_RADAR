import React,{useEffect,useRef,useState} from 'react';
import {request} from './flight-client.js';
import {audioFocus} from './audio-focus.js';
import {microphone,base64} from './demo-audio.js';
import './demo.css';
import DemoResults from './DemoResults.jsx';
import {readAtcAttempt,writeAtcAttempt,atcAttemptKey} from './atc-attempt.js';

export default function DemoPanel({snapshot,connected,onSpeech}) {
  const flight=snapshot.flight_id, latest=useRef({snapshot,connected});latest.current={snapshot,connected};
  const calibrationImage=useRef(null);
  const video=useRef(null), canvas=useRef(null), camera=useRef(null), mic=useRef(null), drag=useRef(null), loop=useRef(null), capture=useRef(null), busyRef=useRef(false), alive=useRef(true);
  const [devices,setDevices]=useState([]),[cameraId,setCameraId]=useState(''),[micId,setMicId]=useState(''),[preview,setPreview]=useState(false),[micReady,setMicReady]=useState(false),[level,setLevel]=useState(0);
  const [rois,setRois]=useState({}),[field,setField]=useState('ALT'),[frozen,setFrozen]=useState(null),[running,setRunning]=useState(false),[result,setResult]=useState(null),[message,setMessage]=useState('장치를 선택하고 미리보기를 연결하세요.'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[recording,setRecording]=useState(false),[transcript,setTranscript]=useState(''),[scenario,setScenario]=useState('baseline'),[status,setStatus]=useState(null);
  const [atcSource,setAtcSource]=useState('microphone_live');
  const [speechMode,setSpeechMode]=useState('ATC'),[atcTranscript,setAtcTranscript]=useState(''),[atcAttempt,updateAtcAttempt]=useState(()=>readAtcAttempt(flight)),[atcFile,setAtcFile]=useState(null);
  function setAtcAttempt(value){writeAtcAttempt(flight,value);updateAtcAttempt(value);}
  useEffect(()=>{
    updateAtcAttempt(readAtcAttempt(flight));
    const sync=e=>{if(e.key===atcAttemptKey(flight)||e.key===null)updateAtcAttempt(readAtcAttempt(flight));};
    window.addEventListener('storage',sync);
    return()=>window.removeEventListener('storage',sync);
  },[flight]);
  const pilotPending=(recording||busy)&&capture.current?.kind==='PILOT';
  const speechPending=pilotPending || !!(atcAttempt && snapshot.readback_required?.atc_input_id!==atcAttempt);
  const canReadback=!!snapshot.readback_required && snapshot.validation.reason!=='LATEST_ATC_NOT_ADOPTED' && (!atcAttempt || snapshot.readback_required.atc_input_id===atcAttempt);
  useEffect(()=>{onSpeech?.({transcript, pending:speechPending});},[transcript,speechPending,onSpeech]);
  useEffect(()=>()=>{if(atcFile)URL.revokeObjectURL(atcFile.url);},[atcFile]);
  const disabled=!connected || snapshot.status!=='ACTIVE';
  const api=(path,body,timeout=10000)=>request(`/api/demo/${flight}/${path}`,{method:'POST',body,timeout});
  async function health(channel,state,reason=null) {
    return request(`/api/v2/flights/${flight}/health-events`,{method:'POST',body:{schema_version:'2',event_id:crypto.randomUUID(),flight_id:flight,channel,observed_at:new Date().toISOString(),health:{status:state,reason}}});
  }
  const fail=e=>{if(alive.current){setError(e.message);setMessage('입력 중단 · 장치와 설정을 확인하세요.');}};
  async function action(task){if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');try{await task();}catch(e){fail(e);}finally{busyRef.current=false;if(alive.current)setBusy(false);}}
  async function list(){setDevices(await navigator.mediaDevices.enumerateDevices());}
  useEffect(()=>{alive.current=true;request('/api/demo/status').then(setStatus).catch(fail);list().catch(fail);
    return()=>{alive.current=false;const active=loop.current;loop.current=null;clearTimeout(active?.timer);camera.current?.getTracks().forEach(t=>t.stop());mic.current?.close();
      if(capture.current){clearTimeout(capture.current.timer);capture.current.audio?.pause();audioFocus.end(capture.current.focus).catch(()=>{});capture.current=null;}
      health('CAMERA','DISCONNECTED','demo_panel_closed').catch(()=>{});
    };},[flight]);
  useEffect(()=>{if(disabled){stopCamera();if(capture.current)cancelInput().catch(fail);}},[disabled]);
  useEffect(()=>{const hide=()=>{if(document.hidden){stopCamera();cancelInput().catch(fail);}};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide);},[]);
  async function connectCamera(){await stopCamera();camera.current?.getTracks().forEach(t=>t.stop());setFrozen(null);calibrationImage.current=null;setRois({});
    const stream=await navigator.mediaDevices.getUserMedia({video:{deviceId:cameraId?{exact:cameraId}:undefined,width:{ideal:1920},height:{ideal:1080}},audio:false});
    if(!alive.current){stream.getTracks().forEach(t=>t.stop());return;}
    camera.current=stream;video.current.srcObject=stream;await video.current.play();setPreview(true);await list();
    stream.getVideoTracks()[0].onended=()=>{stopCamera();setPreview(false);fail(new Error('카메라 연결이 끊겼습니다.'));};
    setMessage('영역 설정을 누른 뒤 ALT와 HDG 숫자만 드래그하세요.');
  }
  async function connectMic(){mic.current?.close();mic.current=await microphone(micId,n=>alive.current&&setLevel(n));setMicReady(true);await list();await health('MICROPHONE','AVAILABLE');
    mic.current.stream.getAudioTracks()[0].onended=()=>{cancelInput();setMicReady(false);health('MICROPHONE','DISCONNECTED','microphone_disconnected').catch(fail);};}
  function frame(){const v=video.current;if(!v||v.readyState<2||!v.videoWidth)throw new Error('새 카메라 프레임이 없습니다.');const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return c;}
  async function freeze(){await stopCamera();const c=frame();calibrationImage.current=c.toDataURL('image/jpeg',.92);setFrozen(calibrationImage.current);setRois({});setField('ALT');const target=canvas.current;target.width=c.width;target.height=c.height;target.getContext('2d').drawImage(c,0,0);}
  function point(e){const c=canvas.current,b=c.getBoundingClientRect();return [Math.round(Math.max(0,Math.min(c.width,(e.clientX-b.left)*c.width/b.width))),Math.round(Math.max(0,Math.min(c.height,(e.clientY-b.top)*c.height/b.height)))];}
  function draw(next){const image=new Image();image.onload=()=>{const c=canvas.current;if(!c)return;const ctx=c.getContext('2d');ctx.drawImage(image,0,0);ctx.lineWidth=3;for(const [name,r] of Object.entries(next)){ctx.strokeStyle=name==='ALT'?'#71e6c0':'#77afff';ctx.strokeRect(r[0],r[1],r[2]-r[0],r[3]-r[1]);ctx.font='22px sans-serif';ctx.fillStyle=ctx.strokeStyle;ctx.fillText(name,r[0],r[1]-6);}};image.src=frozen;}
  function selectEnd(e){if(!drag.current)return;const end=point(e),start=drag.current;drag.current=null;const roi=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];if(roi[2]-roi[0]<10||roi[3]-roi[1]<10){fail(new Error('숫자 전체가 들어가게 영역을 크게 선택하세요.'));return;}const next={...rois,[field]:roi};setRois(next);draw(next);setField(field==='ALT'?'HDG':'ALT');}
  async function stopCamera(){const active=loop.current;loop.current=null;clearTimeout(active?.timer);if(alive.current){setRunning(false);setResult(null);setMessage('OCR 중지 · 다시 시작하려면 영역을 확인하세요.');}if(active)await health('CAMERA','DISCONNECTED','camera_capture_stopped').catch(fail);}
  async function startCamera(){if(!rois.ALT||!rois.HDG)throw new Error('ALT와 HDG 영역을 모두 지정하세요.');
    const calibration=await api('calibration',{image:calibrationImage.current.split(',')[1],rois});await health('CAMERA','AVAILABLE');setFrozen(null);setRunning(true);
    const active={token:calibration.token,lastMediaTime:-1,timer:null};loop.current=active;
    async function tick(){if(loop.current!==active)return;
      try{if(!latest.current.connected||latest.current.snapshot.status!=='ACTIVE')throw new Error('서버 연결 또는 비행 상태를 확인하세요.');
        const v=video.current;if(v.paused||v.currentTime===active.lastMediaTime)throw new Error('카메라에서 새 프레임이 오지 않습니다.');active.lastMediaTime=v.currentTime;
        const revision=latest.current.snapshot.revision,c=frame(),captured_at=new Date().toISOString();
        const data=await api('frame',{token:active.token,target_revision:revision,captured_at,image:c.toDataURL('image/jpeg',.92).split(',')[1]},45000);
        if(loop.current!==active)return;setResult(data);setMessage('연속 촬영 중 · 동일한 값 3회 후 서버 반영');active.timer=setTimeout(tick,1000);
      }catch(e){await stopCamera();fail(e);}}
    tick();
  }
  async function cancelInput(){const item=capture.current;if(!item)return;capture.current=null;clearTimeout(item.timer);item.audio?.pause();item.reject?.(new Error('입력 취소'));if(item.microphone)mic.current?.stop();setRecording(false);await audioFocus.end(item.focus);await health('MICROPHONE','DEGRADED','capture_cancelled').catch(fail);}
  async function playScenario(){setAtcAttempt('pending');const focus=await audioFocus.begin('ATC');if(!focus)throw new Error('관제 재생 예약 실패 · 음성 안내 연결을 확인하세요.');
    const audio=new Audio(`/api/demo/scenarios/${scenario}/audio`),item={focus,audio,kind:'ATC'};capture.current=item;
    setTranscript('');const started_at=new Date().toISOString();setMessage('사전 등록 관제 음성 재생 중 · ATC 음성 인식은 사용하지 않습니다.');
    try{await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(new Error('관제 음성 재생 실패'));item.reject=reject;audio.play().catch(reject);item.timer=setTimeout(()=>reject(new Error('관제 재생 시간 초과')),30000);});
      if(capture.current!==item)throw new Error('관제 재생 취소');
      const data=await api(`scenario/${scenario}`,{started_at,ended_at:new Date().toISOString()},15000);setAtcAttempt(data.atc_input_id);setMessage('등록 관제 전송 완료 · 서버 지시가 표시되면 복창을 녹음하세요.');
    }finally{clearTimeout(item.timer);audio.pause();capture.current=null;await audioFocus.end(focus);}}
  async function startRecording(playFile=false){
    const kind=speechMode, inputMode=kind==='ATC'?atcSource:null;
    if(capture.current)throw new Error('기존 입력이 끝날 때까지 기다리세요.');
    if(!mic.current || (kind==='PILOT'&&!canReadback))throw new Error('마이크 연결과 현재 관제 지시를 확인하세요.');
    if(playFile && (!atcFile || kind!=='ATC' || inputMode!=='microphone_playback'))throw new Error('재생할 관제 녹음파일을 선택하세요.');
    if(kind==='ATC')setAtcAttempt('pending');
    await mic.current.setCaptureMode(kind,inputMode);
    await health('MICROPHONE','AVAILABLE');await health('SPEECH_API','AVAILABLE');
    const focus=await audioFocus.begin(kind);if(!focus)throw new Error('음성 입력 예약 실패');
    if(!alive.current||!latest.current.connected){await audioFocus.end(focus);return;}
    const item={kind,inputMode,focus,microphone:true,atc_input_id:kind==='PILOT'?latest.current.snapshot.readback_required.atc_input_id:null};
    capture.current=item;
    try{
      item.started_at=mic.current.start();setRecording(true);
      if(kind==='ATC'){setAtcTranscript('');setTranscript('');}
      else setTranscript('');
      setMessage(kind==='ATC'?(inputMode==='microphone_live'?'마이크 켜짐 · 관제사 역할 문장을 말한 뒤 녹음 종료를 누르세요.':'ATC 수음 중 · 별도 기기에서 관제 녹음을 재생하거나 선택한 파일을 들려주세요.'):'파일럿 복창 녹음 중 · 완료하면 녹음 종료를 누르세요.');
      item.timer=setTimeout(()=>{if(capture.current===item)action(async()=>{await cancelInput();throw new Error('녹음 시간 제한(29초)을 넘었습니다. 짧은 관제 구간으로 다시 수음하세요.');});},29000);
      if(playFile){
        const audio=new Audio(atcFile.url);item.audio=audio;
        audio.onloadedmetadata=()=>{if(capture.current!==item)return;if(!Number.isFinite(audio.duration)||audio.duration>28){cancelInput().catch(fail);fail(new Error('28초 이하의 관제 녹음 구간을 선택하세요.'));}};
        audio.onended=()=>{if(capture.current!==item)return;clearTimeout(item.timer);item.timer=setTimeout(()=>{if(capture.current===item)action(stopRecording);},500);};
        audio.onerror=()=>{if(capture.current!==item)return;cancelInput().catch(fail);fail(new Error('관제 파일 재생 실패'));};
        await audio.play();
      }
    }catch(e){await cancelInput();throw e;}
  }
  async function stopRecording(){
    const item=capture.current;if(!item?.microphone)return;
    clearTimeout(item.timer);item.audio?.pause();setRecording(false);setMessage(`${item.kind==='ATC'?'관제':'복창'} 음성을 인식·검증 중입니다…`);
    try{
      const audio=base64(mic.current.stop());
      const body={audio,started_at:item.started_at,ended_at:new Date().toISOString()};
      if(item.kind==='ATC')body.input_mode=item.inputMode;else body.atc_input_id=item.atc_input_id;
      const data=await api(item.kind==='ATC'?'atc':'readback',body,120000);
      if(!alive.current||capture.current!==item)return;
      if(item.kind==='ATC'){setAtcTranscript(data.transcript||'(인식된 발화 없음)');setAtcAttempt(data.atc_input_id);}
      else setTranscript(data.transcript||'(인식된 발화 없음)');
      setMessage(data.quality_reason?`판단 보류: ${data.quality_reason}`:item.kind==='ATC'?'관제 음성 처리 완료 · 서버 지시를 확인한 뒤 파일럿 복창 모드로 전환하세요.':'복창 처리 완료 · 서버 비교 결과를 확인하세요.');
    }finally{if(capture.current===item)capture.current=null;await audioFocus.end(item.focus);}
  }
  return <div className="demo-console-layout"><section className="op-panel demo-panel" aria-label="중간 시연 콘솔">
    <div className="demo-device-toolbar">
      <div className="demo-live-status"><span>{running?'● 카메라 수신 중':'○ 카메라 중지 · 장치 설정에서 연결'}</span><span>{micReady?'● 마이크 연결됨':'○ 마이크 미연결'}</span></div>
    </div>
    <div id="demo-speech" className="demo-speech">
      <h2>① 관제사 발화 → ② 파일럿 복창 → ③ 설정 확인</h2>
      <label>음성 입력 모드<select value={speechMode} disabled={busy||recording} onChange={e=>setSpeechMode(e.target.value)}><option value="ATC">관제사 지시 (ATC)</option><option value="PILOT">파일럿 복창</option></select></label>
      <p>{speechMode==='ATC'?'관제사 역할과 파일럿 역할이 번갈아 말하는 모의 시연입니다. 역할을 선택한 후 한 사람씩 말하세요.':'확인된 현재 관제 지시에 대해 호출부호와 지시 값을 복창하세요.'}</p>
      {speechMode==='ATC'&&<><label>관제 음성 입력 방식<select value={atcSource} disabled={busy||recording} onChange={e=>setAtcSource(e.target.value)}><option value="microphone_live">관제사 직접 발화</option><option value="microphone_playback">녹음 재생 시험</option></select></label>
        {atcSource==='microphone_live'&&<p>마이크를 연결하고 ‘관제사 발화 시작’을 누르세요. ‘마이크 켜짐’ 안내 후 호출부호와 고도·방위를 말하고 ‘녹음 종료 · 검증’을 누르세요. 인식된 지시를 확인한 뒤 파일럿 복창으로 전환하세요.</p>}</>}
      {speechMode==='ATC'&&atcSource==='microphone_playback'&&<><label>재생할 실제 관제 녹음파일<input type="file" accept="audio/*" disabled={busy||recording} onChange={e=>{const file=e.target.files?.[0];setAtcFile(file?{name:file.name,url:URL.createObjectURL(file)}:null);}}/></label>
        <p>{atcFile?.name||'별도 휴대폰·스피커에서 재생할 때는 파일 선택 없이 ATC 수음을 시작하세요.'}</p></>}
      <div className="op-row-actions">
        <button className="primary" disabled={disabled||busy||!micReady||recording||!status?.speech_ready||(speechMode==='PILOT'&&!canReadback)} onClick={()=>action(()=>startRecording())}>{speechMode==='ATC'?(atcSource==='microphone_live'?'관제사 발화 시작':'ATC 수음 시작'):'파일럿 복창 시작'}</button>
        {speechMode==='ATC'&&atcSource==='microphone_playback'&&<button disabled={disabled||busy||recording||!micReady||!status?.speech_ready||!atcFile} onClick={()=>action(()=>startRecording(true))}>선택 파일 재생 + 마이크 수음</button>}
        <button disabled={!recording||busy} onClick={()=>action(stopRecording)}>녹음 종료 · 검증</button><button disabled={!recording} onClick={()=>action(cancelInput)}>녹음 취소</button>
      </div>
      <p><b>관제 음성 인식 문장</b><br/>{atcTranscript||'아직 수음한 관제 문장이 없습니다.'}</p>
      {!status?.speech_ready&&<p>로컬 음성 모델 준비가 필요합니다.</p>}
      <details><summary>예비: 사전 등록 시나리오 (ATC STT 사용 안 함)</summary><label>사전 등록 관제<select value={scenario} disabled={busy||recording} onChange={e=>setScenario(e.target.value)}><option value="baseline">ALT 3000 / HDG 270</option><option value="altitude">ALT 3500 / HDG 270</option><option value="heading">ALT 3000 / HDG 290</option></select></label><p lang="en">{status?.scenarios?.[scenario]}</p><button disabled={disabled||busy||recording} onClick={()=>action(playScenario)}>관제 재생 및 지시 등록</button></details>
    </div>
    {error&&<p className="op-error" role="alert">{error}</p>}
    <p className="demo-progress" role="status">{message}</p>
    <DemoResults snapshot={snapshot} connected={connected} transcript={transcript} pending={speechPending} />

  </section>
    <section id="demo-device-setup" className="op-panel demo-panel demo-device-panel" aria-label="장치 설정">
    <h2>장치 설정</h2><p className="op-muted">카메라 미리보기 / 숫자 영역 지정</p>
    <div id="demo-camera" className="demo-devices"><label>카메라<select value={cameraId} disabled={running||busy} onChange={e=>setCameraId(e.target.value)}><option value="">기본 카메라</option>{devices.filter(d=>d.kind==='videoinput').map(d=><option key={d.deviceId} value={d.deviceId}>{d.label||'카메라 (권한 허용 후 이름 표시)'}</option>)}</select></label><button disabled={disabled||busy||running} onClick={()=>action(connectCamera)}>카메라 연결</button>
    <label>마이크<select value={micId} disabled={recording||busy} onChange={e=>{setMicId(e.target.value);setMicReady(false);}}><option value="">기본 마이크</option>{devices.filter(d=>d.kind==='audioinput').map(d=><option key={d.deviceId} value={d.deviceId}>{d.label||'마이크'}</option>)}</select></label><button disabled={disabled||busy||recording} onClick={()=>action(connectMic)}>마이크 연결</button><meter min="0" max="1" value={level} aria-label="마이크 입력 크기"/></div>
    <div className="demo-preview"><video ref={video} autoPlay muted playsInline style={{display:frozen?'none':'block'}}/><canvas ref={canvas} style={{display:frozen?'block':'none'}} onPointerDown={e=>{drag.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);}} onPointerUp={selectEnd}/></div>
    <div className="op-row-actions"><button disabled={!preview||busy||disabled} onClick={()=>action(freeze)}>영역 설정 / 다시 지정</button>{frozen&&<><label>선택할 숫자<select value={field} onChange={e=>setField(e.target.value)}><option>ALT</option><option>HDG</option></select></label><span>숫자만 드래그 · ALT {rois.ALT?'✓':'미지정'} / HDG {rois.HDG?'✓':'미지정'}</span></>}
      <button className="primary" disabled={disabled||busy||running||!calibrationImage.current||!rois.ALT||!rois.HDG||!status?.camera_ready} onClick={()=>action(startCamera)}>연속 OCR 시작</button><button disabled={!running} onClick={stopCamera}>OCR 중지</button></div>
    <p className="op-muted">카메라·아이패드를 고정하세요. 작은 위치 변화는 주변 패널 영상으로 추적합니다. 추적 실패·크기 변화 때는 영역을 다시 지정하세요. 600프레임마다 재시작합니다.</p>
    {result&&<p>최근 OCR: ALT {result.fields.altitude.value??'판독 보류'} / HDG {result.fields.heading.value??'판독 보류'} · {result.fields.altitude.reason||result.fields.heading.reason||'안정화됨'} · {result.captured_at}</p>}

    </section>
  </div>;
}
