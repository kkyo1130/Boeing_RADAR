import React,{useEffect,useRef,useState} from 'react';
import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import './cockpit3d.css';

const slots=[['speed',-3.55,1.65,3,'IAS / MACH','SPEED'],['heading',0,1.65,3,'HEADING','HDG SEL'],['altitude',3.55,2.05,5,'ALTITUDE','ALT HLD']];
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
 useEffect(()=>{
  let renderer;try{renderer=new T.WebGLRenderer({antialias:true,alpha:false});}catch{setStatus('error');return;}
  let disposed=false;const element=host.current;renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0x10191e);renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.65;element.appendChild(renderer.domElement);
  renderer.domElement.setAttribute('aria-label','3D MCP 조종석. 드래그로 회전, 스크롤로 확대. 숫자를 누르면 값 입력.');
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.1,100);camera.position.set(1.1,1.6,13);
  scene.add(new T.HemisphereLight(0xd6e5f0,0x29241a,3));const key=new T.DirectionalLight(0xffe2b7,4);key.position.set(-3,6,8);scene.add(key);const fill=new T.DirectionalLight(0x9bcfff,2);fill.position.set(5,1,4);scene.add(fill);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enablePan=false;controls.enableDamping=true;controls.minDistance=7;controls.maxDistance=23;controls.minPolarAngle=Math.PI*.28;controls.maxPolarAngle=Math.PI*.65;controls.minAzimuthAngle=-.65;controls.maxAzimuthAngle=.65;
  const resize=()=>{const w=element.clientWidth,h=element.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();const distance=Math.max(13,6.3/(Math.tan(16*Math.PI/180)*camera.aspect));camera.position.setLength(distance);controls.maxDistance=Math.max(23,distance*1.5);};const observer=new ResizeObserver(resize);observer.observe(element);resize();
  const displays={},knobs={};runtime.current={camera,controls,displays,knobs,front:()=>{camera.position.set(0,0,Math.max(13,6.3/(Math.tan(16*Math.PI/180)*camera.aspect)));controls.target.set(0,0,0);controls.update();}};
  new GLTFLoader().load('/models/cockpit.glb',gltf=>{
   if(disposed){disposeScene(gltf.scene);return;}scene.add(gltf.scene);
   for(const [name,x,width,digits,title,knobTitle] of slots){
    const display=textPlane('',width*.94,.5,'#ffba69',190);display.position.set(x,.58,.208);display.name=`${name}_display_text`;display.userData.field=name;display.userData.edit=true;scene.add(display);displays[name]=display;
    const label=textPlane(title,2.4,.26,'#ebd6aa',185);label.position.set(x,1.08,.09);scene.add(label);
    const bottom=textPlane(knobTitle,1.1,.18,'#ddceac',175);bottom.position.set(x,-1.045,.18);scene.add(bottom);
    const turnLabel=textPlane('−     +',1.9,.22,'#bdc6c8',76);turnLabel.position.set(x,-.88,.5);scene.add(turnLabel);
    const knob=gltf.scene.getObjectByName(`${name}_knob`);if(knob){knob.userData.field=name;knob.userData.knob=true;knobs[name]=knob;}
    const screen=gltf.scene.getObjectByName(`${name}_display`);screen.userData.field=name;screen.userData.edit=true;
   }
   setStatus('ready');update();
  },undefined,()=>!disposed&&setStatus('error'));
  function update(){for(const [name,,,digits] of slots){displays[name]?.userData.paint(latest.current.hidden[name]?'':String(latest.current.values[name]).padStart(digits,'0'));if(knobs[name])knobs[name].rotation.z=-latest.current.values[name]*(name==='altitude'?.0008:.025);}}
  runtime.current.update=update;
  const raycaster=new T.Raycaster(),pointer=new T.Vector2();let down=null;
  function hit(e){const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);for(const h of raycaster.intersectObjects(scene.children,true)){let object=h.object;while(object){if(object.userData.field)return {object,point:h.point};object=object.parent;}}return null;}
  const pointerDown=e=>{down=[e.clientX,e.clientY];};
  const pointerUp=e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;down=null;const h=hit(e);if(!h)return;const {field,edit}=h.object.userData;if(edit)latest.current.onEdit(field);else latest.current.onChange(field,h.point.x<h.object.position.x?-1:1);};
  const move=e=>{renderer.domElement.style.cursor=hit(e)?'pointer':'grab';};
  renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointerup',pointerUp);renderer.domElement.addEventListener('pointermove',move);
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
  return()=>{disposed=true;observer.disconnect();renderer.setAnimationLoop(null);controls.dispose();renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointermove',move);disposeScene(scene);renderer.dispose();renderer.domElement.remove();runtime.current=null;};
 },[]);
 useEffect(()=>{runtime.current?.update?.();},[values,hidden]);
 useEffect(()=>{const r=runtime.current;if(!r)return;r.controls.enabled=!capture;if(capture){r.front();}},[capture,status]);
 function reset(){const r=runtime.current;if(r){r.front();}}
 return <section className="cockpit-3d" data-state={status} aria-label="GLB 기반 3D MCP 조종석"><div ref={host} className="cockpit-3d-canvas"/>{status==='loading'&&<p className="cockpit-3d-message" role="status">3D 조종석 불러오는 중…</p>}{status==='error'&&<p className="cockpit-3d-message" role="alert">3D 화면을 열 수 없습니다. 사진 보기로 전환하거나 WebGL을 지원하는 브라우저를 사용하세요.</p>}{!capture&&<div className="cockpit-3d-toolbar"><span>3D MCP · 드래그 회전 / 스크롤 확대 / 숫자 클릭 / 노브 좌우 − +</span><button onClick={reset}>정면 보기</button></div>}</section>;
}
function disposeScene(scene){const textures=new Set(),materials=new Set(),geometries=new Set();scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){materials.add(m);if(m.map)textures.add(m.map);}});textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());}
