// Actual PCM from the selected MediaStream. No transcript/target hints enter ASR.
export function wav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
  const text = (at, value) => [...value].forEach((c, i) => view.setUint8(at+i,c.charCodeAt(0)));
  text(0,'RIFF'); view.setUint32(4,36+samples.length*2,true); text(8,'WAVE'); text(12,'fmt ');
  view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
  view.setUint32(24,rate,true); view.setUint32(28,rate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
  text(36,'data'); view.setUint32(40,samples.length*2,true);
  samples.forEach((v,i)=>view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,v))*32767),true));
  return new Uint8Array(buffer);
}
export function base64(bytes) {
  let text=''; for(let i=0;i<bytes.length;i+=32768) text+=String.fromCharCode(...bytes.subarray(i,i+32768));
  return btoa(text);
}
export async function microphone(deviceId, level) {
  const stream=await navigator.mediaDevices.getUserMedia({audio:{deviceId:deviceId?{exact:deviceId}:undefined,channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
  const context=new AudioContext(); await context.resume();
  const source=context.createMediaStreamSource(stream), processor=context.createScriptProcessor(4096,1,1), gain=context.createGain();
  gain.gain.value=0;
  let chunks=[], recording=false, frames=0;
  source.connect(processor); processor.connect(gain); gain.connect(context.destination);
  processor.onaudioprocess=event=>{
    const samples=event.inputBuffer.getChannelData(0);
    level(Math.min(1,Math.sqrt(samples.reduce((a,b)=>a+b*b,0)/samples.length)*8));
    if(recording && frames<context.sampleRate*30){chunks.push(new Float32Array(samples));frames+=samples.length;}
  };
  return {stream,
    start(){chunks=[];frames=0;recording=true;return new Date().toISOString();},
    stop(){recording=false;const samples=new Float32Array(frames);let offset=0;for(const chunk of chunks){samples.set(chunk,offset);offset+=chunk.length;}chunks=[];return wav(samples,context.sampleRate);},
    close(){recording=false;processor.disconnect();source.disconnect();gain.disconnect();stream.getTracks().forEach(t=>t.stop());context.close();},
  };
}
