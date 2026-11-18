export const CAPTURE_PERIOD_MS=250;
// Serial requests: slow inference incurs no extra delay; fast inference is bounded.
export function nextCaptureDelay(started,now){return Math.max(0,CAPTURE_PERIOD_MS-(now-started));}
