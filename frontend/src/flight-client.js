// Transport/order guards only. Numeric comparison and lifecycle belong to the server.
export const POLL_MS = 1000;
export const TIMEOUT_MS = 4000;
const results = ['NORMAL', 'MISMATCH', 'UNVERIFIED'];

export async function request(path, { method = 'GET', body, signal, timeout = TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, timeout);
  try {
    const response = await fetch(path, { method, signal: controller.signal, cache: 'no-store',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || `요청 실패 (${response.status})`);
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw new Error('서버 응답을 확인할 수 없습니다. 연결을 확인하세요.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}

export function checkSnapshot(data, flightId) {
  if (data?.schema_version !== '2' || data.flight_id !== flightId ||
      !Number.isSafeInteger(data.revision) || data.revision < 0 ||
      !['ACTIVE', 'ENDED'].includes(data.status) || typeof data.callsign !== 'string' ||
      !results.includes(data.result) || !data.targets || !data.current?.READBACK ||
      !data.current?.COCKPIT || !data.channels || !data.validation ||
      !results.includes(data.validation.result) || typeof data.validation.phase !== 'string') {
    throw new Error('서버 상태 형식을 확인할 수 없습니다.');
  }
  for (const stage of ['readback', 'setting']) {
    const group = data.validation[stage];
    if (!results.includes(group?.result) || !Array.isArray(group.fields) || group.fields.some(row =>
      !['ALT', 'HDG', 'CALLSIGN'].includes(row.field) || !results.includes(row.result) ||
      typeof row.reason !== 'string' ||
      ![null, 'number', 'string'].includes(row.actual === null ? null : typeof row.actual) ||
      ![null, 'number', 'string'].includes(row.expected === null ? null : typeof row.expected))) {
      throw new Error('서버 항목 판정 형식을 확인할 수 없습니다.');
    }
  }
  return data;
}

export class SnapshotGate {
  constructor(flightId) { this.flightId = flightId; this.snapshot = null; this.serial = -1; }
  accept(data, serial) {
    checkSnapshot(data, this.flightId);
    if (serial < this.serial || data.revision < (this.snapshot?.revision ?? -1) ||
        (this.snapshot?.status === 'ENDED' && data.status !== 'ENDED')) return false;
    this.snapshot = data; this.serial = serial;
    return true;
  }
}

export function dueRevalidations(snapshot, completed) {
  if (snapshot.status !== 'ACTIVE') return [];
  return [...new Set(snapshot.validation.setting.fields.filter(row =>
    row.wait_until && row.reason === 'ADJUSTMENT_DEADLINE_MISMATCH').map(row =>
    `${snapshot.flight_id}/${row.instruction_id}/${row.wait_until}`))].filter(key => !completed.has(key));
}

export function statusLabel(result, connected = true) {
  if (!connected) return '판단 보류';
  return { NORMAL: '일치', MISMATCH: '불일치', UNVERIFIED: '판단 보류' }[result] || '판단 보류';
}

export function numberLabel(value, field) {
  if (value === null || value === undefined) return '확인 불가';
  if (field === 'CALLSIGN') return String(value);
  return `${Number(value).toLocaleString('en-US')}${field === 'ALT' ? ' ft' : '°'}`;
}
