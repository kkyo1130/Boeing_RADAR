// Original, simplified MCP model. No aircraft manufacturer geometry is used.
import * as T from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { writeFile, mkdir } from 'node:fs/promises';
// GLTFExporter uses the browser FileReader API when packing binary buffers.
globalThis.FileReader=class {readAsArrayBuffer(blob){blob.arrayBuffer().then(data=>{this.result=data;this.onloadend?.();});}};
const scene=new T.Scene();
const materials={panel:new T.MeshStandardMaterial({color:0x554d40,roughness:.72,metalness:.35}),edge:new T.MeshStandardMaterial({color:0x20272b,roughness:.55,metalness:.6}),black:new T.MeshStandardMaterial({color:0x080d0e,roughness:.4}),knob:new T.MeshStandardMaterial({color:0xa19a85,roughness:.52,metalness:.45}),screw:new T.MeshStandardMaterial({color:0x9b9e9a,metalness:.85,roughness:.3}),green:new T.MeshStandardMaterial({color:0x92dd66,emissive:0x5a9c37,emissiveIntensity:.6})};
function mesh(name,geo,mat,x,y,z){const m=new T.Mesh(geo,materials[mat]);m.name=name;m.position.set(x,y,z);scene.add(m);return m;}
function box(name,w,h,d,mat,x,y,z){return mesh(name,new T.BoxGeometry(w,h,d),mat,x,y,z);}
function cylinder(name,r,d,mat,x,y,z){const m=mesh(name,new T.CylinderGeometry(r,r,d,48),mat,x,y,z);m.rotation.x=Math.PI/2;return m;}
box('glareshield',11.5,.32,1.1,'edge',0,1.44,-.18);
box('mcp_chassis',11.2,2.7,.65,'edge',0,0,-.36);
box('mcp_face',10.85,2.55,.12,'panel',0,0,0);
box('lower_sill',11.5,.25,.95,'edge',0,-1.46,-.2);
for(const x of [-5.18,-1.92,1.92,5.18])for(const y of [-1.1,1.1]){cylinder(`screw_${x}_${y}`,.066,.035,'screw',x,y,.09);box(`screw_slot_${x}_${y}`,.08,.012,.009,'black',x,y,.112);}
for(const [key,x,w] of [['speed',-3.55,1.65],['heading',0,1.65],['altitude',3.55,2.05]]){
 box(`${key}_bezel`,w+.18,.76,.12,'edge',x,.58,.11);
 box(`${key}_display`,w,.57,.03,'black',x,.58,.187);
 const knob=new T.Group();knob.name=`${key}_knob`;knob.position.set(x,-.48,.16);scene.add(knob);
 const rim=new T.Mesh(new T.CylinderGeometry(.41,.43,.18,48),materials.edge);rim.rotation.x=Math.PI/2;knob.add(rim);
 const cap=new T.Mesh(new T.CylinderGeometry(.31,.36,.26,48),materials.knob);cap.rotation.x=Math.PI/2;cap.position.z=.17;knob.add(cap);
 for(let i=0;i<24;i++){const a=i/24*Math.PI*2;const ridge=new T.Mesh(new T.BoxGeometry(.036,.09,.23),materials.knob);ridge.position.set(Math.cos(a)*.32,Math.sin(a)*.32,.15);ridge.rotation.z=a;knob.add(ridge);}
 const marker=new T.Mesh(new T.BoxGeometry(.035,.15,.014),materials.black);marker.position.set(0,.2,.309);knob.add(marker);
 for(const [j,label] of ['LEFT','RIGHT'].entries()){const bx=x+(j?1:-1)*.99;box(`${key}_${label}_button`,.37,.39,.12,'edge',bx,-.52,.15);box(`${key}_${label}_indicator`,.19,.035,.015,'green',bx,-.42,.22);}
 box(`${key}_bottom_button`,.82,.28,.1,'edge',x,-1.05,.12);
}
for(const x of [-1.78,1.78])box(`panel_divider_${x}`,.024,2.25,.02,'edge',x,0,.077);
const glb=await new GLTFExporter().parseAsync(scene,{binary:true});
const target=new URL('../public/models/cockpit.glb',import.meta.url);await mkdir(new URL('.',target),{recursive:true});await writeFile(target,Buffer.from(glb));console.log(`cockpit.glb: ${glb.byteLength} bytes`);
