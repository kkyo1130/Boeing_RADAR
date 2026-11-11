// A multi-pointer orbit/zoom gesture must never also edit an instrument.
export function clickGesture(){
 const active=new Map();let blocked=false;
 const distance=(e,p)=>Math.hypot(e.clientX-p.x,e.clientY-p.y);
 return {
  down(e){
   if(active.size===0)blocked=false;
   if(active.has(e.pointerId))blocked=true;
   active.set(e.pointerId,{x:e.clientX,y:e.clientY,moved:false,button:e.button});
   if(active.size>1)blocked=true;
  },
  move(e){const p=active.get(e.pointerId);if(p&&distance(e,p)>5)p.moved=true;},
  up(e){
   const p=active.get(e.pointerId);if(!p)return false;
   active.delete(e.pointerId);
   return !blocked&&!p.moved&&p.button===0&&e.button===0&&distance(e,p)<=5;
  },
  cancel(e){if(active.has(e.pointerId)){active.delete(e.pointerId);blocked=true;}},
  clear(){active.clear();blocked=true;},
 };
}
