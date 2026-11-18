import { wav } from './demo-audio.js';

export function mixToMono(channels) {
  if (!channels.length || !channels[0].length || channels.some(c => c.length !== channels[0].length)) {
    throw new Error('음성 채널을 읽을 수 없습니다.');
  }
  const mono = new Float32Array(channels[0].length);
  for (const channel of channels) for (let i = 0; i < mono.length; i++) mono[i] += channel[i] / channels.length;
  return mono;
}

export async function decodeAudioFile(file, OfflineContext = globalThis.OfflineAudioContext) {
  if (!file || file.size < 1 || file.size > 10 * 1024 * 1024) throw new Error('10MB 이하의 음성 파일을 선택하세요.');
  if (!OfflineContext) throw new Error('이 브라우저에서는 파일 변환을 지원하지 않습니다. 최신 Chrome에서 시도하세요.');
  let decoded;
  const decoder = new OfflineContext(1, 1, 16000);
  try { decoded = await decoder.decodeAudioData(await file.arrayBuffer()); }
  catch { throw new Error('음성 파일을 읽을 수 없습니다. WAV·MP3 또는 브라우저가 지원하는 M4A 파일을 선택하세요.'); }
  const duration = decoded.length / decoded.sampleRate;
  if (!Number.isFinite(duration) || duration < .1 || duration > 30) throw new Error('파일 한 개는 0.1초 이상 30초 이하여야 합니다. 긴 녹음은 발화별로 잘라 주세요.');
  const channels = Array.from({ length: decoded.numberOfChannels }, (_, i) => decoded.getChannelData(i));
  const mono = mixToMono(channels);
  const renderer = new OfflineContext(1, Math.ceil(duration * 16000), 16000);
  const buffer = renderer.createBuffer(1, mono.length, decoded.sampleRate);
  buffer.getChannelData(0).set(mono);
  const source = renderer.createBufferSource(); source.buffer = buffer; source.connect(renderer.destination); source.start();
  const audio = await renderer.startRendering();
  return { bytes: wav(audio.getChannelData(0), 16000), duration };
}

export function fileSpeechBody(kind, audio, startedAt, endedAt, atcInputId) {
  if (!['ATC', 'PILOT'].includes(kind)) throw new Error('음성 역할을 확인하세요.');
  if (kind === 'PILOT' && !atcInputId) throw new Error('먼저 관제 파일을 처리하고 채택된 지시를 확인하세요.');
  const body = { audio, input_mode: 'file_upload', started_at: startedAt, ended_at: endedAt };
  if (kind === 'PILOT') body.atc_input_id = atcInputId;
  return body;
}
