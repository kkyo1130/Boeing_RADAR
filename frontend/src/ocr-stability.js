export function advance(history, value, now, previousTime, required=3) {
  if (value == null) return { history: [], value: null, status: 'CHECK' };
  const prior = now - previousTime > 1500 ? [] : history;
  const next = [...prior, value].slice(-required);
  return { history: next, value, status: next.length === required && next.every(v => v === value) ? 'STABLE' : 'CHECK' };
}
