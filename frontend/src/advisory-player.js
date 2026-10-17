// A single playback owner. Server claims bind each complete sentence to occurrences.
export class AdvisoryPlayer {
  constructor({ flightId, request, contextFactory = () => new AudioContext(), fetchAudio = url => fetch(url), notify = () => {} }) {
    Object.assign(this, { flightId, request, contextFactory, fetchAudio, notify });
    this.enabled = false; this.closed = false; this.inputs = new Map(); this.sequence = 0;
    this.snapshot = null; this.connected = false; this.pendingResult = null;
  }
  url(path) { return `/api/v2/flights/${encodeURIComponent(this.flightId)}/voice/${path}`; }
  publish(message) { this.notify({ message, enabled: this.enabled, playing: this.current?.claim?.text || '', inputs: [...this.inputs.values()] }); }
  async enable() {
    try {
      this.context ||= this.contextFactory();
      this.context.onstatechange = () => {
        if (this.enabled && this.context.state !== 'running') {
          this.enabled = false; this.stop('FAILED'); this.publish('음성 사용 불가 · 다시 켜세요');
        }
      };
      await this.context.resume();
      if (this.context.state !== 'running') throw new Error('오디오 출력이 차단되었습니다');
      if (this.closed) return;
      this.enabled = true; this.publish('음성 안내 사용 중');
    } catch { this.enabled = false; this.publish('음성 사용 불가 · 출력 장치와 브라우저 설정을 확인하고 다시 켜세요'); }
  }
  stop(reason = 'INTERRUPTED') {
    this.sequence++;
    const current = this.current; this.current = null;
    if (!current) return;
    clearTimeout(current.timer);
    if (current.source) { current.source.onended = null; try { current.source.stop(); } catch { /* Already ended. */ } }
    if (current.claim) this.report(current.claim.attempt_id, reason);
  }
  async report(attemptId, status) {
    // Retry the SAME terminal report after response loss; never start another
    // claim while completion persistence is uncertain.
    const item = { attemptId, status }; this.pendingResult = item;
    await this.flushResult();
  }
  async flushResult() {
    const item = this.pendingResult;
    if (!item || this.reporting) return;
    this.reporting = true;
    try {
      await this.request(this.url(`attempts/${encodeURIComponent(item.attemptId)}`), { method: 'POST', body: { status: item.status } });
      if (this.pendingResult === item) this.pendingResult = null;
    } catch (e) {
      // A terminal conflict means the server already expired/cancelled this
      // reservation. It must never be translated into a successful completion.
      if (e.status === 409 || e.status === 404) { if (this.pendingResult === item) this.pendingResult = null; }
      else this.publish('음성 기록 저장 대기 · 연결 복구 후 같은 재생 결과를 다시 저장합니다');
    } finally { this.reporting = false; }
  }
  update(snapshot, connected) {
    this.snapshot = snapshot; this.connected = connected;
    const c = this.current?.claim;
    if (this.current && (!connected || snapshot?.status !== 'ACTIVE' || snapshot.flight_id !== this.flightId ||
      snapshot.voice?.inputs.length || (c && !snapshot.voice?.candidates.some(q => q.candidate_id === c.candidate_id)) ||
      (c && snapshot.voice?.active_attempt?.attempt_id === c.attempt_id && snapshot.voice.active_attempt.cancel_requested))) this.stop();
  }
  async tick() {
    if (this.pendingResult) { await this.flushResult(); return; }
    if (!this.enabled || this.closed || this.current || this.inputs.size || !this.connected || this.snapshot?.status !== 'ACTIVE') return;
    if (this.context?.state !== 'running') { this.stop(); this.enabled = false; this.publish('음성 사용 불가 · 다시 켜세요'); return; }
    const voice = this.snapshot.voice;
    if (!voice || voice.inputs.length || (voice.active_attempt && !voice.active_attempt.lease_expired) || !voice.candidates.length) return;
    const candidate = voice.candidates[0], generation = ++this.sequence;
    const current = { generation }; this.current = current;
    const started = performance.now();
    try {
      const claim = await this.request(this.url('claims'), { method: 'POST', body: { candidate_id: candidate.candidate_id, attempt_id: crypto.randomUUID() } });
      if (this.current !== current || this.closed) { await this.report(claim.attempt_id, 'INTERRUPTED'); return; }
      current.claim = claim;
      // Subtract the whole request round trip, avoiding reliance on the client
      // wall clock and never playing beyond the server's reservation.
      const budget = Date.parse(claim.lease_until) - Date.parse(claim.started_at) - (performance.now() - started) - 150;
      if (claim.status !== 'PLAYING' || claim.cancel_requested || budget <= 0) throw new Error('Expired playback reservation');
      current.deadline = performance.now() + budget;
      current.timer = setTimeout(() => this.stop(), budget);
      const response = await this.fetchAudio(claim.asset_url);
      if (!response.ok) throw new Error('Voice asset unavailable');
      const buffer = await this.context.decodeAudioData(await response.arrayBuffer());
      if (this.current !== current || generation !== this.sequence) return;
      if (!this.connected || this.inputs.size || this.context.state !== 'running' || buffer.duration * 1000 > current.deadline-performance.now()) throw new Error('Output unavailable');
      const source = this.context.createBufferSource(); current.source = source;
      source.buffer = buffer; source.connect(this.context.destination);
      source.onended = () => {
        if (this.current !== current) return;
        if (this.context.state !== 'running' || performance.now() >= current.deadline) { this.stop('FAILED'); return; }
        clearTimeout(current.timer); this.current = null;
        this.report(claim.attempt_id, 'COMPLETED'); this.publish('음성 안내 재생 완료');
      };
      source.start(0); this.publish(claim.text);
    } catch (e) {
      if (this.current !== current) return;
      if (current.claim) { this.stop('FAILED'); this.enabled = false; this.publish('음성 사용 불가 · 파일과 출력 장치를 확인하고 다시 켜세요'); }
      else { this.current = null; this.publish('안내 자격을 다시 확인합니다'); }
    }
  }
  async begin(kind, start = () => {}) {
    this.stop();
    const token = crypto.randomUUID(), input = { token, kind }, event_id = crypto.randomUUID();
    this.inputs.set(token, input); this.publish('입력 우선 · 안내 보류');
    try {
      await this.request(this.url('inputs'), { method: 'POST', body: { event_id, token, kind, action: 'BEGIN' } });
      if (this.closed) { await this.end(input); return null; }
      await start(); return input;
    } catch (e) {
      if (e.status === 409 || e.status === 422) this.inputs.delete(token);
      // On a lost BEGIN response preserve the token for explicit END recovery.
      else input.uncertain = true;
      this.publish('입력 시작 실패 · 녹음/재생은 시작하지 않았습니다');
      return null;
    }
  }
  async end(input) {
    if (!input) return;
    input.endEvent ||= crypto.randomUUID();
    try {
      await this.request(this.url('inputs'), { method: 'POST', body: { event_id: input.endEvent, token: input.token, kind: input.kind, action: 'END' } });
      this.inputs.delete(input.token); this.publish('입력 종료 · 현재 안내 대상을 다시 확인합니다');
    } catch (e) {
      if (e.status === 409) {
        try {
          const state = await this.request(`/api/v2/flights/${encodeURIComponent(this.flightId)}/state`);
          if (state.flight_id === this.flightId && state.voice && !state.voice.inputs.some(i => i.token === input.token)) {
            this.inputs.delete(input.token); this.publish('서버에서 입력 종료를 확인했습니다'); return;
          }
        } catch { /* Preserve suppression when reconciliation is unavailable. */ }
      }
      this.publish('입력 종료 확인 실패 · 안내 보류, 종료를 다시 확인하세요');
    }
  }
  disable() { this.enabled = false; this.stop(); this.publish('음성 안내 꺼짐 · 화면 안내 유지'); }
  close() { this.closed = true; this.disable(); this.context?.close(); }
}
