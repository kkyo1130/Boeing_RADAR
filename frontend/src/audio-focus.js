// Input adapters MUST call begin before starting capture/ATC playback. ATC END
// includes its capture tail; no timeout guesses an input's completion.
let owner = null;
const evidence = new Map();
const inputOwners = new Map();
export const audioFocus = {
  register(player) { owner = player; return () => { if (owner === player) owner = null; }; },
  async begin(kind, start) {
    for (const element of evidence.keys()) { element.pause(); this.endEvidence(element); }
    const player = owner;
    const input = await (player?.begin(kind, start) ?? null);
    if (input) inputOwners.set(input.token, player);
    return input;
  },
  async end(input) {
    const player = inputOwners.get(input?.token) || owner;
    await player?.end(input);
    if (input && !player?.inputs.has(input.token)) inputOwners.delete(input.token);
  },
  async startEvidence(element) {
    if (evidence.has(element)) return;
    element.pause();
    const item = { owner, input: null, cancelled: false, phase: 'pending' }; evidence.set(element, item);
    if (!owner) { evidence.delete(element); return; }
    const input = await item.owner.begin('EVIDENCE'); item.input = input;
    if (!input || item.cancelled) { evidence.delete(element); if (input) await item.owner.end(input); return; }
    item.phase = 'playing';
    try { await element.play(); } catch { await this.endEvidence(element); }
  },
  pauseEvidence(element) { if (evidence.get(element)?.phase === 'playing') this.endEvidence(element); },
  async endEvidence(element) {
    const item = evidence.get(element); if (!item) return;
    item.cancelled = true;
    if (item.input) { evidence.delete(element); await item.owner.end(item.input); }
  },
};
