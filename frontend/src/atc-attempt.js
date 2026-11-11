// Persist the local demo attempt before activating any ATC audio source.
// This guards reloads on this browser/origin, not independent API clients.
export const atcAttemptKey=flight=>`radar.atc-attempt.${flight}`;
export function readAtcAttempt(flight){
  try{return localStorage.getItem(atcAttemptKey(flight));}
  catch{return 'pending';}
}
export function writeAtcAttempt(flight,value){
  try{localStorage.setItem(atcAttemptKey(flight),value);}
  catch{throw new Error('관제 입력 상태를 저장할 수 없습니다. 브라우저 저장소를 확인하세요.');}
}
