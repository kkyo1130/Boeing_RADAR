import React,{useEffect,useState} from 'react';
import {readColorMode,saveColorMode,applyColorMode,STORAGE_KEY} from './color-mode.js';
export default function ThemeToggle(){
 const [mode,setMode]=useState(readColorMode);
 useEffect(()=>{applyColorMode(mode);},[mode]);
 useEffect(()=>{
  const sync=event=>{if(event.key===STORAGE_KEY||event.key===null)setMode(readColorMode());};
  window.addEventListener('storage',sync);return()=>window.removeEventListener('storage',sync);
 },[]);
 return <button type="button" className="theme-toggle" aria-pressed={mode==='dark'} onClick={()=>{const next=mode==='dark'?'light':'dark';saveColorMode(next);setMode(next);}}>{mode==='dark'?'☀ 라이트 모드':'☾ 다크 모드'}</button>;
}
