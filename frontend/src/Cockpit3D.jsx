import React,{useEffect,useRef,useState} from 'react';
import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import './cockpit3d.css';

const slots=[['speed',-2.75,1.65,3,'IAS / MACH','SPEED'],['heading',-.35,1.65,3,'HEADING','HDG SEL'],['altitude',2.1,2.05,5,'ALTITUDE','ALT HLD']];
function textPlane(text,width,height,color,size=64){
 const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=256;
 const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
 const material=new T.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false});
 const plane=new T.Mesh(new T.PlaneGeometry(width,height),material);
 plane.userData.paint=value=>{const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,256);ctx.fillStyle=color;ctx.font=`bold ${size}px "Courier New", monospace`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(value,512,138,960);texture.needsUpdate=true;};
 plane.userData.paint(text);return plane;
}
export default function Cockpit3D({values,hidden,onEdit,onChange,capture}){
 const host=useRef(null),runtime=useRef(null),latest=useRef({values,hidden,onEdit,onChange});latest.current={values,hidden,onEdit,onChange};
 const [status,setStatus]=useState('loading');
 const [view,setView]=useState('pilot');
 useEffect(()=>{
  let renderer;try{renderer=new T.WebGLRenderer({antialias:true,alpha:false});}catch{setStatus('error');return;}
  let disposed=false;const element=host.current;renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0x111d29);renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;element.appendChild(renderer.domElement);
  renderer.domElement.setAttribute('aria-label','전체 3D 메시 조종석. 드래그로 회전, 스크롤로 확대. 숫자를 누르면 값 입력.');
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.1,100);camera.position.set(19,13,25);
  scene.add(new T.HemisphereLight(0xdce7ef,0x242c34,2.2));const key=new T.DirectionalLight(0xf3f4ef,3);key.position.set(-12,18,20);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-20,right:20,top:20,bottom:-20,near:1,far:80});key.shadow.normalBias=.035;scene.add(key);const fill=new T.DirectionalLight(0x9bcfff,2);fill.position.set(5,1,4);scene.add(fill);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enablePan=false;controls.enableDamping=true;controls.minDistance=5;controls.maxDistance=90;controls.minPolarAngle=.12;controls.maxPolarAngle=Math.PI*.76;controls.minAzimuthAngle=-Math.PI;controls.maxAzimuthAngle=Math.PI;
  let currentView='pilot';
  function cameraView(next){
   currentView=next;
   const aspect=camera.aspect;camera.fov=next==='pilot'?58:32;camera.updateProjectionMatrix();
   if(next==='mcp'){
    controls.target.set(0,2.18,0);camera.position.set(0,2.18,Math.max(16,6.8/(Math.tan(16*Math.PI/180)*aspect)));
   }else if(next==='pilot'){
    controls.target.set(0,.55,-.5);camera.position.set(0,.15,15.8);
   }else{
    controls.target.set(0,.6,1);const direction=new T.Vector3(19,13,25).normalize();
    const distance=Math.max(48,15/(Math.tan(16*Math.PI/180)*aspect));camera.position.copy(controls.target).addScaledVector(direction,distance);
   }
   controls.update();
  }
  const resize=()=>{const w=element.clientWidth,h=element.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();cameraView(currentView);};
  const observer=new ResizeObserver(resize);observer.observe(element);resize();
  const displays={},knobs={};runtime.current={camera,controls,displays,knobs,front:()=>cameraView('mcp'),cameraView};
  new GLTFLoader().load('/models/cockpit.glb',gltf=>{
   if(disposed){disposeScene(gltf.scene);return;}scene.add(gltf.scene);
   const mcp=gltf.scene.getObjectByName('mcp_root');gltf.scene.traverse(object=>{if(object.isMesh){object.castShadow=!object.material.transparent;object.receiveShadow=true;}});
   for(const [name,x,width,digits,title,knobTitle] of slots){
    const display=textPlane('',width*.94,.5,'#ffba69',190);display.position.set(x,.58,.208);display.name=`${name}_display_text`;display.userData.field=name;display.userData.edit=true;mcp.add(display);displays[name]=display;


    const turnLabel=textPlane('−     +',1.9,.22,'#bdc6c8',76);turnLabel.position.set(x,-.88,.5);mcp.add(turnLabel);
    const knob=gltf.scene.getObjectByName(`${name}_knob`);if(knob){knob.userData.field=name;knob.userData.knob=true;knobs[name]=knob;}
    const screen=gltf.scene.getObjectByName(`${name}_display`);screen.userData.field=name;screen.userData.edit=true;
   }
   const title=textPlane('RADAR / FLIGHT DECK',8,.6,'#9eb6c3',185);title.position.set(0,-6.52,9.4);title.rotation.x=-Math.PI/2;scene.add(title);
   for(const [x,label] of [[-8.05,'EFIS / CAPTAIN'],[8.05,'EFIS / FIRST OFFICER']]){const t=textPlane(label,3,.13,'#d7ded5',175);t.position.set(x,2.78,.22);scene.add(t);}
   for(const [x,label] of [[-5,'COURSE'],[5,'COURSE'],[4.12,'VERT SPEED']]){const value=textPlane(x===4.12?'----':'005',x===4.12?1:.6,.43,'#e3eed8',190);value.position.set(x,.58,.24);mcp.add(value);}
   setStatus('ready');update();
  },undefined,()=>!disposed&&setStatus('error'));
  function update(){renderer.shadowMap.needsUpdate=true;for(const [name,,,digits] of slots){displays[name]?.userData.paint(latest.current.hidden[name]?'':String(latest.current.values[name]).padStart(digits,'0'));if(knobs[name])knobs[name].rotation.z=-latest.current.values[name]*(name==='altitude'?.0008:.025);}}
  runtime.current.update=update;
  const raycaster=new T.Raycaster(),pointer=new T.Vector2();let down=null;
  function hit(e){const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);for(const h of raycaster.intersectObjects(scene.children,true)){let object=h.object;while(object){if(object.userData.field)return {object,point:h.point};object=object.parent;}const material=h.object.material;if(material&&!material.transparent)return null;}return null;}
  const pointerDown=e=>{down=[e.clientX,e.clientY];};
  const pointerUp=e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;down=null;const h=hit(e);if(!h)return;const {field,edit}=h.object.userData;if(edit)latest.current.onEdit(field);else latest.current.onChange(field,h.point.x<h.object.position.x?-1:1);};
  const move=e=>{renderer.domElement.style.cursor=hit(e)?'pointer':'grab';};
  renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointerup',pointerUp);renderer.domElement.addEventListener('pointermove',move);
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
  return()=>{disposed=true;observer.disconnect();renderer.setAnimationLoop(null);controls.dispose();renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointermove',move);disposeScene(scene);renderer.dispose();renderer.domElement.remove();runtime.current=null;};
 },[]);
 useEffect(()=>{runtime.current?.update?.();},[values,hidden]);
 useEffect(()=>{const r=runtime.current;if(!r)return;r.controls.enabled=!capture;if(capture){r.front();setView('mcp');}},[capture,status]);
 function chooseView(next){setView(next);runtime.current?.cameraView(next);}
 return <section className="cockpit-3d" data-state={status} aria-label="GLB 메시 기반 전체 조종석"><div ref={host} className="cockpit-3d-canvas"/>{status==='loading'&&<p className="cockpit-3d-message" role="status">3D 조종석 불러오는 중…</p>}{status==='error'&&<p className="cockpit-3d-message" role="alert">3D 화면을 열 수 없습니다. 사진 보기로 전환하거나 WebGL을 지원하는 브라우저를 사용하세요.</p>}{!capture&&<div className="cockpit-3d-toolbar"><span>드래그 회전 · 스크롤 확대<br/>MCP만 수동 조작 · 주변 계기는 모의 고정 표시</span><div className="cockpit-camera-presets"><button aria-pressed={view==='cabin'} onClick={()=>chooseView('cabin')}>전체 조종석</button><button aria-pressed={view==='pilot'} onClick={()=>chooseView('pilot')}>조종석 시점</button><button aria-pressed={view==='mcp'} onClick={()=>chooseView('mcp')}>MCP 정면</button></div></div>}</section>;
}
function disposeScene(scene){const textures=new Set(),materials=new Set(),geometries=new Set();scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){materials.add(m);if(m.map)textures.add(m.map);}});textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());}
