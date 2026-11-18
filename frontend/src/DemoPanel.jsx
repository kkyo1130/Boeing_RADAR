import React,{useEffect,useRef,useState} from 'react';
import {request} from './flight-client.js';
import {audioFocus} from './audio-focus.js';
import {microphone,base64} from './demo-audio.js';
import {decodeAudioFile,fileSpeechBody} from './file-speech.js';
import './demo.css';
import {nextCaptureDelay} from './capture-policy.js';
import {framePoint,selectedBox} from './roi-selection.js';
import DemoResults from './DemoResults.jsx';
import {readAtcAttempt,writeAtcAttempt,atcAttemptKey} from './atc-attempt.js';

export default function DemoPanel({snapshot,connected,onSpeech}) {
  const flight=snapshot.flight_id, latest=useRef({snapshot,connected});latest.current={snapshot,connected};
  const epoch=useRef(0), drag=useRef(null), pendingDisplay=useRef(null);
  const [mode,setMode]=useState('auto'),[selectedField,setSelectedField]=useState('ALT'),[diagnostics,setDiagnostics]=useState(null);
  const video=useRef(null), camera=useRef(null), mic=useRef(null), loop=useRef(null), capture=useRef(null), busyRef=useRef(false), alive=useRef(true);
  const [devices,setDevices]=useState([]),[cameraId,setCameraId]=useState(''),[micId,setMicId]=useState(''),[preview,setPreview]=useState(false),[micReady,setMicReady]=useState(false),[level,setLevel]=useState(0);
  const [rois,setRois]=useState({}),[running,setRunning]=useState(false),[result,setResult]=useState(null),[message,setMessage]=useState('장치를 선택하고 미리보기를 연결하세요.'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[recording,setRecording]=useState(false),[transcript,setTranscript]=useState(''),[status,setStatus]=useState(null);
  const [speechFiles,setSpeechFiles]=useState({ATC:null,PILOT:null});
  const [speechMode,setSpeechMode]=useState('ATC'),[atcTranscript,setAtcTranscript]=useState(''),[atcAttempt,updateAtcAttempt]=useState(()=>readAtcAttempt(flight));
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
  const disabled=!connected || snapshot.status!=='ACTIVE';
  const api=(path,body,timeout=10000)=>request(`/api/demo/${flight}/${path}`,{method:'POST',body,timeout});
  async function health(channel,state,reason=null) {
    return request(`/api/v2/flights/${flight}/health-events`,{method:'POST',body:{schema_version:'2',event_id:crypto.randomUUID(),flight_id:flight,channel,observed_at:new Date().toISOString(),health:{status:state,reason}}});
  }
  const fail=e=>{if(alive.current){setError(e.message);setMessage('입력 중단 · 장치와 설정을 확인하세요.');}};
  async function action(task){if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');try{await task();}catch(e){fail(e);}finally{busyRef.current=false;if(alive.current)setBusy(false);}}
  async function list(){if(!navigator.mediaDevices?.enumerateDevices){setDevices([]);return;}setDevices(await navigator.mediaDevices.enumerateDevices());}
  useEffect(()=>{alive.current=true;request('/api/demo/status').then(setStatus).catch(fail);list().catch(fail);
    return()=>{alive.current=false;epoch.current++;const active=loop.current;loop.current=null;clearTimeout(active?.timer);camera.current?.getTracks().forEach(t=>t.stop());mic.current?.close();
      if(capture.current){clearTimeout(capture.current.timer);capture.current.abort?.abort();capture.current.audio?.pause();audioFocus.end(capture.current.focus).catch(()=>{});capture.current=null;}
      health('CAMERA','DISCONNECTED','demo_panel_closed').catch(()=>{});
    };},[flight]);
  useEffect(()=>{if(disabled){stopCamera();if(capture.current)cancelInput().catch(fail);}},[disabled]);
  useEffect(()=>{const hide=()=>{if(document.hidden){cancelInput().catch(fail);}};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide);},[]);
  async function connectCamera(){await stopCamera();camera.current?.getTracks().forEach(t=>t.stop());setRois({});
    const stream=await navigator.mediaDevices.getUserMedia({video:{deviceId:cameraId?{exact:cameraId}:undefined,width:{ideal:1920},height:{ideal:1080}},audio:false});
    if(!alive.current){stream.getTracks().forEach(t=>t.stop());return;}
    camera.current=stream;video.current.srcObject=stream;await video.current.play();setPreview(true);await list();
    stream.getVideoTracks()[0].onended=()=>{stopCamera();setPreview(false);fail(new Error('카메라 연결이 끊겼습니다.'));};
    setMessage('Vision AI 자동 인식 시작을 누르면 ALT·HDG 창을 자동으로 찾습니다.');
  }
  async function connectMic(){mic.current?.close();mic.current=await microphone(micId,n=>alive.current&&setLevel(n));setMicReady(true);await list();await health('MICROPHONE','AVAILABLE');
    mic.current.stream.getAudioTracks()[0].onended=()=>{cancelInput();setMicReady(false);health('MICROPHONE','DISCONNECTED','microphone_disconnected').catch(fail);};}
  function frame(){const v=video.current;if(!v||v.readyState<2||!v.videoWidth)throw new Error('새 카메라 프레임이 없습니다.');const c=document.createElement('canvas');const scale=Math.min(1,1920/v.videoWidth,1080/v.videoHeight);c.width=Math.round(v.videoWidth*scale);c.height=Math.round(v.videoHeight*scale);c.getContext('2d').drawImage(v,0,0);return c;}
  async function stopCamera(){epoch.current++;pendingDisplay.current=null;const active=loop.current;loop.current=null;clearTimeout(active?.timer);if(alive.current){setRunning(false);setResult(null);setMessage('OCR 중지 · 다시 시작하려면 영역을 확인하세요.');}if(active)await health('CAMERA','DISCONNECTED','camera_capture_stopped').catch(fail);}
  async function startCamera(){
    const generation=++epoch.current, started=performance.now();
    if(mode==='auto')setRois({});setResult(null);setError('');
    const active={token:null,lastMediaTime:-1,timer:null,waiting:false};loop.current=active;setRunning(true);
    const current=()=>loop.current===active&&generation===epoch.current&&alive.current;
    await health('CAMERA','DEGRADED','automatic_regions_searching');
    async function tick(){
      if(!current())return;
      let delay=250;
      try{
        if(!latest.current.connected||latest.current.snapshot.status!=='ACTIVE'){await stopCamera();return;}
        const v=video.current;
        if(v.paused||v.readyState<2||v.currentTime===active.lastMediaTime){
          setResult(null);setRois({});pendingDisplay.current=null;
          setMessage('새 카메라 프레임 대기 중 · 영상이 돌아오면 자동으로 다시 찾습니다.');
          if(!active.waiting){active.waiting=true;await health('CAMERA','DEGRADED','camera_frame_waiting');}
          return;
        }
        active.lastMediaTime=v.currentTime;active.waiting=false;
        const sent=performance.now(),c=frame();
        if(!active.token){
          const calibration=await api(mode==='auto'?'auto-calibration':'calibration',{image:c.toDataURL('image/jpeg',.92).split(',')[1],...(mode==='manual'?{rois}: {})},15000);
          if(!current())return;
          if(mode==='auto'&&calibration.status!=='READY'){
            setRois({});setMessage('ALT·HDG 탐색 중 · Cockpit이 보이면 자동으로 인식합니다.');return;
          }
          setError('');active.token=calibration.token;
          setRois(calibration.rois||rois);setDiagnostics({roi_ms:Math.round(performance.now()-started)});
          setMessage('영역을 찾았습니다 · 새 프레임 연속 3회 확인 중');return;
        }
        const revision=latest.current.snapshot.revision,captured_at=new Date().toISOString();
        const data=await api('frame',{token:active.token,target_revision:revision,captured_at,media_time:active.lastMediaTime,image:c.toDataURL('image/jpeg',.92).split(',')[1]},45000);
        if(!current())return;
        setError('');setRois(data.rois||{});setDiagnostics(previous=>({...previous,request_ms:Math.round(performance.now()-sent),...data.timings}));setResult(data);
        if(data.tracking_status==='SEARCHING'){pendingDisplay.current=null;setMessage('Cockpit 영역 재탐색 중 · 판독 보류. 다시 보이면 자동으로 인식합니다.');}
        else{
          if(Object.values(data.fields).some(field=>field.stable_count===3))pendingDisplay.current={epoch:generation,captured_at,started:sent-Math.max(0,...Object.values(data.timings?.stabilization_ms||{}).filter(Number.isFinite)),values:{ALT:data.fields.altitude.value,HDG:data.fields.heading.value}};
          setMessage('Cockpit 위치를 따라 인식 중 · 동일 값 3회 확인 후 반영');
        }
        delay=nextCaptureDelay(sent,performance.now());
      }catch(e){
        if(!current())return;
        setResult(null);setRois({});pendingDisplay.current=null;setMessage('입력 확인·재탐색 중 · 판단 보류');setError(e.message);
        if(e.status===409){active.token=null;active.lastMediaTime=-1;}
        await health('CAMERA','DEGRADED','camera_capture_retry').catch(()=>{});delay=500;
      }finally{if(current())active.timer=setTimeout(tick,delay);}
    }
    if(current())tick();
  }
  useEffect(()=>{
    const pending=pendingDisplay.current;
    if(!pending||pending.epoch!==epoch.current)return;
    const visible=Object.entries(pending.values).filter(([,value])=>value!==null);
    if(visible.length&&visible.every(([field,value])=>{const row=snapshot.current?.COCKPIT?.[field];return row?.value===value&&Date.parse(row.observed_at)>=Date.parse(pending.captured_at);})){setDiagnostics(previous=>({...previous,first_candidate_to_display_ms:Math.round(performance.now()-pending.started)}));pendingDisplay.current=null;}
  },[snapshot]);
  function roiPoint(event){const rect=event.currentTarget.getBoundingClientRect();const c=frame();return framePoint(event.clientX,event.clientY,rect,c.width,c.height);}
  function beginROI(event){if(mode!=='manual'||running||busy||!preview)return;event.currentTarget.setPointerCapture(event.pointerId);drag.current=roiPoint(event);}
  function finishROI(event){if(!drag.current)return;const start=drag.current;drag.current=null;let box;try{box=selectedBox(start,roiPoint(event));}catch(e){setError(e.message);return;}setError('');setRois(previous=>({...previous,[selectedField]:box}));setSelectedField(selectedField==='ALT'?'HDG':'ALT');}
  async function resetRegions(next=mode){const stopped=stopCamera();setMode(next);setRois({});setDiagnostics(null);setSelectedField('ALT');await stopped;}
  async function cancelInput(){const item=capture.current;if(!item)return;capture.current=null;clearTimeout(item.timer);item.audio?.pause();item.reject?.(new Error('입력 취소'));item.abort?.abort();if(item.microphone)mic.current?.stop();setRecording(false);await audioFocus.end(item.focus);await health('MICROPHONE','DEGRADED','capture_cancelled').catch(fail);}
  async function startRecording(){
    const kind=speechMode, inputMode=kind==='ATC'?'microphone_live':null;
    if(capture.current)throw new Error('기존 입력이 끝날 때까지 기다리세요.');
    if(!mic.current || (kind==='PILOT'&&!canReadback))throw new Error('마이크 연결과 현재 관제 지시를 확인하세요.');
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
      setMessage(kind==='ATC'?'마이크 켜짐 · 관제사 역할 문장을 말한 뒤 녹음 종료를 누르세요.':'파일럿 복창 녹음 중 · 완료하면 녹음 종료를 누르세요.');
      item.timer=setTimeout(()=>{if(capture.current===item)action(async()=>{await cancelInput();throw new Error('녹음 시간 제한(29초)을 넘었습니다. 짧은 관제 구간으로 다시 수음하세요.');});},29000);
    }catch(e){await cancelInput();throw e;}
  }
  async function uploadSpeechFile(kind){
    if(capture.current)throw new Error('현재 입력 처리가 끝날 때까지 기다리세요.');
    if(disabled || (kind==='PILOT'&&!canReadback))throw new Error('현재 비행 연결과 채택된 관제 지시를 확인하세요.');
    const file=speechFiles[kind];
    const item={kind,flight,source:'file_upload',abort:new AbortController(),focus:null,microphone:false,
      atc_input_id:kind==='PILOT'?latest.current.snapshot.readback_required.atc_input_id:null};
    capture.current=item;
    setMessage(`${kind==='ATC'?'관제':'복창'} 파일을 읽는 중 · 마이크는 사용하지 않습니다.`);
    try{
      const {bytes,duration}=await decodeAudioFile(file);
      if(!alive.current||capture.current!==item||item.abort.signal.aborted||latest.current.snapshot.flight_id!==item.flight)return;
      const state=latest.current.snapshot;
      if(!latest.current.connected||state.status!=='ACTIVE')throw new Error('비행 연결이 변경됐습니다. 다시 시도하세요.');
      if(kind==='PILOT'&&(state.readback_required?.atc_input_id!==item.atc_input_id||state.validation.reason==='LATEST_ATC_NOT_ADOPTED'))throw new Error('관제 지시가 변경됐습니다. 새 지시를 확인한 뒤 복창 파일을 다시 전송하세요.');
      item.focus=await audioFocus.begin(kind);
      if(!item.focus)throw new Error('음성 처리 예약 실패 · 음성 안내 연결을 확인하세요.');
      if(capture.current!==item||item.abort.signal.aborted)return;
      await health('SPEECH_API','AVAILABLE');
      if(kind==='ATC'){setAtcAttempt('pending');setAtcTranscript('');setTranscript('');}else setTranscript('');
      const ended=Date.now(),started=ended-1;
      const body=fileSpeechBody(kind,base64(bytes),new Date(started).toISOString(),new Date(ended).toISOString(),item.atc_input_id);
      setMessage(`${kind==='ATC'?'관제':'복창'} 파일 ${duration.toFixed(1)}초 · STT 변환 및 서버 판정 중…`);
      const data=await request(`/api/demo/${item.flight}/${kind==='ATC'?'atc':'readback'}`,{method:'POST',body,timeout:120000,signal:item.abort.signal});
      if(!alive.current||capture.current!==item||latest.current.snapshot.flight_id!==item.flight)return;
      if(kind==='ATC'){setAtcTranscript(data.transcript||'(인식된 발화 없음)');setAtcAttempt(data.atc_input_id);}else setTranscript(data.transcript||'(인식된 발화 없음)');
      setMessage(data.quality_reason?`파일 처리 완료 · 판단 보류: ${data.quality_reason}`:kind==='ATC'?'관제 파일 STT 완료 · 서버 지시가 채택되면 복창 파일을 전송하세요.':'복창 파일 STT 완료 · 아래 서버 비교 결과를 확인하세요.');
    }finally{
      if(capture.current===item)capture.current=null;
      if(item.focus)await audioFocus.end(item.focus);
    }
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
      <section className="file-speech-panel" aria-label="음성 파일 STT">
        <h3>음성 파일 입력</h3>
        <div className="file-speech-grid">
          <div><label>① 관제 음성 파일<input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={disabled||busy||recording} onChange={e=>setSpeechFiles(f=>({...f,ATC:e.target.files?.[0]||null}))}/></label>
            <button className="primary" disabled={disabled||busy||recording||!status?.speech_ready||!speechFiles.ATC} onClick={()=>action(()=>uploadSpeechFile('ATC'))}>관제 파일 인식</button></div>
          <div><label>② 조종사 복창 음성 파일<input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={disabled||busy||recording} onChange={e=>setSpeechFiles(f=>({...f,PILOT:e.target.files?.[0]||null}))}/></label>
            <button className="primary" disabled={disabled||busy||recording||!status?.speech_ready||!speechFiles.PILOT||!canReadback} onClick={()=>action(()=>uploadSpeechFile('PILOT'))}>복창 파일 인식</button>
            {!canReadback&&<small>관제 파일 처리 후 서버가 지시를 채택해야 복창을 비교할 수 있습니다.</small>}</div>
        </div>
      </section>
      <h3>마이크 녹음 (파일 입력 시 연결 불필요)</h3>
      <label>음성 입력 모드<select value={speechMode} disabled={busy||recording} onChange={e=>setSpeechMode(e.target.value)}><option value="ATC">관제사 지시 (ATC)</option><option value="PILOT">파일럿 복창</option></select></label>
      {speechMode==='PILOT'&&<p>확인된 현재 관제 지시에 대해 호출부호와 지시 값을 복창하세요.</p>}
      <div className="op-row-actions">
        <button className="primary" disabled={disabled||busy||!micReady||recording||!status?.speech_ready||(speechMode==='PILOT'&&!canReadback)} onClick={()=>action(()=>startRecording())}>{speechMode==='ATC'?'관제사 발화 시작':'파일럿 복창 시작'}</button>
        <button disabled={!recording||busy} onClick={()=>action(stopRecording)}>녹음 종료 · 검증</button><button disabled={!recording} onClick={()=>action(cancelInput)}>녹음 취소</button>
      </div>
      <p><b>관제 음성 인식 문장</b><br/>{atcTranscript||'아직 수음한 관제 문장이 없습니다.'}</p>
      {!status?.speech_ready&&<p>로컬 음성 모델 준비가 필요합니다.</p>}
      <details><summary>예비: 사전 등록 시나리오 (ATC STT 사용 안 함)</summary><label>사전 등록 관제<select value={scenario} disabled={busy||recording} onChange={e=>setScenario(e.target.value)}><option value="baseline">ALT 3000 / HDG 270</option><option value="altitude">ALT 3500 / HDG 270</option><option value="heading">ALT 3000 / HDG 290</option></select></label><p lang="en">{status?.scenarios?.[scenario]}</p><button disabled={disabled||busy||recording} onClick={()=>action(playScenario)}>관제 재생 및 지시 등록</button></details>
    </div>
    {error&&<p className="op-error" role="alert">{error}</p>}
    <p className="demo-progress" role="status">{message}</p>


  </section>
    <section id="demo-device-setup" className="op-panel demo-panel demo-device-panel" aria-label="장치 설정">
    <h2>장치 설정</h2><p className="op-muted">자동 탐지 또는 영역 직접 설정</p>
    <div id="demo-camera" className="demo-devices"><label>카메라<select value={cameraId} disabled={running||busy} onChange={e=>{setCameraId(e.target.value);setPreview(false);camera.current?.getTracks().forEach(t=>t.stop());resetRegions();}}><option value="">기본 카메라</option>{devices.filter(d=>d.kind==='videoinput').map(d=><option key={d.deviceId} value={d.deviceId}>{d.label||'카메라 (권한 허용 후 이름 표시)'}</option>)}</select></label><button disabled={disabled||busy||running} onClick={()=>action(connectCamera)}>카메라 연결</button>
    <label>마이크<select value={micId} disabled={recording||busy} onChange={e=>{setMicId(e.target.value);setMicReady(false);}}><option value="">기본 마이크</option>{devices.filter(d=>d.kind==='audioinput').map(d=><option key={d.deviceId} value={d.deviceId}>{d.label||'마이크'}</option>)}</select></label><button disabled={disabled||busy||recording} onClick={()=>action(connectMic)}>마이크 연결</button><meter min="0" max="1" value={level} aria-label="마이크 입력 크기"/></div>
    <div className="op-row-actions"><button disabled={busy} aria-pressed={mode==='auto'} onClick={()=>resetRegions('auto')}>자동 탐지·인식</button><button disabled={busy} aria-pressed={mode==='manual'} onClick={()=>resetRegions('manual')}>영역 직접 설정</button>{mode==='manual'&&<><label>선택할 영역 <select value={selectedField} disabled={running||busy} onChange={e=>setSelectedField(e.target.value)}><option>ALT</option><option>HDG</option></select></label><button disabled={busy} onClick={()=>resetRegions()}>다시 설정</button></>}</div>
    <div className="demo-preview" style={{position:'relative',touchAction:'none'}} onPointerDown={beginROI} onPointerUp={finishROI} onPointerCancel={()=>{drag.current=null;}}><video ref={video} autoPlay muted playsInline style={{display:'block',width:'100%'}}/>{Object.entries(rois).map(([field,box])=>{const c=video.current;if(!c?.videoWidth)return null;const scale=Math.min(1,1920/c.videoWidth,1080/c.videoHeight),w=Math.round(c.videoWidth*scale),h=Math.round(c.videoHeight*scale);return <div key={field} data-roi-field={field} style={{position:'absolute',pointerEvents:'none',border:`2px solid ${field==='ALT'?'#ffb347':'#58d9ef'}`,color:field==='ALT'?'#ffb347':'#58d9ef',left:`${box[0]/w*100}%`,top:`${box[1]/h*100}%`,width:`${(box[2]-box[0])/w*100}%`,height:`${(box[3]-box[1])/h*100}%`}}>{field}</div>;})}</div>
    <div className="op-row-actions">
      <button className="primary" disabled={disabled||busy||running||!preview||!status?.camera_ready||(mode==='manual'&&(!rois.ALT||!rois.HDG))} onClick={()=>action(startCamera)}>{mode==='manual'?'영역 적용·인식':'인식 시작'}</button><button disabled={!running} onClick={stopCamera}>인식 중지</button>
      {rois.ALT&&rois.HDG&&<span>ALT·HDG 영역 설정됨</span>}
    </div>
    <p className="op-muted">자동 탐지가 어려우면 영역 직접 설정에서 ALT·HDG 숫자 창을 각각 드래그하세요. Cockpit이 움직이면 자동 모드가 새 영상에서 영역을 다시 찾습니다. 놓친 동안은 판단 보류이며 재탐색을 계속합니다.</p>
    <details><summary>상세 정보</summary>{diagnostics&&<pre>{JSON.stringify(diagnostics,null,2)}</pre>}{result&&<p>최근 OCR: ALT {result.fields.altitude.value??'판독 보류'} / HDG {result.fields.heading.value??'판독 보류'} · {result.fields.altitude.reason||result.fields.heading.reason||'안정화됨'} · {result.captured_at}</p>}</details>

    </section>
    <DemoResults snapshot={snapshot} connected={connected} transcript={transcript} pending={speechPending} />
  </div>;
}
