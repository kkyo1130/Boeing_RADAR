// Original cockpit mesh assembled from authored geometry. No manufacturer CAD assets.
import * as T from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
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
// Keep the original interactive MCP as its own reusable group.
const mcp=new T.Group();mcp.name='mcp_root';
for(const child of [...scene.children])mcp.add(child);
mcp.position.y=2.6;scene.add(mcp);
Object.assign(materials,{
 cabin:new T.MeshStandardMaterial({color:0x5e625e,roughness:.9}),
 trim:new T.MeshStandardMaterial({color:0x171f24,roughness:.8}),
 upholstery:new T.MeshStandardMaterial({color:0x374b54,roughness:1}),
 cushion:new T.MeshStandardMaterial({color:0x506873,roughness:1}),
 blue:new T.MeshBasicMaterial({color:0x257fc4}),
 earth:new T.MeshBasicMaterial({color:0x88512d}),
 white:new T.MeshBasicMaterial({color:0xc8e3dd}),
 cyan:new T.MeshBasicMaterial({color:0x45d8e8}),
 magenta:new T.MeshBasicMaterial({color:0xf580d9}),
 glass:new T.MeshStandardMaterial({color:0x83baca,transparent:true,opacity:.18,metalness:.15,roughness:.15,side:T.DoubleSide}),
 floor:new T.MeshStandardMaterial({color:0x212b31,roughness:.98}),
 belt:new T.MeshStandardMaterial({color:0x20272a,roughness:1}),
});
function round(name,w,h,d,mat,x,y,z,r=.1){return mesh(name,new RoundedBoxGeometry(w,h,d,3,r),mat,x,y,z);}
function line(name,points,r,mat){return mesh(name,new T.TubeGeometry(new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p))),Math.max(2,points.length*5),r,5,false),mat,0,0,0);}
function quad(name,points,mat){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(points.flat(),3));g.setIndex([0,1,2,0,2,3]);g.computeVertexNormals();return mesh(name,g,mat,0,0,0);}
function segmentNumber(name,value,x,y,z,scale=.12,mat='white'){
 const segments={0:'abcedf',1:'bc',2:'abged',3:'abgcd',4:'fgbc',5:'afgcd',6:'afgecd',7:'abc',8:'abcdefg',9:'abfgcd'};
 const positions={a:[0,1,1,0],b:[.5,.5,0,1],c:[.5,-.5,0,1],d:[0,-1,1,0],e:[-.5,-.5,0,1],f:[-.5,.5,0,1],g:[0,0,1,0]};
 [...String(value)].forEach((digit,i)=>{for(const seg of segments[digit]||''){const [dx,dy,horizontal]=positions[seg];box(`${name}_${i}_${seg}`,scale*(horizontal?.82:.14),scale*(horizontal?.14:.82),.015,mat,x+i*scale*1.5+dx*scale,y+dy*scale,z);}});
}
// Floor and lower fuselage are left open at the back for an inspection view.
round('flight_deck_floor',22,.45,15,'floor',0,-6.8,2.5,.18);
for(const side of [-1,1]){
 round(`side_console_${side}`,2.1,2.6,9,'trim',side*10,-4.9,1.5,.16);
 round(`side_armrest_${side}`,2.25,.32,6,'panel',side*9.9,-3.48,2,.12);
 for(let i=0;i<8;i++)box(`side_switch_${side}_${i}`,.15,.2,.3,'knob',side*(9.4+(i%2)*.45),-3.2,-1.3+Math.floor(i/2)*.5);
 line(`side_window_lower_frame_${side}`,[[side*10,-.6,5],[side*10,3.9,0],[side*8.9,4.3,-4.4]],.18,'cabin');
 line(`side_window_upper_frame_${side}`,[[side*10,4.7,6],[side*10,8,0],[side*8.9,8.2,-4.4]],.18,'cabin');
 line(`side_window_pillar_${side}`,[[side*10,3.9,0],[side*10,8,0]],.12,'trim');
 quad(`side_window_${side}`,[[side*10,3.9,.1],[side*8.9,4.3,-4.4],[side*8.9,8.2,-4.4],[side*10,8,0]],'glass');
}
// Sloped windshield, divided by substantial center and corner posts.
for(const side of [-1,1]){
 quad(`windshield_${side}`,[[side*.17,4.2,-4.55],[side*8.75,4.3,-4.4],[side*8.75,8.2,-6],[side*.17,8.65,-6.4]],'glass');
 line(`windshield_sill_${side}`,[[0,4.2,-4.55],[side*8.9,4.3,-4.4]],.19,'trim');
 line(`windshield_header_${side}`,[[0,8.65,-6.4],[side*8.9,8.2,-6]],.22,'cabin');
 line(`windshield_corner_${side}`,[[side*8.9,4.3,-4.4],[side*8.9,8.2,-6]],.22,'cabin');
 line(`wiper_${side}`,[[side*1.2,4.3,-4.3],[side*2.5,5.3,-4.8],[side*5.4,5.35,-4.85]],.035,'edge');
}
line('windshield_center_post',[[0,4.2,-4.4],[0,8.65,-6.25]],.19,'cabin');
// Main instrument panel and padded glareshield.
round('instrument_panel_body',19.8,5.5,1.1,'panel',0,-1.55,-.65,.24);
round('full_glareshield',20.4,.42,3.6,'trim',0,1.4,-1.1,.16);
round('lower_panel_lip',19.8,.35,1.2,'edge',0,-4.32,-.1,.1);
for(const side of [-1,1]){
 const x=side*7.3;
 // Primary flight display: modeled screen geometry, not a photograph.
 round(`pfd_bezel_${side}`,3.25,3.25,.24,'edge',x,-.5,.03,.14);
 box(`pfd_screen_${side}`,2.94,2.94,.04,'black',x,-.5,.18);
 box(`pfd_sky_${side}`,1.82,1.07,.02,'blue',x,-.04,.207);
 box(`pfd_ground_${side}`,1.82,1.07,.02,'earth',x,-1.11,.207);
 box(`pfd_horizon_${side}`,1.82,.035,.025,'white',x,-.575,.225);
 for(let k=-3;k<=3;k++){
  box(`pfd_pitch_${side}_${k}`,k%2===0?.65:.38,.018,.02,'white',x,-.575+k*.2,.23);
  for(const dx of [-1.18,1.18])box(`pfd_tape_${side}_${k}_${dx}`,.14,.02,.018,'white',x+dx,-.5+k*.32,.235);
 }
 box(`pfd_aircraft_left_${side}`,.48,.045,.025,'knob',x-.36,-.5,.26);box(`pfd_aircraft_right_${side}`,.48,.045,.025,'knob',x+.36,-.5,.26);
 segmentNumber(`pfd_speed_${side}`,250,x-1.39,-.5,.26,.09);
 segmentNumber(`pfd_alt_${side}`,3000,x+.91,-.5,.26,.07);
 for(let i=0;i<6;i++)cylinder(`pfd_key_${side}_${i}`,.055,.05,'knob',x-1.18+i*.46,-2.27,.17);
 // Navigation display, concentric compass rings and a magenta route.
 const nx=side*3.65;
 round(`nd_bezel_${side}`,3.25,3.25,.24,'edge',nx,-.5,.03,.14);
 box(`nd_screen_${side}`,2.94,2.94,.04,'black',nx,-.5,.18);
 for(const r of [.55,.95,1.28]){const points=[];for(let i=0;i<=64;i++){const a=i/64*Math.PI*2;points.push([nx+Math.sin(a)*r,-.5+Math.cos(a)*r,.225]);}line(`nd_ring_${side}_${r}`,points,.009,'white');}
 for(let i=0;i<36;i++){const a=i/36*Math.PI*2;const tick=box(`nd_tick_${side}_${i}`,.018,i%3===0?.13:.06,.02,'white',nx+Math.sin(a)*1.28,-.5+Math.cos(a)*1.28,.24);tick.rotation.z=-a;}
 line(`nd_route_${side}`,[[nx,-1.5,.25],[nx+.1,-.8,.25],[nx-.45,.1,.25],[nx-.24,.7,.25]],.025,'magenta');
 segmentNumber(`nd_heading_${side}`,270,nx-.22,.8,.25,.09,'green');
 box(`nd_aircraft_${side}`,.08,.25,.02,'cyan',nx,-1.1,.27);
 for(let i=0;i<6;i++)cylinder(`nd_key_${side}_${i}`,.055,.05,'knob',nx-1.18+i*.46,-2.27,.17);
 // EFIS and radio switch panels below the screens.
 for(let j=0;j<9;j++){
  const bx=side*(3.1+(j%5)*1.12),by=-3.08-Math.floor(j/5)*.65;
  cylinder(`instrument_control_${side}_${j}`,.14,.12,'knob',bx,by,.06);
  box(`instrument_control_mark_${side}_${j}`,.02,.11,.015,'black',bx,by+.02,.13);
 }
}
round('engine_display_bezel',3.1,3.25,.25,'edge',0,-.5,.03,.14);
box('engine_display',2.8,2.95,.04,'black',0,-.5,.18);
for(const x of [-.65,.65])for(let j=0;j<3;j++){
 const y=.42-j*.83;const pts=[];for(let i=0;i<=24;i++){const a=(-.8+i/24*1.6)*Math.PI;pts.push([x+Math.sin(a)*.29,y+Math.cos(a)*.29,.23]);}line(`engine_gauge_${x}_${j}`,pts,.014,'green');
 line(`engine_needle_${x}_${j}`,[[x,y,.25],[x+.18,y+.2,.25]],.016,'white');
 segmentNumber(`engine_value_${x}_${j}`,j===0?92:48,x-.22,y-.32,.25,.065);
}
// Separate columns, yoke hubs, grips and switches.
for(const side of [-1,1]){
 const x=side*6.6;
 line(`control_column_${side}`,[[x,-6.5,2.8],[x,-4.4,2.9],[x,-3.3,3.65]],.18,'trim');
 cylinder(`yoke_hub_${side}`,.3,.45,'edge',x,-3.3,3.65);
 line(`yoke_${side}`,[[x-1,-2.55,3.7],[x-1.05,-3.25,3.7],[x-.5,-3.65,3.7],[x+.5,-3.65,3.7],[x+1.05,-3.25,3.7],[x+1,-2.55,3.7]],.14,'edge');
 for(const dx of [-1,1]){round(`yoke_grip_${side}_${dx}`,.32,.76,.36,'belt',x+dx,-2.75,3.72,.12);box(`yoke_button_${side}_${dx}`,.12,.13,.06,'knob',x+dx,-2.55,3.93);}
 for(const dx of [-.5,.5]){const pedal=round(`rudder_pedal_${side}_${dx}`,.72,.26,.95,'screw',x+dx,-6.1,.85,.05);pedal.rotation.x=-.38;}
 // Captain / first officer seats, with mesh cushions and webbing.
 round(`seat_base_${side}`,3.5,.48,3.8,'edge',x,-5.7,6,.15);
 round(`seat_cushion_${side}`,3.35,.56,3.6,'upholstery',x,-5.2,6,.23);
 const back=round(`seat_back_${side}`,3.2,3.35,.65,'upholstery',x,-3.6,7.55,.26);back.rotation.x=-.12;
 round(`headrest_${side}`,2.15,1.02,.67,'cushion',x,-1.58,7.78,.23);
 for(const dx of [-1.8,1.8])round(`seat_arm_${side}_${dx}`,.32,.35,2,'edge',x+dx,-4.25,6.4,.12);
 for(const dx of [-.75,.75]){const strap=box(`shoulder_harness_${side}_${dx}`,.19,2.65,.055,'belt',x+dx,-3.58,7.12);strap.rotation.z=dx*.14;}
 box(`seat_buckle_${side}`,.35,.28,.15,'screw',x,-4.85,6.1);
 for(const dx of [-1.15,1.15])box(`seat_rail_${side}_${dx}`,.12,.12,4.1,'screw',x+dx,-6.52,6);
}
// Center pedestal, throttle quadrant, speedbrake, flaps and radio panels.
round('center_pedestal',3.8,1.9,8.6,'trim',0,-5.55,4.1,.18);
round('throttle_quadrant',3.5,.62,3.2,'panel',0,-4.34,2.7,.12);
for(const x of [-.62,.62]){
 box(`throttle_slot_${x}`,.14,.035,2.1,'black',x,-4.005,2.8);
 line(`throttle_lever_${x}`,[[x,-4,2.9],[x,-3.25,2.65],[x,-2.98,2.8]],.07,'screw');
 round(`throttle_handle_${x}`,.72,.28,.38,'knob',x,-2.98,2.8,.1);
}
for(const side of [-1,1]){box(`aux_lever_slot_${side}`,.08,.035,1.6,'black',side*1.36,-4,2.8);line(`aux_lever_${side}`,[[side*1.36,-4,3],[side*1.36,-3.45,3]],.055,'screw');round(`aux_handle_${side}`,.35,.17,.32,'edge',side*1.36,-3.4,3,.05);}
for(let j=0;j<3;j++){
 const z=4.8+j*1.15;
 round(`radio_panel_${j}`,3.4,.12,1.02,'panel',0,-4.53,z,.04);
 box(`radio_screen_${j}`,1.65,.025,.32,'black',-.3,-4.45,z);
 for(const x of [-1.32,1.32]){const dial=cylinder(`radio_dial_${j}_${x}`,.16,.17,'knob',x,-4.39,z);dial.rotation.x=0;}
 for(let k=0;k<5;k++)box(`radio_button_${j}_${k}`,.18,.08,.16,'edge',-.85+k*.37,-4.4,z+.32);
}
// Dual flight management units on sloped lower instrument panels.
for(const side of [-1,1]){
 const unit=new T.Group();unit.name=`fmc_${side}`;unit.position.set(side*1.12,-3.75,1.22);unit.rotation.x=-.55;scene.add(unit);
 const face=new T.Mesh(new RoundedBoxGeometry(1.75,2.2,.18,2,.06),materials.edge);unit.add(face);
 const screen=new T.Mesh(new T.BoxGeometry(1.35,.83,.025),materials.black);screen.position.set(0,.5,.105);unit.add(screen);
 for(let row=0;row<4;row++)for(let col=0;col<5;col++){const key=new T.Mesh(new T.BoxGeometry(.19,.16,.065),materials.knob);key.position.set(-.52+col*.26,-.15-row*.26,.12);unit.add(key);}
}
// Overhead console: a shallow tilted panel rather than a closing roof.
const overhead=new T.Group();overhead.name='overhead_console';overhead.position.set(0,7.4,.4);overhead.rotation.x=.32;scene.add(overhead);
const overheadBase=new T.Mesh(new RoundedBoxGeometry(5.3,.25,5.1,2,.08),materials.panel);overhead.add(overheadBase);
for(let row=0;row<7;row++)for(let col=0;col<7;col++){
 const toggle=new T.Mesh(new T.CylinderGeometry(.038,.038,.25,8),materials.screw);toggle.position.set(-2.1+col*.7,-.25,-1.95+row*.63);overhead.add(toggle);
 const bezel=new T.Mesh(new T.BoxGeometry(.45,.035,.32),materials.edge);bezel.position.set(toggle.position.x,-.145,toggle.position.z);overhead.add(bezel);
}
// Model metadata is also available when opening the GLB in a DCC tool.
scene.userData={title:'RADAR Flight Deck',description:'Original simulated twin-seat cockpit mesh. MCP values are the only live instruments.',units:'arbitrary visualization units'};
const glb=await new GLTFExporter().parseAsync(scene,{binary:true});
const target=new URL('../public/models/cockpit.glb',import.meta.url);await mkdir(new URL('.',target),{recursive:true});await writeFile(target,Buffer.from(glb));console.log(`cockpit.glb: ${glb.byteLength} bytes`);
