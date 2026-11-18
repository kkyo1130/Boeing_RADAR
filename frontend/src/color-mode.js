const STORAGE_KEY='radar.ui.color-mode';
export function readColorMode(){
 try{return typeof window!=='undefined'&&window.localStorage.getItem(STORAGE_KEY)==='dark'?'dark':'light';}
 catch{return 'light';}
}
export function applyColorMode(mode){
 if(typeof document!=='undefined')document.documentElement.dataset.theme=mode==='dark'?'dark':'light';
}
export function saveColorMode(mode){
 applyColorMode(mode);
 try{window.localStorage.setItem(STORAGE_KEY,mode);}catch{/* The current mode still works when storage is unavailable. */}
}
export {STORAGE_KEY};
