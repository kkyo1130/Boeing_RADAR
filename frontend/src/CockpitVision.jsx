import { useMcpAutoControl } from './mcpAutoControl.js';
import React,{useState} from 'react';
import Cockpit3D from './VisionCockpit3D.jsx';
import WebcamOCR from './WebcamOCR.jsx';
import './cockpit-vision.css';
export default function CockpitVision(){
 const [values,setValues]=useState({speed:250,heading:270,altitude:3000});
 const onRendered=useMcpAutoControl(setValues);
 const limits={speed:[0,999,1],heading:[0,359,1],altitude:[0,99900,100]};
 const collectionDisplay=new URLSearchParams(location.search).has('display');
 function change(key,direction){if(collectionDisplay)return;const [min,max,step]=limits[key];setValues(v=>({...v,[key]:key==='heading'?(v[key]+direction+360)%360:Math.max(min,Math.min(max,v[key]+direction*step))}));}
 function edit(key){if(collectionDisplay)return;const raw=window.prompt(`${key.toUpperCase()} 수동 선택값`,String(values[key]));if(raw===null)return;const [min,max]=limits[key];if(!/^[0-9]+$/.test(raw)||Number(raw)<min||Number(raw)>max){window.alert(`${min}~${max} 정수를 입력하세요.`);return;}setValues(v=>({...v,[key]:Number(raw)}));}
 return <main className="cockpit-vision"><header><a href="/">기존 MCP 화면</a><a href="/operations">운영 화면</a><strong>Boeing 737 · Vision LAB</strong></header><p>모의 조종석 · MCP 수동 조작 · OCR은 설정을 자동 변경하지 않습니다.</p><Cockpit3D onRendered={onRendered} values={values} hidden={{}} onEdit={edit} onChange={change} capture={false}/><div className="ocr-actions">{Object.keys(values).map(key=><button key={key} onClick={()=>edit(key)}>{key.toUpperCase()} {values[key]}</button>)}</div><WebcamOCR/></main>;
}
