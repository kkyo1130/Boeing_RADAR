import React,{useEffect,useRef,useState} from 'react';
import {advance} from './ocr-stability.js';
import TrainingCapture from './TrainingCapture.jsx';
const empty=()=>({hdg:{value:null,status:'CHECK'},alt:{value:null,status:'CHECK'}});
export default function WebcamOCR(){
 const video=useRef(null),overlay=useRef(null),stream=useRef(null),generation=useRef(0),abort=useRef(null);
 const [running,setRunning]=useState(false),[error,setError]=useState(''),[result,setResult]=useState(empty),[observed,setObserved]=useState('');
 function erase(){const c=overlay.current;if(c)c.getContext('2d').clearRect(0,0,c.width,c.height);}
 function stop(){generation.current++;abort.current?.abort();stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;setRunning(false);setResult(empty());setObserved('');erase();}
 useEffect(()=>()=>{generation.current++;abort.current?.abort();stream.current?.getTracks().forEach(t=>t.stop());},[]);
 async function start(){stop();setError('');const epoch=generation.current;
  try{const media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});
   if(epoch!==generation.current){media.getTracks().forEach(t=>t.stop());return;}
   stream.current=media;video.current.srcObject=media;await video.current.play();setRunning(true);
   media.getVideoTracks()[0].addEventListener('ended',()=>{if(epoch!==generation.current)return;stop();setError('카메라 연결이 종료됐습니다.');});
  }catch(e){if(epoch!==generation.current)return;stop();setError(`카메라를 열 수 없습니다 (${e.name}). macOS와 브라우저 카메라 권한을 확인하세요.`);}
 }
 useEffect(()=>{
  if(!running)return;
  let cancelled=false,timer,watchdog;const histories={hdg:[],alt:[]};let last=0,lastFrame=-1,lastBoxes=null;const epoch=generation.current;
  function clear(){histories.hdg=[];histories.alt=[];lastBoxes=null;last=0;setResult(empty());setObserved('');erase();}
  async function tick(){
   if(cancelled||epoch!==generation.current)return;
   const v=video.current;
   if(v.readyState<2||!stream.current?.active||v.currentTime===lastFrame){clear();setError('새 카메라 프레임 대기 중입니다.');timer=setTimeout(tick,250);return;}
   lastFrame=v.currentTime;
   const sentAt=performance.now(),frame=document.createElement('canvas');const scale=Math.min(1,1280/v.videoWidth,960/v.videoHeight);
   frame.width=Math.round(v.videoWidth*scale);frame.height=Math.round(v.videoHeight*scale);frame.getContext('2d').drawImage(v,0,0,frame.width,frame.height);
   const controller=new AbortController();abort.current=controller;const timeout=setTimeout(()=>controller.abort(),1400);
   try{const response=await fetch('/ocr-api/infer-frame',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:frame.toDataURL('image/jpeg',.9).split(',')[1]}),signal:controller.signal});if(!response.ok)throw Error(`OCR HTTP ${response.status}`);const data=await response.json();
    if(cancelled||epoch!==generation.current)return;
    const now=performance.now();if(now-sentAt>1500)throw Error('OCR 응답이 오래됐습니다.');
    if(!data.rois?.hdg||!data.rois?.alt){clear();setError('HDG·ALT 숫자 창 탐색 중 · 계기판 전체와 주황색 숫자가 선명하게 보이도록 맞추세요.');}
    else{
     if(lastBoxes&&['hdg','alt'].some(k=>data.rois[k].some((n,i)=>Math.abs(n-lastBoxes[k][i])>Math.max(10,(lastBoxes[k][3]-lastBoxes[k][1])*.5))))clear();
     const next={};for(const key of ['hdg','alt']){const item=data[key];const valid=typeof item?.value==='string'&&new RegExp(key==='hdg'?'^[0-9]{3}$':'^[0-9]{5}$').test(item.value)&&(key!=='hdg'||Number(item.value)<=359);const state=advance(histories[key],valid?item.value:null,now,last);histories[key]=state.history;next[key]={...item,...state};}
     last=now;lastBoxes=data.rois;setResult(next);setObserved(data.observed_at);setError(['hdg','alt'].some(k=>next[k].value===null)?'숫자 창을 찾았습니다 · 판독 보류. MCP 정면 보기로 숫자를 크게 하고 초점·반사를 확인하세요.':'');erase();
     const c=overlay.current,ctx=c.getContext('2d');ctx.lineWidth=3;ctx.font='20px sans-serif';
     for(const key of ['hdg','alt']){const [x,y,r,b]=data.rois[key].map(n=>n/scale);ctx.strokeStyle=key==='hdg'?'#ffbc66':'#63d8d0';ctx.fillStyle=ctx.strokeStyle;ctx.strokeRect(x,y,r-x,b-y);ctx.fillText(key.toUpperCase(),x,Math.max(20,y-5));}
    }
   }catch(e){if(!cancelled){clear();setError(`OCR 연결/입력 확인 필요: ${e.message}`);}}finally{clearTimeout(timeout);if(!cancelled)timer=setTimeout(tick,250);}
  }
  tick();watchdog=setInterval(()=>{if(last&&performance.now()-last>1500)clear();},250);
  return()=>{cancelled=true;clearTimeout(timer);clearInterval(watchdog);abort.current?.abort();};
 },[running]);
 return <section className="ocr-panel" aria-label="웹캠 OCR"><h2>웹캠 자동 OCR</h2><p>실험용 관측 · STABLE은 연속 3회 같은 판독값이며 정확도나 운항 판정이 아닙니다.</p>
 <div className="ocr-actions"><button onClick={start} disabled={running}>웹캠 시작</button><button onClick={stop} disabled={!running}>중지</button></div>
 <p>웹캠을 켜면 HDG·ALT 숫자 창을 자동으로 찾아 연속 인식합니다. 계기판 전체가 보이도록 고정하세요. 위치를 찾지 못하면 값을 비웁니다.</p>
 <div className="ocr-camera"><video ref={video} muted playsInline onLoadedMetadata={()=>{overlay.current.width=video.current.videoWidth;overlay.current.height=video.current.videoHeight;}}/><canvas ref={overlay}/></div>
 <div className="ocr-readings" aria-live="polite">{['hdg','alt'].map(k=><div key={k}><strong>{k.toUpperCase()} {result[k].value??'—'}</strong><span>{result[k].status}</span><small>{k==='alt'?'feet':'degrees'} · {result[k].reason==='LOW_MODEL_SCORE'?'모델 점수 부족 · ':result[k].reason==='OUT_OF_RANGE'?'범위 밖 판독 · ':''}모델 점수 {result[k].model_score?.toFixed(3)??'—'}</small></div>)}</div>
 {observed&&<small>서버 관측 UTC: {observed}</small>}{error&&<p role="alert">{error}</p>}
 <TrainingCapture video={video} running={running}/>
 </section>;
}
