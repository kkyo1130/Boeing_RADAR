import React,{useEffect,useRef,useState} from 'react';
const sessionId=()=>crypto.randomUUID().replaceAll('-','');
async function call(path,body,method='POST'){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{
  const response=await fetch('/ocr-api/dataset/'+path,{method,signal:controller.signal,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  let data;try{data=await response.json();}catch{throw Error(`저장 서버 응답 오류 (${response.status})`);}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`입력을 확인하세요 (${response.status})`);
  return data;
 }catch(e){if(controller.signal.aborted)throw Error('서버 응답 대기 시간이 지났습니다. 같은 캡처로 다시 시도하세요.');throw e;}
 finally{clearTimeout(timer);}
}
export default function TrainingCapture({video,running}){
 const [session,setSession]=useState(sessionId),[draft,setDraft]=useState(null),[hdg,setHdg]=useState(''),[alt,setAlt]=useState(''),[confirmed,setConfirmed]=useState(false),[count,setCount]=useState(0),[message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const pending=useRef(false),alive=useRef(true),token=useRef(null);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;if(token.current)call('preview/'+token.current,null,'DELETE').catch(()=>{});};},[]);
 async function action(task){if(pending.current)return;pending.current=true;setBusy(true);setError('');try{await task();}catch(e){if(alive.current)setError(e.message);}finally{pending.current=false;if(alive.current)setBusy(false);}}
 async function capture(){const v=video.current;if(!running||v?.readyState<2)throw Error('웹캠을 먼저 시작하세요.');
  const canvas=document.createElement('canvas'),scale=Math.min(1,1280/v.videoWidth,960/v.videoHeight);canvas.width=Math.round(v.videoWidth*scale);canvas.height=Math.round(v.videoHeight*scale);canvas.getContext('2d').drawImage(v,0,0,canvas.width,canvas.height);
  const image=canvas.toDataURL('image/jpeg',.95),data=await call('preview',{image:image.split(',')[1],session_id:session});
  if(!alive.current){call('preview/'+data.token,null,'DELETE').catch(()=>{});return;}
  token.current=data.token;setDraft({...data,image});setHdg('');setAlt('');setConfirmed(false);setMessage('아래 고정된 캡처의 두 숫자를 읽고 정답을 입력하세요. 실시간 영상과 다를 수 있습니다.');
 }
 async function discard(){if(token.current)await call('preview/'+token.current,null,'DELETE');token.current=null;setDraft(null);setConfirmed(false);setMessage('캡처 취소 · 저장하지 않았습니다.');}
 async function save(){const data=await call('save',{token:draft.token,hdg,alt,confirmed});if(!alive.current)return;
  setCount(data.session_samples);setMessage(`저장 완료 · 이 촬영 세션 ${data.session_samples}장. 숫자·거리·각도를 바꿔 다음 장면을 촬영하세요.`);
  const savedToken=token.current;token.current=null;setDraft(null);setConfirmed(false);call('preview/'+savedToken,null,'DELETE').catch(()=>{});
 }
 const valid=/^[0-9]{3}$/.test(hdg)&&Number(hdg)<=359&&/^[0-9]{5}$/.test(alt);
 return <section className="training-capture" aria-label="학습용 캡처"><h3>학습용 캡처 · 정답 직접 확인</h3>
 <p>저장 버튼을 누른 장면만 로컬에 저장합니다. OCR 결과는 정답으로 채우지 않습니다. 아직 모델을 학습하거나 교체하지 않습니다.</p>
 <p>현재 촬영 세션 {session.slice(0,8)} · 저장 {count}장</p>
 <div className="ocr-actions"><button disabled={!running||busy||!!draft} onClick={()=>action(capture)}>학습용 장면 캡처</button><button disabled={busy||!!draft} onClick={()=>{setSession(sessionId());setCount(0);setMessage('새 촬영 세션입니다. 촬영 조건을 바꾼 뒤 수집하세요.');setError('');}}>새 촬영 세션</button></div>
 {draft&&<div className="capture-review"><h4>저장할 고정 장면</h4><img className="capture-frame" src={draft.image} alt="캡처 시점의 고정된 웹캠 전체 영상"/>
 <div className="capture-labels">{[['hdg','HDG',hdg,setHdg,3],['alt','ALT',alt,setAlt,5]].map(([kind,label,value,setValue,digits])=><label key={kind}>{label} 잘라낸 영상<img src={'data:image/jpeg;base64,'+draft.crops[kind]} alt={label+' 정답 확인용 고정 숫자 창'}/>{label} 정답 ({digits}자리)<input aria-label={label+' 정답'} inputMode="numeric" value={value} maxLength={digits} placeholder={kind==='hdg'?'예: 270':'예: 03000'} disabled={busy} onChange={e=>{setValue(e.target.value);setConfirmed(false);}}/></label>)}</div>
 <label className="capture-confirm"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>두 잘라낸 영상이 각각 HDG·ALT이고, 입력한 정답을 직접 확인했습니다.</label>
 <p>숫자가 가려졌거나 창이 잘못 잡혔다면 저장하지 말고 취소하세요.</p>
 <div className="ocr-actions"><button disabled={busy||!valid||!confirmed} onClick={()=>action(save)}>정답 확인 후 저장</button><button disabled={busy} onClick={()=>action(discard)}>캡처 취소</button></div></div>}
 {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
 <small>저장 위치: vision/data/webcam_labeled · 연속 촬영분은 같은 세션으로 묶습니다. 평가용 촬영은 새 세션에서 진행하세요.</small>
 </section>;
}
